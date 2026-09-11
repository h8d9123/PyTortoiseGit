"""autotexttestdlg.py —— AutoTextTestDlg：正则测试（IDD_AUTOTEXTTESTDLG 模板）。

330x323 "Autotext Tester"：输入文件内容 + 正则 + Scan → 显示测试结果。
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
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
)
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class AutoTextTestDlg(QDialog):
    def __init__(self, regex: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_AUTOTEXTTESTDLG")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_fixed_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Autotext Tester")
        self._ctl: dict = {}

        self.static = QLabel(tr("autotext_hint", "Enter file content to test for below:"), self)
        self.content_edit = QPlainTextEdit(self)
        self.regex_edit = QLineEdit(self)
        self.regex_edit.setText(regex)
        self.btn_scan = QPushButton(tr("autotext_scan", "Scan"), self)
        self.btn_scan.setDefault(True)
        self.btn_scan.clicked.connect(self._scan)
        self.result_edit = QLineEdit(self)
        self.result_edit.setReadOnly(True)
        self.timing_label = QLabel("", self)
        self.btn_exit = QPushButton(tr("autotext_exit", "Exit"), self)
        self.btn_exit.clicked.connect(self.reject)

        mapping = {
            "IDC_STATIC": self.static,
            "IDC_AUTOTEXTCONTENT": self.content_edit,
            "IDC_AUTOTEXTREGEX": self.regex_edit,
            "IDC_AUTOTEXTSCAN": self.btn_scan,
            "IDC_TESTRESULT": self.result_edit,
            "IDC_TIMINGLABEL": self.timing_label,
            "IDCANCEL": self.btn_exit,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def _scan(self):
        text = self.content_edit.toPlainText()
        pat = self.regex_edit.text()
        try:
            m = re.search(pat, text)
            if m:
                self.result_edit.setText(text[max(0, m.start()-30):m.end()+30])
                self.timing_label.setText(tr("autotext_match", "Match: {}").format(m.group(0)))
            else:
                self.result_edit.setText(tr("autotext_nomatch", "No match"))
        except re.error as exc:
            self.result_edit.setText(str(exc))