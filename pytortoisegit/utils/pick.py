"""utils/pick.py —— 文件/目录选择助手（QFileDialog 封装）。"""

from __future__ import annotations

from typing import Optional


def pick_file(parent=None, title: str = "", pattern: str = "") -> Optional[str]:
    from PySide6.QtWidgets import QFileDialog
    path, _ = QFileDialog.getSaveFileName(parent, title, "", pattern)
    return path or None


def pick_open_file(parent=None, title: str = "",
                   pattern: str = "") -> Optional[str]:
    from PySide6.QtWidgets import QFileDialog
    path, _ = QFileDialog.getOpenFileName(parent, title, "", pattern)
    return path or None


def pick_open_files(parent=None, title: str = "",
                    pattern: str = "") -> Optional[list]:
    from PySide6.QtWidgets import QFileDialog
    paths, _ = QFileDialog.getOpenFileNames(parent, title, "", pattern)
    return list(paths) or None


def pick_dir(parent=None, title: str = "", start: str = "") -> Optional[str]:
    from PySide6.QtWidgets import QFileDialog
    path = QFileDialog.getExistingDirectory(parent, title, start or "")
    return path or None

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
