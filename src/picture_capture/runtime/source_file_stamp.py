"""Filesystem identity and change time for an open source-image handle."""
from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO


def source_file_stamp(stream: BinaryIO) -> tuple[int, ...]:
    stat = os.fstat(stream.fileno())
    change_time = stat.st_ctime_ns
    if os.name == "nt":
        # Python st_ctime is creation time on Windows. Query the same handle
        # for change time, including updates that restore the write time.
        import ctypes
        import msvcrt
        from ctypes import wintypes

        class FileBasicInfo(ctypes.Structure):
            _fields_ = [
                ("creation_time", ctypes.c_int64),
                ("access_time", ctypes.c_int64),
                ("write_time", ctypes.c_int64),
                ("change_time", ctypes.c_int64),
                ("attributes", wintypes.DWORD),
            ]

        info = FileBasicInfo()
        query = ctypes.windll.kernel32.GetFileInformationByHandleEx
        if not query(
            wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno())),
            0,  # FileBasicInfo
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            raise ctypes.WinError()
        change_time = info.change_time
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, change_time


def source_file_digest(path: Path, *, stamp=source_file_stamp) -> tuple[tuple[int, ...], bytes]:
    """Stream the complete source and reject metadata changes during the read."""
    with path.open("rb") as stream:
        return source_stream_digest(stream, stamp=stamp)


def source_stream_digest(stream: BinaryIO, *, stamp=source_file_stamp) -> tuple[tuple[int, ...], bytes]:
    """Hash the same open file a caller will decode, then rewind it."""
    stream.seek(0)
    before = stamp(stream)
    digest = sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    if stamp(stream) != before:
        raise OSError("源图已变化，请重新加载页面后重试")
    stream.seek(0)
    return before, digest.digest()
