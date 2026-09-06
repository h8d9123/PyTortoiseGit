"""bisectstartdlg.py —— BisectStartDlg：开始二分查找（IDD_BISECTSTART 模板）。

315x66 "Bisect start"：Last known good / First known bad。
OK 执行 git bisect start <bad> <good>。
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
    QComboBox, QDialog, QLabel, QPushButton,
)
from ..asyncfw import run_async
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class BisectStartDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_BISECTSTART")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Bisect start")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.good_label = QLabel(tr("bisect_good", "Last known &good:"), self)
        self.good_combo = QComboBox(self)
        self.good_combo.setEditable(True)
        self.btn_good = QPushButton("...", self)
        self.bad_label = QLabel(tr("bisect_bad", "First known &bad:"), self)
        self.bad_combo = QComboBox(self)
        self.bad_combo.setEditable(True)
        self.btn_bad = QPushButton("...", self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_start)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_STATIC_LOCAL_BRANCH": self.good_label,
            "IDC_COMBOBOXEX_GOOD": self.good_combo,
            "IDC_BUTTON_GOOD": self.btn_good,
            "IDC_STATIC_REMOTE_BRANCH": self.bad_label,
            "IDC_COMBOBOXEX_BAD": self.bad_combo,
            "IDC_BUTTON_BAD": self.btn_bad,
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
        refs = [x.strip() for x in out.splitlines() if x.strip()] or ["HEAD"]
        self.good_combo.addItems([r for r in refs])
        self.bad_combo.addItems([r for r in refs] + ["HEAD"])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _on_start(self):
        good = self.good_combo.currentText().strip()
        bad = self.bad_combo.currentText().strip()
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label(f"git bisect start {bad} {good}")

        def _bg():
            r = self.repo.runner.run("bisect", "start", bad, good)
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0

        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_STATIC_LOCAL_BRANCH": ("TOP_LEFT",),
    "IDC_STATIC_REMOTE_BRANCH": ("TOP_LEFT",),
    "IDC_BUTTON_GOOD": ("TOP_RIGHT",),
    "IDC_BUTTON_BAD": ("TOP_RIGHT",),
    "IDC_COMBOBOXEX_GOOD": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_BAD": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}