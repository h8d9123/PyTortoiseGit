"""conflicteditordlg.py —— ConflictEditorDlg：合并冲突（IDD_RESOLVE_CONFLICT 模板）。

315x129 "Conflict"：delete/modify 冲突 → Modify/Delete/Abort。
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
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QGroupBox
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class ConflictEditorDlg(QDialog):
    def __init__(self, repo: Repository, path: str, from_hash="", to_hash="",
                 parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.path = path
        spec = rc_mod.load_spec("IDD_RESOLVE_CONFLICT")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_fixed_size(self, r.width(), r.height())
        self.setWindowTitle(tr("conflicteditor_title", "Conflict - {}").format(path))
        self._ctl: dict = {}

        self.grp_del = QGroupBox(tr("conflicteditor_group", "Delete/modify merge conflict"), self)

        self.info_label = QLabel(tr("conflicteditor_reminder", "Delete/modify merge conflict"), self)
        self.local_status = QLabel(tr("conflicteditor_local", "Local:"), self)
        self.from_hash = QLineEdit(self)
        self.from_hash.setText(from_hash)
        self.btn_log = QPushButton(tr("showlog", "Show log"), self)
        self.btn_diff = QPushButton(tr("conflicteditor_diff", "Show &changes"), self)
        self.remote_status = QLabel(tr("conflicteditor_remote", "Remote:"), self)
        self.to_hash = QLineEdit(self)
        self.to_hash.setText(to_hash)
        self.btn_log2 = QPushButton(tr("showlog", "Show log"), self)
        self.btn_diff2 = QPushButton(tr("conflicteditor_diff", "Show &changes"), self)
        self.btn_modify = QPushButton(tr("ok"), self)
        self.btn_modify.clicked.connect(self._on_modify)
        self.btn_delete = QPushButton(tr("conflicteditor_delete", "Delete"), self)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_abort = QPushButton(tr("conflicteditor_abort", "Abort"), self)
        self.btn_abort.setDefault(True)
        self.btn_abort.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.choice = "abort"

        mapping = {
            "IDC_DEL_GROUP": self.grp_del,
            "IDC_INFOLABEL": self.info_label,
            "IDC_LOCAL_STATUS": self.local_status,
            "IDC_FROMHASH": self.from_hash,
            "IDC_LOG": self.btn_log,
            "IDC_SHOWDIFF": self.btn_diff,
            "IDC_REMOTE_STATUS": self.remote_status,
            "IDC_TOHASH": self.to_hash,
            "IDC_LOG2": self.btn_log2,
            "IDC_SHOWDIFF2": self.btn_diff2,
            "IDC_MODIFY": self.btn_modify,
            "IDC_DELETE": self.btn_delete,
            "IDCANCEL": self.btn_abort,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def _on_modify(self):
        self.choice = "modify"
        self.accept()

    def _on_delete(self):
        self.choice = "delete"
        self.accept()