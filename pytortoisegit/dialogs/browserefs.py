"""browserefs.py —— BrowseRefsDlg：分支/标签浏览与切换。

镜像 TortoiseGit 的 BrowseRefsDlg。
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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.rev import GitRevLoglist, RefInfo
from ..res.strings import tr


class BrowseRefsDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_branch = repo.current_branch()
        self.setWindowTitle(f"{repo.name} — {tr('browse_refs', '分支与标签')}")
        self.resize(720, 520)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("browse_current", "当前分支") + "：", self))
        self._curr = QLabel(self.current_branch, self)
        head.addWidget(self._curr)
        head.addStretch(1)
        lay.addLayout(head)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([tr("ref_name", "名称"), tr("ref_target", "指向"), tr("ref_subject", "信息")])
        self.tree.setColumnWidth(0, 220)
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_menu)
        lay.addWidget(self.tree, 1)

        box = QDialogButtonBox(self)
        self._btn_checkout = box.addButton(
            tr("browse_checkout", "检出"), QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_checkout.clicked.connect(self._checkout_selected)
        self._btn_delete = box.addButton(
            tr("browse_delete", "删除…"), QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_delete.clicked.connect(self._delete_selected)
        sep = box.addButton(QDialogButtonBox.StandardButton.Close)
        sep.setText(tr("close"))
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _load(self):
        run_async(self._load_bg, on_done=self._on_loaded, parent=self)

    def _load_bg(self) -> dict:
        log = GitRevLoglist(self.repo)
        log.load_refs()
        return {full: r for full, r in log.refs.items()}

    def _on_loaded(self, refs: dict):
        self.tree.clear()
        by_type = {
            "branch": [],
            "remote": [],
            "tag": [],
        }
        for full, r in refs.items():
            by_type.setdefault(r.ref_type, []).append(r)
        for tname, label in (("branch", tr("browse_branches", "分支")),
                             ("remote", tr("browse_remotes", "远程分支")),
                             ("tag", tr("browse_tags", "标签"))):
            group = by_type.get(tname, [])
            if not group:
                continue
            top = QTreeWidgetItem([label, "", ""])
            self.tree.addTopLevelItem(top)
            for r in sorted(group, key=lambda x: x.shortname):
                subj = self._subject_of(r)
                child = QTreeWidgetItem([r.shortname, r.target[:8], subj])
                child.setData(0, Qt.ItemDataRole.UserRole, r.fullname)
                child.setData(0, Qt.ItemDataRole.UserRole + 1, r.ref_type)
                top.addChild(child)
            top.setExpanded(True)

    def _subject_of(self, ref: RefInfo) -> str:
        if ref.ref_type == "tag":
            return ""
        return ""

    def _selected(self):
        item = self.tree.currentItem()
        if item is None:
            return None, None
        fullname = item.data(0, Qt.ItemDataRole.UserRole)
        if fullname is None:
            return None, None
        rtype = item.data(0, Qt.ItemDataRole.UserRole + 1)
        return fullname, rtype

    def _checkout_selected(self):
        fullname, rtype = self._selected()
        if fullname is None:
            return
        if rtype == "branch":
            args = ["checkout", fullname.replace("refs/heads/", "")]
        elif rtype == "remote":
            from PySide6.QtWidgets import QMessageBox
            from ..res.strings import format_string
            QMessageBox.information(
                self, tr("information"),
                format_string(tr("browse_checkout_remote", "无法直接检出远程分支 {name}，请用 git checkout -b <local> {name}"),
                              name=fullname))
            return
        else:
            args = ["checkout", fullname.replace("refs/tags/", "")]
        result = self.repo.runner.run(*args)
        if result.returncode != 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("error"), result.stderr)
            return
        self.current_branch = self.repo.current_branch()
        self._curr.setText(self.current_branch)

    def _delete_selected(self):
        fullname, rtype = self._selected()
        if fullname is None:
            return
        name = fullname.replace("refs/heads/", "").replace("refs/tags/", "").replace("refs/remotes/", "")
        from PySide6.QtWidgets import QMessageBox
        resp = QMessageBox.question(
            self, tr("confirm"), f"确定删除「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        if rtype == "branch":
            args = ["branch", "-d", name]
        elif rtype == "tag":
            args = ["tag", "-d", name]
        else:
            args = ["branch", "-dr", fullname.replace("refs/remotes/", "")]
        result = self.repo.runner.run(*args)
        if result.returncode != 0:
            QMessageBox.warning(self, tr("error"), result.stderr)
            return
        self._load()

    def _on_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        fullname, rtype = self._selected()
        if fullname is None:
            return
        self.tree.setCurrentItem(item)
        menu = QMenu(self)
        act_checkout = menu.addAction(tr("browse_checkout", "检出"))
        act_delete = menu.addAction(tr("browse_delete", "删除…"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is act_checkout:
            self._checkout_selected()
        elif chosen is act_delete:
            self._delete_selected()