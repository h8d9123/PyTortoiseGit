"""renamedlg.py —— RenameDlg：重命名（IDD_RENAME 模板）。

257x69 "Rename - TortoiseGit"：新名称 + browse。OK 执行 git mv/重命名。
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
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class RenameDlg(QDialog):
    def __init__(self, repo: Repository, paths=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.paths = list(paths or [])
        spec = rc_mod.load_spec("IDD_RENAME")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Rename - TortoiseGit")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.info_label = QLabel("", self)
        self.name_label = QLabel(tr("rename_name", "New &name:"), self)
        self.name_edit = QLineEdit(self)
        if self.paths:
            self.name_edit.setText(self.paths[0])
        self.btn_browse = QPushButton(tr("rename_browse", "&..."), self)
        self.btn_browse.clicked.connect(self._browse)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_rename)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)

        mapping = {
            "IDC_RENINFOLABEL": self.info_label,
            "IDC_LABEL": self.name_label,
            "IDC_NAME": self.name_edit,
            "IDC_BUTTON_BROWSE_REF": self.btn_browse,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
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

    def _browse(self):
        import os
        from ..utils.pick import pick_file
        d = pick_file(self, tr("rename_browse", "Select file"), "")
        if d:
            self.name_edit.setText(d)

    def _on_rename(self):
        if not self.paths:
            self.reject()
            return
        old = self.paths[0]
        new = self.name_edit.text().strip()
        if not new or new == old:
            self.reject()
            return
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label(f"git mv {old} {new}")
        def _bg():
            r = self.repo.runner.run("mv", old, new)
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0
        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_RENINFOLABEL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_LABEL": ("TOP_LEFT",),
    "IDC_NAME": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_REF": ("TOP_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
}