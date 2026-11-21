"""Project crop publication and its historical compatibility entry points."""
from __future__ import annotations

import os as os  # Compatibility hook used by crop publication callers.
from pathlib import Path

from ..persistence.file_publication import (
    _publish_temp_path as _publish_temp_path,
    _write_journal as _write_journal,
    journal_path,
    publish_file_transaction,
    recover_journal as _recover_journal,
)


def _journal_path(parent: Path, token: str, state: str = "pending") -> Path:
    return journal_path(parent, token, state, namespace="crop")


def recover_incomplete_crop_publications(project_root: Path) -> int:
    """Recover interrupted page exports when a project is opened, before jobs start.

    Scans only the QT root and its immediate output directories, not every PNG.
    No recovery runs during a live parallel batch; other pages may be publishing.
    """
    from ..persistence.project_storage import qt_root

    root = qt_root(Path(project_root))
    if not root.is_dir():
        return 0
    directories = [root, *(p for p in root.iterdir() if p.is_dir())]
    recovered = 0
    for folder in directories:
        for journal in sorted(folder.glob(".crop-publish-*.pending.json")) + sorted(
            folder.glob(".crop-publish-*.committed.json")
        ):
            _recover_journal(journal, allowed_root=root)
            recovered += 1
    return recovered


def _publish_file_transaction(
    replacements: list[tuple[Path, Path]], *, stale_paths: list[Path] | None = None,
) -> None:
    """Publish a crop page and its manifests, then clean up the previous set."""
    publish_file_transaction(
        replacements,
        namespace="crop",
        rollback_failure="切图发布失败，且回滚旧文件时发生错误；已保留隐藏 .bak 恢复副本。",
        stale_paths=stale_paths,
    )
