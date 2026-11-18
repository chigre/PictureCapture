"""Exercise focused save completion against in-flight Tcl text edits."""
from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PIL import Image

from picture_capture.io.formats import read_pdic
from picture_capture.persistence.project_storage import pdic_path_for_image
from picture_capture.proofreading.focused_crop_source_fingerprint import focused_save_source_witness
from picture_capture.proofreading.focused_pdic_updates import FocusedPdicDeps, apply_focused_review_page_updates
from picture_capture.proofreading.pdic_restore import write_pdic_atomic
from picture_capture.ui import focused_filter_workflow as flow


@pytest.fixture
def focused_save(tmp_path):
    page = tmp_path / "001.bmp"
    Image.new("RGB", (8, 8), "white").save(page)
    pdic = pdic_path_for_image(page)
    pdic.write_bytes(b"before#3#4#37.5#50#001#@#@\n")
    target = {
        "page_index": 0, "x": 3, "y": 4,
        "original_word": "before", "current_word": "before",
        "_focused_save_source_witness": focused_save_source_witness(page),
    }
    tcl = tk.Tcl()
    word = tk.StringVar(master=tcl, value="before")
    status = tk.StringVar(master=tcl)
    timers, dispatches, writes, warnings = {}, [], [], []
    sequence = iter(range(100))

    def after(delay, callback):
        token = next(sequence)
        timers[token] = (delay, callback)
        return token

    def fire_next_timer():
        token = min(timers, key=lambda key: (timers[key][0], key))
        _, callback = timers.pop(token)
        callback()

    def dispatch(_key, worker, done, _failed, **_kwargs):
        dispatches.append((worker, done))
        return len(dispatches)

    pdic_deps = FocusedPdicDeps(pdic_path_for_image, read_pdic, replace, Image, write_pdic_atomic)

    def write(the_page, pages, index, changes):
        writes.append(tuple((change["original_word"], change["new_word"]) for change in changes))
        return apply_focused_review_page_updates(the_page, pages, index, changes, deps=pdic_deps)

    deps = SimpleNamespace(
        tk=tk,
        _apply_focused_review_page_updates=write,
        messagebox=SimpleNamespace(showwarning=lambda *args, **_kwargs: warnings.append(args)),
    )
    review = SimpleNamespace(
        parent=SimpleNamespace(
            project=SimpleNamespace(images=[page]), status_var=status,
            _project_words=(), _start_ui_worker=dispatch,
        ),
        filter_vars=[word], filter_editors=[SimpleNamespace(configure=lambda **_kwargs: None)],
        filtered_targets=[target], _filter_current_batch_targets=[target],
        _filter_rows_active=True, _filter_pending_changes={}, _filter_save_job=None,
        _filter_save_running=False, _filter_close_after_save=False,
        after=after, after_cancel=timers.pop,
    )
    review._queue_focused_change = lambda row, value: flow._queue_focused_change(review, deps, row, value)
    review._flush_focused_changes = lambda: flow._flush_focused_changes(review, deps)
    word.trace_add("write", lambda *_args: flow._commit_filter_editor_value(review, deps, 0))
    return SimpleNamespace(
        review=review, word=word, pdic=pdic, target=target, timers=timers, fire_next_timer=fire_next_timer,
        dispatches=dispatches, writes=writes, warnings=warnings, status=status,
    )


def test_success_replaces_pending_debounce_and_saves_latest_text(focused_save):
    case = focused_save
    case.word.set("first")
    case.fire_next_timer()
    worker, done = case.dispatches[0]

    case.word.set("intermediate")
    case.word.set("latest")
    old_timer = case.review._filter_save_job
    result = worker()
    assert case.pdic.read_bytes() == b"first#3#4#37.5#50#001#@#@\n"
    done(result)

    pending = case.review._filter_pending_changes[0][(3, 4)]
    assert (pending["original_word"], pending["new_word"]) == ("first", "latest")
    assert pending["_focused_save_source_witness"] == case.target["_focused_save_source_witness"]
    assert case.timers[case.review._filter_save_job][0] == 1
    case.fire_next_timer()
    worker, done = case.dispatches[1]
    done(worker())

    assert case.pdic.read_bytes() == b"latest#3#4#37.5#50#001#@#@\n"
    assert case.writes == [(('before', 'first'),), (('first', 'latest'),)]
    assert case.target["original_word"] == case.word.get() == "latest"
    assert case.warnings == []
    assert old_timer not in case.timers
    assert not case.timers and not case.review._filter_pending_changes


def test_pdic_conflict_cancels_inflight_edit_debounce(focused_save):
    case = focused_save
    case.word.set("first")
    case.fire_next_timer()
    worker, done = case.dispatches[0]
    case.word.set("latest")

    foreign_bytes = b"foreign#3#4#37.5#50#001#@#@\n"
    case.pdic.write_bytes(foreign_bytes)
    done(worker())

    assert len(case.warnings) == 1
    assert "冲突" in case.status.get()
    assert case.review._filter_pending_changes[0][(3, 4)]["new_word"] == "latest"
    assert case.target["original_word"] == "before"
    assert case.word.get() == "latest"
    if case.timers:
        case.fire_next_timer()
    assert len(case.dispatches) == 1
    assert case.review._filter_save_job is None and not case.timers
    assert case.pdic.read_bytes() == foreign_bytes


def test_expired_debounce_is_rearmed_after_inflight_save(focused_save):
    case = focused_save
    case.word.set("first")
    case.fire_next_timer()
    worker, done = case.dispatches[0]
    case.word.set("latest")
    case.fire_next_timer()
    assert len(case.dispatches) == 1
    assert case.review._filter_save_job is None

    done(worker())
    case.fire_next_timer()
    worker, done = case.dispatches[1]
    done(worker())
    assert case.pdic.read_bytes() == b"latest#3#4#37.5#50#001#@#@\n"
    assert not case.timers and not case.review._filter_pending_changes
    assert case.warnings == []


def test_inflight_reversion_to_original_is_saved_after_first_commit(focused_save):
    case = focused_save
    original_bytes = case.pdic.read_bytes()
    case.word.set("first")
    case.fire_next_timer()
    worker, done = case.dispatches[0]
    case.word.set("before")
    case.fire_next_timer()
    assert not case.review._filter_pending_changes

    done(worker())
    case.fire_next_timer()
    worker, done = case.dispatches[1]
    done(worker())
    assert case.writes == [(("before", "first"),), (("first", "before"),)]
    assert case.pdic.read_bytes() == original_bytes
    assert not case.timers and not case.review._filter_pending_changes
    assert case.warnings == []
