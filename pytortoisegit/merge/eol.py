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

"""eol.py —— TortoiseMerge 的 EOL（行尾），逐行翻译 EOL.h。

每行可携带的行尾风格（CRLF/LF/CR/…）。
"""

from __future__ import annotations

from ..res.strings import tr

from enum import Enum


class EOL(Enum):
    AutoLine = 0
    CRLF = 1     # CR (U+000D) + LF (U+000A)
    LF = 2       # Line Feed, U+000A
    CR = 3       # Carriage Return, U+000D
    LFCR = 4
    VT = 5       # Vertical Tab, U+000B
    FF = 6       # Form Feed, U+000C
    NEL = 7      # Next Line, U+0085
    LS = 8       # Line Separator, U+2028
    PS = 9       # Paragraph Separator, U+2029
    NoEnding = 10


_EOL_NAME = {
    EOL.AutoLine: ("eol_auto", "Auto"),
    EOL.CRLF: ("eol_crlf", "CRLF"),
    EOL.LF: ("eol_lf", "LF"),
    EOL.CR: ("eol_cr", "CR"),
    EOL.LFCR: ("eol_lfcr", "LFCR"),
    EOL.VT: ("eol_vt", "VT"),
    EOL.FF: ("eol_ff", "FF"),
    EOL.NEL: ("eol_nel", "NEL"),
    EOL.LS: ("eol_ls", "LS"),
    EOL.PS: ("eol_ps", "PS"),
    EOL.NoEnding: ("eol_none", "None"),
}


def get_eol_name(eol: EOL) -> str:
    entry = _EOL_NAME.get(eol)
    if entry is None:
        return str(eol)
    key, default = entry
    return tr(key, default)


def detect_eol(text: str) -> EOL:
    """检测文本的主流行尾（翻译 WorkingFile/BaseView 的自动检测）。"""
    if "\r\n" in text:
        return EOL.CRLF
    if "\r" in text and "\n" not in text.replace("\r\n", ""):
        return EOL.CR
    if "\n" in text:
        return EOL.LF
    return EOL.AutoLine


def eol_sequence(eol: EOL) -> str:
    return {
        EOL.CRLF: "\r\n",
        EOL.LF: "\n",
        EOL.CR: "\r",
        EOL.LFCR: "\n\r",
    }.get(eol, "\n")