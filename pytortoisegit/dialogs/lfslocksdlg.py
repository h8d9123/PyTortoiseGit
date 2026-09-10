"""lfslocksdlg.py —— LfsLocksDlg：LFS 锁管理（IDD_LFS_LOCKS 模板）。

316x216 "LFS Locks"：锁列表 + Select all/Force + Unlock。
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
    QCheckBox, QDialog, QMenu, QPushButton, QTreeWidget, QTreeWidgetItem,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class LfsLocksDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        spec = rc_mod.load_spec("IDD_LFS_LOCKS")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "LFS Locks")
        self._ctl: dict = {}

        self.lock_list = QTreeWidget(self)
        self.lock_list.setColumnCount(2)
        self.lock_list.setHeaderLabels([
            tr("lfs_path", "Path"), tr("lfs_owner", "Owner")])
        self.lock_list.setRootIsDecorated(False)
        self.lock_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lock_list.customContextMenuRequested.connect(self._on_menu)
        self.chk_selectall = QCheckBox(
            tr("lfs_selectall", "Select/deselect &all"), self)
        self.chk_selectall.toggled.connect(self._on_select_all)
        self.chk_force = QCheckBox(tr("lfs_force", "&Force"), self)
        self.btn_unlock = QPushButton(tr("lfs_unlock", "&Unlock"), self)
        self.btn_unlock.clicked.connect(self._on_unlock)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_LOCKSLIST": self.lock_list,
            "IDC_SELECTALL": self.chk_selectall,
            "IDC_FORCE": self.chk_force,
            "IDC_LFS_UNLOCK": self.btn_unlock,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def _on_select_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.lock_list.topLevelItemCount()):
            self.lock_list.topLevelItem(i).setCheckState(0, state)

    def _on_unlock(self):
        paths = []
        for i in range(self.lock_list.topLevelItemCount()):
            it = self.lock_list.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                paths.append(it.text(0))
        for p in paths:
            args = ["lfs", "unlock"]
            if self.chk_force.isChecked():
                args.append("--force")
            args.append(p)
            self.repo.runner.run(*args)
        self.accept()

    def _on_menu(self, pos):
        item = self.lock_list.itemAt(pos)
        if item is None:
            return
        path = item.text(0)
        menu = QMenu(self)
        act_unlock = menu.addAction(tr("lfs_unlock", "&Unlock"))
        act_copy = menu.addAction(tr("menu_copy_path", "Copy path"))
        chosen = menu.exec(self.lock_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_unlock:
            args = ["lfs", "unlock"]
            if self.chk_force.isChecked():
                args.append("--force")
            args.append(path)
            self.repo.runner.run(*args)
            self.accept()