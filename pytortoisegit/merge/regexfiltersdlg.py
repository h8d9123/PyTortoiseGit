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

"""regexfiltersdlg.py —— TortoiseMerge 的 RegexFiltersDlg（正则过滤列表）。

翻译 RegexFiltersDlg.h：管理一组正则过滤(name/regex/replace)，
Add/Edit/Remove/双击编辑。
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QListWidget, QPushButton,
    QVBoxLayout,
)

from ..res.strings import tr
from .regexfilterdlg import RegexFilterDlg


class RegexFiltersDlg(QDialog):
    """正则过滤列表管理（Add/Edit/Remove/双击编辑）。"""

    def __init__(self, parent=None, filters=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("regex_filters_title", "正则过滤列表"))
        self.resize(520, 320)
        self._filters: List[Tuple[str, str, str]] = list(filters or [])
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        self.list = QListWidget(self)
        self._fill()
        self.list.itemDoubleClicked.connect(lambda *_: self._edit())
        lay.addWidget(self.list, 1)
        btns = QHBoxLayout()
        btn_add = QPushButton(tr("call_add", "&Add…"), self)
        btn_add.clicked.connect(self._add)
        btn_edit = QPushButton(tr("call_edit", "&Edit…"), self)
        btn_edit.clicked.connect(self._edit)
        btn_remove = QPushButton(tr("call_remove", "&Remove"), self)
        btn_remove.clicked.connect(self._remove)
        btns.addWidget(btn_add)
        btns.addWidget(btn_edit)
        btns.addWidget(btn_remove)
        btns.addStretch(1)
        lay.addLayout(btns)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _fill(self):
        self.list.clear()
        for (name, _rx, _re) in self._filters:
            self.list.addItem(name)

    def _add(self):
        dlg = RegexFilterDlg(self)
        if dlg.exec():
            self._filters.append((dlg.m_sName, dlg.m_sRegex, dlg.m_sReplace))
            self._fill()

    def _edit(self):
        row = self.list.currentRow()
        if row < 0:
            return
        name, rx, re_ = self._filters[row]
        dlg = RegexFilterDlg(self, name, rx, re_)
        if dlg.exec():
            self._filters[row] = (dlg.m_sName, dlg.m_sRegex, dlg.m_sReplace)
            self._fill()

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            self._filters.pop(row)
            self._fill()

    @property
    def filters(self) -> List[Tuple[str, str, str]]:
        return self._filters