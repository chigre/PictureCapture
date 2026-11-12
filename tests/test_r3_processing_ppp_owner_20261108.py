"""R3 synthetic regression: processing owner must not be acknowledged by PPP save."""
from types import SimpleNamespace

from picture_capture.ui import main_pdic_persistence, review_page_lifecycle


class _Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


def test_processing_review_unsaved_text_not_masked_by_ppp_success():
    statuses = []
    entry = SimpleNamespace(word="persisted")
    page = SimpleNamespace(stem="synthetic")
    parent = SimpleNamespace(
        project=object(), current_page=page, current_index=0,
        entries=[entry], status_var=SimpleNamespace(set=statuses.append),
        _foreground_batch_state=lambda _index: "processing",
    )
    review = SimpleNamespace(
        parent=parent, _filter_rows_active=False,
        _rendered_page_stem="synthetic",
        vars=[_Var("typed but not committed")],
        _simplified_dirty_pages=set(),
        _bound_row_entries=lambda: [entry],
        winfo_exists=lambda: True,
    )
    review.autosave_commit = lambda: review_page_lifecycle.autosave_commit(review, None)
    rearms = []
    app = SimpleNamespace(
        autosave_job="previous", autosave_var=SimpleNamespace(get=lambda: True),
        _batch_active=False, project=object(), current_page=page,
        review_window=review, status_var=SimpleNamespace(set=statuses.append),
        _last_pdic_write_changed=False,
        _save_normalized_ppp=lambda: True,
        save_pdic=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("stale main write")),
        toggle_autosave=lambda: rearms.append(True),
    )
    main_pdic_persistence.autosave_tick(
        app, deps={"tk": SimpleNamespace(TclError=RuntimeError)}
    )
    assert rearms == [True]
    assert review.vars[0].get() == "typed but not committed"
    assert entry.word == "persisted"
    assert getattr(review, "_r3_autosave_unconfirmed", False) is True
    assert statuses and "未保存" in statuses[-1]
    assert "已自动保存" not in statuses[-1] or "但" in statuses[-1]
