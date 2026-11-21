from __future__ import annotations

"""Source-file and sidecar I/O for image preprocessing and manual geometry."""

import json
import math
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Callable, Iterable, Iterator

from PIL import Image

from ..io.formats import write_text_atomic
from ..persistence.project_storage import image_preprocess_data_root
from ..runtime.source_file_stamp import source_file_stamp, source_stream_digest
from .models import PreprocessAnalysis


def _check_current_path(page: Path, expected_stamp: tuple[int, ...]) -> None:
    with page.open("rb") as current:
        if source_file_stamp(current) != expected_stamp:
            raise OSError("预处理期间源图已变化，请重新分析")


def analyze_source_path(
    path: Path, settings, *, analyzer: Callable[..., PreprocessAnalysis], **options,
) -> PreprocessAnalysis:
    """Bind the saved metadata to the image bytes read for this analysis."""
    path = Path(path)
    with path.open("rb") as source:
        original_stamp, digest = source_stream_digest(source)
        with Image.open(source) as opened:
            analysis = analyzer(opened, settings, **options)
        if source_file_stamp(source) != original_stamp:
            raise OSError("预处理期间源图已变化，请重新分析")
    _check_current_path(path, original_stamp)
    _, _, size_bytes, mtime_ns, _ = original_stamp
    analysis.source_size_bytes = size_bytes
    analysis.source_mtime_ns = mtime_ns
    analysis._source_digest = digest
    analysis._verified_source_stamp = original_stamp
    return analysis


def _verify_analyzed_source(source: BinaryIO, analysis: PreprocessAnalysis) -> tuple[int, ...]:
    stamp = source_file_stamp(source)
    if stamp[2:4] != (analysis.source_size_bytes, analysis.source_mtime_ns):
        raise OSError("预处理期间源图已变化，请重新分析")
    # A previously verified handle stamp skips repeat hashing on GUI redraws.
    if stamp != analysis._verified_source_stamp:
        stamp, digest = source_stream_digest(source)
        if (
            stamp[2:4] != (analysis.source_size_bytes, analysis.source_mtime_ns)
            or digest != analysis._source_digest
        ):
            raise OSError("预处理期间源图已变化，请重新分析")
        analysis._verified_source_stamp = stamp
    return stamp


def analysis_source_is_current(analysis: PreprocessAnalysis, page: Path) -> bool:
    """A disk cache needs a verified source digest before it can be reused."""
    if analysis._source_digest is None:
        return False
    try:
        with Path(page).open("rb") as source:
            stamp = _verify_analyzed_source(source, analysis)
        _check_current_path(Path(page), stamp)
    except OSError:
        return False
    return True


def check_analysis_source_current(analysis: PreprocessAnalysis, page: Path) -> None:
    """Reject a stale disk-backed analysis at the point of publication."""
    if analysis._source_digest is not None and not analysis_source_is_current(analysis, page):
        raise OSError("预处理期间源图已变化，请重新分析")


@contextmanager
def open_analysis_image(page: Path, analysis: PreprocessAnalysis) -> Iterator[Image.Image]:
    """Decode from the verified handle and check for replacement before export."""
    if analysis._source_digest is None:
        # Direct rendering APIs also accept analyses made from an in-memory image.
        with Image.open(page) as opened:
            yield opened
        return
    page = Path(page)
    with page.open("rb") as source:
        stamp = _verify_analyzed_source(source, analysis)
        with Image.open(source) as opened:
            yield opened
        if source_file_stamp(source) != stamp:
            raise OSError("预处理期间源图已变化，请重新分析")
    _check_current_path(page, stamp)


def _page_artifact_paths(
    project_root: Path, page: Path, filename: str, legacy_suffix: str,
) -> tuple[Path, Path]:
    root = image_preprocess_data_root(project_root)
    page = Path(page)
    return root / "by-source" / page.name / filename, root / f"{page.stem}{legacy_suffix}"


