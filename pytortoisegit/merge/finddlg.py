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

from enum import Enum
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QLineEdit, QVBoxLayout,
)

from ..res.strings import tr


class FindType(Enum):
    """对齐 CFindDlg::FindType。"""
    Find = 0
    Count = 1
    Replace = 2
    ReplaceAll = 3


class FindDlg(QDialog):
    """查找/替换对话框。"""

    def __init__(self, parent=None, replace_mode: bool = True):
        super().__init__(parent)
        self.setWindowTitle(tr("find_title", "Find/Replace"))
        self.resize(420, 190)
        self.replace_mode = replace_mode
        self._build_ui(replace_mode)
        self.find_string = ""
        self.replace_string = ""
        self.search_down = True
        self.case_sensitive = False
        self.match_whole_word = False
        self.regex = False
        self.limit_to_diffs = False
        self.find_type = FindType.Find
        self._terminating = False
        self.count = 0
        self._load_history()

    def _build_ui(self, replace_mode: bool):
        """布局对齐 IDD_FIND：左列 查找/替换 + 复选框（一行一个）；
        右列 Find/Replace/ReplaceAll/Count/Cancel 同一列；底部状态行。"""
        from PySide6.QtWidgets import QGridLayout, QPushButton
        outer = QVBoxLayout(self)
        body = QHBoxLayout()

        left = QVBoxLayout()
        form = QGridLayout()
        form.addWidget(QLabel(tr("find_label", "Find what:"), self), 0, 0)
        self.find_combo = QComboBox(self)
        self.find_combo.setEditable(True)
        form.addWidget(self.find_combo, 0, 1)
        form.addWidget(QLabel(tr("replace_label", "Replace with:"), self), 1, 0)
        self.replace_combo = QComboBox(self)
        self.replace_combo.setEditable(True)
        form.addWidget(self.replace_combo, 1, 1)
        left.addLayout(form)

        # 复选框：一行一个（对齐原版 IDD_FIND 顺序）
        self.chk_case = QCheckBox(tr("find_case", "Match case"), self)
        self.chk_limit = QCheckBox(tr("find_limit", "Search only in modified lines"), self)
        self.chk_up = QCheckBox(tr("find_up", "Search up"), self)
        self.chk_whole = QCheckBox(tr("find_whole", "Match whole word"), self)
        for chk in (self.chk_case, self.chk_limit, self.chk_up, self.chk_whole):
            left.addWidget(chk)
        left.addStretch(1)
        body.addLayout(left, 1)

        # 按钮：同一列（对齐原版 IDD_FIND）
        right = QVBoxLayout()
        self._btn_find = QPushButton(tr("find_find", "Find"), self)
        self._btn_replace = QPushButton(tr("find_replace", "Replace"), self)
        self._btn_replace_all = QPushButton(tr("find_replace_all", "Replace All"), self)
        self._btn_count = QPushButton(tr("find_count", "Count"), self)
        self._btn_cancel = QPushButton(tr("cancel", "Cancel"), self)
        for b in (self._btn_find, self._btn_replace, self._btn_replace_all,
                  self._btn_count, self._btn_cancel):
            right.addWidget(b)
        right.addStretch(1)
        body.addLayout(right)
        outer.addLayout(body)

        self.status_label = QLabel("", self)
        outer.addWidget(self.status_label)

        self._btn_find.clicked.connect(lambda: self._accept_find(FindType.Find))
        self._btn_replace.clicked.connect(lambda: self._accept_find(FindType.Replace))
        self._btn_replace_all.clicked.connect(
            lambda: self._accept_find(FindType.ReplaceAll))
        self._btn_count.clicked.connect(lambda: self._accept_find(FindType.Count))
        self._btn_cancel.clicked.connect(self.reject)

    def _accept_find(self, find_type: FindType = FindType.Find):
        self.find_type = find_type
        self.find_string = self.find_combo.currentText()
        self.replace_string = self.replace_combo.currentText() if self.replace_mode else ""
        self.search_down = not self.chk_up.isChecked()
        self.case_sensitive = self.chk_case.isChecked()
        self.match_whole_word = self.chk_whole.isChecked()
        self.limit_to_diffs = self.chk_limit.isChecked()
        self._save_history()
        self.accept()

    # ---- 历史记录（对齐 CHistoryCombo + 注册表）----
    _HIST_KEY = "TortoiseGitMerge/FindHistory"

    def _load_history(self):
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("TortoiseGit", "TortoiseGitMerge")
            self.find_combo.addItems(s.value(self._HIST_KEY, [], type=list) or [])
        except Exception:  # noqa: BLE001
            pass

    def _save_history(self):
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("TortoiseGit", "TortoiseGitMerge")
            hist = s.value(self._HIST_KEY, [], type=list) or []
            if self.find_string and self.find_string in hist:
                hist.remove(self.find_string)
            if self.find_string:
                hist.insert(0, self.find_string)
            s.setValue(self._HIST_KEY, hist[:20])
        except Exception:  # noqa: BLE001
            pass

    # ---- 状态访问（对齐 CFindDlg 的 getter）----
    def is_terminating(self) -> bool:
        return self._terminating

    def find_next(self) -> bool:
        return self.find_type == FindType.Find

    def match_case(self) -> bool:
        return self.case_sensitive

    def is_limit_to_diffs(self) -> bool:
        return self.limit_to_diffs

    def whole_word(self) -> bool:
        return self.match_whole_word

    def search_up(self) -> bool:
        return not self.search_down

    def set_find_string(self, s: str):
        self.find_combo.setEditText(s)

    def get_find_string(self) -> str:
        return self.find_string

    def get_replace_string(self) -> str:
        return self.replace_string

    def set_status_text(self, text: str):
        if hasattr(self, "status_label"):
            self.status_label.setText(text)
        else:
            self.setWindowTitle(text)

    def set_readonly(self, ro: bool):
        self.find_combo.setEnabled(not ro)