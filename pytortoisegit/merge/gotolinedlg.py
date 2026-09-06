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

"""gotolinedlg.py —— TortoiseMerge 的 GotoLineDlg（跳转行），翻译 GotoLineDlg.h。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QLineEdit, QSpinBox, QVBoxLayout,
)

from ..res.strings import tr


class GotoLineDlg(QDialog):
    """跳转到指定行。"""

    def __init__(self, parent=None, line_count: int = 1):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("gotoline_title", "跳转到行"))
        self.resize(280, 110)
        self._build_ui(line_count)

    def _build_ui(self, line_count: int):
        lay = QVBoxLayout(self)
        self.label = QLabel(tr("gotoline_label", "行号:"), self)
        lay.addWidget(self.label)
        self.spin = QSpinBox(self)
        self.spin.setRange(1, max(1, line_count))
        self.spin.setValue(1)
        lay.addWidget(self.spin)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                               QDialogButtonBox.StandardButton.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def set_label(self, text: str):
        self.label.setText(text)

    def set_limits(self, minimum: int, maximum: int):
        self.spin.setRange(minimum, max(minimum, maximum))

    def get_line_number(self) -> int:
        return self.spin.value()