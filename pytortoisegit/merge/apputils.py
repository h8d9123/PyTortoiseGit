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

"""apputils.py —— TortoiseMerge 的 CAppUtils（应用工具）。

翻译 AppUtils.h：获取某修订文件(Git 实现)、创建统一 diff、启动外部
diff/merge 工具。
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

from ..git.repo import Repository


def get_versioned_file(repo: Repository, path: str, version: str,
                       save_path: str) -> bool:
    """把指定修订的某文件版本保存到 save_path（翻译 GetVersionedFile）。"""
    try:
        out = repo.runner.run("show", f"{version}:{path}").stdout or ""
        with open(save_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
        return True
    except Exception:
        return False


def create_unified_diff(repo: Repository, path1: str, path2: str,
                        output: str = "", context_size: int = 3) -> str:
    """两个文件/修订之间的统一 diff（翻译 CreateUnifiedDiff）。"""
    try:
        text = repo.runner.run(
            "diff", "--no-color", f"-U{context_size}", path1, path2).stdout or ""
        if output:
            with open(output, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        return text
    except Exception:  # noqa: BLE001
        return ""


def has_clipboard_format(fmt: str) -> bool:
    """对齐 CAppUtils::HasClipboardFormat。"""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return False
        cb = app.clipboard()
        return bool(cb and cb.mimeData() and cb.mimeData().hasFormat(fmt))
    except Exception:  # noqa: BLE001
        return False


def intense_color(scale: int, color) -> "QColor":
    """对齐 CAppUtils::IntenseColor：浅色变暗、深色变亮。"""
    from PySide6.QtGui import QColor
    gray = (color.red() + color.green() + color.blue()) // 3
    if gray > 127:
        r = color.red() * (255 - scale) // 255
        g = color.green() * (255 - scale) // 255
        b = color.blue() * (255 - scale) // 255
    else:
        r = color.red() + (255 - color.red()) * scale // 255
        g = color.green() + (255 - color.green()) * scale // 255
        b = color.blue() + (255 - color.blue()) * scale // 255
    return QColor(r, g, b)


def run_external_merge(repo: Optional[Repository], base: str, theirs: str,
                       ours: str, merged: str):
    """用外部 merge 工具打开（git mergetool 语义）。"""
    try:
        subprocess.Popen(["git", "mergetool", "--tool-help"], shell=False)
    except OSError:
        pass


def write_merge_output(merged_path: str, text: str):
    os.makedirs(os.path.dirname(os.path.abspath(merged_path)), exist_ok=True)
    with open(merged_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)