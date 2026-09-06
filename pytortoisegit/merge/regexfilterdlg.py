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

"""regexfilterdlg.py —— TortoiseMerge 的 RegexFilterDlg（单个正则过滤）。

翻译 RegexFilterDlg.h：名称 + 正则表达式 + 替换。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout,
)

from ..res.strings import tr


class RegexFilterDlg(QDialog):
    """编辑一条正则过滤。"""

    def __init__(self, parent=None, name: str = "", regex: str = "",
                 replace: str = ""):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("regex_filter_title", "正则过滤"))
        self.resize(420, 140)
        self.m_sName = name
        self.m_sRegex = regex
        self.m_sReplace = replace
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        self.name_edit.setText(self.m_sName)
        self.regex_edit = QLineEdit(self)
        self.regex_edit.setText(self.m_sRegex)
        self.replace_edit = QLineEdit(self)
        self.replace_edit.setText(self.m_sReplace)
        form.addRow(tr("regex_name", "名称:"), self.name_edit)
        form.addRow(tr("regex_expr", "正则:"), self.regex_edit)
        form.addRow(tr("regex_replace", "替换为:"), self.replace_edit)
        lay.addLayout(form)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                               QDialogButtonBox.StandardButton.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def accept(self):
        self.m_sName = self.name_edit.text().strip()
        self.m_sRegex = self.regex_edit.text().strip()
        self.m_sReplace = self.replace_edit.text().strip()
        super().accept()


class RegexFiltersDlg(QDialog):
    """正则过滤列表管理（Add/Edit/Remove/双击编辑）。"""

    def __init__(self, parent=None, filters=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("regex_filters_title", "正则过滤列表"))
        self.resize(520, 320)
        self._filters = list(filters or [])  # list of (name, regex, replace)
        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QPushButton)
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