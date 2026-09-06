# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

"""tempfile.py —— TortoiseMerge 的 CTempFiles（临时文件单例）。

翻译 TempFile.h：临时文件/目录创建，_remove_at_end 语义（退出时删除）。
"""

from __future__ import annotations

import os
import tempfile
import weakref
from typing import Dict, Optional


class _TempEntry:
    def __init__(self, path: str, remove_at_end: bool):
        self.path = path
        self.remove_at_end = remove_at_end

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def remove(self):
        if self.remove_at_end:
            try:
                if os.path.isdir(self.path):
                    import shutil
                    shutil.rmtree(self.path, ignore_errors=True)
                else:
                    os.remove(self.path)
            except OSError:
                pass


class TempFiles:
    """临时文件单例。"""

    _instance = None

    def __init__(self):
        self._entries: Dict[str, _TempEntry] = {}
        self._counter = 0

    @classmethod
    def instance(cls) -> "TempFiles":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_temp_file_path(self, remove_at_end: bool = True,
                           path: str = "") -> str:
        """返回临时文件路径（可带与 path 相同的扩展名）。"""
        self._counter += 1
        suffix = os.path.splitext(path)[1] if path else ".tmp"
        fd, name = tempfile.mkstemp(prefix="ptg-", suffix=suffix)
        os.close(fd)
        self._entries[name] = _TempEntry(name, remove_at_end)
        return name

    def get_temp_file_path_string(self) -> str:
        return self.get_temp_file_path()

    def get_temp_dir_path(self, remove_at_end: bool = True) -> str:
        self._counter += 1
        name = tempfile.mkdtemp(prefix="ptg-")
        self._entries[name] = _TempEntry(name, remove_at_end)
        return name

    def cleanup(self):
        for e in list(self._entries.values()):
            e.remove()
        self._entries.clear()

    def clear_all(self):
        self.cleanup()

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass