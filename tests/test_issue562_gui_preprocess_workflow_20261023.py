"""#562 preprocessing GUI workflow physical owner and compatibility checks."""
from __future__ import annotations

import csv
from dataclasses import fields
import json
import os
from pathlib import Path
import inspect
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from picture_capture import app as app_module
from picture_capture.models import ProjectState
from picture_capture.preprocess.reporting import export_summary_csv
from picture_capture.ui import preprocess_workflow as owner


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_preprocess_ui_owner_import_is_independent_of_app_tk_and_paddle():
    subprocess.run([sys.executable, "-c", """
import sys
from picture_capture.ui.preprocess_workflow import PreprocessUiDeps
assert 'picture_capture.app' not in sys.modules
assert 'picture_capture.paddle_headwords_core' not in sys.modules
assert 'paddle' not in sys.modules
"""], check=True)


def test_exact_24_instance_and_static_preprocess_methods_still_on_app():
    names = [
        "_preprocess_mode_active", "_preprocess_config",
        "_preprocess_export_config", "_preprocess_export_settings_changed",
        "_preprocess_settings_changed", "_set_workspace_preprocess_locked",
        "_preprocess_blocking_window_name", "toggle_preprocess_mode",
        "_set_preprocess_mode", "_default_preprocess_corner_quad",
        "edit_preprocess_corners", "reset_preprocess_corners",
        "_preprocess_result_for_page", "_set_current_preprocess_status",
        "analyze_preprocess_current", "analyze_preprocess_selected",
        "show_preprocess_diagnostics", "promote_preprocessed_working_images",
        "jump_preprocess_review", "_preprocess_analysis_for_export",
        "export_preprocess_previews", "export_preprocess_images",
        "_get_preprocess_display_photo", "_redraw_preprocess_preview",
    ]
    for name in names:
        assert name in app_module.PictureCaptureApp.__dict__
        assert hasattr(owner, name)
    assert isinstance(
        app_module.PictureCaptureApp.__dict__["_default_preprocess_corner_quad"],
        staticmethod,
    )
    assert list(inspect.signature(
        app_module.PictureCaptureApp.analyze_preprocess_current
    ).parameters) == ["self", "silent"]
    assert list(inspect.signature(
        app_module.PictureCaptureApp._set_preprocess_mode
    ).parameters) == ["self", "active", "analyze"]
    assert list(inspect.signature(
        app_module.PictureCaptureApp._preprocess_analysis_for_export
    ).parameters) == [
        "self", "project", "page", "settings", "safety",
        "auto_deskew", "geometry_mode",
    ]


def test_preprocess_gui_globals_resolve_original_live_patch_points(monkeypatch):
    names = {f.name for f in fields(owner.PreprocessUiDeps)}
    assert len(names) == 43
    assert {
        "analyze_preprocess_path", "load_preprocess_analysis",
        "save_preprocess_analysis", "save_processed_page",
        "promote_processed_pages", "save_manual_perspective_quad",
        "load_manual_perspective_quad", "geometry_corrected_image",
        "preprocess_result_summary", "overlay_excluded_regions",
        "messagebox", "tk", "ttk", "ImageTk", "AUTO_FONT_FAMILY",
    } <= names
    func = lambda *args: None
    monkeypatch.setattr(app_module, "analyze_preprocess_path", func)
    deps = app_module._preprocess_ui_deps()
    assert deps.analyze_preprocess_path is func
    assert deps.messagebox is app_module.messagebox


def test_preprocess_mode_gate_and_config_use_original_widget_variables():
    app = SimpleNamespace(
        preprocess_mode_var=Var(True),
        preprocess_safety_var=Var("28"),
        preprocess_geometry_var=Var("自动透视"),
        preprocess_auto_deskew_var=Var(False),
        settings=SimpleNamespace(preprocess_safety_margin_px=20),
    )
    assert app_module.PictureCaptureApp._preprocess_mode_active(app) is True
    assert app_module.PictureCaptureApp._preprocess_config(app) == (
        28, False, "perspective"
    )
    app.preprocess_safety_var = Var("bad")
    assert app_module.PictureCaptureApp._preprocess_config(app)[0] == 20
    app.preprocess_mode_var = Var(False)
    assert not app_module.PictureCaptureApp._preprocess_mode_active(app)


