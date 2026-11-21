from __future__ import annotations

"""Crash-recoverable publication of related output files.

A journal is written before any existing output is moved aside. A committed
marker separates rollback from cleanup so an interrupted publish is recoverable
without guessing which of several output files is authoritative.
"""

import json
import os
from pathlib import Path
import uuid


def _publish_temp_path(target: Path) -> Path:
    """Return a same-filesystem temporary path for one eventual atomic publish."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")


def journal_path(parent: Path, token: str, state: str = "pending", *, namespace: str) -> Path:
    return parent / f".{namespace}-publish-{token}.{state}.json"


def _write_journal(path: Path, payload: dict) -> None:
    temp = _publish_temp_path(path)
    try:
        with temp.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def recover_journal(journal: Path, *, allowed_root: Path | None = None) -> None:
    journal = Path(journal)
    # A journal and the paths it names must stay inside the recovery boundary.
    if allowed_root is not None:
        boundary = Path(allowed_root).resolve()
        if not journal.resolve().is_relative_to(boundary):
            raise ValueError(f"Publication journal is outside its project: {journal}")
    payload = json.loads(journal.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError(f"Unsupported publication transaction: {journal}")
    originals = [(Path(item["target"]), Path(item["backup"]), bool(item["existed"]))
                 for item in payload["originals"]]
    staged = [Path(path) for path in payload["staged"]]
    paths = [path for pair in originals for path in pair[:2]] + staged
    if allowed_root is not None:
        boundary = allowed_root.resolve()
        if any(not path.resolve().is_relative_to(boundary) for path in paths):
            raise ValueError(f"Publication journal refers outside its project: {journal}")
    if ".committed." not in journal.name:
        # Roll back a transaction that never received the durable commit marker.
        for target, backup, existed in reversed(originals):
            if backup.exists():
                os.replace(backup, target)
            elif not existed:
                target.unlink(missing_ok=True)
    else:
        # The full new set was published. Keep it and discard its backups.
        for _target, backup, _existed in originals:
            backup.unlink(missing_ok=True)
    for temp in staged:
        temp.unlink(missing_ok=True)
    journal.unlink(missing_ok=True)


def publish_file_transaction(
    replacements: list[tuple[Path, Path]],
    *,
    namespace: str,
    rollback_failure: str,
    stale_paths: list[Path] | None = None,
    journal_directory: Path | None = None,
    defer_committed_cleanup: bool = False,
) -> None:
    """Publish one page of files, rollback on errors, recover on next project open."""
    pairs = [(Path(temp), Path(target)) for temp, target in replacements]
    if not pairs:
        return
    token = uuid.uuid4().hex
    old_candidates: list[Path] = []
    seen: set[str] = set()
    for path in [*(target for _temp, target in pairs), *(stale_paths or [])]:
        key = os.fspath(path)
        if key not in seen:
            seen.add(key)
            old_candidates.append(path)

    originals = [
        (target, target.with_name(f".{target.name}.{token}.bak"), target.exists())
        for target in old_candidates
    ]
    directory = journal_directory if journal_directory is not None else pairs[0][1].parent
    journal = journal_path(directory, token, namespace=namespace)
    committed = journal_path(directory, token, "committed", namespace=namespace)
    payload = {
        "version": 1,
        "originals": [
            {"target": str(target.resolve()), "backup": str(backup.resolve()), "existed": existed}
            for target, backup, existed in originals
        ],
        "staged": [str(temp.resolve()) for temp, _target in pairs],
    }
    # Make journal paths absolute: reopening from another working directory is safe.
    journal.parent.mkdir(parents=True, exist_ok=True)
    _write_journal(journal, payload)
    try:
        for target, backup, existed in originals:
            if existed:
                os.replace(target, backup)
        for temp, target in pairs:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp, target)
        os.replace(journal, committed)
    except Exception:
        # Preserve the journal and backups for the next recovery if rollback fails.
        try:
            recover_journal(journal)
        except Exception as restore_exc:
            raise RuntimeError(rollback_failure) from restore_exc
        raise
    finally:
        if committed.exists():
            # Failed backup cleanup must leave the committed journal for recovery.
            try:
                recover_journal(committed)
            except OSError:
                if not defer_committed_cleanup:
                    raise
