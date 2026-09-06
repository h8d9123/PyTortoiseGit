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

"""finddlg.py —— TortoiseMerge 的 FindDlg（查找/替换），翻译 FindDlg.h。

提供 find/replace 字符串、替换/全部替换、计数、可搜索向（向上/向下）。
UI 用 PySide6，功能流程对齐 CFindDlg。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QLineEdit, QVBoxLayout,
)

from ..res.strings import tr


class FindDlg(QDialog):
    """查找/替换对话框。"""

    def __init__(self, parent=None, replace_mode: bool = True):
        super().__init__(parent)
        self.setWindowTitle(tr("find_title", "查找/替换"))
        self.resize(420, 180)
        self.replace_mode = replace_mode
        self._build_ui(replace_mode)
        self.find_string = ""
        self.replace_string = ""
        self.search_down = True
        self.case_sensitive = False
        self.match_whole_word = False
        self.regex = False
        self.count = 0

    def _build_ui(self, replace_mode: bool):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("find_label", "查找内容:"), self))
        self.find_combo = QComboBox(self)
        self.find_combo.setEditable(True)
        lay.addWidget(self.find_combo)
        if replace_mode:
            lay.addWidget(QLabel(tr("replace_label", "替换为:"), self))
            self.replace_combo = QComboBox(self)
            self.replace_combo.setEditable(True)
            lay.addWidget(self.replace_combo)
        else:
            self.replace_combo = QComboBox(self)
            self.replace_combo.setEditable(True)
            self.replace_combo.hide()

        opts = QHBoxLayout()
        self.chk_down = QCheckBox(tr("find_down", "向下搜索"), self)
        self.chk_down.setChecked(True)
        self.chk_case = QCheckBox(tr("find_case", "区分大小写"), self)
        self.chk_whole = QCheckBox(tr("find_whole", "全词匹配"), self)
        self.chk_regex = QCheckBox(tr("find_regex", "正则表达式"), self)
        opts.addWidget(self.chk_down)
        opts.addWidget(self.chk_case)
        opts.addWidget(self.chk_whole)
        opts.addWidget(self.chk_regex)
        lay.addLayout(opts)

        btns = QDialogButtonBox(self)
        self._btn_btns = btns
        self._btn_find = btns.addButton(tr("find_next", "查找下一个"), QDialogButtonBox.ButtonRole.AcceptRole)
        if replace_mode:
            self._btn_replace = btns.addButton(tr("replace", "替换"), QDialogButtonBox.ButtonRole.ActionRole)
            self._btn_replace_all = btns.addButton(tr("replace_all", "全部替换"), QDialogButtonBox.ButtonRole.ActionRole)
            self._btn_count = btns.addButton(tr("find_count", "计数"), QDialogButtonBox.ButtonRole.ActionRole)
        btns.addButton(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._btn_find.clicked.connect(self._accept_find)

    def _accept_find(self):
        self.find_string = self.find_combo.currentText()
        self.replace_string = self.replace_combo.currentText() if self.replace_mode else ""
        self.search_down = self.chk_down.isChecked()
        self.case_sensitive = self.chk_case.isChecked()
        self.match_whole_word = self.chk_whole.isChecked()
        self.regex = self.chk_regex.isChecked()
        self.accept()

    def set_find_string(self, s: str):
        self.find_combo.setEditText(s)

    def get_find_string(self) -> str:
        return self.find_string

    def get_replace_string(self) -> str:
        return self.replace_string

    def set_status_text(self, text: str):
        self.setWindowTitle(text)

    def set_readonly(self, ro: bool):
        self.find_combo.setEnabled(not ro)