def test_original_static_corner_quad_stays_bounded_by_image():
    image = Image.new("RGB", (400, 300), "white")
    try:
        points = app_module.PictureCaptureApp._default_preprocess_corner_quad(image)
        assert len(points) == 8
        assert points[0] >= 0 and points[1] >= 0
        assert points[2] < 400 and points[5] < 300
        assert points[0] < points[2] and points[1] < points[5]
    finally:
        image.close()


def test_instance_adapter_forwards_original_gui_self_and_user_event(monkeypatch):
    captured = {}
    sentinel = object()
    def spy(instance, deps, event=None):
        captured.update(instance=instance, deps=deps, event=event)
        return sentinel
    monkeypatch.setattr(owner, "_preprocess_settings_changed", spy)
    app = object()
    event = object()
    result = app_module.PictureCaptureApp._preprocess_settings_changed(app, event)
    assert result is sentinel
    assert captured["instance"] is app and captured["event"] is event
    assert captured["deps"].save_processed_page is app_module.save_processed_page


def test_export_preprocess_callback_returns_leaf_result(monkeypatch):
    value = object()
    monkeypatch.setattr(owner, "export_preprocess_images", lambda instance, deps: value)
    assert app_module.PictureCaptureApp.export_preprocess_images(object()) is value


def _solid_page(path, color):
    with Image.new("RGB", (80, 120), color) as image:
        image.save(path)


def _pixel(path):
    with Image.open(path) as image:
        return image.getpixel((30, 40))


def _processed_outputs(project, page):
    image = app_module.preprocess_processed_output_root(project.root) / page.name
    diagnostic = app_module.preprocess_metadata_output_root(project.root) / f"{page.stem}.preprocess.json"
    return image, diagnostic


def _export_view(project, selected=None):
    tasks = []
    idle = []
    view = SimpleNamespace(
        project=project, settings=project.settings, status_var=Var(""),
        _preprocess_results={}, _ui_worker_key_active=lambda *_: False,
        selected_page_indices=lambda: list(range(len(project.images))) if selected is None else selected,
        _preprocess_config=lambda: (20, True, "auto"),
        _preprocess_export_config=lambda: (False, "batch_max", 0, 0, 0, 0, 0, 0, "center", "center"),
        after_idle=idle.append,
        _start_batch_task=lambda _title, items, worker, *, on_done, **_kwargs: tasks.append(
            (items, worker, on_done)
        ),
    )
    view._preprocess_analysis_for_export = lambda *args: (
        app_module.PictureCaptureApp._preprocess_analysis_for_export(view, *args)
    )

    def run_batch():
        items, worker, on_done = tasks.pop(0)
        results = []
        for position, item in enumerate(items, 1):
            try:
                results.append(worker(item, position, len(items)))
            except OSError as exc:
                on_done(len(results), len(items), True, results, (exc, ""))
                return exc
        on_done(len(results), len(items), False, results, None)
        return None

    return view, run_batch, idle, tasks


@pytest.mark.parametrize("failure", ["stage", "publish"])
def test_batch_keeps_previous_pair_for_failed_page_and_summarizes_completed_pages(
    tmp_path, monkeypatch, failure,
):
    pages = [tmp_path / "001.bmp", tmp_path / "002.bmp"]
    for page in pages:
        _solid_page(page, "blue")
    project = ProjectState.open(tmp_path)
    image, diagnostic = _processed_outputs(project, pages[1])
    _solid_page(image, "red")
    diagnostic.write_text('{"previous": true}', encoding="utf-8")
    previous = image.read_bytes(), diagnostic.read_bytes()
    view, run_batch, idle, tasks = _export_view(project)

    def start_export():
        app_module.PictureCaptureApp.export_preprocess_images(view)
        assert run_batch() is None
        idle.pop(0)()
        assert len(tasks) == 1

    with monkeypatch.context() as patch:
        if failure == "stage":
            real_diagnostic = app_module.export_diagnostic_json

            def fail_second_report(page, *args, **kwargs):
                if page == pages[1]:
                    raise PermissionError("diagnostic write failed")
                return real_diagnostic(page, *args, **kwargs)

            patch.setattr(app_module, "export_diagnostic_json", fail_second_report)
        else:
            real_replace = os.replace

            def fail_second_publication(source, destination):
                if Path(destination) == diagnostic and Path(source).name.startswith(".preprocess-report-"):
                    raise PermissionError("diagnostic publication failed")
                return real_replace(source, destination)

            patch.setattr(os, "replace", fail_second_publication)

        start_export()
        assert isinstance(run_batch(), PermissionError)

    first_image, first_diagnostic = _processed_outputs(project, pages[0])
    assert _pixel(first_image) == (0, 0, 255)
    assert json.loads(first_diagnostic.read_text(encoding="utf-8"))["export"]["output_filename"] == "001.bmp"
    assert (image.read_bytes(), diagnostic.read_bytes()) == previous
    summary = image.parent.parent / "preprocess_summary.csv"
    assert "已写入 1 页的汇总" in view.status_var.get()
    with summary.open(encoding="utf-8-sig", newline="") as stream:
        assert [row["page"] for row in csv.DictReader(stream)] == ["001.bmp"]
    assert not list(summary.parent.rglob(".preprocess-image-*"))
    assert not list(summary.parent.rglob(".preprocess-report-*"))
    assert not list(summary.parent.rglob("*.bak"))

    start_export()
    assert run_batch() is None
    assert _pixel(image) == (0, 0, 255)
    assert json.loads(diagnostic.read_text(encoding="utf-8"))["export"]["output_filename"] == "002.bmp"
    with summary.open(encoding="utf-8-sig", newline="") as stream:
        assert [row["page"] for row in csv.DictReader(stream)] == ["001.bmp", "002.bmp"]


