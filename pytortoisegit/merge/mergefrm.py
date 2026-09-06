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

"""mergefrm.py —— TortoiseGitMerge 的 MainFrm（主窗口）。

逐行翻译 MainFrm.cpp 的并排 diff 主框架：
  * 左右两个 BaseView（LeftView / RightView）+ LineDiffBar（侧边差异条）
  * 打开时用 DiffData 构建行，填充视图并着色
  * 同步滚动（ScrollAllToLine）、差异跳转、关闭
功能流程对齐 TortoiseMerge：从两个修订 diff 出一份"并排对比"窗口。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..git.repo import Repository
from ..res.strings import tr
from .baseview import BaseView, LeftView, RightView
from .diffcolors import DiffColors
from .diffdata import DiffData
from .linediffbar import LineDiffBar
from .viewdata import DiffState


class MergeFrm(QMainWindow):
    """并排 diff 主窗口（对齐 TortoiseGitMerge CMainFrame）。"""

    def __init__(self, repo: Repository, path: str, rev1: str | None,
                 rev2: str | None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.path = path
        self.rev1 = rev1
        self.rev2 = rev2
        self.setWindowTitle(tr("merge_title", "比较 - {}").format(path))
        self.resize(1020, 660)
        self._build_ui()
        self._load()

    def _build_ui(self):
        central = QWidget(self)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(6, 6, 6, 6)

        self._header = QLabel("", central)
        self._header.setWordWrap(True)
        lay.addWidget(self._header)

        self.line_bar = LineDiffBar(central)
        self.line_bar._on_click = self._on_bar_click
        lay.addWidget(self.line_bar)

        split = QSplitter(Qt.Orientation.Horizontal, central)
        self.left_view = LeftView(split)
        self.right_view = RightView(split)
        split.addWidget(self.left_view)
        split.addWidget(self.right_view)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, central)
        box.rejected.connect(self.close)
        box.button(QDialogButtonBox.StandardButton.Close).setText(tr("close"))
        lay.addWidget(box)

        self.setCentralWidget(central)

    def _load(self):
        left, right = DiffData(self.repo).load(self.path, self.rev1, self.rev2)
        self.left_view.set_view_data(left)
        self.right_view.set_view_data(right)
        self.line_bar.set_rows([vd.state for vd in left])
        self._sync_scrolls()
        added = sum(1 for vd in right if vd.is_added)
        removed = sum(1 for vd in left if vd.is_removed)
        self._header.setText(
            f" {self.path}  ·  {(self.rev1 or '工作区')} → {(self.rev2 or '工作区')}   "
            f"+{added}/-{removed}")

    def _sync_scrolls(self):
        self.left_view.verticalScrollBar().valueChanged.connect(
            self.right_view.verticalScrollBar().setValue)
        self.right_view.verticalScrollBar().valueChanged.connect(
            self.left_view.verticalScrollBar().setValue)

    def _on_bar_click(self, line: int):
        self.left_view.scroll_all_to_line(line, self.right_view)

    def exec(self):
        from PySide6.QtWidgets import QApplication
        self.show()
        return QApplication.instance().exec() if QApplication.instance() else 0


def open_merge_window(repo: Repository, path: str, rev1: str | None,
                      rev2: str | None, parent=None):
    """打开一个并排 diff 主窗口。"""
    frm = MergeFrm(repo, path, rev1, rev2, parent)
    frm.show()
    return frm