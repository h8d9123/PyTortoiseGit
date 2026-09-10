"""worktreecreatedlg.py —— WorktreeCreateDlg：新建工作树（IDD_WORKTREE_CREATE 模板）。

296x188 "New Worktree"：Location 目录 + Base On（HEAD/Branch/Tag/Commit）
+ Options（Create New Branch/Checkout/Force/Detach）。
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
    QCheckBox, QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QRadioButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from ..utils.pick import pick_dir
from .resize import AnchorLayout
from .progress import ProgressDialog


class WorktreeCreateDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_WORKTREE_CREATE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "New Worktree")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.dir_label = QLabel(tr("wt_dir", "Directory:"), self)
        self.dir_edit = QLineEdit(self)
        self.dir_edit.setText(os.path.join(
            os.path.dirname(self.repo.root), os.path.basename(self.repo.root) + "-wt"))
        self.btn_browse_dir = QPushButton(tr("wt_browse", "Bro&wse..."), self)
        self.btn_browse_dir.clicked.connect(self._pick_dir)

        self.rd_head = QRadioButton(tr("wt_head", "&HEAD"), self)
        self.rd_branch = QRadioButton(tr("wt_branch", "&Branch"), self)
        self.branch_combo = QComboBox(self)
        self.btn_browse_ref = QPushButton("...", self)
        self.rd_tags = QRadioButton(tr("wt_tag", "&Tag"), self)
        self.tags_combo = QComboBox(self)
        self.rd_version = QRadioButton(tr("wt_commit", "&Commit"), self)
        self.version_combo = QComboBox(self)
        self.btn_show = QPushButton("...", self)

        self.chk_newbranch = QCheckBox(tr("wt_newbranch", "Create &New Branch"), self)
        self.newbranch_edit = QLineEdit(self)
        self.chk_checkout = QCheckBox(tr("wt_checkout", "&Checkout"), self)
        self.chk_force = QCheckBox(tr("wt_force", "&Force"), self)
        self.chk_detach = QCheckBox(tr("wt_detach", "&Detach"), self)
        self.chk_checkout.setChecked(True)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_create)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_LABEL_BRANCH": self.dir_label,
            "IDC_WORKTREE_DIR": self.dir_edit,
            "IDC_BUTTON_DIR": self.btn_browse_dir,
            "IDC_RADIO_HEAD": self.rd_head,
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
            "IDC_CHECK_CHECKOUT": self.chk_checkout,
            "IDC_CHECK_FORCE": self.chk_force,
            "IDC_CHECK_DETACH": self.chk_detach,
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
        self.branch_combo.addItems([r for r in refs if r.startswith("heads/")])
        self.tags_combo.addItems([r[5:] for r in refs if r.startswith("tags/")])
        self.version_combo.addItems(refs + ["HEAD"])
        self.rd_head.setChecked(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _pick_dir(self):
        d = pick_dir(self, tr("wt_dir", "Worktree directory"), self.repo.root)
        if d:
            self.dir_edit.setText(d)

    def _target(self) -> str:
        if self.rd_branch.isChecked():
            return self.branch_combo.currentText()
        if self.rd_tags.isChecked():
            return self.tags_combo.currentText()
        if self.rd_version.isChecked():
            return self.version_combo.currentText()
        return "HEAD"

    def _on_create(self):
        path = self.dir_edit.text().strip()
        if not path:
            return
        args = ["worktree", "add"]
        if self.chk_force.isChecked():
            args.append("--force")
        if self.chk_detach.isChecked():
            args.append("--detach")
        branch = self.newbranch_edit.text().strip()
        if self.chk_newbranch.isChecked() and branch and branch != self._target():
            args.append("-b")
            args.append(branch)
        args.append(path)
        args.append(self._target())
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
    "IDC_GROUP_OPTION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_EDIT_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}