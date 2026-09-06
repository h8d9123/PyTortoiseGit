"""submoduledlg.py —— SubmoduleDlg：子模块管理对话框。

镜像 TortoiseGit 的 SubmoduleDlg：列出子模块（路径/提交/状态/远程），
支持添加、更新(--init --recursive)、同步、取消初始化；双击打开日志。
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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.submodule import GitSubmodule, SubmoduleEntry
from ..res.strings import format_string, tr
from .logdlg import LogDlg
from .progress import ProgressDialog


class SubmoduleDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.sub = GitSubmodule(repo)
        self.entries: list = []
        self.setWindowTitle(f"{repo.name} — {tr('submodule_title')}")
        self.resize(760, 460)
        self._build_ui()
        self.refresh()

    # ---- UI ----
    def _build_ui(self):
        lay = QVBoxLayout(self)

        opts = QHBoxLayout()
        self.init_box = QCheckBox(tr("submodule_update_init"), self)
        opts.addWidget(self.init_box)
        self.recursive_box = QCheckBox(tr("submodule_update_recursive"), self)
        opts.addWidget(self.recursive_box)
        opts.addStretch(1)
        self._status = QLabel("", self)
        opts.addWidget(self._status)
        lay.addLayout(opts)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels([tr("submodule_path"), tr("submodule_sha"),
                                   tr("submodule_status"), tr("submodule_desc")])
        self.tree.setColumnWidth(0, 220)
        self.tree.setColumnWidth(1, 240)
        self.tree.itemDoubleClicked.connect(self._on_item_double)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_menu)
        lay.addWidget(self.tree, 1)

        btns = QDialogButtonBox(self)
        btn_add = btns.addButton(tr("submodule_add"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_add.clicked.connect(self._on_add)
        btn_update = btns.addButton(tr("submodule_update"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_update.clicked.connect(self._on_update)
        btn_sync = btns.addButton(tr("submodule_sync"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_sync.clicked.connect(self._on_sync)
        btn_deinit = btns.addButton(tr("submodule_deinit"), QDialogButtonBox.ButtonRole.ActionRole)
        btn_deinit.clicked.connect(self._on_deinit)
        btn_close = btns.addButton(QDialogButtonBox.StandardButton.Close)
        btn_close.setText(tr("close"))
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ---- 数据 ----
    def refresh(self):
        self._status.setText(tr("loading"))
        run_async(self.sub.list, args=(True,),
                  on_done=self._on_loaded,
                  on_error=lambda m, _tb: self._status.setText(m), parent=self)

    def _on_loaded(self, entries: list):
        self.entries = entries
        self.tree.clear()
        for e in entries:
            item = QTreeWidgetItem([e.path, e.sha1, e.status_text, e.description])
            item.setData(0, Qt.ItemDataRole.UserRole, e.path)
            self.tree.addTopLevelItem(item)
        self._status.setText("")
        if not entries:
            self._status.setText(tr("submodule_empty"))

    def _selected_path(self) -> str | None:
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None

    # ---- 动作 ----
    def _on_add(self):
        url, ok = QInputDialog.getText(self, tr("submodule_add"), tr("submodule_url"))
        if not ok or not url.strip():
            return
        path = url.strip().rstrip("/").rsplit("/", 1)[-1]
        if path.endswith(".git"):
            path = path[:-4]
        path2, ok2 = QInputDialog.getText(
            self, tr("submodule_add"), tr("submodule_path"), text=path)
        if not ok2 or not path2.strip():
            return
        if self.sub.add(path2.strip(), url.strip()):
            self.refresh()
        else:
            QMessageBox.warning(self, tr("error"), tr("submodule_added"))

    def _on_update(self):
        dlg = ProgressDialog(title="git submodule update", parent=self)
        dlg.set_label("git submodule update")

        def _bg() -> bool:
            okflag = self.sub.update(init=self.init_box.isChecked(),
                                     recursive=self.recursive_box.isChecked())
            if not okflag:
                dlg.log(tr("sync_failed", "更新失败"))
            return okflag

        dlg.run(_bg)
        dlg.on_finish(lambda _ok: self.refresh())
        dlg.exec()

    def _on_sync(self):
        dlg = ProgressDialog(title="git submodule sync", parent=self)
        dlg.set_label("git submodule sync")

        def _bg() -> bool:
            ok = self.sub.sync(recursive=self.recursive_box.isChecked())
            if not ok:
                dlg.log(tr("sync_failed", "同步失败"))
            return ok

        dlg.run(_bg)
        dlg.exec()

    def _on_deinit(self):
        path = self._selected_path()
        if not path:
            return
        if self.sub.deinit(path, force=True):
            self.refresh()
        else:
            QMessageBox.warning(self, tr("error"), tr("submodule_deinited"))

    def _on_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        menu = QMenu(self)
        act_update = menu.addAction(tr("submodule_update", "更新"))
        act_sync = menu.addAction(tr("submodule_sync", "同步"))
        act_deinit = menu.addAction(tr("submodule_deinit", "取消初始化"))
        menu.addSeparator()
        act_copy = menu.addAction(tr("menu_copy_path", "复制路径"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_update:
            self.tree.setCurrentItem(item)
            self._on_update()
        elif chosen is act_sync:
            self.tree.setCurrentItem(item)
            self._on_sync()
        elif chosen is act_deinit:
            self.tree.setCurrentItem(item)
            self._on_deinit()

    def _on_item_double(self, item, _col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        sub_path = self.repo.full_path(path)
        from ..git.repo import Repository as RepoCls
        try:
            sub_repo = RepoCls.open(sub_path)
        except Exception:  # noqa: BLE001
            return
        LogDlg(sub_repo, pathspec=None, parent=self).exec()