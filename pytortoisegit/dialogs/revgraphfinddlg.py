"""revgraphfinddlg.py —— RevGraphFindDlg：修订图查找（对应原版 CFindDlg）。

原版 CFindDlg 支持：查找字符串、区分大小写、正则、仅在引用名中查找、
查找下一个/上一个，并把命中项列在列表里。这里实现同样的功能面，
以非模态窗口出现；双击（或回车）命中项即在图中选中并滚动到该提交。
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
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from ..res.strings import tr


class RevGraphFindDlg(QDialog):
    """修订图查找窗口（非模态）。"""

    activated = Signal(str)      # 命中项被激活（hash）

    def __init__(self, items=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("revgraph_find_title", "Find in Revision Graph"))
        self.resize(430, 320)
        self._items = list(items or [])   # [(hash, refs_text, subject)]

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText(tr("revgraph_find_prompt", "Find:"))
        self.edit.returnPressed.connect(self.find_next)
        self.edit.textChanged.connect(self.refresh_list)
        row.addWidget(self.edit, 1)
        lay.addLayout(row)

        opts = QHBoxLayout()
        self.chk_case = QCheckBox(tr("revgraph_find_case", "Match case"), self)
        self.chk_regex = QCheckBox(tr("revgraph_find_regex", "Regex"), self)
        self.chk_refs = QCheckBox(tr("revgraph_find_refs", "Search ref names"), self)
        for chk in (self.chk_case, self.chk_regex, self.chk_refs):
            chk.toggled.connect(self.refresh_list)
            opts.addWidget(chk)
        opts.addStretch(1)
        lay.addLayout(opts)

        self.list = QTreeWidget(self)
        self.list.setColumnCount(3)
        self.list.setHeaderLabels([
            tr("revgraph_find_col_hash", "Commit"),
            tr("revgraph_find_col_refs", "Refs"),
            tr("revgraph_find_col_subject", "Subject")])
        self.list.setRootIsDecorated(False)
        self.list.itemDoubleClicked.connect(self._on_activated)
        self.list.itemActivated.connect(self._on_activated)
        lay.addWidget(self.list, 1)

        self.status = QLabel("", self)
        lay.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_next = QPushButton(tr("revgraph_find_next", "Find &next"), self)
        self.btn_next.clicked.connect(self.find_next)
        self.btn_prev = QPushButton(tr("revgraph_find_prev", "Find &previous"), self)
        self.btn_prev.clicked.connect(self.find_prev)
        self.btn_close = QPushButton(tr("close", "Close"), self)
        self.btn_close.clicked.connect(self.close)
        for b in (self.btn_next, self.btn_prev, self.btn_close):
            btns.addWidget(b)
        lay.addLayout(btns)

        self.refresh_list()

    # ---- 数据 ----
    def set_items(self, items) -> None:
        self._items = list(items or [])
        self.refresh_list()

    def _matcher(self):
        text = self.edit.text()
        if not text:
            return None
        flags = 0 if self.chk_case.isChecked() else re.IGNORECASE
        pattern = text if self.chk_regex.isChecked() else re.escape(text)
        try:
            return re.compile(pattern, flags)
        except re.error:
            # 正则写错时按字面量处理，避免边输边报错
            return re.compile(re.escape(text), flags)

    def _haystack(self, item) -> str:
        h, refs, subject = item
        if self.chk_refs.isChecked():
            return f"{refs} {h}"
        return f"{refs} {subject} {h}"

    def refresh_list(self) -> None:
        matcher = self._matcher()
        self.list.clear()
        if matcher is None:
            self.status.setText("")
            return
        hits = 0
        for item in self._items:
            if matcher.search(self._haystack(item)):
                h, refs, subject = item
                node = QTreeWidgetItem([h[:8], refs, subject])
                node.setData(0, Qt.ItemDataRole.UserRole, h)
                self.list.addTopLevelItem(node)
                hits += 1
        self.status.setText(
            tr("revgraph_find_none", "No matches") if hits == 0
            else tr("revgraph_find_count", "{count} matches").replace(
                "{count}", str(hits)))

    # ---- 导航 ----
    def _step(self, delta: int) -> None:
        count = self.list.topLevelItemCount()
        if count == 0:
            return
        row = self.list.currentItem()
        index = self.list.indexOfTopLevelItem(row) if row is not None else -1
        index = (index + delta) % count
        item = self.list.topLevelItem(index)
        self.list.setCurrentItem(item)
        self.list.scrollToItem(item)

    def find_next(self) -> None:
        self._step(1)

    def find_prev(self) -> None:
        self._step(-1)

    def _on_activated(self, item, _column=0):
        if item is None:
            return
        h = item.data(0, Qt.ItemDataRole.UserRole)
        if h:
            self.activated.emit(str(h))
