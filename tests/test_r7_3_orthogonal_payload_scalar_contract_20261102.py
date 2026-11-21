"""R7.3 RED-first tests for strict persisted orthogonal replay scalars."""
from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from picture_capture.preprocess.coordinate_mapping import (
    CoordinateMappingUnavailable,
    PreprocessCoordinateMap,
)
from picture_capture.preprocess.models import PreprocessAnalysis
from picture_capture.preprocess.persistence import load_analysis, result_path, save_analysis
from picture_capture.preprocess.pipeline import geometry_corrected_image, save_processed_page
from picture_capture.ui.preprocess_workflow import _preprocess_analysis_for_export


def _payload(**overrides):
    payload = {
        "row_gain": 0.7,
        "reference_x": 50.0,
        "y_knots": [0.0, 50.0, 100.0],
        "angle_knots_deg": [],
        "x_knots": [0.0, 50.0, 100.0],
        "row_grid_rows": 3,
        "row_grid_cols": 3,
        "row_angle_grid_deg": [0.1] * 9,
        "row_displacement_grid_px": [],
        "separator_y_knots": [],
        "separator_shift_knots_px": [],
    }
    payload.update(overrides)
    return payload


def _analysis(payload) -> PreprocessAnalysis:
    return PreprocessAnalysis(
        source_width=100,
        source_height=100,
        correction_angle_deg=0.0,
        applied_angle_deg=0.0,
        crop_box=(0, 0, 100, 100),
        raw_content_box=(0, 0, 100, 100),
        text_box=(0, 0, 100, 100),
        source_boxes=0,
        angle_samples=0,
        angle_mad_deg=0.0,
        retained_ratio=1.0,
        confidence=1.0,
        status="synthetic",
        method="r7_3_orthogonal_payload_scalar_contract",
        geometry_mode="perspective",
        perspective_matrix=None,
        orthogonal_applied=True,
        orthogonal_steps=(payload,),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("row_grid_rows", 3.5),
        ("row_grid_cols", 3.5),
        ("row_grid_rows", "3"),
        ("row_grid_cols", "3"),
        ("row_grid_rows", True),
        ("row_grid_cols", True),
    ),
)
def test_orthogonal_replay_rejects_noninteger_grid_dimensions(field, value):
    with pytest.raises(CoordinateMappingUnavailable, match="orthogonal"):
        PreprocessCoordinateMap(_analysis(_payload(**{field: value})))


@pytest.mark.parametrize("row_gain", (True, False))
def test_orthogonal_replay_rejects_boolean_row_gain(row_gain):
    with pytest.raises(CoordinateMappingUnavailable, match="orthogonal"):
        PreprocessCoordinateMap(_analysis(_payload(row_gain=row_gain)))


def test_orthogonal_replay_keeps_legacy_missing_row_gain_default():
    payload = _payload()
    payload.pop("row_gain")
    mapping = PreprocessCoordinateMap(_analysis(payload))
    assert mapping.approximate is True
    assert mapping.source_to_output_point((40.0, 40.0)).status == "mapped"


def _legacy_analysis():
    analysis = _analysis(_payload())
    analysis.orthogonal_steps = ()
    analysis.orthogonal_y_knots = (0.0, 100.0)
    analysis.orthogonal_x_knots = (0.0, 100.0)
    analysis.orthogonal_angle_knots_deg = (0.1, 0.2)
    analysis.orthogonal_row_grid_rows = 2
    analysis.orthogonal_row_grid_cols = 2
    analysis.orthogonal_row_angle_grid_deg = (0.1, 0.2, 0.3, 0.4)
    analysis.orthogonal_reference_x = 50.0
    return analysis


@pytest.mark.parametrize(("field", "value"), [
    ("orthogonal_row_grid_rows", 2.9),
    ("orthogonal_row_grid_cols", "2"),
    ("orthogonal_row_gain", True),
    ("orthogonal_row_gain", False),
])
def test_legacy_orthogonal_metadata_does_not_coerce_invalid_scalars(field, value):
    analysis = _legacy_analysis()
    setattr(analysis, field, value)
    with pytest.raises(CoordinateMappingUnavailable, match="orthogonal"):
        PreprocessCoordinateMap(analysis)


@pytest.mark.parametrize("steps", [True, {}])
def test_malformed_step_container_cannot_use_valid_legacy_fallback(steps):
    analysis = _legacy_analysis()
    analysis.orthogonal_steps = steps
    with pytest.raises(CoordinateMappingUnavailable, match="orthogonal"):
        PreprocessCoordinateMap(analysis)


def test_legacy_zero_gain_keeps_source_pixels_stationary():
    analysis = _legacy_analysis()
    analysis.orthogonal_row_gain = 0.0
    mapping = PreprocessCoordinateMap(analysis)
    result = mapping.source_to_output_point((40.0, 45.0))
    assert result.status == "mapped"
    assert result.point == pytest.approx((40.0, 45.0))


