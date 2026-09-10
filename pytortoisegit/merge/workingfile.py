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

"""workingfile.py —— TortoiseMerge 的 CWorkingFile，逐行翻译 WorkingFile.h/.cpp。

封装与文件名/描述名相关的细节：InUse/Exists/CreateEmptyFile/IsReadonly/
GetWindowName 等。
"""

from __future__ import annotations

import os
from typing import Optional


class WorkingFile:
    """一个参与比较/合并的文件。"""

    def __init__(self):
        self.filename: str = ""
        self.converted_filename: str = ""
        self.descriptive_name: str = ""
        self.reflected_name: str = ""
        self._saved_mode = None
        self._saved_mtime = None

    # ---- InUse / SetOutOfUse ----
    def in_use(self) -> bool:
        return bool(self.filename)

    def set_out_of_use(self):
        self.filename = ""
        self.converted_filename = ""
        self.descriptive_name = ""
        self.reflected_name = ""
        self.clear_stored_attributes()

    # ---- 文件名 ----
    def set_file_name(self, new_filename: str):
        self.filename = new_filename

    def get_filename(self) -> str:
        return self.filename

    # ---- 描述名 / 反射名 ----
    def set_descriptive_name(self, name: str):
        self.descriptive_name = name

    def get_descriptive_name(self) -> str:
        return self.descriptive_name or self.filename

    def set_reflected_name(self, name: str):
        self.reflected_name = name

    def get_reflected_name(self) -> str:
        return self.reflected_name

    def set_converted_filename(self, name: str):
        self.converted_filename = name

    def get_converted_filename(self) -> str:
        return self.converted_filename

    # ---- 状态 ----
    def exists(self) -> bool:
        return bool(self.filename) and os.path.isfile(self.filename)

    def is_readonly(self) -> bool:
        if not self.filename:
            return False
        try:
            return not os.access(self.filename, os.W_OK)
        except OSError:
            return True

    def create_empty_file(self):
        if self.filename:
            with open(self.filename, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("")

    def get_window_name(self, mtype: int = 0) -> str:
        desc = self.get_descriptive_name()
        refl = self.get_reflected_name()
        if mtype == 0 and refl:
            return f"{desc} ({refl})"
        return desc

    # ---- 文件属性（对齐 StoreFileAttributes/HasSourceFileChanged）----
    def store_file_attributes(self):
        self._saved_mode = None
        self._saved_mtime = None
        if self.filename and os.path.isfile(self.filename):
            try:
                st = os.stat(self.filename)
                self._saved_mode = st.st_mode
                self._saved_mtime = st.st_mtime
            except OSError:
                pass

    def clear_stored_attributes(self):
        self._saved_mode = None
        self._saved_mtime = None

    def has_source_file_changed(self) -> bool:
        if not self.filename or self._saved_mtime is None:
            return False
        try:
            return os.stat(self.filename).st_mtime != self._saved_mtime
        except OSError:
            return True

    # ---- 拷贝细节（TransferDetailsFrom）----
    def transfer_details_from(self, other: "WorkingFile"):
        self.filename = other.filename
        self.converted_filename = other.converted_filename
        self.descriptive_name = other.descriptive_name
        self.reflected_name = other.reflected_name
        other.set_out_of_use()

    # ---- 临时文件辅助 ----
    @staticmethod
    def temp_path_for(prefix: str, suffix: str = ".tmp") -> str:
        import tempfile
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        os.close(fd)
        return path