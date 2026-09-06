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

"""filetextlines.py —— TortoiseMerge 的 CFileTextLines（文件行文本数组）。

翻译 FileTextLines.h：一个基于 list 的行数组，用 FileLine 元素承载
文本 + EOL + 状态，提供 GetCount/GetAt/Add/InsertAt/RemoveAt 等接口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .eol import EOL


@dataclass
class FileLine:
    text: str = ""
    eol: EOL = EOL.AutoLine


class CStdArray:
    """行数组（别名 STL 语义的简化封装）。"""

    def __init__(self):
        self._vec: List[FileLine] = []

    def get_count(self) -> int:
        return len(self._vec)

    def get_at(self, index: int) -> FileLine:
        return self._vec[index]

    def add(self, val: FileLine):
        self._vec.append(val)

    def insert_at(self, index: int, val: FileLine, copies: int = 1):
        for _ in range(copies):
            self._vec.insert(index, val)
            index += 1

    def remove_at(self, index: int):
        del self._vec[index]

    def set_at(self, index: int, val: FileLine):
        self._vec[index] = val

    def remove_all(self):
        self._vec.clear()

    def reserve(self, n: int):
        pass  # list 自动扩容

    def line(self, index: int) -> str:
        return self._vec[index].text if 0 <= index < len(self._vec) else ""

    def eol(self, index: int) -> EOL:
        return self._vec[index].eol if 0 <= index < len(self._vec) else EOL.AutoLine


class FileTextLines(CStdArray):
    """文件行文本数组（带行尾）。"""

    @classmethod
    def from_text(cls, text: str) -> "FileTextLines":
        inst = cls()
        eol = EOL.LF
        if "\r\n" in text:
            eol = EOL.CRLF
        # 用 keepends 保行尾
        for line in text.splitlines(keepends=True):
            line = line.rstrip("\r\n")
            inst.add(FileLine(line, eol))
        return inst

    def to_text(self) -> str:
        return "".join(f.text + "\n" for f in self._vec)