def test_list_of_modern_steps_matches_tuple_for_json_style_metadata():
    payload = _payload()
    analysis = _analysis(payload)
    expected = PreprocessCoordinateMap(analysis).source_to_output_point((40.0, 45.0))
    analysis.orthogonal_steps = [payload]
    assert PreprocessCoordinateMap(analysis).source_to_output_point((40.0, 45.0)) == expected


@pytest.mark.parametrize(("field", "value"), [
    ("orthogonal_applied", "false"),
    ("orthogonal_steps", {}),
    ("orthogonal_steps", [_payload(), None]),
    ("orthogonal_steps", [_payload(y_knots="123")]),
    ("orthogonal_steps", [_payload(row_gain=float("nan"))]),
    ("orthogonal_steps", [_payload(row_grid_cols=2.9)]),
    ("orthogonal_steps", [_payload(row_angle_grid_deg=[], row_displacement_grid_px=[])]),
    ("orthogonal_passes", 2),
    ("source_width", float("inf")),
])
def test_saved_analysis_rejects_unreplayable_cache_without_rewriting_it(tmp_path, field, value):
    page = tmp_path / "synthetic.png"
    payload = _analysis(_payload()).to_dict()
    payload[field] = value
    path = result_path(tmp_path, page)
    saved = json.dumps(payload).encode("utf-8")
    path.write_bytes(saved)

    assert load_analysis(tmp_path, page) is None
    assert path.read_bytes() == saved


@pytest.mark.parametrize(("field", "value"), [
    ("orthogonal_row_grid_rows", 2.9),
    ("orthogonal_row_grid_cols", "2"),
    ("orthogonal_row_gain", True),
    ("orthogonal_reference_x", float("inf")),
    ("orthogonal_passes", 2),
])
def test_saved_legacy_cache_rejects_invalid_geometry_instead_of_coercing(tmp_path, field, value):
    page = tmp_path / "synthetic.png"
    payload = _legacy_analysis().to_dict()
    payload[field] = value
    result_path(tmp_path, page).write_text(json.dumps(payload), encoding="utf-8")
    assert load_analysis(tmp_path, page) is None


def test_invalid_second_stage_leaves_original_and_existing_export_untouched(tmp_path):
    analysis = _analysis(_payload())
    analysis.orthogonal_steps += ({"row_gain": 1.0},)
    with Image.new("RGB", (100, 100), "white") as source:
        page = tmp_path / "synthetic.png"
        source.save(page)
        with pytest.raises(ValueError, match="orthogonal"):
            geometry_corrected_image(source, analysis)
    destination = tmp_path / "processed" / page.name
    destination.parent.mkdir()
    before = page.read_bytes()
    destination.write_bytes(before)
    with pytest.raises(ValueError, match="orthogonal"):
        save_processed_page(page, analysis, destination)
    assert page.read_bytes() == destination.read_bytes() == before
    with pytest.raises(CoordinateMappingUnavailable, match="orthogonal"):
        PreprocessCoordinateMap(analysis)


def test_export_reanalyzes_broken_cache_and_replays_two_valid_passes_after_reopen(tmp_path):
    page = tmp_path / "synthetic.png"
    with Image.new("RGB", (100, 100), "white") as source:
        ImageDraw.Draw(source).rectangle((40, 40, 49, 49), fill="black")
        source.save(page)
    steps = tuple(
        {"separator_y_knots": [0.0, 100.0], "separator_shift_knots_px": [shift, shift]}
        for shift in (2.0, 3.0)
    )
    fresh = replace(_analysis(steps[0]), orthogonal_steps=steps, orthogonal_passes=2)
    invalid = fresh.to_dict()
    invalid["orthogonal_steps"] = [steps[0], None]
    cache = result_path(tmp_path, page)
    cache.write_text(json.dumps(invalid), encoding="utf-8")
    analyses = []
    deps = SimpleNamespace(
        preprocess_analysis_is_current=lambda *_args, **_kwargs: True,
        load_preprocess_analysis=load_analysis,
        load_manual_perspective_quad=lambda *_args: None,
        analyze_preprocess_path=lambda page, *_args, **_kwargs: analyses.append(page) or fresh,
        save_preprocess_analysis=save_analysis,
    )
    project = SimpleNamespace(root=tmp_path)
    recovered = _preprocess_analysis_for_export(None, deps, project, page, object(), 20, True, "auto")
    assert analyses == [page]
    assert recovered is fresh

    reopened = load_analysis(tmp_path, page)
    assert reopened is not None and reopened.orthogonal_steps == steps
    mapped = PreprocessCoordinateMap(reopened).source_to_output_point((40.0, 45.0))
    assert mapped.point == pytest.approx((35.0, 45.0))
    destination = save_processed_page(page, reopened, tmp_path / "processed" / page.name)
    with Image.open(destination) as result:
        assert result.getpixel((35, 45)) == (0, 0, 0)
        assert result.getpixel((34, 45)) == (255, 255, 255)
