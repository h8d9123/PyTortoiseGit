"""repobrowserdlg.py —— RepositoryBrowserDlg：仓库浏览器（IDD_REPOSITORY_BROWSER 模板）。

415x279 "Repository Browser"：仓库树（目录）+ 文件列表 + 修订按钮。
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
    QDialog, QLabel, QLineEdit, QMenu, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)
from ..git.repo import Repository
from ..git.rev import GitRevLoglist
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class RepositoryBrowserDlg(QDialog):
    def __init__(self, repo: Repository, rev: str = "HEAD", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.rev = rev
        self._build_ui()
        self._load()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_REPOSITORY_BROWSER")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Repository Browser")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.path_label = QLabel(tr("repobrowser_path", "Path:"), self)
        self.url_edit = QLineEdit(self)
        self.url_edit.setReadOnly(True)
        self.ref_label = QLabel(tr("repobrowser_rev", "Revision:"), self)
        self.btn_revision = QPushButton(self.rev, self)
        self.btn_revision.clicked.connect(self._pick_rev)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels([tr("repobrowser_tree", "Path")])
        self.tree.itemClicked.connect(self._on_tree_clicked)
        self.list = QTreeWidget(self)
        self.list.setColumnCount(3)
        self.list.setHeaderLabels([
            tr("repobrowser_name", "Name"), tr("repobrowser_mode", "Mode"),
            tr("repobrowser_size", "Size")])
        self.list.setRootIsDecorated(False)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_list_menu)
        self.info_label = QLabel("", self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_STATIC_REPOURL": self.path_label,
            "IDC_REPOBROWSER_URL": self.url_edit,
            "IDC_STATIC_REF": self.ref_label,
            "IDC_BUTTON_REVISION": self.btn_revision,
            "IDC_REPOTREE": self.tree,
            "IDC_REPOLIST": self.list,
            "IDC_INFOLABEL": self.info_label,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _load(self):
        self.url_edit.setText(self.repo.root)
        self.tree.clear()
        self.list.clear()
        out = self.repo.runner.run("ls-tree", self.rev).stdout or ""
        for line in out.splitlines():
            meta, name = line.split("\t", 1) if "\t" in line else (line, "")
            mode, _, oid = meta.split(" ", 2) if len(meta.split(" ")) == 3 else ("", "", "")
            if mode == "040000" or name and oid and mode.startswith("04"):
                it = QTreeWidgetItem([name.rstrip("/")])
                it.setData(0, Qt.ItemDataRole.UserRole, (name.rstrip("/"), oid, "tree"))
                self.tree.addTopLevelItem(it)
            else:
                it = QTreeWidgetItem([name, mode, ""])
                it.setData(0, Qt.ItemDataRole.UserRole, (name, oid, "blob"))
                self.list.addTopLevelItem(it)
        self.info_label.setText(
            f"{self.rev[:7]} · {self.repo.current_branch()}")

    def _on_list_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        name = item.text(0) if data is None else (data[0] if isinstance(data, tuple) else str(data))
        menu = QMenu(self)
        act_copy = menu.addAction(tr("menu_copy_path", "Copy path"))
        act_open = menu.addAction(tr("menu_open", "View blob content"))
        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(name)
        elif chosen is act_open and isinstance(data, tuple) and len(data) > 1:
            import subprocess
            from PySide6.QtWidgets import QMessageBox
            out = self.repo.runner.run("cat-file", "-p", data[1]).stdout or ""
            QMessageBox.information(self, name[:40], out[:4000])

    def _on_tree_clicked(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        _, oid, _k = data
        out = self.repo.runner.run("ls-tree", oid).stdout or ""
        self.list.clear()
        for line in out.splitlines():
            meta, name = line.split("\t", 1) if "\t" in line else (line, "")
            mode, _, child_oid = meta.split(" ", 2) if len(meta.split(" ")) == 3 else ("", "", "")
            it = QTreeWidgetItem([name, mode, ""])
            it.setData(0, Qt.ItemDataRole.UserRole, (name, child_oid, "blob"))
            self.list.addTopLevelItem(it)

    def _pick_rev(self):
        try:
            revs = GitRevLoglist(self.repo)
            revs.load(limit=500)
            items = [c.short_hash for c in revs]
        except Exception:
            return
        if items:
            self.rev = items[0]
            self.btn_revision.setText(self.rev)
            self._load()


_ANCHORS = {
    "IDC_REPOTREE": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_REPOLIST": ("TOP_RIGHT", "BOTTOM_RIGHT"),
    "IDC_INFOLABEL": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}