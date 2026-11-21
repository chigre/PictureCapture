"""Synthetic adjacent-page cache ownership when source BMP bytes change."""
import os

import pytest
from PIL import Image

from test_r42_review_prefetch_section_same_stamp_20261107 import _fixture
from picture_capture.ui import review_page_lifecycle as lifecycle


def _cached_bmp(tmp_path):
    _, review, deps = _fixture(tmp_path)
    page = tmp_path / "adjacent.bmp"
    Image.new("RGB", (12, 12), "red").save(page)
    review.parent.project.images[:] = [page]
    review._prefetched_pages[0] = {
        "project_root": str(tmp_path),
        "signature": review._page_prefetch_signature(page),
        "review_key": review._review_prefetch_key(),
        "review_crops": [Image.new("RGB", (12, 12), "red")],
    }
    return page, review, deps


@pytest.mark.parametrize("stable_metadata", [False, True])
def test_same_stamp_changed_image_bytes_reject_cached_adjacent_crop(tmp_path, monkeypatch, stable_metadata):
    if stable_metadata:
        monkeypatch.setattr(lifecycle, "source_file_stamp", lambda stream: (1, 2, 486, 3, 4))
    page, review, deps = _cached_bmp(tmp_path)
    original = page.read_bytes()
    stamp = page.stat()
    Image.new("RGB", (12, 12), "blue").save(page)
    os.utime(page, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert page.read_bytes() != original
    assert page.stat().st_size == stamp.st_size
    assert page.stat().st_mtime_ns == stamp.st_mtime_ns

    assert lifecycle._take_prefetched_page(review, deps, 0) is None


def test_unchanged_image_accepts_cached_adjacent_crop(tmp_path):
    _, review, deps = _cached_bmp(tmp_path)
    payload = lifecycle._take_prefetched_page(review, deps, 0)
    assert payload["review_crops"][0].getpixel((0, 0)) == (255, 0, 0)
