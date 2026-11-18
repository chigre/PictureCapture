from __future__ import annotations

"""Source-file and sidecar I/O for image preprocessing and manual geometry."""

import json
import math
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image

from ..persistence.project_storage import image_preprocess_data_root
from ..runtime.source_file_stamp import source_file_stamp
from .models import PreprocessAnalysis


def analyze_source_path(
    path: Path, settings, *, analyzer: Callable[..., PreprocessAnalysis], **options,
) -> PreprocessAnalysis:
    """Bind the saved metadata to the image bytes read for this analysis."""
    path = Path(path)
    with path.open("rb") as source:
        original_stamp = source_file_stamp(source)
        with Image.open(source) as opened:
            analysis = analyzer(opened, settings, **options)
        if source_file_stamp(source) != original_stamp:
            raise OSError("预处理期间源图已变化，请重新分析")
    # Reopening after releasing the old handle detects a replacement of the
    # path even when that old file's open handle recorded no change.
    with path.open("rb") as current:
        if source_file_stamp(current) != original_stamp:
            raise OSError("预处理期间源图已变化，请重新分析")
    _, _, size_bytes, mtime_ns, _ = original_stamp
    analysis.source_size_bytes = size_bytes
    analysis.source_mtime_ns = mtime_ns
    return analysis


def result_path(project_root: Path, page: Path) -> Path:
    root = image_preprocess_data_root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{Path(page).stem}.json"


def save_analysis(project_root: Path, page: Path, analysis: PreprocessAnalysis) -> Path:
    path = result_path(project_root, page)
    payload = analysis.to_dict()
    payload["page"] = Path(page).name
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def load_analysis(project_root: Path, page: Path) -> PreprocessAnalysis | None:
    path = result_path(project_root, page)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PreprocessAnalysis.from_dict(payload)
    except (OSError, ValueError, TypeError, OverflowError):
        return None


MANUAL_GEOMETRY_FORMAT = "picture-capture-manual-perspective"
MANUAL_GEOMETRY_VERSION = 1


def manual_geometry_path(project_root: Path, page: Path) -> Path:
    root = image_preprocess_data_root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{Path(page).stem}.geometry.json"


def load_manual_perspective_quad(
    project_root: Path, page: Path,
) -> tuple[float, ...] | None:
    path = manual_geometry_path(project_root, page)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("format") != MANUAL_GEOMETRY_FORMAT
            or int(payload.get("version", 0) or 0) != MANUAL_GEOMETRY_VERSION
        ):
            return None
        values = payload.get("quad")
        if not isinstance(values, (list, tuple)) or len(values) != 8:
            return None
        quad = tuple(float(v) for v in values)
        return quad if all(math.isfinite(v) for v in quad) else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def clear_manual_perspective_quad(project_root: Path, page: Path) -> None:
    path = manual_geometry_path(project_root, page)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
