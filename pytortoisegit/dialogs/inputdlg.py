"""inputdlg.py —— 通用输入提示对话框（IDD_URL / IDD_INPUTDLG 模板）。"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton,
)
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class UrlDlg(QDialog):
    """IDD_URL：URL 输入下拉。"""

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

    def __init__(self, title="", initial="", candidates=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_URL")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(title or spec.caption or "URL")
        self._ctl: dict = {}

        self.label = QLabel(tr("url_label", "&URL:"), self)
        self.combo = QComboBox(self)
        self.combo.setEditable(True)
        for c in (candidates or []):
            self.combo.addItem(c)
        if initial:
            self.combo.setEditText(initial)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.result_url = ""

        mapping = {
            "IDC_LABEL": self.label,
            "IDC_URLCOMBO": self.combo,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def accept(self):
        self.result_url = self.combo.currentText().strip()
        super().accept()


class InputDlg(QDialog):
    """IDD_INPUTDLG：多行文本输入（提交信息/日志信息）。"""

    def __init__(self, title="", hint="", text="", checkbox_label="",
                 checkbox_state=False, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_INPUTDLG")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(title or spec.caption or "Input")
        self._ctl: dict = {}

        self.hint_label = QLabel(hint or tr("input_hint", "Enter log &message:"), self)
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setPlainText(text)
        self.chk = QCheckBox(checkbox_label or "", self)
        self.chk.setChecked(checkbox_state)
        if not checkbox_label:
            self.chk.hide()
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.result_text = ""

        mapping = {
            "IDC_HINTTEXT": self.hint_label,
            "IDC_INPUTTEXT": self.text_edit,
            "IDC_CHECKBOX": self.chk,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def accept(self):
        self.result_text = self.text_edit.toPlainText()
        super().accept()