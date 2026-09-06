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
from .locatorbar import LocatorBar
from .movedblocks import mark_moved as mark_moved_blocks
from .undo import AllViewState, get_undo
from .viewdata import DiffState, EOL, HideState, ViewData


class MergeFrm(QMainWindow):
    """并排 diff 主窗口（对齐 TortoiseGitMerge CMainFrame）。"""

    def __init__(self, repo: Repository, path: str, rev1: str | None,
                 rev2: str | None, parent=None, three_way: bool = False):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.path = path
        self.rev1 = rev1
        self.rev2 = rev2
        self.three_way = three_way
        self.setWindowTitle(tr("merge_title", "比较 - {}").format(path))
        self.resize(1020, 680 if not three_way else 760)
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
        self._act_undo = tb.addAction(tr("merge_undo", "撤销"))
        self._act_undo.triggered.connect(self._undo)
        self._act_redo = tb.addAction(tr("merge_redo", "重做"))
        self._act_redo.triggered.connect(self._redo)
        tb.addSeparator()
        self._act_find = tb.addAction(tr("merge_find", "查找"))
        self._act_find.triggered.connect(self._find)
        self._act_goto = tb.addAction(tr("merge_goto", "跳转行"))
        self._act_goto.triggered.connect(self._goto_line)
        lay.addWidget(tb)

        split = QSplitter(Qt.Orientation.Horizontal, central)
        self.left_view = LeftView(split)
        self.right_view = RightView(split)
        split.addWidget(self.left_view)
        split.addWidget(self.right_view)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)

        if self.three_way:
            # 三栏合并：上方左右对比 + 下方合并输出
            outer = QSplitter(Qt.Orientation.Vertical, central)
            outer.addWidget(split)
            self.bottom_view = LeftView(outer)
            self._bottom_label = QLabel(tr("merge_output", "合并输出"), outer)
            bottom_box = _wrap_box(outer, self.bottom_view, self._bottom_label)
            outer.addWidget(bottom_box)
            outer.setStretchFactor(0, 3)
            outer.setStretchFactor(1, 2)
            lay.addWidget(outer, 1)
        else:
            lay.addWidget(split, 1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, central)
        box.rejected.connect(self.close)
        box.button(QDialogButtonBox.StandardButton.Close).setText(tr("close"))
        lay.addWidget(box)

        self.setCentralWidget(central)

    def _load(self):
        if self.three_way:
            left, right, bottom = DiffData(self.repo).three_way(
                self.path, self.rev2 or "HEAD", self.rev1 or "HEAD")
            mark_moved_blocks(
                left, right, left_lines=[vd.line for vd in left],
                right_lines=[vd.line for vd in right], min_block=3)
            self.left_view.set_view_data(left)
            self.right_view.set_view_data(right)
            self.bottom_view.set_view_data(bottom)
            self._undo_stack = get_undo()
            self._undo_stack.clear()
            self.line_bar.set_rows([vd.state for vd in left])
            self._locator = LocatorBar(self)
            self._locator.set_states([vd.state for vd in left])
            self._locator._on_locate = self._on_bar_click
            self._sync_scrolls()
            conflicts = sum(1 for vd in bottom if vd.is_conflict)
            self._header.setText(
                f" {self.path}  ·  ours={self.rev2 or '工作区'}  theirs={self.rev1 or '工作区'}   "
                f"冲突 {conflicts}")
            return
        left, right = DiffData(self.repo).load(self.path, self.rev1, self.rev2)
        # 移动块检测（对齐 TortoiseMerge MovedBlocks）：把左右匹配行标 MovedFrom/MovedTo
        mark_moved_blocks(
            left, right, left_lines=[vd.line for vd in left],
            right_lines=[vd.line for vd in right], min_block=3)
        self.left_view.set_view_data(left)
        self.right_view.set_view_data(right)
        self._undo_stack = get_undo()
        self._undo_stack.clear()
        self.line_bar.set_rows([vd.state for vd in left])
        self._locator = LocatorBar(self)
        self._locator.set_states([vd.state for vd in left])
        self._locator._on_locate = self._on_bar_click
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
        if self.three_way and hasattr(self, "bottom_view"):
            self.left_view.verticalScrollBar().valueChanged.connect(
                self.bottom_view.verticalScrollBar().setValue)
            self.right_view.verticalScrollBar().valueChanged.connect(
                self.bottom_view.verticalScrollBar().setValue)

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

    def _save_undo_step(self):
        """记录一次变更前的状态到撤销栈（翻译 CBaseView::SaveUndoStep）。"""
        st = AllViewState().snapshot(
            [vd for vd in self.left_view.view_data],
            [vd for vd in self.right_view.view_data])
        self._undo_stack.add_state(st)

    def _take(self, side: str):
        line = self._current_line()
        if line < 0 or line >= len(self.left_view.view_data):
            return
        self._save_undo_step()
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
        self._save_undo_step()
        self.left_view.mark_resolved(line)
        self.right_view.mark_resolved(line)
        self._update_header()

    def _undo(self):
        if self._undo_stack.undo(
                [vd for vd in self.left_view.view_data],
                [vd for vd in self.right_view.view_data]):
            self.left_view._rebuild()
            self.right_view._rebuild()
            self._update_header()

    def _redo(self):
        if self._undo_stack.redo(
                [vd for vd in self.left_view.view_data],
                [vd for vd in self.right_view.view_data]):
            self.left_view._rebuild()
            self.right_view._rebuild()
            self._update_header()

    def _find(self):
        from .finddlg import FindDlg
        dlg = FindDlg(self, replace_mode=False)
        if dlg.exec():
            self._find_text = dlg.get_find_string()
            self._search_down = dlg.search_down
            self._case = dlg.case_sensitive
            self._highlight_find(self._find_text)

    def _highlight_find(self, text: str):
        if not text:
            return
        import re
        flags = 0 if self._case else re.IGNORECASE
        from PySide6.QtGui import QColor, QTextCharFormat
        from PySide6.QtWidgets import QTextEdit
        for view in (self.left_view, self.right_view):
            extra = []
            for block in range(view.document().blockCount()):
                blk = view.document().findBlockByNumber(block)
                if re.search(text, blk.text(), flags):
                    sel = QTextEdit.ExtraSelection()
                    sel.cursor = view.textCursor()
                    sel.cursor.setPosition(blk.position())
                    sel.cursor.setPosition(blk.position() + len(blk.text()),
                                           sel.cursor.MoveMode.KeepAnchor)
                    fmt = QTextCharFormat()
                    fmt.setBackground(QColor(255, 255, 0))
                    sel.format = fmt
                    extra.append(sel)
            view.setExtraSelections(extra)

    def _goto_line(self):
        from .gotolinedlg import GotoLineDlg
        dlg = GotoLineDlg(self, line_count=max(1, len(self.left_view.view_data)))
        if dlg.exec():
            line = dlg.get_line_number() - 1
            self.left_view.go_to_diff(line, self.right_view)

    def _update_header(self):
        if self.three_way and hasattr(self, "bottom_view"):
            conflicts = sum(1 for vd in self.bottom_view.view_data if vd.is_conflict)
            self._header.setText(
                f" {self.path}  ·  ours={self.rev2 or '工作区'}  theirs={self.rev1 or '工作区'}   "
                f"冲突 {conflicts}")
            return
        added = sum(1 for vd in self.right_view.view_data if vd.is_added)
        removed = sum(1 for vd in self.left_view.view_data if vd.is_removed)
        solved = sum(1 for vd in self.right_view.view_data
                      if vd.state == DiffState.ConflictsResolved)
        self._header.setText(
            f" {self.path}  ·  {(self.rev1 or '工作区')} → {(self.rev2 or '工作区')}   "
            f"+{added}/-{removed}   已解决 {solved}")

    def _save_result(self):
        if self.three_way and hasattr(self, "bottom_view"):
            merged = self.bottom_view.merged_lines()
        else:
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


def _wrap_box(parent, view, label):
    """把 label + view 包进一个 QWidget。"""
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    box = QWidget(parent)
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    v.addWidget(label)
    v.addWidget(view, 1)
    return box
    return frm