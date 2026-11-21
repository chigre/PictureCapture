"""R4.2 synthetic async ReviewWindow crop owner: input revision must match crop.

Capture production worker callback without starting a thread or opening a real
image. Source Entry remains unchanged; human Tk text changes before delivery.
No user images, private words, persisted sidecars, or real OCR.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

from PIL import Image

from picture_capture.ui import review_workspace_workflow as workflow


@dataclass
class Entry:
    word: str = "first"
    x: int = 12
    y: int = 34


@dataclass
class Settings:
    review_zoom_percent: int = 100


class Value:
    def __init__(self, value):
        self.text = value

    def get(self):
        return self.text

    def set(self, value):
        self.text = value


def _case(tmp_path):
    page = tmp_path / "page-01.png"
    Image.new("RGB", (12, 12), "red").save(page)
    row = Entry()
    text = Value(row.word)
    observed, rendered, retried = [], [], []
    parent = SimpleNamespace(
        project=SimpleNamespace(root=page.parent, images=[page]),
        current_page=page, current_index=0, image=object(), settings=Settings(),
        canvas=SimpleNamespace(winfo_width=lambda: 800),
        _ordered_entries_reading_order=lambda: [row],
        _start_ui_worker=lambda key, worker, done, failed: observed.append(
            (key, worker, done, failed)
        ),
    )
    review = SimpleNamespace(
        parent=parent, vars=[text], row_entries=[row], active_index=0,
        _filter_rows_active=False, review_zoom_auto=False, review_zoom=1.0,
        _prefetch_closed=False, _review_render_worker_key="review-render",
        _bound_row_entries=lambda: [row],
        _review_image_area_width=lambda: 700,
        winfo_exists=lambda: True,
        render_rows=lambda **kw: rendered.append(kw),
        _request_render_rows=lambda **kw: retried.append(kw),
        editors=[],
    )
    deps = SimpleNamespace(
        ttk=SimpleNamespace(), tk=SimpleNamespace(TclError=RuntimeError),
        Image=Image,
        _format_layout_percent=lambda value: str(value),
        _review_crop_context=lambda *args: (None, None),
        _review_line_box=lambda *args, **kwargs: (0, 0, 12, 12),
        sync_review_entry_classification=lambda _review: None,
        normalize_page_rgb=lambda opened: opened.convert("RGB"),
        review_auto_fit_zoom=lambda *args: 1.0,
        replace=replace,
    )
    workflow._request_render_rows(review, deps, focus_index=0)
    assert len(observed) == 1
    _, worker, done, _ = observed[0]
    payload = worker()
    return review, text, rendered, retried, lambda: done(payload), observed


def test_async_crop_with_changed_live_editor_text_is_rejected_and_requeued(tmp_path):
    _view, text, rendered, retried, deliver, observed = _case(tmp_path)
    text.set("first was revised into a much longer human edit")
    deliver()
    assert rendered == [], "stale crop length was accepted despite changed Tk text"
    assert len(retried) == 1, "new editor revision needs its own crop worker"
    assert text.get() == "first was revised into a much longer human edit"
    assert len(observed) == 1


def test_async_crop_with_unchanged_live_editor_text_is_accepted(tmp_path):
    _view, _text, rendered, retried, deliver, observed = _case(tmp_path)
    deliver()
    assert not rendered
    _, verify, verified, _ = observed[1]
    verified(verify())
    assert len(rendered) == 1
    assert retried == []


def test_async_crop_rechecks_live_editor_text_after_source_verification(tmp_path):
    _view, text, rendered, retried, deliver, observed = _case(tmp_path)
    deliver()
    assert not rendered
    _, verify, verified, _ = observed[1]
    result = verify()
    text.set("new unsaved edit")
    verified(result)
    assert rendered == []
    assert len(retried) == 1
    assert text.get() == "new unsaved edit"