@pytest.mark.parametrize(("legacy", "point"), [(True, "pending"), (False, "pending"), (False, "committed")])
def test_project_open_recovers_an_interrupted_preprocess_pair(tmp_path, legacy, point):
    page = tmp_path / "001.bmp"
    _solid_page(page, "blue")
    if legacy:
        (tmp_path / "QT").mkdir()
    project = ProjectState.open(tmp_path)
    image, diagnostic = _processed_outputs(project, page)
    _solid_page(image, "red")
    diagnostic.write_text('{"previous": true}', encoding="utf-8")

    completed = subprocess.run([sys.executable, "-c", """
from pathlib import Path
import os
import sys
from picture_capture.models import ProjectState
from picture_capture.preprocess import pipeline
from picture_capture.preprocess.storage import publish_processed_page

page, image, diagnostic = map(Path, sys.argv[1:4])
point = sys.argv[4]
project = ProjectState.open(page.parent)
analysis = pipeline.analyze_preprocess_path(page, project.settings)
canvas = pipeline.output_canvas_info(analysis, enabled=False)
real_replace = os.replace

def interrupt(source, destination):
    real_replace(source, destination)
    if point == "pending" and Path(destination) == image:
        os._exit(79)
    if point == "committed" and Path(destination).name.endswith(".committed.json"):
        os._exit(79)

os.replace = interrupt
publish_processed_page(
    project.root, page, analysis, image, diagnostic, canvas=canvas,
    settings=project.settings, save_image=pipeline.save_processed_page,
    save_diagnostic=pipeline.export_diagnostic_json,
)
""", str(page), str(image), str(diagnostic), point], capture_output=True, text=True)
    assert completed.returncode == 79, completed.stderr
    root = image.parent.parent
    assert list(root.rglob(f".preprocess-publish-*.{point}.json"))
    assert _pixel(image) == (0, 0, 255)
    ProjectState.open(tmp_path)

    if point == "pending":
        assert _pixel(image) == (255, 0, 0)
        assert json.loads(diagnostic.read_text(encoding="utf-8")) == {"previous": True}
    else:
        assert _pixel(image) == (0, 0, 255)
        assert json.loads(diagnostic.read_text(encoding="utf-8"))["export"]["output_filename"] == "001.bmp"
    assert not list(root.rglob("*.bak"))
    assert not list(root.rglob(".preprocess-publish-*.json"))
    assert not list(root.rglob(".preprocess-report-*"))


def test_export_summary_replace_failure_preserves_prior_csv(tmp_path, monkeypatch):
    destination = tmp_path / "preprocess_summary.csv"
    destination.write_bytes(b"previous summary")
    real_replace = os.replace

    def fail_summary(source, target):
        if Path(target) == destination:
            raise PermissionError("summary is locked")
        return real_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_summary)
    with pytest.raises(PermissionError, match="summary is locked"):
        export_summary_csv([], destination)
    assert destination.read_bytes() == b"previous summary"
    assert list(tmp_path.iterdir()) == [destination]


