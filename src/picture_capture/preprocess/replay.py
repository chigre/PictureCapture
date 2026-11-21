"""Replay accepted preprocessing geometry through explicitly supplied operations."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable, Sequence

import numpy as np
from PIL import Image

from .orthogonal_dewarp import OrthogonalWarpEstimate
from .orthogonal_policy import (
    _orthogonal_estimate_from_step,
    _orthogonal_finite_number,
    _orthogonal_geometry_from_step,
    _orthogonal_grid_dimension,
)

if TYPE_CHECKING:
    from .models import PreprocessAnalysis


def orthogonal_step_records(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(step, dict) for step in value):
        raise ValueError("orthogonal replay steps must be a sequence of step records")
    return tuple(value)


def _validate_orthogonal_replay_estimate(
    estimate: OrthogonalWarpEstimate,
) -> None:
    """Reject applied orthogonal stages whose saved geometry cannot replay."""
    def finite(values: Sequence[float]) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    def increasing(values: Sequence[float]) -> bool:
        return all(
            float(right) > float(left)
            for left, right in zip(values, values[1:])
        )

    y_knots = estimate.y_knots
    angle_knots = estimate.angle_knots_deg
    x_knots = estimate.x_knots
    separator_y = estimate.separator_y_knots
    separator_shift = estimate.separator_shift_knots_px
    row_angles = estimate.row_angle_grid_deg
    row_displacements = estimate.row_displacement_grid_px

    if bool(separator_y) != bool(separator_shift) or (
        separator_y and len(separator_y) != len(separator_shift)
    ):
        raise ValueError(
            "orthogonal replay separator geometry is incomplete"
        )
    if separator_y and (
        not finite(separator_y)
        or not finite(separator_shift)
        or not increasing(separator_y)
    ):
        raise ValueError(
            "orthogonal replay separator geometry is invalid"
        )

    rows = _orthogonal_grid_dimension(estimate.row_grid_rows, "row_grid_rows")
    cols = _orthogonal_grid_dimension(estimate.row_grid_cols, "row_grid_cols")
    has_row_grid = bool(row_angles or row_displacements)
    if has_row_grid or rows or cols:
        if (
            not has_row_grid
            or rows < 2 or cols < 2
            or len(y_knots) != rows
            or len(x_knots) != cols
            or not finite(y_knots)
            or not finite(x_knots)
            or not increasing(y_knots)
            or not increasing(x_knots)
            or (row_angles and len(row_angles) != rows * cols)
            or (
                row_displacements
                and len(row_displacements) != rows * cols
            )
            or not finite(row_angles)
            or not finite(row_displacements)
        ):
            raise ValueError(
                "orthogonal replay row-grid geometry is invalid"
            )
        has_row_geometry = True
    else:
        if bool(y_knots) != bool(angle_knots) or (
            y_knots and len(y_knots) != len(angle_knots)
        ):
            raise ValueError(
                "orthogonal replay legacy row geometry is incomplete"
            )
        if y_knots and (
            not finite(y_knots)
            or not finite(angle_knots)
            or not increasing(y_knots)
        ):
            raise ValueError(
                "orthogonal replay legacy row geometry is invalid"
            )
        has_row_geometry = bool(y_knots and angle_knots)

    if not math.isfinite(float(estimate.reference_x)):
        raise ValueError(
            "orthogonal replay reference coordinate is not finite"
        )
    if not has_row_geometry and not separator_y:
        raise ValueError(
            "orthogonal replay geometry is missing"
        )


def orthogonal_replay_steps(
    analysis: PreprocessAnalysis, *, step_decoder: Callable = _orthogonal_estimate_from_step,
) -> tuple[tuple[OrthogonalWarpEstimate, float], ...]:
    """Validate the complete saved stage sequence before replaying any pixels."""
    if not isinstance(analysis.orthogonal_applied, (bool, np.bool_)):
        raise ValueError("orthogonal_applied flag must be boolean")
    if not analysis.orthogonal_applied:
        return ()
    records = orthogonal_step_records(analysis.orthogonal_steps)
    passes = _orthogonal_grid_dimension(analysis.orthogonal_passes, "orthogonal_passes")
    if records:
        if passes and passes != len(records):
            raise ValueError("orthogonal replay step count does not match the saved pass count")
        steps = tuple(step_decoder(dict(record)) for record in records)
    else:
        if passes > 1:
            raise ValueError("orthogonal replay steps are missing for a multi-pass analysis")
        # Older analyses keep one stage in the top-level geometry fields.
        geometry = {
            field: getattr(analysis, f"orthogonal_{field}")
            for field in (
                "y_knots", "angle_knots_deg", "x_knots", "row_grid_rows",
                "row_grid_cols", "row_angle_grid_deg", "row_displacement_grid_px",
                "separator_y_knots", "separator_shift_knots_px", "reference_x",
            )
        }
        steps = ((
            _orthogonal_geometry_from_step(geometry),
            _orthogonal_finite_number(analysis.orthogonal_row_gain, "orthogonal_row_gain"),
        ),)
    for estimate, row_gain in steps:
        _orthogonal_finite_number(row_gain, "row_gain")
        _validate_orthogonal_replay_estimate(estimate)
    return steps


def geometry_corrected_image(
    image: Image.Image,
    analysis: PreprocessAnalysis,
    *, deskewer: Callable, homography_warper: Callable,
    document_unwarper: Callable, orthogonal_warper: Callable,
    step_decoder: Callable,
) -> Image.Image:
    """Apply the saved geometric correction without cropping.

    Export/preview reuse the exact analysis transform; they do not run Paddle
    again, so a reviewed result remains deterministic.
    """
    steps = orthogonal_replay_steps(analysis, step_decoder=step_decoder)
    corrected = deskewer(image, analysis.applied_angle_deg)
    if analysis.perspective_matrix is not None:
        corrected = homography_warper(
            corrected, analysis.perspective_matrix,
        )
    if analysis.geometry_mode == "uvdoc":
        corrected = document_unwarper(corrected)
    for estimate, row_gain in steps:
        corrected = orthogonal_warper(
            corrected, estimate, row_gain=row_gain, separator_gain=1.0,
        )
    return corrected
