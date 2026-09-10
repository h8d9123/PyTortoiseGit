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

"""aboutdlg.py —— TortoiseMerge 的 AboutDlg（关于对话框）。

翻译 AboutDlg.h：显示 TortoiseMerge 版本/Logo。用 PySide6 实现。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .. import __appname__, __version__
from ..res.strings import tr


class AboutDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("about_title", "About"))
        self.resize(360, 180)
        lay = QVBoxLayout(self)
        title = QLabel(tr("merge_about_title", "TortoiseMerge (PyTortoiseGit)"), self)
        f = title.font(); f.setPointSize(f.pointSize() + 4); f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)
        ver = QLabel(tr("merge_about_version", "Version {ver} · reimplementation based on TortoiseGit").format(ver=__version__), self)
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ver)
        link = QLabel('<a href="https://tortoisegit.org">tortoisegit.org</a>', self)
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(link)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        box.accepted.connect(self.accept)
        lay.addWidget(box)