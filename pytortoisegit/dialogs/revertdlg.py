"""revertdlg.py —— RevertDlg：还原修改（IDD_REVERT 模板）。

279x232 "Revert"：改动文件复选列表 + Select all + OK/Cancel/Help。
OK 执行 git restore（工作区↔暂存区按状态还原）。
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
    QCheckBox, QDialog, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
)
from ..git.repo import Repository
from ..git.statuslist import GitStatusList, StatusRow
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class RevertDlg(QDialog):
    def __init__(self, repo: Repository, paths=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.paths = list(paths or [])
        self.listctrl = GitStatusList(repo)
        self._build_ui()
        self._populate()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_REVERT")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Revert")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.revert_list = QTreeWidget(self)
        self.revert_list.setColumnCount(2)
        self.revert_list.setHeaderLabels([tr("revert_col_path", "Path"),
                                         tr("revert_col_status", "Status")])
        self.revert_list.setColumnWidth(0, 200)
        self.revert_list.setRootIsDecorated(False)
        self.revert_list.setIndentation(0)
        self.chk_selectall = QCheckBox(tr("revert_selectall", "Select/deselect &all"), self)
        self.chk_selectall.toggled.connect(self._on_select_all)
        self.note_unversioned = QLabel(
            tr("revert_unver", "Note: the folder contains unversioned items"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_revert)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_REVERTLIST": self.revert_list,
            "IDC_SELECTALL": self.chk_selectall,
            "IDC_UNVERSIONEDITEMS": self.note_unversioned,
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

    def _populate(self):
        rows = self.listctrl.fetch(include_unversioned=False)
        self._rows = [r for r in rows if r.state not in ("untracked", "added")]
        for r in self._rows:
            it = QTreeWidgetItem([r.path, r.action])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked)
            it.setData(0, Qt.ItemDataRole.UserRole, r.path)
            self.revert_list.addTopLevelItem(it)
        any_unver = any(r.state == "untracked" for r in
                        self.listctrl.fetch(include_staged=False))
        self.note_unversioned.setVisible(any_unver)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _on_select_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.revert_list.topLevelItemCount()):
            self.revert_list.topLevelItem(i).setCheckState(0, state)

    def _on_revert(self):
        selected = []
        for i in range(self.revert_list.topLevelItemCount()):
            it = self.revert_list.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                selected.append(it.data(0, Qt.ItemDataRole.UserRole))
        if not selected:
            self.reject()
            return
        args = ["restore"] + selected
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label("git restore " + " ".join(selected[:2]) + ("…" if len(selected) > 2 else ""))

        def _bg():
            r = self.repo.runner.run(*args)
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0

        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_REVERTLIST": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_SELECTALL": ("BOTTOM_LEFT",),
    "IDC_UNVERSIONEDITEMS": ("BOTTOM_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}