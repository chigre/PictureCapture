"""R4.2 synthetic crop callback ownership after in-place source image replacement.

Only temporary synthetic BMP pixels; no real scan, OCR, Tk root or saved project.
"""
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from picture_capture.ui import review_workspace_workflow as flow


@dataclass
class Entry:
    word: str = "synthetic"
    x: int = 12
    y: int = 34


@dataclass
class Settings:
    review_zoom_percent: int = 100


def _normalize_and_notify(opened, after_read):
    # Capture pixels from the already-opened image before the path is replaced.
    pixels = opened.convert("RGB")
    if after_read is not None:
        after_read()
    return pixels


def _start(page: Path, *, after_read=None):
    row = Entry()
    callbacks, rendered, retried = [], [], []
    parent = SimpleNamespace(
        project=object(), current_page=page, current_index=0, image=object(),
        settings=Settings(), canvas=SimpleNamespace(winfo_width=lambda: 800),
        _ordered_entries_reading_order=lambda: [row],
        _start_ui_worker=lambda key, work, done, fail: callbacks.append((work, done)),
    )
    review = SimpleNamespace(
        parent=parent, vars=[SimpleNamespace(get=lambda: "synthetic")],
        row_entries=[row], active_index=0, _filter_rows_active=False,
        review_zoom_auto=False, review_zoom=1.0, _prefetch_closed=False,
        _review_render_worker_key="source-content-worker",
        _bound_row_entries=lambda: [row], _review_image_area_width=lambda: 700,
        winfo_exists=lambda: True, render_rows=lambda **kw: rendered.append(kw),
        _request_render_rows=lambda **kw: retried.append(kw), editors=[],
    )
    deps = SimpleNamespace(
        ttk=SimpleNamespace(), tk=SimpleNamespace(TclError=RuntimeError),
        Image=Image, _format_layout_percent=str,
        _review_crop_context=lambda *a: (None, object()),
        _review_line_box=lambda *a, **kw: (0, 0, 12, 12),
        sync_review_entry_classification=lambda *_: None,
        normalize_page_rgb=lambda opened: _normalize_and_notify(opened, after_read),
        review_auto_fit_zoom=lambda *a: 1.0, replace=replace,
    )
    flow._request_render_rows(review, deps, focus_index=0)
    assert len(callbacks) == 1
    # Execute the real crop worker against the original red synthetic image.
    payload = callbacks[0][0]()
    assert payload[2][0].getpixel((0, 0)) == (255, 0, 0)
    def deliver():
        callbacks[0][1](payload)
    return rendered, retried, deliver


def _write_bmp(page: Path, rgb):
    Image.new("RGB", (12, 12), rgb).save(page, format="BMP")


def test_same_path_same_size_same_mtime_changed_pixels_reject_old_crop(tmp_path):
    page = tmp_path / "page.bmp"
    _write_bmp(page, (255, 0, 0))
    original = page.read_bytes()
    stamp = page.stat()
    rendered, retried, deliver = _start(page)
    _write_bmp(page, (0, 0, 255))
    import os
    os.utime(page, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert page.read_bytes() != original
    assert page.stat().st_size == stamp.st_size
    assert page.stat().st_mtime_ns == stamp.st_mtime_ns
    deliver()
    assert not rendered, "old crop pixels were painted after source content changed"


def test_same_path_unchanged_pixels_accept_crop(tmp_path):
    page = tmp_path / "page.bmp"
    _write_bmp(page, (255, 0, 0))
    rendered, retried, deliver = _start(page)
    deliver()
    assert len(rendered) == 1
    assert not retried


def test_source_replaced_while_worker_is_cropping_reject_old_pixels(tmp_path):
    page = tmp_path / "page.bmp"
    _write_bmp(page, (255, 0, 0))
    original = page.read_bytes()
    stamp = page.stat()

    def replace_during_worker():
        # Worker has read red pixels; mutate the same path before crop finishes.
        _write_bmp(page, (0, 0, 255))
        import os
        os.utime(page, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

    rendered, retried, deliver = _start(page, after_read=replace_during_worker)
    assert page.read_bytes() != original
    assert page.stat().st_size == stamp.st_size
    assert page.stat().st_mtime_ns == stamp.st_mtime_ns
    deliver()
    assert not rendered, "worker crop from pre-replacement pixels was painted"
