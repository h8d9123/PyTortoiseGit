"""ignoredlg.py —— IgnoreDlg：忽略项（IDD_IGNORE 模板）。

261x151 "Ignore"：Ignore Type（仅含目录/递归）+ Ignore File
（根 .gitignore / 所在目录 .gitignore / .git/info/exclude）。
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
    QGroupBox,
    QDialog, QLabel, QPushButton, QRadioButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class IgnoreDlg(QDialog):
    def __init__(self, repo: Repository, paths=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.paths = list(paths or [])
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_IGNORE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_fixed_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Ignore")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.grp_ignore_type = QGroupBox(tr("ignore_group_type", "Ignore Type"), self)
        self.grp_ignore_file = QGroupBox(tr("ignore_group_file", "Ignore File"), self)

        self.rd_only_folder = QRadioButton(
            tr("ignore_onlyfolder", "Ignore item(s) only in the containing folder"), self)
        self.rd_recursive = QRadioButton(
            tr("ignore_recursive", "Ignore item(s) recursively"), self)
        self.rd_only_folder.setChecked(True)
        self.rd_root = QRadioButton(
            tr("ignore_root", ".gitignore in the repository root"), self)
        self.rd_local = QRadioButton(
            tr("ignore_local", ".gitignore in the containing directories"), self)
        self.rd_exclude = QRadioButton(tr("ignore_exclude", ".git/info/exclude"), self)
        self.rd_root.setChecked(True)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ignore)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_GROUP_IGNORE_TYPE": self.grp_ignore_type,
            "IDC_GROUP_IGNORE_FILE": self.grp_ignore_file,
            "IDC_RADIO_IGNORETYPE_ONLYINFOLDER": self.rd_only_folder,
            "IDC_RADIO_IGNORETYPE_RECURSIVELY": self.rd_recursive,
            "IDC_RADIO_IGNOREFILE_GLOBALGITIGNORE": self.rd_root,
            "IDC_RADIO_IGNOREFILE_LOCALGITIGNORES": self.rd_local,
            "IDC_RADIO_IGNOREFILE_GITINFOEXCLUDE": self.rd_exclude,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _on_ignore(self):
        patterns = []
        for p in self.paths:
            name = os.path.basename(p.rstrip("/\\"))
            patterns.append(name if self.rd_recursive.isChecked()
                           else os.path.join(p.rstrip("/\\"), name).replace("\\", "/").lstrip("./"))
        lines = "\n".join(patterns) + "\n"
        if self.rd_exclude.isChecked():
            target = os.path.join(self.repo.root, ".git", "info", "exclude")
        elif self.rd_local.isChecked():
            target = os.path.join(self.repo.root, ".gitignore")
        else:
            target = os.path.join(self.repo.root, ".gitignore")
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(lines)
        self.accept()