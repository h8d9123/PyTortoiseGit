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

"""settings.py —— TortoiseMerge 的 Settings（设置对话框）。

翻译 Settings.h / SetMainPage / SetColorPage：
  * 用 QTabWidget 承载各设置页（CPropertySheet 语义）
  * 每页有 load(SaveData 前的读回显) + save(SaveData)
  * 主页：字体/字号/备份/忽略空白等
  * 配色页：各 DiffState 的颜色（DiffColors 可改）
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..res.strings import tr
from .diffcolors import DiffColors
from .viewdata import DiffState


class _BasePage(QWidget):
    """设置页基类：提供 SaveData 语义的 load/save。"""

    def load(self):
        pass

    def save(self):
        pass


class _MainPage(_BasePage):
    """SetMainPage：字体/字号/忽略空白/备份/字数统计等。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        self.font_combo = QComboBox(self)
        self.font_combo.addItems(["Consolas", "Courier New", "Lucida Console"])
        self.size_edit = QLineEdit(self)
        self.size_edit.setText("10")
        self.chk_backup = QCheckBox(tr("settings_backup", "合并时备份文件"), self)
        self.chk_ignore_ws = QCheckBox(tr("settings_ignorews", "忽略空白差异"), self)
        self.chk_ignore_case = QCheckBox(tr("settings_ignorecase", "忽略大小写"), self)
        form.addRow(tr("settings_font", "字体:"), self.font_combo)
        form.addRow(tr("settings_fontsize", "字号:"), self.size_edit)
        form.addRow("", self.chk_backup)
        form.addRow("", self.chk_ignore_ws)
        form.addRow("", self.chk_ignore_case)

    def save(self):
        try:
            n = int(self.size_edit.text())
        except ValueError:
            n = 10
        self._saved = {"font": self.font_combo.currentText(), "size": n,
                       "backup": self.chk_backup.isChecked(),
                       "ignorews": self.chk_ignore_ws.isChecked(),
                       "ignorecase": self.chk_ignore_case.isChecked()}

    def load(self):
        self.chk_backup.setChecked(True)


class _ColorPage(_BasePage):
    """SetColorPage：各 DiffState 颜色编辑。"""

    _STATE_LABELS = {
        DiffState.Removed: "删除行",
        DiffState.Added: "新增行",
        DiffState.Edited: "修改行",
        DiffState.Conflict: "冲突行",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = {s: c for s, c in DiffColors()._LIGHT_BG.items() if s in self._STATE_LABELS}
        form = QFormLayout(self)
        self._buttons: Dict[DiffState, QPushButton] = {}
        for s, label in self._STATE_LABELS.items():
            btn = QPushButton(self)
            btn.clicked.connect(lambda _=False, st=s: self._pick(st))
            self._buttons[s] = btn
            form.addRow(label, btn)
        self._refresh()

    def _pick(self, state: DiffState):
        c = self.colors.get(state, QColor(255, 255, 255))
        picked = QColorDialog.getColor(c, self, tr("color_pick", "选择颜色"))
        if picked.isValid():
            self.colors[state] = picked
            self._refresh()

    def _refresh(self):
        for s, btn in self._buttons.items():
            c = self.colors.get(s, QColor(255, 255, 255))
            btn.setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid gray; min-height: 24px;")

    def save(self):
        self._saved_colors = dict(self.colors)


class Settings(QDialog):
    """TortoiseMerge 设置对话框（CPropertySheet → QTabWidget）。"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("merge_settings_title", "TortoiseMerge 设置"))
        self.resize(460, 340)
        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import (QHBoxLayout, QPushButton)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.main_page = _MainPage(self)
        self.color_page = _ColorPage(self)
        self.tabs.addTab(self.main_page, tr("merge_settings_main", "常规"))
        self.tabs.addTab(self.color_page, tr("merge_settings_colors", "颜色"))
        lay.addWidget(self.tabs, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_ok = QPushButton(tr("ok"), self)
        btn_ok.clicked.connect(self._save_and_accept)
        btn_cancel = QPushButton(tr("cancel"), self)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        lay.addLayout(btns)

    def _save_and_accept(self):
        self.main_page.save()
        self.color_page.save()
        self.accept()

    @property
    def diff_colors(self) -> Dict[DiffState, QColor]:
        return getattr(self.color_page, "_saved_colors", {})

    @property
    def main_options(self) -> dict:
        return getattr(self.main_page, "_saved", {})