"""stashprompt.py —— pull/rebase 等操作前询问是否暂存本地改动。

交互对齐 TortoiseGit：本地有未提交改动时，提示是否 stash，操作后自动 pop。
"""

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

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ..res.strings import tr


def ask_stash(parent=None) -> bool:
    """询问是否先 stash；返回 True 表示用户选择暂存。"""
    ans = QMessageBox.question(
        parent, tr("stash_prompt_title", "Local changes"),
        tr("stash_prompt_ask",
           "You have uncommitted local changes.\n\n"
           "Stash them, run the operation, then restore them (stash pop)?"),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes)
    return ans == QMessageBox.StandardButton.Yes
