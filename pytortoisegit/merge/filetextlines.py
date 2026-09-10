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

翻译 FileTextLines.h/.cpp：
  * UnicodeType 检测（CheckUnicodeType）：BINARY/ASCII/UTF16/UTF32/UTF8±BOM
  * Load：读字节 → 检测编码 → 解码 → 按 CRLF/CR/LF 拆行并记录行尾
  * Save：按保存参数编码写回
"""

from __future__ import annotations

import locale
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from .eol import EOL, eol_sequence


class UnicodeType(Enum):
    AUTOTYPE = 0
    BINARY = 1
    ASCII = 2
    UTF16_LE = 3
    UTF16_BE = 4
    UTF16_LEBOM = 5
    UTF16_BEBOM = 6
    UTF32_LE = 7
    UTF32_BE = 8
    UTF8 = 9
    UTF8BOM = 10


_BOM_TYPES = (UnicodeType.UTF8BOM, UnicodeType.UTF16_LEBOM,
              UnicodeType.UTF16_BEBOM, UnicodeType.UTF32_LE, UnicodeType.UTF32_BE)

# UnicodeType → (python 编码, BOM 字节)
_ENCODING = {
    UnicodeType.ASCII: (None, b""),
    UnicodeType.UTF8: ("utf-8", b""),
    UnicodeType.UTF8BOM: ("utf-8", b"\xef\xbb\xbf"),
    UnicodeType.UTF16_LE: ("utf-16-le", b""),
    UnicodeType.UTF16_LEBOM: ("utf-16-le", b"\xff\xfe"),
    UnicodeType.UTF16_BE: ("utf-16-be", b""),
    UnicodeType.UTF16_BEBOM: ("utf-16-be", b"\xfe\xff"),
    UnicodeType.UTF32_LE: ("utf-32-le", b"\xff\xfe\x00\x00"),
    UnicodeType.UTF32_BE: ("utf-32-be", b"\x00\x00\xfe\xff"),
}


def check_unicode_type(buf: bytes) -> UnicodeType:
    """对齐 CFileTextLines::CheckUnicodeType。"""
    cb = len(buf)
    if cb < 2:
        return UnicodeType.ASCII
    # 扫描 0x00000000 序列 → 二进制
    n_dwords = cb // 4
    for j in range(n_dwords):
        if buf[j * 4:j * 4 + 4] == b"\x00\x00\x00\x00":
            return UnicodeType.BINARY
    if cb >= 4:
        if buf[0:4] == b"\xff\xfe\x00\x00":
            return UnicodeType.UTF32_LE
        if buf[0:4] == b"\x00\x00\xfe\xff":
            return UnicodeType.UTF32_BE
    if buf[0:2] == b"\xff\xfe":
        return UnicodeType.UTF16_LEBOM
    if buf[0:2] == b"\xfe\xff":
        return UnicodeType.UTF16_BEBOM
    if cb < 3:
        return UnicodeType.ASCII
    if buf[0:3] == b"\xef\xbb\xbf":
        return UnicodeType.UTF8BOM
    # 检查非法 UTF-8 序列
    non_ansi = False
    need_data = 0
    null_count = 0
    i = 0
    while i < cb:
        b = buf[i]
        if b == 0:
            null_count += 1
            if null_count > cb // 50:
                return UnicodeType.UTF16_LE if (i % 2) else UnicodeType.UTF16_BE
        if b & 0x80:
            non_ansi = True
            break
        i += 1
    while i < cb:
        z = buf[i]
        if (z & 0x80) == 0:
            if z == 0:
                null_count += 1
                if null_count > cb // 50:
                    return UnicodeType.UTF16_LE if (i % 2) else UnicodeType.UTF16_BE
                need_data = 0
            elif need_data:
                return UnicodeType.ASCII
            i += 1
            continue
        if (z & 0x40) == 0:
            if not need_data:
                return UnicodeType.ASCII
            need_data -= 1
        elif need_data:
            return UnicodeType.ASCII
        elif (z & 0x20) == 0:
            if z <= 0xC1:
                return UnicodeType.ASCII
            need_data = 1
        elif (z & 0x10) == 0:
            need_data = 2
        elif (z & 0x08) == 0:
            if z >= 0xF5:
                return UnicodeType.ASCII
            need_data = 3
        else:
            return UnicodeType.ASCII
        i += 1
    if non_ansi and need_data == 0:
        return UnicodeType.UTF8
    return UnicodeType.ASCII


def _ansi_encoding() -> str:
    try:
        return locale.getpreferredencoding(False) or "latin-1"
    except Exception:  # noqa: BLE001
        return "latin-1"


def split_lines_eol(text: str) -> Tuple[List[str], List[EOL]]:
    """按 CRLF/LFCR/CR/LF 拆行并记录行尾（对齐 CFileTextLines::Load）。"""
    lines: List[str] = []
    eols: List[EOL] = []
    i, n = 0, len(text)
    while i < n:
        j = i
        while j < n and text[j] not in "\r\n":
            j += 1
        lines.append(text[i:j])
        if j >= n:
            eols.append(EOL.NoEnding)
            break
        if text[j] == "\r" and j + 1 < n and text[j + 1] == "\n":
            eols.append(EOL.CRLF)
            i = j + 2
        elif text[j] == "\n" and j + 1 < n and text[j + 1] == "\r":
            eols.append(EOL.LFCR)
            i = j + 2
        elif text[j] == "\r":
            eols.append(EOL.CR)
            i = j + 1
        else:
            eols.append(EOL.LF)
            i = j + 1
    return lines, eols


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
    """文件行文本数组（带编码与行尾）。"""

    def __init__(self):
        super().__init__()
        self.unicode_type = UnicodeType.AUTOTYPE
        self.line_endings = EOL.AutoLine
        self.needs_conversion = False
        self.error_string = ""
        self._keep_encoding = False

    # ---- 加载 ----
    def load(self, path: str) -> bool:
        self.line_endings = EOL.AutoLine
        if not self._keep_encoding:
            self.unicode_type = UnicodeType.AUTOTYPE
        self.remove_all()
        self.error_string = ""
        if os.path.isdir(path):
            self.error_string = f"不是文件: {path}"
            return False
        if not os.path.isfile(path):
            return True  # 文件不存在视为成功（对齐 C++）
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:  # noqa: BLE001
            self.error_string = str(exc)
            return False
        if self.unicode_type == UnicodeType.AUTOTYPE:
            self.unicode_type = check_unicode_type(data)
        self.needs_conversion = self.unicode_type not in (
            UnicodeType.UTF8, UnicodeType.ASCII)
        if not data:
            return True
        if self.unicode_type == UnicodeType.BINARY:
            self.error_string = f"二进制文件: {path}"
            return False
        enc, bom = _ENCODING.get(self.unicode_type, (None, b""))
        if enc is None:
            enc = _ansi_encoding()
        if bom and data.startswith(bom):
            data = data[len(bom):]
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            text = data.decode(enc, errors="replace")
        lines, eols = split_lines_eol(text)
        for ln, eol in zip(lines, eols):
            self.add(FileLine(ln, eol))
        # 主流行尾（AutoLine → 最常见）
        if eols:
            counts: dict = {}
            for e in eols:
                counts[e] = counts.get(e, 0) + 1
            self.line_endings = max(counts, key=counts.get)
        return True

    # ---- 保存 ----
    def save(self, path: str, save_as_utf8: bool = False,
             use_svn_compatible_eols: bool = False) -> bool:
        self.error_string = ""
        eol_default = self.line_endings
        if eol_default in (EOL.AutoLine, EOL.NoEnding):
            eol_default = EOL.LF
        if use_svn_compatible_eols and eol_default not in (EOL.CRLF, EOL.CR, EOL.LF):
            eol_default = EOL.LF
        parts: List[str] = []
        for f in self._vec:
            eol = f.eol
            if use_svn_compatible_eols and eol not in (EOL.CRLF, EOL.CR, EOL.LF):
                eol = eol_default
            if eol in (EOL.AutoLine, EOL.NoEnding):
                eol = eol_default
            parts.append(f.text + eol_sequence(eol))
        text = "".join(parts)
        utype = self.unicode_type
        if save_as_utf8 or utype in (UnicodeType.AUTOTYPE, UnicodeType.BINARY):
            utype = UnicodeType.UTF8
        enc, bom = _ENCODING.get(utype, ("utf-8", b""))
        if enc is None:
            enc = _ansi_encoding()
        try:
            with open(path, "wb") as fh:
                fh.write(bom)
                fh.write(text.encode(enc))
        except (OSError, UnicodeEncodeError) as exc:  # noqa: BLE001
            self.error_string = str(exc)
            return False
        return True

    def to_text(self) -> str:
        return "".join(f.text + eol_sequence(
            f.eol if f.eol not in (EOL.AutoLine, EOL.NoEnding) else EOL.LF)
            for f in self._vec)

    # ---- 兼容旧接口 ----
    @classmethod
    def from_text(cls, text: str) -> "FileTextLines":
        inst = cls()
        lines, eols = split_lines_eol(text)
        for ln, eol in zip(lines, eols):
            inst.add(FileLine(ln, eol))
        return inst
