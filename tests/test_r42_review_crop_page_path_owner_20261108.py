"""R4.2 synthetic same-stem page replacement crop callback ownership.

No real scans, OCR, Tk root, persistent project data, or dictionary used.
"""
from pathlib import Path

from test_r42_review_crop_geometry_epoch_20261107 import _launch


def test_same_stem_different_page_path_rejects_old_crop_success():
    review, _width, rendered, retried, deliver = _launch()
    original = review.parent.current_page
    # Preserve project, page index, Entry identity, visible text and geometry.
    # Only the actual source page changes to a distinct path with same stem.
    review.parent.current_page = Path("/synthetic/replacement/page.png")
    assert review.parent.current_page != original
    assert review.parent.current_page.stem == original.stem
    deliver()
    assert not rendered, "crop from another page path was painted over current page"


def test_unchanged_exact_page_path_accepts_crop_success():
    review, _width, rendered, retried, deliver = _launch()
    original = review.parent.current_page
    deliver()
    assert review.parent.current_page == original
    assert len(rendered) == 1
    assert not retried
