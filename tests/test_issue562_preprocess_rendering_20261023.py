"""Rendering ownership, live API wiring and real image export contracts."""
from __future__ import annotations

import ast
from dataclasses import replace
import os
from pathlib import Path
import pickle
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image, JpegImagePlugin
import pytest

from picture_capture.preprocess import pipeline as api
from picture_capture.preprocess import rendering

NAMES = ("overlay_excluded_regions", "review_image", "processed_image",
         "processed_image_with_canvas", "save_review_preview", "save_processed_page")


@pytest.fixture
def analysis():
    return api.PreprocessAnalysis(
        source_width=40, source_height=60, correction_angle_deg=0, applied_angle_deg=0,
        crop_box=(4, 6, 34, 56), raw_content_box=(4, 6, 34, 56), text_box=None,
        source_boxes=0, angle_samples=0, angle_mad_deg=0, retained_ratio=.625,
        confidence=1, status="normal", method="test",
    )


@pytest.fixture
def source():
    return Image.fromarray(np.arange(40 * 60 * 3, dtype=np.uint8).reshape(60, 40, 3))


@pytest.mark.parametrize("name", NAMES)
def test_single_owner_and_compatible_callable(name):
    fn = getattr(api, name)
    assert pickle.loads(pickle.dumps(fn)) is fn
    assert Path(getattr(rendering, name).__code__.co_filename) == Path(rendering.__file__)
    defs = {n.name: n for n in ast.parse(Path(api.__file__).read_text(encoding="utf-8")).body
            if isinstance(n, ast.FunctionDef)}
    assert len(defs[name].body) == 1
    assert isinstance(defs[name].body[0], ast.Return)


def test_leaf_import_does_not_initialize_facade_gui_or_paddle():
    subprocess.run([sys.executable, "-c", """
import sys
from picture_capture.preprocess import rendering
assert 'picture_capture.preprocess.pipeline' not in sys.modules
assert 'picture_capture.app' not in sys.modules
assert 'paddle' not in sys.modules
"""], check=True)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
@pytest.mark.parametrize("box", [(4, 6, 34, 56), (-20, -30, 80, 90)])
def test_overlay_normalizes_modes_clamps_and_preserves_source(source, mode, box):
    source = source.convert(mode)
    before = source.tobytes()
    result = api.overlay_excluded_regions(source, box)
    assert result.size == source.size and result.mode == "RGB"
    assert result.getpixel((20, 30)) == api.normalize_page_rgb(source).getpixel((20, 30))
    assert source.tobytes() == before


def test_live_render_operations_are_supplied_at_call_time(monkeypatch, source, analysis):
    overlay_adapter = api.overlay_excluded_regions
    corrected = Image.new("RGB", source.size, "red")
    calls = []
    monkeypatch.setattr(api, "geometry_corrected_image", lambda *args: corrected)
    assert api.processed_image(source, analysis).getpixel((0, 0)) == (255, 0, 0)
    monkeypatch.setattr(api, "overlay_excluded_regions", lambda image, box: calls.append((image, box)) or image)
    assert api.review_image(source, analysis) is corrected
    assert calls == [(corrected, analysis.crop_box)]
    monkeypatch.setattr(api, "normalize_page_rgb", lambda image: corrected)
    assert api.overlay_excluded_regions is not rendering.overlay_excluded_regions
    # Restore the adapter to verify the live normalizer as well.
    monkeypatch.setattr(api, "overlay_excluded_regions", overlay_adapter)
    assert api.overlay_excluded_regions(source, analysis.crop_box).getpixel((20, 30)) == (255, 0, 0)


def test_canvas_expands_without_resampling_and_uses_current_factory(monkeypatch, source, analysis):
    content = source.crop(analysis.crop_box)
    canvas = api.output_canvas_info(analysis, enabled=True, canvas_width=70, canvas_height=90,
                                  margin_left=3, margin_right=5, margin_top=7, margin_bottom=9)
    undersized = replace(canvas, width=1, height=1)
    factory = api.output_canvas_info
    calls = []
    monkeypatch.setattr(api, "output_canvas_info", lambda *a, **kw: calls.append(kw) or factory(*a, **kw))
    result = api.processed_image_with_canvas(source, analysis, undersized)
    assert result.size == (38, 66)
    assert calls[0]["canvas_width"] == 38 and calls[0]["canvas_height"] == 66
    assert result.crop((3, 7, 33, 57)).tobytes() == content.tobytes()
    assert result.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("suffix,fmt", [(".PNG", "PNG"), (".jpg", "JPEG"),
                                        (".JPEG", "JPEG"), (".tif", "TIFF"), (".TIFF", "TIFF")])
def test_export_reopens_in_original_coordinates(tmp_path, source, analysis, suffix, fmt):
    page = tmp_path / "scan.png"
    source.save(page)
    destination = tmp_path / "nested" / ("crop" + suffix)
    assert api.save_processed_page(page, analysis, destination) == destination
    with Image.open(destination) as output:
        assert output.format == fmt and output.size == (30, 50)
        if fmt == "JPEG":
            assert JpegImagePlugin.get_sampling(output) == 0
        else:
            assert output.tobytes() == source.crop(analysis.crop_box).tobytes()
        if fmt == "TIFF":
            assert output.info["compression"] == "tiff_lzw"
    with Image.open(page) as original:
        assert original.tobytes() == source.tobytes()


