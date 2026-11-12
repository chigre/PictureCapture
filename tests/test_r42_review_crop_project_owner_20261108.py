"""R4.2 synthetic project-owner witness for asynchronous ReviewWindow crops.

No real images, dictionary, Tk root, OCR or persistent data are used.
"""
from types import SimpleNamespace

from test_r42_review_crop_geometry_epoch_20261107 import _launch


def test_old_project_crop_success_cannot_publish_after_project_switch():
    review, _width, rendered, retried, deliver = _launch()
    original_project = review.parent.project
    # Same page/index, same Entry objects and unchanged geometry: the project
    # object alone changes while an old worker callback is in flight.
    review.parent.project = SimpleNamespace(
        root=original_project.root,
        images=list(original_project.images),
    )
    deliver()
    assert not rendered, "old project's successful crop painted into replacement project"


def test_unchanged_project_crop_success_still_publishes():
    review, _width, rendered, retried, deliver = _launch()
    original_project = review.parent.project
    deliver()
    assert review.parent.project is original_project
    assert len(rendered) == 1
    assert not retried