def result_path(project_root: Path, page: Path) -> Path:
    path, _legacy = _page_artifact_paths(project_root, page, "analysis.json", ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_analysis(project_root: Path, page: Path, analysis: PreprocessAnalysis) -> Path:
    path = result_path(project_root, page)
    payload = analysis.to_dict()
    payload["page"] = Path(page).name
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    check_analysis_source_current(analysis, page)
    write_text_atomic(path, content)
    if analysis._source_digest is not None:
        # The separate proof binds both files. An interrupted or concurrent
        # publication can leave a miss, but cannot authorize a mismatched pair.
        analysis_hash = sha256(content.encode("utf-8")).hexdigest()
        write_text_atomic(
            path.with_suffix(".source.sha256"),
            f"{analysis_hash} {analysis._source_digest.hex()}\n",
        )
    return path


def load_analysis(project_root: Path, page: Path) -> PreprocessAnalysis | None:
    current, legacy = _page_artifact_paths(project_root, page, "analysis.json", ".json")
    path = current if current.is_file() else legacy
    try:
        content = path.read_text(encoding="utf-8")
        payload = json.loads(content)
        if not isinstance(payload, dict) or payload.get("page", Path(page).name) != Path(page).name:
            return None
        analysis = PreprocessAnalysis.from_dict(payload)
    except (OSError, ValueError, TypeError, OverflowError):
        return None
    try:
        analysis_hash, source_hash = path.with_suffix(".source.sha256").read_text(encoding="utf-8").split()
        digest = bytes.fromhex(source_hash)
        if len(digest) == 32 and sha256(content.encode("utf-8")).hexdigest() == analysis_hash:
            analysis._source_digest = digest
    except (OSError, ValueError):
        pass
    return analysis


MANUAL_GEOMETRY_FORMAT = "picture-capture-manual-perspective"
MANUAL_GEOMETRY_VERSION = 1


def manual_geometry_path(project_root: Path, page: Path) -> Path:
    path, _legacy = _page_artifact_paths(project_root, page, "geometry.json", ".geometry.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _manual_geometry_payload(path: Path, page: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            isinstance(payload, dict)
            and payload.get("format") == MANUAL_GEOMETRY_FORMAT
            and int(payload.get("version", 0) or 0) == MANUAL_GEOMETRY_VERSION
            and payload.get("page") == Path(page).name
        ):
            return payload
    except (FileNotFoundError, ValueError, TypeError, OverflowError):
        pass
    return None


def load_manual_perspective_quad(
    project_root: Path, page: Path,
) -> tuple[float, ...] | None:
    current, legacy = _page_artifact_paths(project_root, page, "geometry.json", ".geometry.json")
    path = current if current.is_file() else legacy
    try:
        payload = _manual_geometry_payload(path, page)
        values = payload.get("quad") if payload is not None else None
        if not isinstance(values, (list, tuple)) or len(values) != 8:
            return None
        quad = tuple(float(v) for v in values)
        return quad if all(math.isfinite(v) for v in quad) else None
    except (OSError, ValueError, TypeError, OverflowError):
        return None


def save_manual_perspective_quad(
    project_root: Path,
    page: Path,
    quad: Iterable[float],
) -> Path:
    values = tuple(float(v) for v in quad)
    if len(values) != 8 or not all(math.isfinite(v) for v in values):
        raise ValueError("手动四角坐标无效")
    path = manual_geometry_path(project_root, page)
    payload = {
        "format": MANUAL_GEOMETRY_FORMAT,
        "version": MANUAL_GEOMETRY_VERSION,
        "page": Path(page).name,
        "quad": list(values),
    }
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def clear_manual_perspective_quad(project_root: Path, page: Path) -> None:
    current, legacy = _page_artifact_paths(project_root, page, "geometry.json", ".geometry.json")
    # Remove the matching legacy record first so it cannot show up again
    # when the current page-specific file has been deleted.
    if _manual_geometry_payload(legacy, page) is not None:
        legacy.unlink(missing_ok=True)
    current.unlink(missing_ok=True)
