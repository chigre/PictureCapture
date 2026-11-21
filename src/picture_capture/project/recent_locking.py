"""Serialize writes to the registry of recent projects."""
from __future__ import annotations

from pathlib import Path
from typing import ContextManager

from ..persistence.file_lock import exclusive_file_lock


def recent_registry_lock(path: Path, *, timeout: float = 15.0) -> ContextManager[None]:
    path = Path(path)
    return exclusive_file_lock(
        path.with_name(path.name + ".lock"),
        busy_message="最近项目记录被其他进程占用",
        timeout=timeout,
    )
