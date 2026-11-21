"""R4.2: delayed row-height crop must belong to the exact editor text.

Synthetic only: no Tk root, private page, OCR, PDIC, or filesystem I/O.
"""
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from picture_capture.ui.review_crop_actions import (
    ReviewCropDeps, _refresh_review_row_crop,
)


@dataclass
class Entry:
    word: str = "甲"


@dataclass
class Settings:
    review_zoom_percent: int = 100


class Text:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _harness(initial):
    entry = Entry()
    text = Text(initial)
    page = object()
    image = object()
    launched = []
    displayed = []
    crop = SimpleNamespace(width=41)
    parent = SimpleNamespace(
        image=image, current_page=page, current_index=0,
        settings=Settings(),
        canvas=SimpleNamespace(winfo_width=lambda: 800),
        _start_ui_worker=lambda key, worker, done: launched.append(done),
    )
    row_picture = SimpleNamespace(
        configure=lambda **kw: displayed.append(kw["image"]),
    )
    review = SimpleNamespace(
        parent=parent, vars=[text], review_zoom=1.0,
        _review_crop_render_generation=0,
        _review_render_worker_key="synthetic-height",
        _review_display_crops=[object()],
        _review_row_pictures=[row_picture],
        _review_crop_single_flags=[False],
        thumbnails=[None], editor_crop_widths=[0],
        active_index=-1, _review_crop_height_jobs={},
        _bound_row_entries=lambda: [entry],
        winfo_exists=lambda: True,
        _ordinary_review_photo=lambda index: "new-photo",
    )
    deps = ReviewCropDeps(
        tk=SimpleNamespace(TclError=RuntimeError),
        Image=SimpleNamespace(), ImageTk=SimpleNamespace(),
        replace=replace, _review_crop_context=lambda *a: None,
        _review_line_box=lambda *a, **kw: None,
        parse_review_crop_multiplier=lambda *a: 2,
        extended_review_crop_box=lambda *a: None,
        _focused_review_is_single_character=lambda value: len(value) == 1,
        themed_display_image=lambda *a: None,
    )
    _refresh_review_row_crop(review, deps, 0)
    assert len(launched) == 1
    return text, launched[0], review, crop, displayed


@pytest.mark.parametrize(
    "before,after",
    [("甲", "乙"), ("甲乙", "丙丁"), ("甲", "甲乙")],
)
def test_stale_editor_text_must_not_publish_row_crop(before, after):
    text, done, review, crop, displayed = _harness(before)
    old = review._review_display_crops[0]
    text.value = after
    done(crop)
    assert review._review_display_crops[0] is old
    assert displayed == []


@pytest.mark.parametrize("word", ["甲", "甲乙"])
def test_unchanged_editor_text_publishes_row_crop(word):
    _, done, review, crop, displayed = _harness(word)
    done(crop)
    assert review._review_display_crops[0] is crop
    assert displayed == ["new-photo"]
    assert review.editor_crop_widths == [41]
