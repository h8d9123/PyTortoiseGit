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
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..git.repo import Repository
from ..res.strings import tr
from .baseview import BaseView, LeftView, RightView
from .diffcolors import DiffColors
from .diffdata import DiffData
from .linediffbar import LineDiffBar
from .viewdata import DiffState, EOL, HideState, ViewData


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

        # 合并工具栏（对齐 TortoiseMerge 主窗口）
        tb = QToolBar(tr("merge_toolbar", "合并"), central)
        tb.setMovable(False)
        self._act_prev = tb.addAction(tr("merge_prev", "上一个差异"))
        self._act_prev.triggered.connect(lambda: self._goto_diff(-1))
        self._act_next = tb.addAction(tr("merge_next", "下一个差异"))
        self._act_next.triggered.connect(lambda: self._goto_diff(1))
        tb.addSeparator()
        self._act_take_left = tb.addAction(tr("merge_take_left", "取左侧"))
        self._act_take_left.triggered.connect(lambda: self._take("left"))
        self._act_take_right = tb.addAction(tr("merge_take_right", "取右侧"))
        self._act_take_right.triggered.connect(lambda: self._take("right"))
        self._act_mark = tb.addAction(tr("merge_mark", "标记已解决"))
        self._act_mark.triggered.connect(self._mark_resolved)
        tb.addSeparator()
        self._act_save = tb.addAction(tr("merge_save", "保存合并结果"))
        self._act_save.triggered.connect(self._save_result)
        lay.addWidget(tb)

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

    # ---- 合并操作 ----
    def _current_line(self) -> int:
        c = self.left_view.textCursor()
        return c.blockNumber()

    def _goto_diff(self, direction: int):
        cur = self._current_line()
        nxt = self.left_view.next_diff_from(cur) if direction > 0 else \
            self.left_view.prev_diff_from(cur)
        if nxt is None or nxt < 0:
            # 从头/到尾回绕
            nxt = self.left_view.first_diff_line() if direction > 0 else \
                self.left_view.prev_diff_from(len(self.left_view.view_data))
        if nxt is not None and nxt >= 0:
            self.left_view.go_to_diff(nxt, self.right_view)

    def _take(self, side: str):
        line = self._current_line()
        if line < 0 or line >= len(self.left_view.view_data):
            return
        if side == "left":
            # 取左侧（旧）：把右侧该行替换为左侧内容并标记已解决
            self.right_view.take_block(line, self.left_view)
            self.left_view.mark_resolved(line)
        else:
            self.left_view.take_block(line, self.right_view)
            self.right_view.mark_resolved(line)
        self._update_header()

    def _mark_resolved(self):
        line = self._current_line()
        self.left_view.mark_resolved(line)
        self.right_view.mark_resolved(line)
        self._update_header()

    def _update_header(self):
        added = sum(1 for vd in self.right_view.view_data if vd.is_added)
        removed = sum(1 for vd in self.left_view.view_data if vd.is_removed)
        solved = sum(1 for vd in self.right_view.view_data
                      if vd.state == DiffState.ConflictsResolved)
        self._header.setText(
            f" {self.path}  ·  {(self.rev1 or '工作区')} → {(self.rev2 or '工作区')}   "
            f"+{added}/-{removed}   已解决 {solved}")

    def _save_result(self):
        merged = self.right_view.merged_lines()
        if not merged:
            QMessageBox.information(self, tr("merge_save", "保存"),
                                    tr("merge_no_result", "没有可保存的合并结果。"))
            return
        try:
            path = self.repo.full_path(self.path)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(merged) + "\n")
            QMessageBox.information(self, tr("merge_save", "保存"),
                                    tr("merge_saved", "已写入 {}").format(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("error"), str(exc))

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