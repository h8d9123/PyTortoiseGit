"""stashdlg.py —— StashDlg：stash 管理对话框（镜像 TortoiseGit 的 StashDlg）。"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.stash import GitStash, StashEntry
from ..res.strings import tr
from .widgets import DiffView


class StashDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.stash = GitStash(repo)
        self.entries: List[StashEntry] = []
        self._current: Optional[StashEntry] = None

        self.setWindowTitle(f"{repo.name} — {tr('stash_title')}")
        self.resize(860, 560)
        self._build_ui()
        self.refresh()

    # ---- UI ----
    def _build_ui(self):
        root = QVBoxLayout(self)

        create = QHBoxLayout()
        self.msg_edit = QLineEdit(self)
        self.msg_edit.setPlaceholderText(tr("stash_msg"))
        create.addWidget(self.msg_edit, 1)
        self.untracked_box = QCheckBox(tr("stash_untracked"), self)
        create.addWidget(self.untracked_box)
        btn_add = QPushButton(tr("stash_create"), self)
        btn_add.clicked.connect(self._on_create)
        create.addWidget(btn_add)
        root.addLayout(create)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.tree = QTreeWidget(splitter)
        self.tree.setHeaderLabels([tr("stash_ref"), tr("stash_subject"),
                                   tr("stash_date")])
        self.tree.setColumnWidth(0, 90)
        self.tree.setColumnWidth(1, 260)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_menu)
        splitter.addWidget(self.tree)

        self.view = DiffView(splitter)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        btns = QDialogButtonBox(self)
        btn_apply = btns.addButton(tr("stash_apply"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_apply.clicked.connect(self._on_apply)
        btn_pop = btns.addButton(tr("stash_pop"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_pop.clicked.connect(self._on_pop)
        btn_drop = btns.addButton(tr("stash_drop"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_drop.clicked.connect(self._on_drop)
        btn_clear = btns.addButton(tr("stash_clear"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_clear.clicked.connect(self._on_clear)
        self._btn_refresh = btns.addButton(tr("refresh"), QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_refresh.clicked.connect(self.refresh)
        btn_close = btns.addButton(QDialogButtonBox.StandardButton.Close)
        btn_close.setText(tr("close"))
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ---- 数据 ----
    def refresh(self):
        run_async(self._load_bg, on_done=self._on_loaded,
                  on_error=lambda m, _tb: self.view.display_text(m), parent=self)

    def _load_bg(self) -> List[StashEntry]:
        return self.stash.list()

    def _on_loaded(self, entries: List[StashEntry]):
        self.entries = entries
        self._current = None
        self.tree.clear()
        for e in entries:
            item = QTreeWidgetItem([e.gd, e.subject, e.date])
            item.setData(0, Qt.ItemDataRole.UserRole, e.gd)
            self.tree.addTopLevelItem(item)
        if entries:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
            self._current = entries[0]
            self._load_preview(entries[0])
        else:
            self.view.display_text(tr("stash_empty"))

    def _current_entry(self) -> Optional[StashEntry]:
        id_by_gd = {e.gd: e for e in self.entries}
        item = self.tree.currentItem()
        if item is None:
            return None
        return id_by_gd.get(item.data(0, Qt.ItemDataRole.UserRole))

    def _on_selection_changed(self):
        e = self._current_entry()
        if e is not None and e is not self._current:
            self._current = e
            self._load_preview(e)

    def _load_preview(self, entry: StashEntry):
        self.view.display_text(tr("loading"))
        run_async(self.stash.show, args=(entry.gd,),
                  on_done=self.view.display_patch,
                  on_error=lambda m, _tb: self.view.display_text(m), parent=self)

    # ---- 动作 ----
    def _on_create(self):
        msg = self.msg_edit.text().strip()
        ok = self.stash.create(message=msg,
                               include_untracked=self.untracked_box.isChecked())
        if ok:
            self.msg_edit.clear()
            self.untracked_box.setChecked(False)
            self.refresh()
        else:
            QMessageBox.warning(self, tr("error"), tr("stash_created"))

    def _on_apply(self):
        e = self._current_entry()
        if e is None:
            return
        if self.stash.apply(e.gd):
            self.refresh()
        else:
            QMessageBox.warning(self, tr("error"), tr("stash_applied"))

    def _on_pop(self):
        e = self._current_entry()
        if e is None:
            return
        if self.stash.pop(e.gd):
            self.refresh()
        else:
            QMessageBox.warning(self, tr("error"), tr("stash_popped"))

    def _on_drop(self):
        e = self._current_entry()
        if e is None:
            return
        if self.stash.drop(e.gd):
            self.refresh()
        else:
            QMessageBox.warning(self, tr("error"), tr("stash_dropped"))

    def _on_clear(self):
        if not self.entries:
            return
        resp = QMessageBox.question(
            self, tr("confirm"), tr("stash_confirm_clear"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        self.stash.clear()
        self.refresh()

    def _on_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        e = self._current_entry()
        if e is None:
            return
        menu = QMenu(self)
        act_apply = menu.addAction(tr("stash_apply", "应用 (Apply)"))
        act_pop = menu.addAction(tr("stash_pop", "弹出 (Pop)"))
        act_drop = menu.addAction(tr("stash_drop", "删除 (Drop)"))
        menu.addSeparator()
        act_diff = menu.addAction(tr("log_diff", "查看 diff"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_apply:
            self._on_apply()
        elif chosen is act_pop:
            self._on_pop()
        elif chosen is act_drop:
            self._on_drop()
        elif chosen is act_diff:
            from .diffdlg import DiffDlg
            DiffDlg(self.repo, rev1=e.gd, rev2=None, parent=self).show()

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
