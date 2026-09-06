"""createrepoldg.py —— CreateRepoDlg：git init（IDD_CREATEREPO 模板）。

309x97 "Git Init"：Make it Bare + 说明 + OK/Cancel/Help。
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
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QPushButton
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .progress import ProgressDialog


class CreateRepoDlg(QDialog):
    def __init__(self, directory: str, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.directory = directory
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_CREATEREPO")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Git Init")
        self._ctl: dict = {}

        self.chk_bare = QCheckBox(tr("init_bare", "Make it Bare (No working directories)"), self)
        self.desc = QLabel(
            tr("init_desc", "If you plan to work inside this folder, "
               "leave this unchecked (not bare).\n"
               "Bare repositories are usually used for "
               "remote/server bare stores."), self)
        self.desc.setWordWrap(True)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_init)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_CHECK_BARE": self.chk_bare,
            "IDC_INIT_REPO_DESC": self.desc,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def _on_init(self):
        from ..git.git import GitRunner
        runner = GitRunner(cwd=self.directory)
        args = ["init"]
        if self.chk_bare.isChecked():
            args.append("--bare")
        runner.init(self.directory, bare=self.chk_bare.isChecked())
        self.accept()