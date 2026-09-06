"""catdlg.py —— CatDlg：显示某修订的文件内容（可复用 PatchView 全窗只读文本）。"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QPlainTextEdit
from ..res.strings import tr


class CatDlg(QDialog):
    def __init__(self, repo, revision: str = "HEAD", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.revision = revision
        self.setWindowTitle(tr("cat_title", "Cat - {}").format(revision))
        self.resize(700, 460)

        self.view = QPlainTextEdit(self)
        self.view.setReadOnly(True)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(9)
        self.view.setFont(mono)
        self._load()

    def _load(self):
        commit, _, path = self.revision.partition(":")
        if not path:
            self.view.setPlainText("")
            return
        r = self.repo.runner.run("show", f"{commit}:{path}")
        self.view.setPlainText(r.stdout or r.stderr or "")

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
