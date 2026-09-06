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

"""encodingdlg.py —— TortoiseMerge 的 EncodingDlg（编码/行尾），翻译 EncodingDlg.h。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)

from ..res.strings import tr
from .eol import EOL

# UnicodeType（简化取值）
UNICODE_NAMES = ["ASCII", "UTF-8", "UTF-8 with BOM", "UTF-16 LE", "UTF-16 BE"]


class EncodingDlg(QDialog):
    """选择文本编码与行尾。"""

    def __init__(self, parent=None, texttype: int = 0,
                 eol: EOL = EOL.AutoLine):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("encoding_title", "编码 / 行尾"))
        self.resize(320, 140)
        self.texttype = texttype
        self.lineendings = eol
        self.view = ""
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("encoding_label", "编码:"), self))
        self.encoding_combo = QComboBox(self)
        self.encoding_combo.addItems(UNICODE_NAMES)
        self.encoding_combo.setCurrentIndex(max(0, self.texttype))
        lay.addWidget(self.encoding_combo)
        lay.addWidget(QLabel(tr("eol_label", "行尾:"), self))
        self.eol_combo = QComboBox(self)
        for e in [EOL.AutoLine, EOL.LF, EOL.CRLF, EOL.CR]:
            self.eol_combo.addItem(_EOL_LABEL[e], e)
        self.eol_combo.setCurrentIndex(
            list(_EOL_LABEL.keys()).index(self.lineendings)
            if self.lineendings in _EOL_LABEL else 0)
        lay.addWidget(self.eol_combo)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                               QDialogButtonBox.StandardButton.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def accept(self):
        self.texttype = self.encoding_combo.currentIndex()
        sel = self.eol_combo.currentData()
        self.lineendings = sel if sel is not None else EOL.AutoLine
        super().accept()


_EOL_LABEL = {
    EOL.AutoLine: "自动",
    EOL.LF: "LF",
    EOL.CRLF: "CRLF",
    EOL.CR: "CR",
}