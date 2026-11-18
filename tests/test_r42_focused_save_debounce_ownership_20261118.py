"""Exercise focused save completion against in-flight Tcl text edits."""
from __future__ import annotations

import os
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
from picture_capture.ui import main_pdic_persistence, review_page_lifecycle


def _pdic_bytes(word):
    # PDIC text is written with the platform-native line ending.
    return f"{word}#3#4#37.5#50#001#@#@{os.linesep}".encode("utf-8")


@pytest.fixture
def focused_save(tmp_path):
    page = tmp_path / "001.bmp"
    Image.new("RGB", (8, 8), "white").save(page)
    pdic = pdic_path_for_image(page)
    pdic.write_bytes(_pdic_bytes("before"))
    target = {
        "page_index": 0, "x": 3, "y": 4,
        "original_word": "before", "current_word": "before",
        "_focused_save_source_witness": focused_save_source_witness(page),
    }
    tcl = tk.Tcl()
    word = tk.StringVar(master=tcl, value="before")
    status = tk.StringVar(master=tcl)
    timers, dispatches, failures, writes, warnings = {}, [], [], [], []
    post_write_errors = []
    sequence = iter(range(100))

    def after(delay, callback):
        token = next(sequence)
        timers[token] = (delay, callback)
        return token

    def fire_next_timer():
        token = min(timers, key=lambda key: (timers[key][0], key))
        _, callback = timers.pop(token)
        callback()

    def dispatch(_key, worker, done, failed, **_kwargs):
        dispatches.append((worker, done))
        failures.append(failed)
        return len(dispatches)

    def publish(*args):
        write_pdic_atomic(*args)
        if post_write_errors:
            raise post_write_errors.pop()

    pdic_deps = FocusedPdicDeps(pdic_path_for_image, read_pdic, replace, Image, publish)

    def write(the_page, pages, index, changes):
        writes.append(tuple((change["original_word"], change["new_word"]) for change in changes))
        return apply_focused_review_page_updates(the_page, pages, index, changes, deps=pdic_deps)

    deps = SimpleNamespace(
        tk=tk,
        _apply_focused_review_page_updates=write,
        messagebox=SimpleNamespace(
            showwarning=lambda *args, **_kwargs: warnings.append(args),
            showerror=lambda *args, **_kwargs: warnings.append(args),
        ),
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
    review._flush_focused_changes_now = lambda: flow._flush_focused_changes_now(review, deps)
    review.autosave_commit = lambda: review_page_lifecycle.autosave_commit(review, None)
    review.winfo_exists = lambda: True
    word.trace_add("write", lambda *_args: flow._commit_filter_editor_value(review, deps, 0))
    return SimpleNamespace(
        review=review, word=word, pdic=pdic, target=target, timers=timers, fire_next_timer=fire_next_timer,
        dispatches=dispatches, failures=failures, writes=writes, warnings=warnings, status=status,
        post_write_errors=post_write_errors,
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
    assert case.pdic.read_bytes() == _pdic_bytes("first")
    done(result)

    pending = case.review._filter_pending_changes[0][(3, 4)]
    assert (pending["original_word"], pending["new_word"]) == ("first", "latest")
    assert pending["_focused_save_source_witness"] == case.target["_focused_save_source_witness"]
    assert case.timers[case.review._filter_save_job][0] == 1
    case.fire_next_timer()
    worker, done = case.dispatches[1]
    done(worker())

    assert case.pdic.read_bytes() == _pdic_bytes("latest")
    assert case.writes == [(("before", "first"),), (("first", "latest"),)]
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

    foreign_bytes = _pdic_bytes("foreign")
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
    assert case.pdic.read_bytes() == _pdic_bytes("latest")
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


def _run_shared_autosave(case):
    app = case.review.parent
    touches = []
    app.autosave_var = SimpleNamespace(get=lambda: True)
    app._batch_active = False
    app.current_page = app.project.images[0]
    app.review_window = case.review
    app.save_pdic = lambda **_kwargs: touches.append("main PDIC")
    app._save_normalized_ppp = lambda: touches.append("PPP") or True
    app.toggle_autosave = lambda: touches.append("rearm")
    main_pdic_persistence.autosave_tick(app, deps={"tk": tk})
    return touches


@pytest.mark.parametrize("failure", ["launch-refused", "after-pdic-publication"])
def test_shared_autosave_cannot_replay_an_unconfirmed_focused_save(focused_save, failure):
    case = focused_save
    app = case.review.parent
    dispatch = app._start_ui_worker
    original_bytes = case.pdic.read_bytes()
    case.word.set("first")
    if failure == "launch-refused":
        app._start_ui_worker = lambda *_args, **_kwargs: -1
        case.fire_next_timer()
        assert case.review._filter_save_launch_failed
        app._start_ui_worker = dispatch
        expected_bytes = original_bytes
    else:
        case.fire_next_timer()
        case.post_write_errors.append(OSError("synthetic post-publication failure"))
        with pytest.raises(OSError, match="synthetic post-publication failure") as error:
            case.dispatches[0][0]()
        case.failures[0](error.value, "synthetic error details")
        expected_bytes = _pdic_bytes("first")

    assert case.pdic.read_bytes() == expected_bytes
    assert case.review._filter_save_uncertain_pages == {0}
    attempt_count = len(case.dispatches)
    assert _run_shared_autosave(case) == ["PPP", "rearm"]
    assert len(case.dispatches) == attempt_count
    assert case.review._filter_pending_changes[0][(3, 4)]["new_word"] == "first"
    assert case.word.get() == "first" and case.target["original_word"] == "before"
    assert case.pdic.read_bytes() == expected_bytes
    assert case.review._filter_save_uncertain_pages == {0}
    assert "未确认" in case.status.get()

    if failure == "launch-refused":
        # After checking that the refused launch did not write, a deliberate
        # save uses the existing explicit entry point and settles ownership.
        assert review_page_lifecycle.save(case.review, None, redraw_main=False) is False
        assert len(case.dispatches) == attempt_count + 1
        work, complete = case.dispatches[-1]
        complete(work())
        assert case.pdic.read_bytes() == _pdic_bytes("first")
        assert not case.review._filter_save_uncertain_pages
        assert not case.review._filter_pending_changes


def test_shared_autosave_still_flushes_ordinary_pending_focused_edit(focused_save):
    case = focused_save
    case.word.set("first")
    assert _run_shared_autosave(case) == ["PPP", "rearm"]
    assert len(case.dispatches) == 1
    worker, done = case.dispatches[0]
    done(worker())
    assert case.pdic.read_bytes() == _pdic_bytes("first")
    assert not case.review._filter_pending_changes and not case.timers


@pytest.mark.parametrize("uncertain", [False, True])
def test_main_page_navigation_only_flushes_a_confirmed_pending_queue(focused_save, uncertain):
    from picture_capture.ui.review_page_sync import save_review_before_page_change

    case = focused_save
    app = case.review.parent
    app.current_page = app.project.images[0]
    app.project.images.append(app.current_page.with_name("002.bmp"))
    app.review_window = case.review
    case.review.save = lambda **kwargs: review_page_lifecycle.save(case.review, None, **kwargs)
    dispatch = app._start_ui_worker
    initial_bytes = case.pdic.read_bytes()
    case.word.set("first")
    if uncertain:
        app._start_ui_worker = lambda *_args, **_kwargs: -1
        case.fire_next_timer()
        app._start_ui_worker = dispatch
        assert case.review._filter_save_uncertain_pages == {0}

    assert save_review_before_page_change(app, 1) is None
    assert len(case.dispatches) == (0 if uncertain else 1)
    assert case.pdic.read_bytes() == initial_bytes
    assert app.current_page == app.project.images[0]
    if uncertain:
        assert case.review._filter_pending_changes[0][(3, 4)]["new_word"] == "first"
        assert case.word.get() == "first"
        assert "核对" in case.status.get()
