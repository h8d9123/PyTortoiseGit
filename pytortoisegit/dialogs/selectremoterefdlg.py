"""selectremoterefdlg.py —— SelectRemoteRefDlg：选择远端引用（IDD_SELECTREMOTEREF 模板）。

293x66 "Select remote ref - TortoiseGit"：远端名 + 远端分支。
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
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QLineEdit, QPushButton
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class SelectRemoteRefDlg(QDialog):
    def __init__(self, repo: Repository, remote: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        spec = rc_mod.load_spec("IDD_SELECTREMOTEREF")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Select remote ref - TortoiseGit")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.label = QLabel(tr("sel_remote", "Remote:"), self)
        self.remote_edit = QLineEdit(self)
        self.remote_edit.setText(remote)
        self.remote_branch = QComboBox(self)
        self.remote_branch.setEditable(True)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.selected = None

        mapping = {
            "IDC_STATIC": self.label,
            "IDC_EDIT_REMOTE": self.remote_edit,
            "IDC_REMOTE_BRANCH": self.remote_branch,
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

        out = self.repo.runner.run(
            "for-each-ref", "--format=%(refname:short)",
            "refs/remotes").stdout or ""
        refs = [x.strip() for x in out.splitlines() if x.strip()]
        self.remote_branch.addItems(refs)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def accept(self):
        self.selected = self.remote_branch.currentText().strip()
        super().accept()


_ANCHORS = {
    "IDC_REMOTE_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
}