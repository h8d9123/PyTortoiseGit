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

import fnmatch
import os
import re
from typing import Optional, Tuple

from .eol import EOL
from .filetextlines import UnicodeType


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


_EOL_MAP = {"lf": EOL.LF, "crlf": EOL.CRLF, "cr": EOL.CR}
_CHARSET_MAP = {
    "utf-8": UnicodeType.UTF8, "utf-8-bom": UnicodeType.UTF8BOM,
    "utf-16le": UnicodeType.UTF16_LE, "utf-16be": UnicodeType.UTF16_BE,
    "latin1": UnicodeType.ASCII,
}


def _match_section(pattern: str, rel: str) -> bool:
    """editorconfig section 匹配（支持 {a,b} 与 **）。"""
    if pattern == "*":
        return True
    pat = pattern
    # {a,b} → (a|b) 正则
    if "{" in pat and "}" in pat:
        rx = re.escape(pat)
        rx = rx.replace(r"\{", "(").replace(r"\}", ")")
        rx = rx.replace(r"\,", "|").replace(r"\*", "[^/]*").replace(r"\*\*", ".*")
        try:
            if re.fullmatch(rx, rel) or re.fullmatch(rx, os.path.basename(rel)):
                return True
        except re.error:
            pass
    return (fnmatch.fnmatch(rel, pat)
            or fnmatch.fnmatch(os.path.basename(rel), pat))


class EditorConfigWrapper:
    """读取文件所在目录的 .editorconfig 设置。"""

    def __init__(self):
        self.indent_style: Nullable = Nullable()
        self.indent_size: Nullable = Nullable()
        self.tab_width: Nullable = Nullable()
        self.end_of_line: Nullable = Nullable()      # EOL
        self.charset: Nullable = Nullable()          # UnicodeType
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
            if v in _EOL_MAP:
                self.end_of_line = Nullable(_EOL_MAP[v])
        elif key == "charset":
            if v in _CHARSET_MAP:
                self.charset = Nullable(_CHARSET_MAP[v])
        elif key == "trim_trailing_whitespace":
            self.trim_trailing_ws = Nullable(v in ("true", "yes"))
        elif key == "insert_final_newline":
            self.insert_final_newline = Nullable(v in ("true", "yes"))

    def load(self, filename: str) -> bool:
        """自文件所在目录向上合并 .editorconfig（对齐 editorconfig-core 语义）。"""
        d = os.path.dirname(os.path.abspath(filename))
        chain = []
        cur = d
        while True:
            cfg = os.path.join(cur, ".editorconfig")
            if os.path.isfile(cfg):
                chain.append((cfg, cur))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        found = False
        for cfg, base in reversed(chain):  # 根 → 近 顺序应用（近者覆盖）
            self._read_config(cfg, base, filename)
            found = True
            if self._is_root(cfg):
                break
        return found

    def _is_root(self, path: str) -> bool:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip().lower()
                    if line.startswith("root") and "=" in line:
                        k, _, v = line.partition("=")
                        if k.strip() == "root" and v.strip() in ("true", "yes"):
                            return True
        except OSError:
            pass
        return False

    def _read_config(self, path: str, base: str, filename: str) -> bool:
        try:
            rel = os.path.relpath(os.path.abspath(filename), base).replace("\\", "/")
        except ValueError:
            rel = os.path.basename(filename)
        try:
            section_matches = False
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith(("#", ";")):
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        section_matches = _match_section(line[1:-1].strip(), rel)
                        continue
                    if "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip().lower()
                    if k == "root":
                        continue
                    if section_matches:
                        self._parse_value(k, v)
            return True
        except OSError:
            return False


def _to_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        return None