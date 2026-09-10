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
    QDialog, QDialogButtonBox, QHBoxLayout, QPushButton, QVBoxLayout,
)

from ..res.strings import tr
from .regexfilterdlg import RegexFilterDlg


class RegexFiltersDlg(QDialog):
    """正则过滤列表管理（Add/Edit/Remove/双击编辑）。"""

    _INI_KEY = "TortoiseGitMerge/RegexFilters"

    def __init__(self, parent=None, filters=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("regex_filters_title", "正则过滤列表"))
        self.resize(520, 320)
        self._ini_file = None
        if filters is None:
            self._filters: List[Tuple[str, str, str]] = self._load_filters()
        else:
            self._filters = list(filters)
        self._build_ui()

    # ---- 持久化（对齐 CSimpleIni 存储）----
    def set_ini_file(self, ini):
        """兼容 C++ SetIniFile 接口。"""
        self._ini_file = ini

    def _load_filters(self) -> List[Tuple[str, str, str]]:
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("TortoiseGit", "TortoiseGitMerge")
            raw = s.value(self._INI_KEY, [], type=list) or []
            return [tuple(x) for x in raw if len(x) == 3]
        except Exception:  # noqa: BLE001
            return []

    def save_filters(self):
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("TortoiseGit", "TortoiseGitMerge")
            s.setValue(self._INI_KEY, [list(x) for x in self._filters])
        except Exception:  # noqa: BLE001
            pass

    def _build_ui(self):
        from PySide6.QtWidgets import QTreeWidget
        lay = QVBoxLayout(self)
        self.list = QTreeWidget(self)
        self.list.setColumnCount(3)
        self.list.setHeaderLabels([
            tr("regex_name", "名称"),
            tr("regex_expr", "正则表达式"),
            tr("regex_replace", "替换为"),
        ])
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
        from PySide6.QtWidgets import QTreeWidgetItem
        self.list.clear()
        for (name, rx, re_) in self._filters:
            QTreeWidgetItem(self.list, [name, rx, re_])

    def _add(self):
        dlg = RegexFilterDlg(self)
        if dlg.exec():
            self._filters.append((dlg.m_sName, dlg.m_sRegex, dlg.m_sReplace))
            self._fill()

    def _edit(self):
        item = self.list.currentItem()
        if item is None:
            return
        row = self.list.indexOfTopLevelItem(item)
        if row < 0:
            return
        name, rx, re_ = self._filters[row]
        dlg = RegexFilterDlg(self, name, rx, re_)
        if dlg.exec():
            self._filters[row] = (dlg.m_sName, dlg.m_sRegex, dlg.m_sReplace)
            self._fill()

    def _remove(self):
        item = self.list.currentItem()
        if item is None:
            return
        row = self.list.indexOfTopLevelItem(item)
        if row >= 0:
            self._filters.pop(row)
            self._fill()

    def reject(self):
        self.save_filters()
        super().reject()

    @property
    def filters(self) -> List[Tuple[str, str, str]]:
        return self._filters