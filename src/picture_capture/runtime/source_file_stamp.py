"""Filesystem identity and change time for an open source-image handle."""
from __future__ import annotations

import os
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
