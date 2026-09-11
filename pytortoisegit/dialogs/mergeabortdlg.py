"""mergeabortdlg.py —— MergeAbortDlg：中止合并（IDD_MERGEABORT 模板）。

299x124 "Abort Merge"：Reset Type（merge/mixed/hard）+ Show modified files。
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
    QDialog, QLabel, QPushButton, QRadioButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class MergeAbortDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_MERGEABORT")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Abort Merge")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.grp_reset_type = QGroupBox(tr("mergeabort_group_reset", "Reset Type"), self)

        self.reminder = QLabel(
            tr("mergeabort_reminder",
               "In order to abort a merge progress a reset (type) is performed!"), self)
        self.rd_merge = QRadioButton(
            tr("mergeabort_merge",
               "M&erge: Resets the index and try to reconstruct the pre-merge state"), self)
        self.rd_mixed = QRadioButton(
            tr("mergeabort_mixed",
               "&Mixed: Leave working tree untouched, reset index"), self)
        self.rd_hard = QRadioButton(
            tr("mergeabort_hard",
               "&Hard: Reset working tree and index (discard changes)"), self)
        self.rd_mixed.setChecked(True)
        self.btn_showmod = QPushButton(
            tr("mergeabort_show", "Show modified files in &working tree"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_abort)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_GROUP_RESET_TYPE": self.grp_reset_type,
            "IDC_STATIC_REMINDER": self.reminder,
            "IDC_RADIO_RESET_MERGE": self.rd_merge,
            "IDC_RADIO_RESET_MIXED": self.rd_mixed,
            "IDC_RADIO_RESET_HARD": self.rd_hard,
            "IDC_SHOW_MODIFIED_FILES": self.btn_showmod,
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

    def _on_abort(self):
        mode = "mixed"
        if self.rd_merge.isChecked():
            mode = "merge"
        elif self.rd_hard.isChecked():
            mode = "hard"
        args = ["reset", f"--{mode}"]
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
    "IDC_GROUP_RESET_TYPE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_SHOW_MODIFIED_FILES": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}