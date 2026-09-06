"""patchviewdlg.py —— PatchViewDlg：查看补丁（IDD_PATCH_VIEW 模板）。

248x195 "View Patch"：整窗 Scintilla → 只读等宽文本。
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
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QPlainTextEdit
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class PatchViewDlg(QDialog):
    def __init__(self, text: str = "", title: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_PATCH_VIEW")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(title or spec.caption or tr("patch_view", "View Patch"))

        self.view = QPlainTextEdit(self)
        ctrl = spec.controls[0] if spec.controls else None
        if ctrl is not None:
            rr = fu.px(ctrl.x, ctrl.y, ctrl.w, ctrl.h)
            self.view.setGeometry(rr)
        else:
            self.view.setGeometry(self.rect())
        self.view.setReadOnly(True)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(9)
        self.view.setFont(mono)
        if text:
            self.view.setPlainText(text)