@pytest.mark.parametrize("box", [
    (4.5, 6, 34, 56), (False, 6, 34, 56), (-1, 6, 34, 56),
    (4, 6, 41, 56), (4, 6, 34, 61), (4, 6, 4, 56),
])
def test_bad_reviewed_crop_cannot_reopen_or_replace_existing_export(tmp_path, source, analysis, box):
    page = tmp_path / "scan.png"
    source.save(page)
    malformed = replace(analysis, crop_box=box)
    cache = api.save_analysis(tmp_path, page, malformed)
    cached_bytes = cache.read_bytes()
    assert api.load_analysis(tmp_path, page) is None
    assert cache.read_bytes() == cached_bytes

    destination = tmp_path / "output.png"
    original = page.read_bytes()
    destination.write_bytes(original)
    with pytest.raises(ValueError, match="crop_box"):
        api.save_processed_page(page, malformed, destination)
    with pytest.raises(ValueError, match="crop_box"):
        api.save_review_preview(page, malformed, destination)
    assert page.read_bytes() == destination.read_bytes() == original


def test_uvdoc_crop_bounds_follow_the_actual_corrected_image(tmp_path, monkeypatch, source, analysis):
    page = tmp_path / "scan.png"
    source.save(page)
    accepted = replace(analysis, geometry_mode="uvdoc", crop_box=(4, 6, 50, 56))
    api.save_analysis(tmp_path, page, accepted)
    reopened = api.load_analysis(tmp_path, page)
    assert reopened is not None and reopened.crop_box == accepted.crop_box
    monkeypatch.setattr(api, "unwarp_document_image", lambda _image: Image.new("RGB", (50, 60), "white"))
    assert api.processed_image(source, reopened).size == (46, 50)


def test_analysis_uses_the_metadata_of_the_image_it_decoded(tmp_path, monkeypatch, source, analysis):
    page = tmp_path / "scan.png"
    source.save(page)
    monkeypatch.setattr(api, "analyze_preprocess_page", lambda *_args, **_kwargs: replace(analysis))

    result = api.analyze_preprocess_path(page, object())

    assert result.source_size_bytes == page.stat().st_size
    assert result.source_mtime_ns == page.stat().st_mtime_ns


def test_analysis_refuses_a_source_changed_during_processing(tmp_path, monkeypatch, source, analysis):
    page = tmp_path / "scan.png"
    source.save(page)
    before = page.stat()

    def analyze(opened, *_args, **_kwargs):
        opened.load()
        os.utime(page, ns=(before.st_atime_ns, before.st_mtime_ns - 2_000_000_000))
        return replace(analysis)

    monkeypatch.setattr(api, "analyze_preprocess_page", analyze)
    with pytest.raises(OSError, match="源图已变化"):
        api.analyze_preprocess_path(page, object())


def test_analysis_refuses_a_same_size_replacement_before_accepting_metadata(
    tmp_path, monkeypatch, source, analysis,
):
    page = tmp_path / "scan.bmp"
    replacement = tmp_path / "replacement.bmp"
    source.save(page)
    with Image.new("RGB", source.size, "blue") as alternate:
        alternate.save(replacement)
    before = page.stat()
    assert replacement.stat().st_size == before.st_size
    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
    real_open = Path.open
    source_opens = []

    def open_with_replacement(path, mode="r", *args, **kwargs):
        if path == page and mode == "rb":
            if source_opens:
                replacement.replace(page)
            source_opens.append(path)
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_replacement)
    monkeypatch.setattr(api, "analyze_preprocess_page", lambda *_args, **_kwargs: replace(analysis))
    with pytest.raises(OSError, match="源图已变化"):
        api.analyze_preprocess_path(page, object())


@pytest.mark.parametrize("size,requested,expected", [((80, 100), 10, (80, 100)),
    ((400, 800), 10, (160, 320)), ((400, 800), 600, (300, 600))])
def test_preview_size_floor_and_jpeg_policy(tmp_path, monkeypatch, analysis, size, requested, expected):
    page = tmp_path / "scan.png"
    Image.new("RGB", size, "white").save(page)
    calls = []
    monkeypatch.setattr(api, "review_image", lambda image, a: calls.append(a) or image.copy())
    target = tmp_path / "preview" / "extension.png"
    assert api.save_review_preview(page, analysis, target, max_long_side=requested) == target
    with Image.open(target) as output:
        assert output.format == "JPEG" and output.size == expected
    assert calls == [analysis]


def test_save_uses_current_canvas_renderer(tmp_path, monkeypatch, analysis):
    page = tmp_path / "scan.png"
    Image.new("RGB", (40, 60)).save(page)
    canvas = SimpleNamespace(enabled=True)
    calls = []
    monkeypatch.setattr(api, "processed_image_with_canvas",
        lambda image, a, c: calls.append((a, c)) or Image.new("RGB", (7, 9), "blue"))
    target = tmp_path / "result.png"
    api.save_processed_page(page, analysis, target, canvas=canvas)
    with Image.open(target) as output:
        assert output.size == (7, 9) and output.getpixel((0, 0)) == (0, 0, 255)
    assert calls == [(analysis, canvas)]
