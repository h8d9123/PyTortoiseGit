"""gitswitchdlg.py —— GitSwitchDlg：切换/签出（IDD_GITSWITCH 模板）。

296x185 "Switch/Checkout"：Switch To（Branch/Tag/Commit）+ Option
（Create New Branch/Force/Merge/Track/Override）。
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
    QGroupBox,
    QCheckBox, QComboBox, QDialog, QLineEdit, QPushButton, QRadioButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class GitSwitchDlg(QDialog):
    def __init__(self, repo: Repository, parent=None, commit: str | None = None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        if commit:
            self.rd_version.setChecked(True)
            self.version_combo.setCurrentText(commit)

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_GITSWITCH")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Switch/Checkout")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.grp_baseon = QGroupBox(tr("switch_group_baseon", "Switch To"), self)

        self.rd_branch = QRadioButton(tr("switch_branch", "&Branch"), self)
        self.branch_combo = QComboBox(self)
        self.btn_browse_ref = QPushButton("...", self)
        self.rd_tags = QRadioButton(tr("switch_tag", "&Tag"), self)
        self.tags_combo = QComboBox(self)
        self.rd_version = QRadioButton(tr("switch_commit", "&Commit"), self)
        self.version_combo = QComboBox(self)
        self.btn_show = QPushButton("...", self)

        self.chk_newbranch = QCheckBox(tr("switch_newbranch", "Create &New Branch"), self)
        self.newbranch_edit = QLineEdit(self)
        self.chk_force = QCheckBox(
            tr("switch_force", "Overwrite working tree changes (&force)"), self)
        self.chk_merge = QCheckBox(tr("switch_merge", "&Merge"), self)
        self.chk_track = QCheckBox(tr("switch_track", "T&rack"), self)
        self.chk_override = QCheckBox(
            tr("switch_override", "&Override branch if exists"), self)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_switch)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_GROUP_BASEON": self.grp_baseon,
            "IDC_RADIO_BRANCH": self.rd_branch,
            "IDC_COMBOBOXEX_BRANCH": self.branch_combo,
            "IDC_BUTTON_BROWSE_REF": self.btn_browse_ref,
            "IDC_RADIO_TAGS": self.rd_tags,
            "IDC_COMBOBOXEX_TAGS": self.tags_combo,
            "IDC_RADIO_VERSION": self.rd_version,
            "IDC_COMBOBOXEX_VERSION": self.version_combo,
            "IDC_BUTTON_SHOW": self.btn_show,
            "IDC_CHECK_BRANCH": self.chk_newbranch,
            "IDC_EDIT_BRANCH": self.newbranch_edit,
            "IDC_CHECK_FORCE": self.chk_force,
            "IDC_CHECK_MERGE": self.chk_merge,
            "IDC_CHECK_TRACK": self.chk_track,
            "IDC_CHECK_BRANCHOVERRIDE": self.chk_override,
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

        out = self.repo.runner.run("for-each-ref",
                                   "--format=%(refname:short)").stdout or ""
        refs = [x.strip() for x in out.splitlines() if x.strip()]
        self.branch_combo.addItems([r for r in refs if r.startswith(("heads/",))])
        self.branch_combo.setEditable(True)
        self.tags_combo.addItems([r[5:] for r in refs if r.startswith("tags/")])
        self.version_combo.addItems([r for r in refs if r.startswith(("heads/", "tags/"))] + ["HEAD"])
        self.version_combo.setEditable(True)
        self.rd_branch.setChecked(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _target(self) -> str:
        if self.rd_tags.isChecked():
            return self.tags_combo.currentText()
        if self.rd_version.isChecked():
            return self.version_combo.currentText()
        return self.branch_combo.currentText()

    def _on_switch(self):
        target = self._target().strip()
        if not target:
            return
        args = ["checkout"]
        if self.chk_newbranch.isChecked():
            args.append("-b")
            args.append(self.newbranch_edit.text().strip() or "newbranch")
        if self.chk_force.isChecked() or self.chk_override.isChecked():
            args.append("-f")
        if self.chk_track.isChecked():
            args.append("--track")
        args.append(target)
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label("git " + " ".join(args))
        def _bg():
            r = self.repo.runner.run(*args)
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0
        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_GROUP_BASEON": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_GROUP_OPTION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_EDIT_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}