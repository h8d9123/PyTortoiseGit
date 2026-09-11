"""pulldlg.py —— PullFetchDlg：拉取/合并远端（IDD_PULLFETCH 模板）。

327x223 "Pull/Fetch"：Remote 组（Remote combo/URL/Remote Branch）+
Options 组（squash/nofastforward/nocommit/depth/ffonly/tags/prune/putty/rebase）。
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
    QCheckBox, QComboBox, QDialog, QGroupBox, QLabel, QLineEdit, QPushButton,
    QSpinBox,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class PullFetchDlg(QDialog):
    def __init__(self, repo: Repository, fetch_only: bool = False, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.fetch_only = fetch_only
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_PULLFETCH")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(tr("pullfetch_title", "Pull/Fetch"))
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        # 分组框（与其它控件同级，先创建置于底层，对齐 IDD_PULLFETCH）
        self.grp_remote = QGroupBox(tr("pull_group_remote", "Remote"), self)
        self.grp_options = QGroupBox(tr("pull_group_options", "Options"), self)

        self.rd_remote = QCheckBox(tr("pull_remote", "&Remote:"), self)
        self.remote_combo = QComboBox(self)
        self.rd_other = QCheckBox(tr("pull_url", "Arbitrary &URL:"), self)
        self.other_edit = QLineEdit(self)
        self.static_branch = QLabel(tr("pull_branch", "Remote &Branch:"), self)
        self.remote_branch_edit = QLineEdit("master", self)
        self.btn_browse_ref = QPushButton("...", self)

        self.chk_squash = QCheckBox(tr("pull_squash", "&Squash"), self)
        self.chk_noff = QCheckBox(tr("pull_noff", "No &Fast Forward"), self)
        self.chk_nocommit = QCheckBox(tr("pull_nocommit", "No Co&mmit"), self)
        self.chk_depth = QCheckBox(tr("pull_depth", "Depth"), self)
        self.depth_edit = QSpinBox(self)
        self.depth_edit.setRange(1, 100000)
        self.chk_ffonly = QCheckBox(tr("pull_ffonly", "Fast Forward O&nly"), self)
        self.chk_fetchtags = QCheckBox(tr("pull_tags", "Tags"), self)
        self.tag_option_label = QLabel("", self)
        self.chk_prune = QCheckBox(tr("pull_prune", "Prune"), self)
        self.prune_label = QLabel("", self)
        self.chk_putty = QCheckBox(tr("pull_putty", "AutoLoad Putty &Key"), self)
        self.lnk_manage = QLabel(tr("pull_manage", "Manage Remotes"), self)
        self.chk_rebase = QCheckBox(tr("pull_rebase", "&Launch Rebase After Fetch"), self)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_GROUPT_REMOTE": self.grp_remote,
            "IDC_GROUP_OPTION": self.grp_options,
            "IDC_REMOTE_RD": self.rd_remote,
            "IDC_REMOTE_COMBO": self.remote_combo,
            "IDC_OTHER_RD": self.rd_other,
            "IDC_OTHER": self.other_edit,
            "IDC_STATIC": self.static_branch,
            "IDC_REMOTE_BRANCH": self.remote_branch_edit,
            "IDC_BUTTON_BROWSE_REF": self.btn_browse_ref,
            "IDC_CHECK_SQUASH": self.chk_squash,
            "IDC_CHECK_NOFF": self.chk_noff,
            "IDC_CHECK_NOCOMMIT": self.chk_nocommit,
            "IDC_CHECK_DEPTH": self.chk_depth,
            "IDC_EDIT_DEPTH": self.depth_edit,
            "IDC_CHECK_FFONLY": self.chk_ffonly,
            "IDC_CHECK_FETCHTAGS": self.chk_fetchtags,
            "IDC_STATIC_TAGOPT": self.tag_option_label,
            "IDC_CHECK_PRUNE": self.chk_prune,
            "IDC_STATIC_PRUNE": self.prune_label,
            "IDC_PUTTYKEY_AUTOLOAD": self.chk_putty,
            "IDC_REMOTE_MANAGE": self.lnk_manage,
            "IDC_CHECK_REBASE": self.chk_rebase,
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
            a = _PULL_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        remotes = self.repo.runner.run("remote").stdout or ""
        self.remote_combo.addItems([x for x in remotes.splitlines() if x.strip()] or ["origin"])
        if self.fetch_only:
            self.setWindowTitle(tr("fetch_title", "Fetch"))
            self.chk_squash.hide()
            self.chk_noff.hide()
            self.chk_nocommit.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _on_ok(self):
        remote = self.remote_combo.currentText()
        if self.rd_other.isChecked() and self.other_edit.text():
            remote = self.other_edit.text()
        if self.fetch_only:
            args = ["fetch", remote]
            branch = self.remote_branch_edit.text().strip()
            if branch:
                args.append(branch)
        else:
            args = ["pull", remote]
            branch = self.remote_branch_edit.text().strip()
            if branch:
                args.append(branch)
        if self.chk_squash.isChecked():
            args.append("--squash")
        if self.chk_noff.isChecked():
            args.append("--no-ff")
        if self.chk_nocommit.isChecked():
            args.append("--no-commit")
        if self.chk_ffonly.isChecked():
            args.append("--ff-only")
        if self.chk_fetchtags.isChecked():
            args.append("--tags")
        if self.chk_prune.isChecked():
            args.append("--prune")
        if self.chk_rebase.isChecked():
            args.append("--rebase")
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


_PULL_ANCHORS = {
    "IDC_GROUPT_REMOTE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_GROUP_OPTION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REMOTE_COMBO": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_OTHER": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REMOTE_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_REF": ("TOP_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
    "IDC_PUTTYKEY_AUTOLOAD": ("BOTTOM_LEFT",),
    "IDC_CHECK_PRUNE": ("BOTTOM_LEFT",),
    "IDC_CHECK_REBASE": ("BOTTOM_LEFT",),
    "IDC_REMOTE_MANAGE": ("BOTTOM_LEFT",),
}