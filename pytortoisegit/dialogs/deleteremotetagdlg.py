"""deleteremotetagdlg.py —— DeleteRemoteTagDlg：删除远端标签（IDD_DELETEREMOTETAG 模板）。

225x121 "Delete remote tag - TortoiseGit"：远端名 + 标签列表 + Delete。
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
    QCheckBox, QDialog, QLabel, QLineEdit, QMenu, QPushButton, QTreeWidget,
    QTreeWidgetItem,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class DeleteRemoteTagDlg(QDialog):
    def __init__(self, repo: Repository, remote: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        spec = rc_mod.load_spec("IDD_DELETEREMOTETAG")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Delete remote tag - TortoiseGit")
        self._ctl: dict = {}

        self.label = QLabel(tr("deletetag_remote", "Remote:"), self)
        self.remote_edit = QLineEdit(self)
        self.remote_edit.setText(remote or "origin")
        self.tags_list = QTreeWidget(self)
        self.tags_list.setColumnCount(1)
        self.tags_list.setHeaderLabels([tr("deletetag_tag", "Tag")])
        self.tags_list.setRootIsDecorated(False)
        self.tags_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tags_list.customContextMenuRequested.connect(self._on_menu)
        self.chk_selectall = QCheckBox(tr("deletetag_selectall", "Select/deselect &all"), self)
        self.chk_selectall.toggled.connect(self._on_select_all)
        self.btn_delete = QPushButton(tr("deletetag_delete", "&Delete"), self)
        self.btn_delete.setDefault(True)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_close = QPushButton(tr("deletetag_close", "Close"), self)
        self.btn_close.clicked.connect(self.reject)

        mapping = {
            "IDC_STATIC": self.label,
            "IDC_EDIT_REMOTE": self.remote_edit,
            "IDC_LIST_TAGS": self.tags_list,
            "IDC_SELECTALL": self.chk_selectall,
            "IDOK": self.btn_delete,
            "IDCANCEL": self.btn_close,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

        remote_tags = self.repo.runner.run(
            "ls-remote", self.remote_edit.text(), "refs/tags/*").stdout or ""
        names = []
        for line in remote_tags.splitlines():
            oid, _, ref = line.partition("\t")
            if ref.startswith("refs/tags/"):
                names.append(ref[len("refs/tags/"):])
        for n in names:
            it = QTreeWidgetItem([n])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked)
            it.setData(0, Qt.ItemDataRole.UserRole, n)
            self.tags_list.addTopLevelItem(it)

    def _on_select_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.tags_list.topLevelItemCount()):
            self.tags_list.topLevelItem(i).setCheckState(0, state)

    def _on_delete(self):
        remote = self.remote_edit.text().strip()
        for i in range(self.tags_list.topLevelItemCount()):
            it = self.tags_list.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                tag = it.data(0, Qt.ItemDataRole.UserRole)
                self.repo.runner.run("push", remote, f":refs/tags/{tag}")
        self.accept()

    def _on_menu(self, pos):
        item = self.tags_list.itemAt(pos)
        if item is None:
            return
        tag = item.data(0, Qt.ItemDataRole.UserRole)
        if not tag:
            return
        menu = QMenu(self)
        act_del = menu.addAction(tr("deletetag_delete", "&Delete"))
        act_copy = menu.addAction(tr("menu_copy_tag", "复制标签名"))
        chosen = menu.exec(self.tags_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(tag)
        elif chosen is act_del:
            remote = self.remote_edit.text().strip()
            self.repo.runner.run("push", remote, f":refs/tags/{tag}")
            for i in range(self.tags_list.topLevelItemCount()):
                if self.tags_list.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == tag:
                    self.tags_list.takeTopLevelItem(i)
                    break