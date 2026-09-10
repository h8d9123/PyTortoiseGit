"""logorderingdlg.py —— LogOrderingDlg：提交排序（IDD_LOGORDERING 模板）。

285x46 "Log commit ordering"：提交排序下拉。
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
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QPushButton
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class LogOrderingDlg(QDialog):
    ORDERINGS = ["topo-order", "date-order", "author-date-order", "default"]
    LABELS = [
        ("logorder_topo", "Topological order"),
        ("logorder_date", "Date order"),
        ("logorder_author_date", "Author date order"),
        ("logorder_default", "Default"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_LOGORDERING")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Log commit ordering")
        self._ctl: dict = {}

        self.label = QLabel(tr("logorder_label", "Commit Ordering:"), self)
        self.combo = QComboBox(self)
        self.combo.addItems([tr(k, d) for k, d in self.LABELS])
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(lambda: self._accept())
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.selected = "default"

        mapping = {
            "IDC_STATIC_ORDER": self.label,
            "IDC_COMBOBOXEX_ORDERING": self.combo,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def _accept(self):
        self.selected = self.ORDERINGS[self.combo.currentIndex()]
        self.accept()