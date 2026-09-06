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

"""xsplitter.py —— TortoiseMerge 的 CXSplitter（自定义分割器）。

翻译 CXSplitter：分割器条的锁定、显示/隐藏列、动态替换视图。
用 PySide6 QSplitter 实现（IsBarLocked/LockBar/ShowCol/ReplaceView）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QWidget


class XSplitter(QSplitter):
    """带锁定/隐藏列能力的分割器。"""

    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal,
                 parent=None):
        super().__init__(orientation, parent)
        self._bar_locked = False

    def is_bar_locked(self) -> bool:
        return self._bar_locked

    def lock_bar(self, state: bool = True):
        self._bar_locked = state
        self.setHandleWidth(0 if state else (self.handleWidth() or 6))

    def show_column(self, index: int):
        self.widget(index).show()

    def hide_column(self, index: int):
        self.widget(index).hide()

    def replace_view(self, index: int, new_widget: QWidget):
        old = self.widget(index)
        self.insertWidget(index, new_widget)
        if old is not None:
            old.deleteLater()

    def is_column_visible(self, index: int) -> bool:
        return self.widget(index).isVisible()