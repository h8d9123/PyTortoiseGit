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
        from .submoduleadddlg import SubmoduleAddDlg
        dlg = SubmoduleAddDlg(self.repo, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not self.sub.add(dlg.path, dlg.repository,
                            force=dlg.force, branch=dlg.branch or None):
            QMessageBox.warning(self, tr("error"), tr("submodule_added"))
            return
        if dlg.putty_key:
            # 添加成功后写入子模块的 remote.origin.puttykeyfile（对齐原版）
            import os
            from ..git.git import GitRunner
            sub_root = os.path.join(self.repo.root, dlg.path)
            GitRunner(cwd=sub_root).run(
                "config", "remote.origin.puttykeyfile", dlg.putty_key)
        self.refresh()

    def _on_update(self):
        from .submoduleupdatedlg import SubmoduleUpdateDlg
        dlg = SubmoduleUpdateDlg(
            self.repo, parent=self,
            init=self.init_box.isChecked(),
            recursive=self.recursive_box.isChecked())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        args = ["submodule", "update"]
        for flag, on in (("--init", dlg.init), ("--recursive", dlg.recursive),
                         ("--force", dlg.force), ("--no-fetch", dlg.no_fetch),
                         ("--merge", dlg.merge), ("--rebase", dlg.rebase),
                         ("--remote", dlg.remote)):
            if on:
                args.append(flag)
        if not dlg.all_selected:
            args += ["--", *dlg.paths]
        dlg_prog = ProgressDialog(title="git submodule update", parent=self)
        dlg_prog.set_label("git " + " ".join(args))

        def _bg() -> bool:
            result = self.repo.runner.run(*args)
            if result.stdout:
                dlg_prog.log(result.stdout)
            if result.stderr:
                dlg_prog.log(result.stderr)
            return result.returncode == 0

        dlg_prog.run(_bg)
        dlg_prog.on_finish(lambda _ok: self.refresh())
        dlg_prog.exec()

    def _on_sync(self):
        dlg = ProgressDialog(title="git submodule sync", parent=self)
        dlg.set_label("git submodule sync")

        def _bg() -> bool:
            ok = self.sub.sync(recursive=self.recursive_box.isChecked())
            if not ok:
                dlg.log(tr("sync_failed", "Sync failed"))
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

    def _build_menu(self):
        """构建子模块右键菜单，返回 (menu, {action: key})，便于测试。"""
        menu = QMenu(self)
        acts = {}
        acts[menu.addAction(tr("submodule_update", "Update"))] = "update"
        acts[menu.addAction(tr("submodule_sync", "Sync"))] = "sync"
        acts[menu.addAction(tr("submodule_deinit", "Deinit"))] = "deinit"
        menu.addSeparator()
        acts[menu.addAction(tr("menu_copy_path", "Copy path"))] = "copy"
        return menu, acts

    def _handle_menu(self, key: str, path: str):
        from ..utils.clipboard import ClipboardHelper
        if key == "copy":
            ClipboardHelper().copy_text(path)
        elif key == "update":
            self._on_update()
        elif key == "sync":
            self._on_sync()
        elif key == "deinit":
            self._on_deinit()

    def _on_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        self.tree.setCurrentItem(item)
        menu, acts = self._build_menu()
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        key = acts.get(chosen)
        if key:
            self._handle_menu(key, path)

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
        from .modeless import show_modeless
        show_modeless(LogDlg(sub_repo, pathspec=None, parent=self))