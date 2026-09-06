"""toolassocdlg.py —— ToolAssocDlg：扩展名指定 diff/merge 工具（IDD_TOOLASSOC 模板）。

383x79 "Add/Edit Extension Specific Diff/Merge Program"：扩展名 + 工具路径。
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
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from ..utils.pick import pick_open_file


class ToolAssocDlg(QDialog):
    def __init__(self, ext: str = "", tool: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_TOOLASSOC")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Add/Edit Extension Specific Program")
        self._ctl: dict = {}

        self.ext_label = QLabel(tr("tool_ext", "Extension:"), self)
        self.ext_edit = QLineEdit(self)
        self.ext_edit.setText(ext)
        self.tool_edit = QLineEdit(self)
        self.tool_edit.setText(tool)
        self.btn_browse = QPushButton("...", self)
        self.btn_browse.clicked.connect(self._browse)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)

        mapping = {
            "IDC_STATIC": self.ext_label,
            "IDC_EXTEDIT": self.ext_edit,
            "IDC_TOOLEDIT": self.tool_edit,
            "IDC_TOOLBROWSE": self.btn_browse,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def _browse(self):
        p = pick_open_file(self, tr("tool_browse", "选择工具"), "")
        if p:
            self.tool_edit.setText(p)

    @property
    def result_value(self):
        return self.ext_edit.text().strip(), self.tool_edit.text().strip()