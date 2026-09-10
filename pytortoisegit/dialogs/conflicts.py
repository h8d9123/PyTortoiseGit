"""conflicts.py —— ConflictsWidget：合并/变基冲突解决视图。

列出冲突文件，支持 标记解决 / 采用 ours/theirs / 外部合并工具 / 中止操作。
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

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..git.mergeop import conflicted_entries, mark_resolved
from ..git.repo import Repository
from ..git.status import GitStatusEntry
from ..res.strings import tr


class ConflictsWidget(QWidget):
    """刷新显示冲突文件并提供逐文件操作。resolved 信号：全部解决后发出。"""

    resolved = Signal()

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._entries: List[GitStatusEntry] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("conflicts_title"), self))
        head.addStretch(1)
        btn_mark = QPushButton(tr("conflict_mark"), self)
        btn_mark.clicked.connect(self._on_mark)
        head.addWidget(btn_mark)
        btn_ours = QPushButton(tr("conflict_ours"), self)
        btn_ours.clicked.connect(lambda: self._on_take("ours"))
        head.addWidget(btn_ours)
        btn_theirs = QPushButton(tr("conflict_theirs"), self)
        btn_theirs.clicked.connect(lambda: self._on_take("theirs"))
        head.addWidget(btn_theirs)
        btn_ext = QPushButton(tr("conflict_extmerge"), self)
        btn_ext.clicked.connect(self._on_extmerge)
        head.addWidget(btn_ext)
        btn_all = QPushButton(tr("conflict_all"), self)
        btn_all.clicked.connect(self._on_mark_all)
        head.addWidget(btn_all)
        lay.addLayout(head)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([tr("file"), tr("status")])
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_menu)
        lay.addWidget(self.tree, 1)

    # ---- 数据 ----
    def refresh(self):
        self._entries = conflicted_entries(self.repo)
        self.tree.clear()
        for e in self._entries:
            item = QTreeWidgetItem([e.display_path, e.status_text])
            item.setData(0, Qt.ItemDataRole.UserRole, e.path)
            self.tree.addTopLevelItem(item)

    @property
    def count(self) -> int:
        return len(self._entries)

    def _selected_path(self) -> str | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    # ---- 动作 ----
    def _after_change(self):
        self.refresh()
        if self.count == 0:
            self.resolved.emit()

    def _on_mark(self):
        path = self._selected_path()
        if path and mark_resolved(self.repo, path):
            self._after_change()

    def _on_take(self, side: str):
        path = self._selected_path()
        if not path:
            return
        from ..git.mergeop import resolve_as
        if resolve_as(self.repo, path, side):
            self._after_change()

    def _on_mark_all(self):
        for e in self._entries:
            mark_resolved(self.repo, e.path)
        self._after_change()

    def _on_extmerge(self):
        path = self._selected_path()
        if not path:
            return
        from ..utils.externaltools import launch_merge_for_conflict
        if launch_merge_for_conflict(self.repo, path):
            self._after_change()
        else:
            QMessageBox.warning(self, tr("error"), tr("xtool_not_configured"))

    def _on_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        path = self._selected_path()
        if not path:
            return
        self.tree.setCurrentItem(item)
        menu = QMenu(self)
        act_open = menu.addAction(tr("menu_open", "Open in editor"))
        act_copy = menu.addAction(tr("menu_copy_path", "Copy path"))
        menu.addSeparator()
        act_ours = menu.addAction(tr("conflicts_take_ours", "Take ours"))
        act_theirs = menu.addAction(tr("conflicts_take_theirs", "Take theirs"))
        act_mark = menu.addAction(tr("conflicts_mark", "Mark as resolved"))
        act_ext = menu.addAction(tr("conflicts_extmerge", "Resolve with merge tool"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        import os
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_open:
            fp = self.repo.full_path(path)
            if os.path.isfile(fp):
                os.startfile(fp)  # noqa: S606
        elif chosen is act_ours:
            self._on_take("ours")
        elif chosen is act_theirs:
            self._on_take("theirs")
        elif chosen is act_mark:
            self._on_mark()
        elif chosen is act_ext:
            self._on_extmerge()