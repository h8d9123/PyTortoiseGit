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

"""editorconfigwrapper.py —— TortoiseMerge 的 CEditorConfigWrapper。

翻译 EditorConfigWrapper.h：读取 .editorconfig 的缩进风格/缩进大小/
制表符宽度等编辑设置。用简单的行解析实现（无需第三方库）。
"""

from __future__ import annotations

import os
from typing import Optional, Tuple


class Nullable:
    """可为空的值包装（翻译 EditorConfigWrapper.h 的 Nullable）。"""

    def __init__(self, value=None):
        self._value = value
        self._is_null = value is None

    def is_null(self) -> bool:
        return self._is_null

    def get(self, default=None):
        return default if self._is_null else self._value

    def __bool__(self):
        return not self._is_null

    def __eq__(self, other):
        return self._value == other


class EditorConfigWrapper:
    """读取文件所在目录的 .editorconfig 设置。"""

    def __init__(self):
        self.indent_style: Nullable = Nullable()
        self.indent_size: Nullable = Nullable()
        self.tab_width: Nullable = Nullable()
        self.end_of_line: Nullable = Nullable()      # lf/crlf/cr
        self.trim_trailing_ws: Nullable = Nullable()
        self.insert_final_newline: Nullable = Nullable()

    def _parse_value(self, key: str, value: str):
        v = value.strip().lower()
        if key == "indent_style":
            self.indent_style = Nullable(v in ("space", "tab"))
        elif key == "indent_size":
            self.indent_size = Nullable(_to_int(v))
        elif key == "tab_width":
            self.tab_width = Nullable(_to_int(v))
        elif key == "end_of_line":
            self.end_of_line = Nullable(v)
        elif key == "trim_trailing_whitespace":
            self.trim_trailing_ws = Nullable(v in ("true", "yes"))
        elif key == "insert_final_newline":
            self.insert_final_newline = Nullable(v in ("true", "yes"))

    def load(self, filename: str) -> bool:
        """自文件所在目录向上查找合并 .editorconfig（简化：只读本目录/向上）。"""
        d = os.path.dirname(os.path.abspath(filename))
        # 从当前目录向上直到根，逐个应用 .editorconfig（后者覆盖前者）
        chain = []
        cur = d
        while True:
            cfg = os.path.join(cur, ".editorconfig")
            if os.path.isfile(cfg):
                chain.append(cfg)
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        found = False
        for cfg in reversed(chain):  # 根 → 近 顺序应用
            if self._read_config(cfg):
                found = True
        return found

    def _read_config(self, path: str) -> bool:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith(("#", ";", "[")):
                        continue
                    if "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    self._parse_value(k.strip(), v)
            return True
        except OSError:
            return False


def _to_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        return None