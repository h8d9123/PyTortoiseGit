"""pushdlg.py —— PushDlg：推送到远端（IDD_PUSH 模板）。

311x277 "Push"：Ref 组（push all/本地分支/远端分支）+
Destination 组（Remote/URL）+ Options 组（force/tags/putty/upstream/submodules/push option）。
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
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QLabel, QLineEdit, QPushButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class PushDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_PUSH")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Push")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        # Ref group
        self.chk_push_all = QCheckBox(tr("push_all", "&Push all branches"), self)
        self.local_label = QLabel(tr("push_local", "&Local:"), self)
        self.local_combo = QComboBox(self)
        self.btn_browse_local = QPushButton("...", self)
        self.remote_label = QLabel(tr("push_remote", "&Remote:"), self)
        self.remote_combo = QComboBox(self)
        self.btn_browse_remote = QPushButton("...", self)

        # Destination group
        self.rd_remote = QCheckBox(tr("push_rd_remote", "Re&mote:"), self)
        self.remote_name_combo = QComboBox(self)
        self.btn_manage = QPushButton(tr("push_manage", "Mana&ge"), self)
        self.rd_url = QCheckBox(tr("push_rd_url", "Arbitrary &URL:"), self)
        self.url_edit = QLineEdit(self)

        # Options group
        self.chk_force_with_lease = QCheckBox(tr("push_force_lease", "Force &with lease"), self)
        self.chk_force = QCheckBox(tr("push_force", "&Force"), self)
        self.chk_tags = QCheckBox(tr("push_tags", "Include &Tags"), self)
        self.chk_putty = QCheckBox(tr("push_putty", "&Autoload Putty Key"), self)
        self.chk_set_upstream = QCheckBox(tr("push_upstream", "&Set upstream/track remote branch"), self)
        self.chk_push_remote = QCheckBox(tr("push_push_remote", "Always push to selected remote archive"), self)
        self.chk_push_branch = QCheckBox(tr("push_push_branch", "Always push to selected remote branch"), self)
        self.sub_label = QLabel(tr("push_sub", "Recurse submodule"), self)
        self.sub_combo = QComboBox(self)
        self.sub_combo.addItems(["Check ", "On-demand", "Off"])
        self.push_option_label = QLabel(tr("push_option", "Push &option:"), self)
        self.push_option_edit = QLineEdit(self)

        # Buttons
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_push)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self._status = QLabel(self)
        self._status.setText(tr("push_ready", "就绪"))
        self._details = QLabel(self)

        mapping = {
            "IDC_PUSHALL": self.chk_push_all,
            "IDC_STATIC_SOURCE": self.local_label,
            "IDC_BRANCH_SOURCE": self.local_combo,
            "IDC_BUTTON_BROWSE_SOURCE_BRANCH": self.btn_browse_local,
            "IDC_STATIC_REMOTE": self.remote_label,
            "IDC_BRANCH_REMOTE": self.remote_combo,
            "IDC_BUTTON_BROWSE_DEST_BRANCH": self.btn_browse_remote,
            "IDC_RD_REMOTE": self.rd_remote,
            "IDC_REMOTE": self.remote_name_combo,
            "IDC_REMOTE_MANAGE": self.btn_manage,
            "IDC_RD_URL": self.rd_url,
            "IDC_URL": self.url_edit,
            "IDC_FORCE_WITH_LEASE": self.chk_force_with_lease,
            "IDC_FORCE": self.chk_force,
            "IDC_TAGS": self.chk_tags,
            "IDC_PUTTYKEY_AUTOLOAD": self.chk_putty,
            "IDC_PROC_PUSH_SET_UPSTREAM": self.chk_set_upstream,
            "IDC_PROC_PUSH_SET_PUSHREMOTE": self.chk_push_remote,
            "IDC_PROC_PUSH_SET_PUSHBRANCH": self.chk_push_branch,
            "IDC_STATIC_RECURSE_SUBMODULES": self.sub_label,
            "IDC_COMBOBOX_RECURSE_SUBMODULES": self.sub_combo,
            "IDC_STATIC_PUSHOPTION": self.push_option_label,
            "IDC_PUSHOPTION": self.push_option_edit,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        self._status.setObjectName("IDC_STATIC_STATUS")
        self._status.setParent(self)

        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _PUSH_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        self._populate()

    def _populate(self):
        branches = self.repo.runner.run("for-each-ref",
                                         "--format=%(refname:short)").stdout or ""
        refs = [b.strip() for b in branches.splitlines() if b.strip()]
        cur = self.repo.current_branch()
        self.local_combo.addItems(refs or [cur])
        if cur in refs:
            self.local_combo.setCurrentText(cur)
        self.remote_combo.addItems(["origin"])
        self.remote_name_combo.addItems(["origin"])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _on_push(self):
        remote = self.remote_name_combo.currentText() or "origin"
        local_branch = self.local_combo.currentText()
        if self.rd_url.isChecked() and self.url_edit.text():
            remote = self.url_edit.text()
        args = ["push", remote]
        if self.chk_push_all.isChecked():
            args.append("--all")
        if self.chk_force.isChecked():
            args.append("--force")
        if self.chk_force_with_lease.isChecked():
            args.append("--force-with-lease")
        if self.chk_tags.isChecked():
            args.append("--tags")
        if self.chk_set_upstream.isChecked():
            args.append("--set-upstream")
        if local_branch:
            args.append(f"{local_branch}:{local_branch}")
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label("git " + " ".join(args))
        def _bg():
            r = self.repo.runner.run_interactive(*args)
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0
        dlg.run(_bg)
        dlg.exec()
        self.accept()


_PUSH_ANCHORS = {
    "IDC_PUSHALL": ("TOP_LEFT",),
    "IDC_STATIC_SOURCE": ("TOP_LEFT",),
    "IDC_BRANCH_SOURCE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_SOURCE_BRANCH": ("TOP_RIGHT",),
    "IDC_STATIC_REMOTE": ("TOP_LEFT",),
    "IDC_BRANCH_REMOTE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_DEST_BRANCH": ("TOP_RIGHT",),
    "IDC_RD_REMOTE": ("TOP_LEFT",),
    "IDC_REMOTE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REMOTE_MANAGE": ("TOP_RIGHT",),
    "IDC_RD_URL": ("TOP_LEFT",),
    "IDC_URL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_FORCE_WITH_LEASE": ("TOP_LEFT",),
    "IDC_FORCE": ("TOP_LEFT",),
    "IDC_TAGS": ("TOP_LEFT",),
    "IDC_PUTTYKEY_AUTOLOAD": ("TOP_LEFT",),
    "IDC_PROC_PUSH_SET_UPSTREAM": ("TOP_LEFT",),
    "IDC_PROC_PUSH_SET_PUSHREMOTE": ("TOP_LEFT",),
    "IDC_PROC_PUSH_SET_PUSHBRANCH": ("TOP_LEFT",),
    "IDC_STATIC_RECURSE_SUBMODULES": ("TOP_LEFT",),
    "IDC_COMBOBOX_RECURSE_SUBMODULES": ("TOP_LEFT",),
    "IDC_STATIC_PUSHOPTION": ("TOP_LEFT",),
    "IDC_PUSHOPTION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}