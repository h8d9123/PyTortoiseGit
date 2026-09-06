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

"""opendlg.py —— TortoiseMerge 的 OpenDlg（打开文件比较），翻译 OpenDlg.h。

选择 base/their/your 三个文件 + unified diff 文件 + 补丁目录。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel,
    QLineEdit, QVBoxLayout,
)

from ..res.strings import tr
from ..utils.pick import pick_open_file, pick_dir


class _FileRow(QLineEdit):
    """带浏览按钮的文件输入行。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
        # 用 QWidget 组合 + 外部方法不值得；此处仅使用 QLineEdit 路径
        self.setPlaceholderText(tr("open_path_hint", "选择文件…"))


class OpenDlg(QDialog):
    """打开文件比较对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("open_title", "打开 "))
        self.resize(520, 260)
        self.base_file = ""
        self.their_file = ""
        self.your_file = ""
        self.unified_diff_file = ""
        self.patch_dir = ""
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        from PySide6.QtWidgets import QHBoxLayout, QPushButton

        def row(label_text):
            edit = QLineEdit(self)
            btn = QPushButton("…", self)
            btn.setFixedWidth(28)
            h = QHBoxLayout()
            h.addWidget(edit, 1)
            h.addWidget(btn)
            return edit, btn, h

        e, b, h = row(tr("open_base", "基础文件(base):"))
        self.base_edit = e
        b.clicked.connect(lambda: self._pick(self.base_edit))
        form.addRow(h)
        e, b, h = row(tr("open_their", "对方文件(their):"))
        self.their_edit = e
        b.clicked.connect(lambda: self._pick(self.their_edit))
        form.addRow(h)
        e, b, h = row(tr("open_your", "我方文件(your):"))
        self.your_edit = e
        b.clicked.connect(lambda: self._pick(self.your_edit))
        form.addRow(h)
        e, b, h = row(tr("open_diff", "统一 diff 文件:"))
        self.diff_edit = e
        b.clicked.connect(lambda: self._pick(self.diff_edit))
        form.addRow(h)
        e, b, h = row(tr("open_patchdir", "补丁目录:"))
        self.dir_edit = e
        b.clicked.connect(lambda: self._pick_dir(self.dir_edit))
        form.addRow(h)
        lay.addLayout(form)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                               QDialogButtonBox.StandardButton.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _pick(self, edit: QLineEdit):
        p = pick_open_file(self, tr("open_title", "选择文件"), "")
        if p:
            edit.setText(p)

    def _pick_dir(self, edit: QLineEdit):
        d = pick_dir(self, tr("open_title", "选择目录"), "")
        if d:
            edit.setText(d)

    def accept(self):
        self.base_file = self.base_edit.text().strip()
        self.their_file = self.their_edit.text().strip()
        self.your_file = self.your_edit.text().strip()
        self.unified_diff_file = self.diff_edit.text().strip()
        self.patch_dir = self.dir_edit.text().strip()
        super().accept()