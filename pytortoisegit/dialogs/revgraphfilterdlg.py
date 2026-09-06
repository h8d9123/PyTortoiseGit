"""revgraphfilterdlg.py —— RevGraphFilterDlg：修订图过滤（IDD_REVGRAPHFILTER 模板）。

303x108 "Revision Graph Filter"：从/到修订范围 + Only Current Branch / Local Branches。
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
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QLineEdit, QPushButton
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class RevGraphFilterDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        spec = rc_mod.load_spec("IDD_REVGRAPHFILTER")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Revision Graph Filter")
        self._ctl: dict = {}

        self.hint = QLabel(tr("revf_hint", "Include only the following revision range:"), self)
        self.from_edit = QLineEdit(self)
        self.btn_from = QPushButton("RefBrowser", self)
        self.btn_from.clicked.connect(self._browse_from)
        self.to_edit = QLineEdit(self)
        self.btn_to = QPushButton("RefBrowser", self)
        self.btn_to.clicked.connect(self._browse_to)
        self.chk_current = QCheckBox(tr("revf_current", "Only Current Branch"), self)
        self.chk_local = QCheckBox(tr("revf_local", "Only Local Branches"), self)
        self.btn_ok = QPushButton(tr("revf_ok", "&OK"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_reset = QPushButton(tr("revf_reset", "&Reset filter"), self)
        self.btn_reset.clicked.connect(self._reset)

        mapping = {
            "IDC_STATIC": self.hint,
            "IDC_FROMREV": self.from_edit,
            "IDC_REV1BTN1": self.btn_from,
            "IDC_TOREV": self.to_edit,
            "IDC_REV1BTN2": self.btn_to,
            "IDC_CURRENT_BRANCH": self.chk_current,
            "IDC_LOCAL_BRANCHES": self.chk_local,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDC_RESETFILTER": self.btn_reset,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def _browse_from(self):
        from .browserefs import BrowseRefsDlg
        dlg = BrowseRefsDlg(self.repo, parent=self)
        if dlg.exec():
            r = getattr(dlg, "_selected", lambda: (None, None))()
            ref = r[0] if r else None
            if ref:
                self.from_edit.setText(ref)

    def _browse_to(self):
        from .browserefs import BrowseRefsDlg
        dlg = BrowseRefsDlg(self.repo, parent=self)
        if dlg.exec():
            r = getattr(dlg, "_selected", lambda: (None, None))()
            ref = r[0] if r else None
            if ref:
                self.to_edit.setText(ref)

    def _reset(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.chk_current.setChecked(False)
        self.chk_local.setChecked(False)