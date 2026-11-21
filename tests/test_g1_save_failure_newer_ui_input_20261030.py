"""G1 fail-first: a failed save must not restore over more recent UI input.

A synchronous Tk callback or event can revise an editor/ReviewWindow var
after a save's initial snapshot but before its writer raises. Matching
PDIC source bytes do not authorize overwriting that newer human input.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from picture_capture.io.formats import pdic_path, write_pdic
from picture_capture.models import Entry
from picture_capture.proofreading.save_safety import (
    protect_app_pdic_commit, protect_review_pdic_commit,
)


class Editor:
    def __init__(self, text):
        self.text = text
    def get(self):
        return self.text
    def delete(self, _from, _to):
        self.text = ""
    def insert(self, _where, text):
        self.text = text


class Var:
    def __init__(self, text):
        self.text = text
    def get(self):
        return self.text
    def set(self, text):
        self.text = text


def _setup(tmp_path):
    page = tmp_path / "001.png"
    page.write_bytes(b"synthetic-image-not-private")
    entry = Entry("old", 10, 20)
    write_pdic(pdic_path(page), [entry], 100, ("001", "@", "@"))
    editor = Editor("pending before-save user text")
    app = SimpleNamespace(
        current_page=page, entries=[entry], entry_editor_bindings=[(editor, entry)],
    )
    review_var = Var("pending review word")
    review = SimpleNamespace(
        parent=app, vars=[review_var], _rendered_page_stem="001",
        _simplified_page_cache={"001": {"10,20": {"text": "original manual"}}},
        _simplified_dirty_pages={"001"},
        simplified_manual_flags=[False],
        simplified_actual_values=["original manual"],
    )
    return page, entry, editor, app, review, review_var


def test_main_save_failure_never_overwrites_newer_tk_editor_input(tmp_path):
    page, entry, editor, app, _, _ = _setup(tmp_path)
    before = pdic_path(page).read_bytes()
    with pytest.raises(OSError, match="writer failure"):
        with protect_app_pdic_commit(app):
            entry.word = "attempted word"
            # Reentrant Tk event or paste occurred while the save was active.
            editor.text = "newest typed Chinese word 中文"
            raise OSError("writer failure")
    assert editor.text == "newest typed Chinese word 中文"
    assert app._deferred_save_uncertain is True
    assert entry.word == "attempted word"
    assert pdic_path(page).read_bytes() == before


def test_review_save_failure_preserves_new_var_and_simplified_cache(tmp_path):
    page, entry, editor, app, review, var = _setup(tmp_path)
    before = pdic_path(page).read_bytes()
    with pytest.raises(OSError, match="writer failure"):
        with protect_review_pdic_commit(review):
            entry.word = "attempted word"
            # ReviewWindow input trace can write newer human sidecar values.
            var.set("newest review input 中文")
            review._simplified_page_cache["001"]["10,20"]["text"] = "newest simplified edit"
            review.simplified_manual_flags[0] = True
            review.simplified_actual_values[0] = "newest simplified edit"
            raise OSError("writer failure")
    assert var.get() == "newest review input 中文"
    assert review._simplified_page_cache["001"]["10,20"]["text"] == "newest simplified edit"
    assert review.simplified_manual_flags == [True]
    assert review.simplified_actual_values == ["newest simplified edit"]
    assert entry.word == "attempted word"
    assert app._deferred_save_uncertain is True
    assert pdic_path(page).read_bytes() == before


def test_review_failure_preserves_newer_main_canvas_editor_input(tmp_path):
    page, entry, editor, app, review, var = _setup(tmp_path)
    with pytest.raises(OSError, match="writer failure"):
        with protect_review_pdic_commit(review):
            entry.word = "attempted"
            editor.text = "newer main canvas input"
            raise OSError("writer failure")
    assert editor.text == "newer main canvas input"
    assert app._deferred_save_uncertain is True


def test_main_failed_save_with_unchanged_widgets_still_rolls_back(tmp_path):
    page, entry, editor, app, _, _ = _setup(tmp_path)
    with pytest.raises(OSError, match="writer failure"):
        with protect_app_pdic_commit(app):
            entry.word = "attempted"
            raise OSError("writer failure")
    assert entry.word == "old"
    assert editor.text == "pending before-save user text"
    assert not app.__dict__.get("_deferred_save_uncertain", False)


def test_review_failed_save_with_unchanged_widgets_still_rolls_back(tmp_path):
    page, entry, editor, app, review, var = _setup(tmp_path)
    with pytest.raises(OSError, match="writer failure"):
        with protect_review_pdic_commit(review):
            entry.word = "attempted"
            review._simplified_page_cache["001"]["10,20"]["text"] = "attempted"
            review.simplified_manual_flags[0] = True
            raise OSError("writer failure")
    assert entry.word == "old"
    assert review._simplified_page_cache["001"]["10,20"]["text"] == "original manual"
    assert review.simplified_manual_flags == [False]
    assert var.get() == "pending review word"
    assert not app.__dict__.get("_deferred_save_uncertain", False)


@pytest.mark.parametrize("rebound", [False, True])
def test_review_save_failure_preserves_simplified_editor_ownership(tmp_path, rebound):
    page, entry, _, app, review, _ = _setup(tmp_path)
    review.simplified_vars = [Var("original manual")]
    before = pdic_path(page).read_bytes()
    with pytest.raises(OSError, match="writer failure"):
        with protect_review_pdic_commit(review):
            entry.word = "attempted word"
            if rebound:
                review.simplified_vars = [Var("new simplified edit")]
            else:
                review.simplified_vars[0].set("new simplified edit")
            review._simplified_page_cache["001"]["10,20"]["text"] = "new simplified edit"
            review.simplified_manual_flags[0] = True
            review.simplified_actual_values[0] = "new simplified edit"
            raise OSError("writer failure")
    assert review.simplified_vars[0].get() == "new simplified edit"
    assert review._simplified_page_cache["001"]["10,20"]["text"] == "new simplified edit"
    assert review.simplified_actual_values == ["new simplified edit"]
    assert review.simplified_manual_flags == [True]
    assert getattr(app, "_deferred_save_uncertain", False) is True
    assert pdic_path(page).read_bytes() == before


def test_review_save_failure_checks_simplified_disk_even_when_pdic_is_unchanged(tmp_path):
    from picture_capture.persistence.project_storage import simplified_review_path_for_image

    page, _, _, app, review, _ = _setup(tmp_path)
    sidecar = simplified_review_path_for_image(page)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_bytes(b"original simplified data")
    pdic_before = pdic_path(page).read_bytes()
    with pytest.raises(OSError, match="writer failure"):
        with protect_review_pdic_commit(review):
            sidecar.write_bytes(b"newer simplified data")
            raise OSError("writer failure")
    assert getattr(app, "_deferred_save_uncertain", False) is True
    assert sidecar.read_bytes() == b"newer simplified data"
    assert pdic_path(page).read_bytes() == pdic_before
