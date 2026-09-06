"""resetdlg.py —— ResetDlg：重置分支（IDD_RESET 模板）。

299x193 "Reset"：Current branch + Reset active branch 组（branch/tag/commit）
+ Reset Type 组（soft/mixed/hard）+ Show modified files + OK/Cancel/Help。
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
    QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QRadioButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class ResetDlg(QDialog):
    def __init__(self, repo: Repository, parent=None, commit: str | None = None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        if commit:
            self.rd_version.setChecked(True)
            self.version_combo.setEditable(True)
            self.version_combo.setCurrentText(commit)

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_RESET")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Reset")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.cur_label = QLabel(self)
        self.cur_edit = QLineEdit(self)
        self.cur_edit.setReadOnly(True)
        self.cur_edit.setText(self.repo.current_branch())

        self.rd_branch = QRadioButton(tr("reset_branch", "&Branch"), self)
        self.branch_combo = QComboBox(self)
        self.btn_browse_branch = QPushButton("...", self)
        self.rd_tags = QRadioButton(tr("reset_tag", "&Tag"), self)
        self.tags_combo = QComboBox(self)
        self.rd_version = QRadioButton(tr("reset_commit", "&Commit"), self)
        self.version_combo = QComboBox(self)
        self.btn_show = QPushButton("...", self)

        self.rd_soft = QRadioButton(
            tr("reset_soft", "&Soft: Leave working tree and index untouched"), self)
        self.rd_mixed = QRadioButton(
            tr("reset_mixed", "&Mixed: Leave working tree untouched, reset index"), self)
        self.rd_hard = QRadioButton(
            tr("reset_hard", "&Hard: Reset working tree and index (discard changes)"), self)
        self.rd_mixed.setChecked(True)

        self.btn_showmodified = QPushButton(
            tr("reset_showmod", "Show modified files in &working tree"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_reset)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_STATIC": self.cur_label,
            "IDC_CURRENTBRANCH": self.cur_edit,
            "IDC_RADIO_BRANCH": self.rd_branch,
            "IDC_COMBOBOXEX_BRANCH": self.branch_combo,
            "IDC_BUTTON_BROWSE_REF": self.btn_browse_branch,
            "IDC_RADIO_TAGS": self.rd_tags,
            "IDC_COMBOBOXEX_TAGS": self.tags_combo,
            "IDC_RADIO_VERSION": self.rd_version,
            "IDC_COMBOBOXEX_VERSION": self.version_combo,
            "IDC_BUTTON_SHOW": self.btn_show,
            "IDC_RADIO_RESET_SOFT": self.rd_soft,
            "IDC_RADIO_RESET_MIXED": self.rd_mixed,
            "IDC_RADIO_RESET_HARD": self.rd_hard,
            "IDC_SHOW_MODIFIED_FILES": self.btn_showmodified,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        self.cur_label.setText(tr("reset_cur", "Current branch:"))

        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _RESET_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        self._populate()

    def _populate(self):
        out = self.repo.runner.run("for-each-ref",
                                   "--format=%(refname:short)").stdout or ""
        refs = [x.strip() for x in out.splitlines() if x.strip()]
        self.branch_combo.addItems([r for r in refs if not r.startswith(("tags",))])
        self.tags_combo.addItems([r[5:] for r in refs if r.startswith("tags/")])
        self.version_combo.addItems(refs)
        self.version_combo.addItem("HEAD")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _on_reset(self):
        mode = "mixed"
        if self.rd_soft.isChecked():
            mode = "soft"
        elif self.rd_hard.isChecked():
            mode = "hard"
        target = self.version_combo.currentText()
        if self.rd_branch.isChecked():
            target = self.branch_combo.currentText()
        elif self.rd_tags.isChecked():
            target = self.tags_combo.currentText()
        args = ["reset", f"--{mode}", target]
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


_RESET_ANCHORS = {
    "IDC_SHOW_MODIFIED_FILES": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}