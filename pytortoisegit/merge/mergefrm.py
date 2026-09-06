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
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QToolButton,
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
        self._build_menu()
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


    def _build_menu(self):
        """Ribbon 风格分组工具栏（对齐 TortoiseGitMerge UIRibbon 观感）。"""
        self.ribbon = QToolBar(tr("merge_ribbon", "Ribbon"), self)
        self.ribbon.setMovable(False)
        self.ribbon.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        try:
            from ..res import icons as _icons
        except Exception:
            _icons = None

        def _btn(label, icon_id, slot):
            b = QToolButton(self.ribbon)
            b.setText(label)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            if _icons is not None:
                ic = _icons.icon(icon_id)
                if ic is not None and not ic.isNull():
                    b.setIcon(ic)
            b.clicked.connect(slot)
            self.ribbon.addWidget(b)
            return b

        def _title(text):
            lab = QLabel(text, self.ribbon)
            self.ribbon.addWidget(lab)
            return lab

        _title(tr("merge_group_file", "文件"))
        _btn(tr("merge_save", "保存"), "IDI_SAVE", self._save_result)
        _btn(tr("merge_reload", "重新加载"), "IDI_REFRESH", self._load)
        self.ribbon.addSeparator()
        _title(tr("merge_group_edit", "编辑"))
        _btn(tr("merge_undo", "撤销"), "IDI_RESTORE", self._undo)
        _btn(tr("merge_redo", "重做"), "IDI_RESTOREOVL", self._redo)
        _btn(tr("merge_find", "查找"), "IDI_LOGFILTER", self._find)
        _btn(tr("merge_goto", "跳转行"), "IDI_OPEN", self._goto_line)
        self.ribbon.addSeparator()
        _title(tr("merge_group_nav", "导航"))
        _btn(tr("merge_prev", "上一差异"), "IDI_SWITCHLEFTRIGHT", lambda: self._goto_diff(-1))
        _btn(tr("merge_next", "下一差异"), "IDI_SWITCHLEFTRIGHT", lambda: self._goto_diff(1))
        self.ribbon.addSeparator()
        _title(tr("merge_group_merge", "合并"))
        _btn(tr("merge_take_left", "取左侧"), "IDI_ACTIONDELETED", lambda: self._take("left"))
        _btn(tr("merge_take_right", "取右侧"), "IDI_ACTIONADDED", lambda: self._take("right"))
        _btn(tr("merge_mark", "标记已解决"), "IDI_MERGEACTIVE", self._mark_resolved)
        _btn(tr("merge_undo", "撤销合并"), "IDI_RESTORE", self._undo)
        self.addToolBar(self.ribbon)

    def _file_open(self):
        from .opendlg import OpenDlg
        dlg = OpenDlg(self)
        if dlg.exec():
            self._load()

    def _toggle_locator(self, on: bool):
        if hasattr(self, "_locator"):
            self._locator.setVisible(on)

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
            # 合并输出可编辑（TortoiseMerge BottomView 可直接编辑解决冲突）
            self.bottom_view.set_writable(True)
            self.bottom_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.bottom_view.customContextMenuRequested.connect(self._on_bottom_menu)
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

    def _on_bottom_menu(self, pos):
        """合并输出右键：取我方/对方块、标记已解决（对齐 BottomView Use*）。"""
        if not self.three_way:
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        act_ours = menu.addAction(tr("merge_take_right", "取我方(ours)"))
        act_theirs = menu.addAction(tr("merge_take_left", "取对方(theirs)"))
        act_mark = menu.addAction(tr("merge_mark", "标记已解决"))
        chosen = menu.exec(self.bottom_view.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        block = self._current_conflict_block()
        if chosen is act_mark:
            self._mark_conflict_resolved(block)
        elif chosen is act_ours:
            self._resolve_conflict(block, self.right_view)
        elif chosen is act_theirs:
            self._resolve_conflict(block, self.left_view)
        self._update_header()

    def _current_conflict_block(self) -> list:
        """返回当前光标处冲突块(cursor 起止行)的 [start,end] 行号；非冲突返回 []。"""
        cur = self.bottom_view.textCursor().blockNumber()
        blocks = self.bottom_view.document().blockCount()
        # 向上找 <<<<<<<，向下找 >>>>>>>
        start = cur
        while start > 0:
            blk = self.bottom_view.document().findBlockByNumber(start).text()
            if blk.startswith("<<<<<<<"):
                break
            start -= 1
        end = cur
        while end < blocks - 1:
            blk = self.bottom_view.document().findBlockByNumber(end).text()
            if blk.startswith(">>>>>>>"):
                break
            end += 1
        if self.bottom_view.document().findBlockByNumber(start).text().startswith("<<<<<<<") and \
           self.bottom_view.document().findBlockByNumber(end).text().startswith(">>>>>>>"):
            return [start, end]
        return []

    def _resolve_conflict(self, block, source):
        """用 source 视图的对应行替换冲突块。"""
        if not block:
            return
        start, end = block
        doc = self.bottom_view.document()
        # 取冲突块内 first 有效行文本：优先从 ours(右) 取，否则 theirs
        chosen_line = ""
        for b in range(start, end + 1):
            txt = doc.findBlockByNumber(b).text().strip()
            if txt and not txt.startswith(("<<<<<<<", "=======", ">>>>>>>")):
                chosen_line = txt
                break
        # 重建：把 [start,end] 替换为一行 chosen_line
        cursor = self.bottom_view.textCursor()
        cursor.setPosition(doc.findBlockByNumber(start).position())
        cursor.setPosition(doc.findBlockByNumber(end).position() + len(doc.findBlockByNumber(end).text()),
                           cursor.MoveMode.KeepAnchor)
        cursor.insertText(chosen_line)

    def _mark_conflict_resolved(self, block):
        if not block:
            return
        start, end = block
        doc = self.bottom_view.document()
        cursor = self.bottom_view.textCursor()
        cursor.setPosition(doc.findBlockByNumber(start).position())
        cursor.setPosition(doc.findBlockByNumber(end).position() + len(doc.findBlockByNumber(end).text()),
                           cursor.MoveMode.KeepAnchor)
        # 取我方块文本（第二个区段）
        import re
        text = cursor.selectedText()
        m = re.search(r'=======\n(.*?)\n>>>>>>>', text, re.S)
        chosen = m.group(1) if m else ""
        cursor.insertText(chosen)
        self._update_header()

    def _update_header(self):
        if self.three_way and hasattr(self, "bottom_view"):
            text = self.bottom_view.toPlainText()
            conflicts = text.count("<<<<<<<")
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
            # 编辑后的合并输出直接取文本
            merged = self.bottom_view.toPlainText().splitlines()
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