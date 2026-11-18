"""Strict source-sized integer bounds shared by saved analysis and rendering."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from operator import index as integer_index

import numpy as np


def validated_raster_size(value: Sequence[int], name: str) -> tuple[int, int]:
    """Return a strict positive integer (width, height) snapshot."""
    try:
        if isinstance(value, (str, bytes, Mapping)) or len(value) != 2:
            raise ValueError
        items = tuple(value)
        if any(isinstance(item, (bool, np.bool_)) for item in items):
            raise ValueError
        dimensions = tuple(integer_index(item) for item in items)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"{name} must contain exactly two positive integer dimensions"
        ) from exc
    if any(dimension <= 0 for dimension in dimensions):
        raise ValueError(
            f"{name} must contain exactly two positive integer dimensions"
        )
    return int(dimensions[0]), int(dimensions[1])


def validated_raster_box(
    value: Sequence[int], name: str,
) -> tuple[int, int, int, int]:
    """Return a strict integer half-open box without lossy int() coercion."""
    try:
        if isinstance(value, (str, bytes, Mapping)) or len(value) != 4:
            raise ValueError
        items = tuple(value)
        if any(isinstance(item, (bool, np.bool_)) for item in items):
            raise ValueError
        coordinates = tuple(integer_index(item) for item in items)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"{name} must contain exactly four integer half-open coordinates"
        ) from exc
    return tuple(int(item) for item in coordinates)


def validated_crop_box(
    value: Sequence[int], image_size: tuple[int, int] | None = None,
) -> tuple[int, int, int, int]:
    box = validated_raster_box(value, "crop_box")
    x0, y0, x1, y1 = box
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
        raise ValueError("crop_box is not valid in the transformed image frame")
    if image_size is not None and (x1 > image_size[0] or y1 > image_size[1]):
        raise ValueError("crop_box is not valid in the transformed image frame")
    return box
