"""historydlg.py —— HistoryDlg：日志历史选择（IDD_HISTORYDLG 模板）。

196x116 "Log History"：历史列表（LISTBOX）供选择。
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
from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QPushButton
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class HistoryDlg(QDialog):
    def __init__(self, entries=None, title="", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_HISTORYDLG")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(title or spec.caption or "Log History")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.list = QListWidget(self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.selected = None

        mapping = {
            "IDC_HISTORYLIST": self.list,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
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

        for e in (entries or []):
            it = QListWidgetItem(str(e))
            it.setData(Qt.ItemDataRole.UserRole, e)
            self.list.addItem(it)
        self.list.itemDoubleClicked.connect(lambda _i: self._accept())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _accept(self):
        it = self.list.currentItem()
        if it is not None:
            self.selected = it.data(Qt.ItemDataRole.UserRole)
        self.accept()


_ANCHORS = {
    "IDC_HISTORYLIST": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
}