def test_export_abandons_idle_handoff_after_project_switch(tmp_path):
    _solid_page(tmp_path / "001.bmp", "blue")
    project = ProjectState.open(tmp_path)
    view, run_batch, idle, tasks = _export_view(project)
    app_module.PictureCaptureApp.export_preprocess_images(view)
    assert run_batch() is None
    assert len(idle) == 1

    # A same-folder reopen also creates a new ProjectState owner.
    view.project = ProjectState.open(tmp_path)
    idle.pop(0)()
    assert tasks == []
    image, diagnostic = _processed_outputs(project, project.images[0])
    assert not image.exists()
    assert not diagnostic.exists()


def test_companion_exports_keep_both_same_stem_pages_across_separate_selections(tmp_path):
    first = tmp_path / "001.bmp"
    second = tmp_path / "001.png"
    _solid_page(first, "red")
    _solid_page(second, "blue")
    project = ProjectState.open(tmp_path)
    for index in range(len(project.images)):
        view, run_batch, idle, _tasks = _export_view(project, selected=[index])
        app_module.PictureCaptureApp.export_preprocess_previews(view)
        assert run_batch() is None
        app_module.PictureCaptureApp.export_preprocess_images(view)
        assert run_batch() is None
        idle.pop(0)()
        assert run_batch() is None
    meta = app_module.preprocess_metadata_output_root(project.root) / "by-source"
    previews = app_module.preprocess_preview_output_root(project.root) / "by-source"
    for page, color in ((first, (255, 0, 0)), (second, (0, 0, 255))):
        diagnostic = meta / f"{page.name}.preprocess.json"
        assert json.loads(diagnostic.read_text(encoding="utf-8"))["export"]["output_filename"] == page.name
        image = app_module.preprocess_processed_output_root(project.root) / page.name
        assert _pixel(image) == color
        preview = _pixel(previews / f"{page.name}_preview.jpg")
        assert all(abs(actual - expected) <= 3 for actual, expected in zip(preview, color))


def test_batch_rejects_source_replaced_while_diagnostic_is_staged(tmp_path, monkeypatch):
    page = tmp_path / "001.bmp"
    _solid_page(page, "blue")
    project = ProjectState.open(tmp_path)
    image, diagnostic = _processed_outputs(project, page)
    _solid_page(image, "red")
    diagnostic.write_text('{"previous": true}', encoding="utf-8")
    previous = image.read_bytes(), diagnostic.read_bytes()
    summary = image.parent.parent / "preprocess_summary.csv"
    summary.write_bytes(b"previous summary")
    replacement = tmp_path / "replacement.bmp"
    _solid_page(replacement, "green")
    metadata = page.stat()
    os.utime(replacement, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    report = app_module.export_diagnostic_json

    def replace_source_after_report(*args, **kwargs):
        result = report(*args, **kwargs)
        replacement.replace(page)
        return result

    monkeypatch.setattr(app_module, "export_diagnostic_json", replace_source_after_report)
    view, run_batch, idle, _tasks = _export_view(project)
    app_module.PictureCaptureApp.export_preprocess_images(view)
    assert run_batch() is None
    idle.pop(0)()
    assert "源图已变化" in str(run_batch())
    assert (image.read_bytes(), diagnostic.read_bytes()) == previous
    assert summary.read_bytes() == b"previous summary"


def test_committed_pair_counts_even_if_cleanup_waits_for_reopen(tmp_path, monkeypatch):
    page = tmp_path / "001.bmp"
    _solid_page(page, "blue")
    project = ProjectState.open(tmp_path)
    image, diagnostic = _processed_outputs(project, page)
    _solid_page(image, "red")
    diagnostic.write_text('{"previous": true}', encoding="utf-8")
    view, run_batch, idle, _tasks = _export_view(project)
    unlink = Path.unlink

    def fail_backup_removal(path, *args, **kwargs):
        if path.suffix == ".bak" and path.parent == image.parent:
            raise PermissionError("previous image temporarily locked")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_backup_removal)
        app_module.PictureCaptureApp.export_preprocess_images(view)
        assert run_batch() is None
        idle.pop(0)()
        assert run_batch() is None

    root = image.parent.parent
    assert list(root.rglob(".preprocess-publish-*.committed.json"))
    assert _pixel(image) == (0, 0, 255)
    assert json.loads(diagnostic.read_text(encoding="utf-8"))["export"]["output_filename"] == "001.bmp"
    with (root / "preprocess_summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert [row["page"] for row in csv.DictReader(stream)] == ["001.bmp"]
    ProjectState.open(tmp_path)
    assert _pixel(image) == (0, 0, 255)
    assert not list(root.rglob("*.bak"))
    assert not list(root.rglob(".preprocess-publish-*.json"))
