"""R4.2 synthetic: stale ReviewWindow crop callback must not undo UI geometry."""
from dataclasses import dataclass, replace
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

class Text:
    def get(self):
        return "synthetic"

def _launch(tmp_path):
    page = tmp_path / "page.png"
    Image.new("RGB", (12, 12), "red").save(page)
    row = Entry()
    width = [800]
    launched, rendered, retried = [], [], []
    parent = SimpleNamespace(
        project=SimpleNamespace(root=page.parent, images=[page]),
        current_page=page, current_index=0, image=object(),
        settings=Settings(),
        canvas=SimpleNamespace(winfo_width=lambda: width[0]),
        _ordered_entries_reading_order=lambda: [row],
        _start_ui_worker=lambda key, work, done, fail: launched.append((work, done)),
    )
    review = SimpleNamespace(
        parent=parent, vars=[Text()], row_entries=[row], active_index=0,
        _filter_rows_active=False, review_zoom_auto=False, review_zoom=1.0,
        _prefetch_closed=False, _review_render_worker_key="geometry-worker",
        _bound_row_entries=lambda: [row], _review_image_area_width=lambda: 700,
        winfo_exists=lambda: True,
        render_rows=lambda **kw: rendered.append(kw),
        _request_render_rows=lambda **kw: retried.append(kw),
        editors=[],
    )
    deps = SimpleNamespace(
        ttk=SimpleNamespace(), tk=SimpleNamespace(TclError=RuntimeError),
        Image=Image, _format_layout_percent=str,
        _review_crop_context=lambda *a: (None, None),
        _review_line_box=lambda *a, **kw: (0, 0, 12, 12),
        sync_review_entry_classification=lambda *_: None,
        normalize_page_rgb=lambda opened: opened.convert("RGB"),
        review_auto_fit_zoom=lambda *a: 1.0, replace=replace,
    )
    flow._request_render_rows(review, deps, focus_index=0)
    assert len(launched) == 1
    work, done = launched[0]
    payload = work()

    def deliver():
        done(payload)
        if len(launched) == 2:
            verify, verified = launched[1]
            verified(verify())
    return review, width, rendered, retried, deliver

def test_stale_zoom_is_rejected_before_crop_publish(tmp_path):
    review, width, rendered, retried, deliver = _launch(tmp_path)
    review.review_zoom = 1.5
    deliver()
    assert not rendered, "stale zoom crop was painted"
    assert len(retried) == 1

def test_stale_viewport_is_rejected_before_crop_publish(tmp_path):
    review, width, rendered, retried, deliver = _launch(tmp_path)
    width[0] = 540
    deliver()
    assert not rendered, "stale viewer-width crop was painted"
    assert len(retried) == 1

def test_stale_settings_are_rejected_before_crop_publish(tmp_path):
    review, width, rendered, retried, deliver = _launch(tmp_path)
    review.parent.settings.review_zoom_percent = 125
    deliver()
    assert not rendered, "stale settings crop was painted"
    assert len(retried) == 1

def test_identical_crop_geometry_is_accepted(tmp_path):
    review, width, rendered, retried, deliver = _launch(tmp_path)
    deliver()
    assert len(rendered) == 1
    assert not retried
