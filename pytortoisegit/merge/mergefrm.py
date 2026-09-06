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

菜单对齐 TortoiseMergeENG.rc 的 IDR_MAINFRAME MENU：
File / Edit / Navigate / View / Help。
工具栏对齐 IDR_MAINFRAME TOOLBAR。
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QSplitter, QToolBar, QVBoxLayout, QWidget,
)

from ..git.repo import Repository
from ..res.strings import tr
from .baseview import BaseView, BottomView, LeftView, RightView
from .diffdata import DiffData, IgnoreWS
from .linediffbar import LineDiffBar
from .locatorbar import LocatorBar
from .movedblocks import mark_moved as mark_moved_blocks
from .undo import AllViewState, get_undo
from .viewdata import DiffState, HideState


class MergeFrm(QMainWindow):
    """并排 diff 主窗口（对齐 TortoiseGitMerge CMainFrame）。"""

    def __init__(self, repo: Repository | None, path: str, rev1: str | None,
                 rev2: str | None, parent=None, three_way: bool = False):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.path = path
        self.rev1 = rev1
        self.rev2 = rev2
        self.three_way = three_way
        self._local_left = ""
        self._local_right = ""
        self.ignore_ws = IgnoreWS.None_
        self.ignore_eol = False
        self.ignore_comments = False
        self.ignore_case = False
        self.inline_diff = True
        self.inline_word = True
        self.show_ws = False
        self.wrap_lines = False
        self.view_moved = True
        self.one_way = False
        self.collapsed = False
        self.edit_enabled = False
        self._search = ""
        self._search_down = True
        self._case = False
        self.setWindowTitle(tr("tm_title", "TortoiseGitMerge - {}").format(path or ""))
        self.resize(1100, 720 if not three_way else 820)
        try:
            from ..res import icons
            self.setWindowIcon(icons.app_icon())
        except Exception:
            pass
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._load()

    # ---- 布局 ----
    def _build_central(self):
        central = QWidget(self)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        self._header = QLabel("", central)
        self._header.setWordWrap(True)
        lay.addWidget(self._header)

        body = QHBoxLayout()
        self.locator = LocatorBar(central)
        self.locator._on_locate = self._on_bar_click
        body.addWidget(self.locator)

        views = QSplitter(Qt.Orientation.Horizontal, central)
        self.left_view = LeftView(views)
        self.right_view = RightView(views)
        self.left_view.other_view = self.right_view
        self.right_view.other_view = self.left_view
        views.addWidget(self.left_view)
        views.addWidget(self.right_view)
        views.setStretchFactor(0, 1)
        views.setStretchFactor(1, 1)
        self._h_split = views

        if self.three_way:
            outer = QSplitter(Qt.Orientation.Vertical, central)
            outer.addWidget(views)
            self.bottom_view = BottomView(outer)
            self.bottom_view.other_view = self.right_view
            self.bottom_view.set_writable(True)
            outer.addWidget(self.bottom_view)
            outer.setStretchFactor(0, 3)
            outer.setStretchFactor(1, 2)
            body.addWidget(outer, 1)
        else:
            self.bottom_view = None
            body.addWidget(views, 1)
        lay.addLayout(body, 1)

        self.line_bar = LineDiffBar(central)
        lay.addWidget(self.line_bar)
        self.setCentralWidget(central)

        for v in self._views():
            v.line_moved.connect(self._on_view_line)
            v.verticalScrollBar().valueChanged.connect(self._sync_from)

    def _build_statusbar(self):
        self._status = QLabel("")
        self.statusBar().addWidget(self._status, 1)
        self._col_lab = QLabel(tr("tm_col", "列: 0"))
        self.statusBar().addPermanentWidget(self._col_lab)

    def _views(self) -> List[BaseView]:
        out = [self.left_view, self.right_view]
        if self.bottom_view is not None:
            out.append(self.bottom_view)
        return out

    # ---- 菜单（IDR_MAINFRAME MENU）----
    def _act(self, text: str, slot, shortcut: str | None = None,
             checkable: bool = False, checked: bool = False, icon: str = "") -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if icon:
            try:
                from ..res import icons
                ic = icons.icon(icon)
                if ic and not ic.isNull():
                    act.setIcon(ic)
            except Exception:
                pass
        if checkable:
            act.setCheckable(True)
            act.setChecked(checked)
            act.toggled.connect(slot)
        else:
            act.triggered.connect(slot)
        return act

    def _build_menu(self):
        bar = self.menuBar()
        m_file = bar.addMenu(tr("tm_file", "文件(&F)"))
        m_file.addAction(self._act(tr("tm_open", "打开"), self._file_open, "Ctrl+O", icon="IDI_OPEN"))
        m_file.addAction(self._act(tr("tm_save", "保存"), self._save_result, "Ctrl+S", icon="IDI_SAVE"))
        m_file.addAction(self._act(tr("tm_saveas", "另存为..."), self._save_as, icon="IDI_SAVEAS"))
        m_file.addAction(self._act(tr("tm_mark", "标记为已解决"), self._mark_resolved))
        m_file.addSeparator()
        m_file.addAction(self._act(tr("tm_patch", "创建补丁文件"), self._create_patch))
        m_file.addSeparator()
        m_file.addAction(self._act(tr("tm_reload", "重新加载"), self._load, "F5", icon="IDI_REFRESH"))
        self._act_edit_en = self._act(tr("tm_enable_edit", "允许编辑"), self._toggle_edit,
                                      checkable=True, checked=False)
        m_file.addAction(self._act_edit_en)
        m_file.addSeparator()
        m_file.addAction(self._act(tr("tm_exit", "退出"), self.close, "Ctrl+Q"))

        m_edit = bar.addMenu(tr("tm_edit", "编辑(&E)"))
        m_edit.addAction(self._act(tr("tm_undo", "撤销"), self._undo, "Ctrl+Z"))
        m_edit.addAction(self._act(tr("tm_redo", "重做"), self._redo, "Ctrl+Y"))
        m_edit.addSeparator()
        m_edit.addAction(self._act(tr("tm_copy", "复制"), self._copy, "Ctrl+C"))
        m_edit.addAction(self._act(tr("tm_paste", "粘贴"), self._paste, "Ctrl+V"))
        m_edit.addSeparator()
        m_edit.addAction(self._act(tr("tm_use_left_block", "使用左侧块"), lambda: self._use_block("left")))
        m_edit.addAction(self._act(tr("tm_use_left_file", "使用左侧文件"), self._use_left_file))
        m_edit.addAction(self._act(tr("tm_use_left_before", "先左后右"),
                                   lambda: self._use_both("left_first")))
        m_edit.addAction(self._act(tr("tm_use_right_before", "先右后左"),
                                   lambda: self._use_both("right_first")))
        m_edit.addSeparator()
        m_edit.addAction(self._act(tr("tm_use_theirs", "使用左侧文本块"),
                                   lambda: self._use_block("left")))
        m_edit.addAction(self._act(tr("tm_use_mine", "使用右侧文本块"),
                                   lambda: self._use_block("right")))
        m_edit.addAction(self._act(tr("tm_use_theirs_then", "先左后右文本块"),
                                   lambda: self._use_both("left_first")))
        m_edit.addAction(self._act(tr("tm_use_mine_then", "先右后左文本块"),
                                   lambda: self._use_both("right_first")))
        m_edit.addSeparator()
        m_edit.addAction(self._act(tr("tm_find", "查找"), self._find, "Ctrl+F"))
        m_edit.addAction(self._act(tr("tm_find_next", "查找下一个"), self._find_next, "F3"))
        m_edit.addAction(self._act(tr("tm_find_prev", "查找上一个"), self._find_prev, "Shift+F3"))
        m_edit.addAction(self._act(tr("tm_goto", "跳转到行"), self._goto_line, "Ctrl+G"))
        m_edit.addSeparator()
        m_edit.addAction(self._act(tr("tm_regex", "配置正则过滤器"), self._regex_filter))
        self._act_ign_cmt = self._act(tr("tm_ignore_comments", "忽略注释"),
                                      self._toggle_ignore_comments, checkable=True)
        m_edit.addAction(self._act_ign_cmt)

        m_nav = bar.addMenu(tr("tm_nav", "导航(&N)"))
        m_nav.addAction(self._act(tr("tm_next_diff", "下一处差异"),
                                  lambda: self._goto_diff(1), "Ctrl+Down", icon="IDI_JUMPDOWN"))
        m_nav.addAction(self._act(tr("tm_prev_diff", "上一处差异"),
                                  lambda: self._goto_diff(-1), "Ctrl+Up", icon="IDI_JUMPUP"))
        m_nav.addAction(self._act(tr("tm_next_conf", "下一处冲突"),
                                  lambda: self._goto_conflict(1)))
        m_nav.addAction(self._act(tr("tm_prev_conf", "上一处冲突"),
                                  lambda: self._goto_conflict(-1)))
        m_nav.addAction(self._act(tr("tm_next_inline", "下一处行内差异"),
                                  lambda: self._goto_inline(1)))
        m_nav.addAction(self._act(tr("tm_prev_inline", "上一处行内差异"),
                                  lambda: self._goto_inline(-1)))

        m_view = bar.addMenu(tr("tm_view", "视图(&V)"))
        self._act_tb = self._act(tr("tm_toolbar", "工具栏"), self._toggle_toolbar,
                                 checkable=True, checked=True)
        m_view.addAction(self._act_tb)
        self._act_sb = self._act(tr("tm_statusbar", "状态栏"), self._toggle_statusbar,
                                 checkable=True, checked=True)
        m_view.addAction(self._act_sb)
        self._act_ldb = self._act(tr("tm_linediffbar", "行差异条"), self._toggle_linediff,
                                  checkable=True, checked=True)
        m_view.addAction(self._act_ldb)
        self._act_loc = self._act(tr("tm_locator", "定位条"), self._toggle_locator,
                                  checkable=True, checked=True)
        m_view.addAction(self._act_loc)
        m_view.addSeparator()
        self._act_wrap = self._act(tr("tm_wrap", "折行"), self._toggle_wrap, checkable=True)
        m_view.addAction(self._act_wrap)
        self._act_moved = self._act(tr("tm_moved", "移动块"), self._toggle_moved,
                                    checkable=True, checked=True)
        m_view.addAction(self._act_moved)
        self._act_inline = self._act(tr("tm_inline", "行内差异"), self._toggle_inline,
                                     checkable=True, checked=True)
        m_view.addAction(self._act_inline)
        self._act_inline_w = self._act(tr("tm_inline_word", "按词行内差异"),
                                       self._toggle_inline_word, checkable=True, checked=True)
        m_view.addAction(self._act_inline_w)
        ws_group = QActionGroup(self)
        ws_group.setExclusive(True)
        self._act_cmp_ws = self._act(tr("tm_cmp_ws", "比较空白"),
                                     lambda on: on and self._set_ws(IgnoreWS.None_),
                                     checkable=True, checked=True)
        self._act_ign_ws = self._act(tr("tm_ign_ws", "忽略空白变化"),
                                     lambda on: on and self._set_ws(IgnoreWS.WhiteSpaces),
                                     checkable=True)
        self._act_ign_all_ws = self._act(tr("tm_ign_all_ws", "忽略全部空白变化"),
                                          lambda on: on and self._set_ws(IgnoreWS.AllWhiteSpaces),
                                          checkable=True)
        for a in (self._act_cmp_ws, self._act_ign_ws, self._act_ign_all_ws):
            ws_group.addAction(a)
            m_view.addAction(a)
        self._act_ign_cmt2 = self._act(tr("tm_ignore_comments", "忽略注释"),
                                       self._toggle_ignore_comments, checkable=True)
        m_view.addAction(self._act_ign_cmt2)
        self._act_ign_eol = self._act(tr("tm_ignore_eol", "忽略换行符"),
                                      self._toggle_ignore_eol, checkable=True)
        m_view.addAction(self._act_ign_eol)
        m_view.addSeparator()
        self._act_show_ws = self._act(tr("tm_show_ws", "显示空白"),
                                      self._toggle_show_ws, checkable=True)
        m_view.addAction(self._act_show_ws)
        self._act_oneway = self._act(tr("tm_oneway", "单栏/双栏切换"),
                                     self._toggle_oneway, checkable=True)
        m_view.addAction(self._act_oneway)
        m_view.addAction(self._act(tr("tm_switch", "左右视图对调"), self._switch_left,
                                   icon="IDI_SWITCHLEFTRIGHT"))
        self._act_collapse = self._act(tr("tm_collapse", "折叠未改段"),
                                       self._toggle_collapse, checkable=True)
        m_view.addAction(self._act_collapse)
        m_view.addSeparator()
        m_view.addAction(self._act(tr("tm_settings", "设置"), self._settings, icon="IDI_GENERAL"))
        m_view.addSeparator()
        m_view.addAction(self._act(tr("tm_filelist", "显示/隐藏补丁文件列表"), self._show_filelist))

        m_help = bar.addMenu(tr("tm_help", "帮助(&H)"))
        m_help.addAction(self._act(tr("tm_help_topics", "帮助主题"), self._help, "F1"))
        m_help.addSeparator()
        m_help.addAction(self._act(tr("tm_about", "关于 TortoiseGitMerge..."), self._about))

    def _build_toolbar(self):
        self.toolbar = QToolBar(tr("tm_toolbar", "工具栏"), self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        items = [
            (tr("tm_open", "打开"), self._file_open, "IDI_OPEN"),
            (tr("tm_save", "保存"), self._save_result, "IDI_SAVE"),
            None,
            (tr("tm_reload", "重新加载"), self._load, "IDI_REFRESH"),
            (tr("tm_undo", "撤销"), self._undo, ""),
            None,
            (tr("tm_prev_diff", "上一差异"), lambda: self._goto_diff(-1), "IDI_JUMPUP"),
            (tr("tm_next_diff", "下一差异"), lambda: self._goto_diff(1), "IDI_JUMPDOWN"),
            (tr("tm_prev_conf", "上一冲突"), lambda: self._goto_conflict(-1), "IDI_ACTIONCONFLICTED"),
            (tr("tm_next_conf", "下一冲突"), lambda: self._goto_conflict(1), "IDI_CONFLICTEDLINE"),
            None,
            (tr("tm_use_left_block", "使用左侧块"), lambda: self._use_block("left"), ""),
            None,
            (tr("tm_use_theirs", "使用左侧文本"), lambda: self._use_block("left"), ""),
            (tr("tm_use_mine", "使用右侧文本"), lambda: self._use_block("right"), ""),
            (tr("tm_use_theirs_then", "先左后右"), lambda: self._use_both("left_first"), ""),
            (tr("tm_use_mine_then", "先右后左"), lambda: self._use_both("right_first"), ""),
            None,
            (tr("tm_mark", "标记已解决"), self._mark_resolved, "IDI_MERGEACTIVE"),
            None,
            (tr("tm_settings", "设置"), self._settings, "IDI_GENERAL"),
        ]
        for item in items:
            if item is None:
                self.toolbar.addSeparator()
                continue
            label, slot, icon = item
            act = self._act(label, slot, icon=icon)
            self.toolbar.addAction(act)

    # ---- 数据加载 ----
    def _engine(self) -> DiffData:
        dd = DiffData(self.repo)
        dd.ignore_ws = self.ignore_ws
        dd.ignore_eol = self.ignore_eol
        dd.ignore_case = self.ignore_case
        dd.ignore_comments = self.ignore_comments
        return dd

    def _apply_view_flags(self):
        for v in self._views():
            v.inline_diff = self.inline_diff
            v.inline_word = self.inline_word
            v.show_whitespaces = self.show_ws
            v.collapsed = self.collapsed
            v.set_wrap(self.wrap_lines)
            v.other_view = self.right_view if v is self.left_view else self.left_view

    def _load(self):
        dd = self._engine()
        if self._local_left and self._local_right:
            left, right = dd.load_local(self._local_left, self._local_right)
            self.three_way = False
        elif self.three_way:
            left, right, bottom = dd.three_way(
                self.path, self.rev2 or "HEAD", self.rev1 or "HEAD")
            if self.view_moved:
                mark_moved_blocks(left, right,
                                  [vd.line for vd in left],
                                  [vd.line for vd in right], min_block=3)
            self._apply_view_flags()
            self.left_view.set_view_data(left)
            self.right_view.set_view_data(right)
            self.bottom_view.set_view_data(bottom)
            self.bottom_view.set_writable(True)
            self._undo_stack = get_undo()
            self._undo_stack.clear()
            self.locator.set_states([vd.state for vd in left])
            self._sync_scrolls()
            conflicts = sum(1 for vd in bottom if vd.is_conflict)
            self._header.setText(
                f" {self.path}  ·  ours={self.rev2 or '工作区'}  theirs={self.rev1 or '工作区'}   "
                f"{tr('tm_conflicts', '冲突')} {conflicts}")
            self._refresh_linebar()
            return
        else:
            left, right = dd.load(self.path, self.rev1, self.rev2)
        if self.view_moved:
            mark_moved_blocks(left, right,
                              [vd.line for vd in left],
                              [vd.line for vd in right], min_block=3)
        self._apply_view_flags()
        self.left_view.set_view_data(left)
        self.right_view.set_view_data(right)
        self._undo_stack = get_undo()
        self._undo_stack.clear()
        self.locator.set_states([vd.state for vd in left])
        self._sync_scrolls()
        added = sum(1 for vd in right if vd.is_added)
        removed = sum(1 for vd in left if vd.is_removed)
        self._header.setText(
            f" {self.path or self._local_left}  ·  "
            f"{(self.rev1 or self._local_left or '工作区')} → "
            f"{(self.rev2 or self._local_right or '工作区')}   +{added}/-{removed}")
        self._refresh_linebar()

    def _sync_scrolls(self):
        # 只连一次：用 blockSignals 避免递归由 valueChanged 自己处理
        pass

    def _sync_from(self, value: int):
        sender = self.sender()
        for v in self._views():
            if v.verticalScrollBar() is sender:
                continue
            bar = v.verticalScrollBar()
            if bar.value() != value:
                bar.blockSignals(True)
                bar.setValue(value)
                bar.blockSignals(False)
        self._update_locator_viewport()

    def _update_locator_viewport(self):
        bar = self.left_view.verticalScrollBar()
        self.locator.set_viewport(bar.value(), bar.value() + 40)

    def _on_bar_click(self, line: int):
        self.left_view.scroll_all_to_line(line, self.right_view)
        if self.bottom_view is not None:
            self.bottom_view.scroll_to_line(line)
        self._refresh_linebar()

    def _on_view_line(self, line: int):
        self._refresh_linebar()
        col = self.left_view.textCursor().columnNumber() + 1
        self._col_lab.setText(tr("tm_col_n", "列: {}").format(col))
        self._update_locator_viewport()

    def _refresh_linebar(self):
        line = self.left_view.current_view_line()
        lt = self.left_view.view_data[line].line if 0 <= line < len(self.left_view.view_data) else ""
        rt = self.right_view.view_data[line].line if 0 <= line < len(self.right_view.view_data) else ""
        self.line_bar.set_lines(lt, rt, self.inline_word)

    def _current_line(self) -> int:
        return self.left_view.current_view_line()

    def _goto_diff(self, direction: int):
        cur = self._current_line()
        nxt = (self.left_view.next_diff_from(cur) if direction > 0
               else self.left_view.prev_diff_from(cur))
        if nxt < 0:
            nxt = (self.left_view.first_diff_line() if direction > 0
                   else self.left_view.prev_diff_from(len(self.left_view.view_data)))
        if nxt >= 0:
            self.left_view.go_to_diff(nxt, self.right_view)
            if self.bottom_view is not None:
                self.bottom_view.scroll_to_line(nxt)
            self._refresh_linebar()

    def _goto_conflict(self, direction: int):
        view = self.bottom_view or self.left_view
        cur = view.current_view_line()
        nxt = (view.next_conflict_from(cur) if direction > 0
               else view.prev_conflict_from(cur))
        if nxt >= 0:
            self.left_view.go_to_diff(nxt, self.right_view)
            if self.bottom_view is not None:
                self.bottom_view.scroll_to_line(nxt)

    def _goto_inline(self, direction: int):
        start = self._current_line()
        n = len(self.left_view.view_data)
        rng = range(start + 1, n) if direction > 0 else range(start - 1, -1, -1)
        for i in rng:
            col = self.left_view.first_inline_col(i, forward=direction > 0)
            if col >= 0:
                self.left_view.go_to_diff(i, self.right_view)
                self._refresh_linebar()
                return

    def _save_undo_step(self):
        extra = [vd for vd in self.bottom_view.view_data] if self.bottom_view else None
        st = AllViewState().snapshot(
            [vd for vd in self.left_view.view_data],
            [vd for vd in self.right_view.view_data])
        self._undo_stack.add_state(st)
        _ = extra

    def _target_view(self) -> BaseView:
        return self.bottom_view if self.bottom_view is not None else self.right_view

    def _use_block(self, side: str):
        line = self._current_line()
        self._save_undo_step()
        src = self.left_view if side == "left" else self.right_view
        self._target_view().take_block(line, src)
        self._update_header()
        self._refresh_linebar()

    def _use_left_file(self):
        self._save_undo_step()
        self._target_view().take_file(self.left_view)
        self._update_header()

    def _use_both(self, order: str):
        line = self._current_line()
        start, end = self.left_view.block_range(line)
        if end < start:
            return
        self._save_undo_step()
        left_txt = [self.left_view.view_data[i].line
                    for i in range(start, end + 1)
                    if not self.left_view.view_data[i].is_empty]
        right_txt = [self.right_view.view_data[i].line
                     for i in range(start, end + 1)
                     if i < len(self.right_view.view_data)
                     and not self.right_view.view_data[i].is_empty]
        combined = (left_txt + right_txt) if order == "left_first" else (right_txt + left_txt)
        target = self._target_view()
        for i, text in enumerate(combined):
            idx = start + i
            if idx <= end and idx < len(target.view_data):
                target.view_data[idx].line = text
                target.view_data[idx].state = DiffState.ConflictsResolved
        for idx in range(start + len(combined), end + 1):
            if idx < len(target.view_data):
                target.view_data[idx].line = ""
                target.view_data[idx].state = DiffState.Empty
        target._rebuild()
        self._update_header()

    def _mark_resolved(self):
        line = self._current_line()
        self._save_undo_step()
        for v in self._views():
            v.mark_resolved(line)
        self._update_header()

    def _undo(self):
        if self._undo_stack.undo(
                [vd for vd in self.left_view.view_data],
                [vd for vd in self.right_view.view_data]):
            self.left_view._rebuild()
            self.right_view._rebuild()
            if self.bottom_view:
                self.bottom_view._rebuild()
            self._update_header()

    def _redo(self):
        if self._undo_stack.redo(
                [vd for vd in self.left_view.view_data],
                [vd for vd in self.right_view.view_data]):
            self.left_view._rebuild()
            self.right_view._rebuild()
            if self.bottom_view:
                self.bottom_view._rebuild()
            self._update_header()

    def _copy(self):
        v = self._active_view()
        QApplication.clipboard().setText(v.textCursor().selectedText())

    def _paste(self):
        v = self._active_view()
        if v.isReadOnly():
            return
        v.paste()

    def _active_view(self) -> BaseView:
        w = QApplication.focusWidget()
        for v in self._views():
            if v is w:
                return v
        return self.right_view

    def _find(self):
        from .finddlg import FindDlg
        dlg = FindDlg(self, replace_mode=False)
        if dlg.exec():
            self._search = dlg.get_find_string()
            self._search_down = dlg.search_down
            self._case = dlg.case_sensitive
            self._highlight_find(self._search)
            self._find_next()

    def _highlight_find(self, text: str):
        if not text:
            return
        import re
        flags = 0 if self._case else re.IGNORECASE
        from PySide6.QtGui import QColor, QTextCharFormat
        from PySide6.QtWidgets import QTextEdit
        for view in self._views():
            extra = []
            for block in range(view.document().blockCount()):
                blk = view.document().findBlockByNumber(block)
                if re.search(re.escape(text), blk.text(), flags):
                    sel = QTextEdit.ExtraSelection()
                    sel.cursor = view.textCursor()
                    sel.cursor.setPosition(blk.position())
                    sel.cursor.setPosition(blk.position() + len(blk.text()),
                                           QTextCursor.MoveMode.KeepAnchor)
                    fmt = QTextCharFormat()
                    fmt.setBackground(QColor(255, 255, 0))
                    sel.format = fmt
                    extra.append(sel)
            view.setExtraSelections(extra)

    def _find_step(self, direction: int):
        if not self._search:
            self._find()
            return
        import re
        flags = 0 if self._case else re.IGNORECASE
        view = self._active_view()
        cur = view.textCursor().blockNumber()
        n = view.document().blockCount()
        rng = range(cur + 1, n) if direction > 0 else range(cur - 1, -1, -1)
        for b in rng:
            txt = view.document().findBlockByNumber(b).text()
            if re.search(re.escape(self._search), txt, flags):
                view.scroll_to_line(view._screen_to_view[b] if b < len(view._screen_to_view) else b)
                return

    def _find_next(self):
        self._find_step(1)

    def _find_prev(self):
        self._find_step(-1)

    def _goto_line(self):
        from .gotolinedlg import GotoLineDlg
        dlg = GotoLineDlg(self, line_count=max(1, len(self.left_view.view_data)))
        if dlg.exec():
            line = dlg.get_line_number() - 1
            self.left_view.go_to_diff(line, self.right_view)

    def _file_open(self):
        from .opendlg import OpenDlg
        dlg = OpenDlg(self)
        if not dlg.exec():
            return
        if dlg.your_file and (dlg.their_file or dlg.base_file):
            self._local_left = dlg.their_file or dlg.base_file
            self._local_right = dlg.your_file
            self.path = self._local_right
            self.three_way = bool(dlg.base_file and dlg.their_file and dlg.your_file)
            if self.three_way:
                QMessageBox.information(
                    self, tr("tm_open", "打开"),
                    tr("tm_open_two", "当前按左右两个文件比较；三文件请用合并命令。"))
                self.three_way = False
            self._load()

    def _regex_filter(self):
        from .regexfiltersdlg import RegexFiltersDlg
        RegexFiltersDlg(self).exec()

    def _settings(self):
        from .settings import Settings
        Settings(self).exec()

    def _about(self):
        from .aboutdlg import AboutDlg
        AboutDlg(self).exec()

    def _help(self):
        QMessageBox.information(self, tr("tm_help_topics", "帮助主题"),
                                tr("tm_help_text", "TortoiseGitMerge 文本比较 / 合并。"))

    def _show_filelist(self):
        from .filepatchesdlg import FilePatchesDlg
        FilePatchesDlg(self).exec()

    def _create_patch(self):
        if self.repo is None or not self.path:
            QMessageBox.information(self, tr("tm_patch", "创建补丁"),
                                    tr("tm_patch_none", "没有可导出的仓库文件。"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("tm_patch", "创建补丁文件"), "", "Patch (*.patch *.diff)")
        if not path:
            return
        args = ["diff", "--no-color"]
        if self.rev1 and self.rev2:
            args += [self.rev1, self.rev2]
        elif self.rev1:
            args += [self.rev1]
        args += ["--", self.path]
        text = self.repo.runner.run(*args).stdout or ""
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        QMessageBox.information(self, tr("tm_patch", "创建补丁"), path)

    def _toggle_edit(self, on: bool):
        self.edit_enabled = on
        self.right_view.set_writable(on)
        if self.bottom_view is not None:
            self.bottom_view.set_writable(True)

    def _toggle_toolbar(self, on: bool):
        self.toolbar.setVisible(on)

    def _toggle_statusbar(self, on: bool):
        self.statusBar().setVisible(on)

    def _toggle_linediff(self, on: bool):
        self.line_bar.setVisible(on)

    def _toggle_locator(self, on: bool):
        self.locator.setVisible(on)

    def _toggle_wrap(self, on: bool):
        self.wrap_lines = on
        for v in self._views():
            v.set_wrap(on)

    def _toggle_moved(self, on: bool):
        self.view_moved = on
        self._load()

    def _toggle_inline(self, on: bool):
        self.inline_diff = on
        self._apply_view_flags()
        for v in self._views():
            v._rebuild()
        self._refresh_linebar()

    def _toggle_inline_word(self, on: bool):
        self.inline_word = on
        self._apply_view_flags()
        for v in self._views():
            v._rebuild()
        self._refresh_linebar()

    def _set_ws(self, mode: IgnoreWS):
        self.ignore_ws = mode
        self._load()

    def _toggle_ignore_comments(self, on: bool):
        if self.ignore_comments == on:
            self._act_ign_cmt.setChecked(on)
            self._act_ign_cmt2.setChecked(on)
            return
        self.ignore_comments = on
        self._act_ign_cmt.blockSignals(True)
        self._act_ign_cmt2.blockSignals(True)
        self._act_ign_cmt.setChecked(on)
        self._act_ign_cmt2.setChecked(on)
        self._act_ign_cmt.blockSignals(False)
        self._act_ign_cmt2.blockSignals(False)
        self._load()

    def _toggle_ignore_eol(self, on: bool):
        self.ignore_eol = on
        self._load()

    def _toggle_show_ws(self, on: bool):
        self.show_ws = on
        self._apply_view_flags()
        for v in self._views():
            v._rebuild()

    def _toggle_oneway(self, on: bool):
        self.one_way = on
        self.left_view.setVisible(not on)

    def _switch_left(self):
        ld, rd = self.left_view.view_data, self.right_view.view_data
        self.left_view.set_view_data(rd)
        self.right_view.set_view_data(ld)
        self._refresh_linebar()

    def _toggle_collapse(self, on: bool):
        self.collapsed = on
        for vd in self.left_view.view_data:
            if not vd.is_diff:
                vd.hidestate = HideState.Hidden if on else HideState.Shown
        for vd in self.right_view.view_data:
            if not vd.is_diff:
                vd.hidestate = HideState.Hidden if on else HideState.Shown
        self._apply_view_flags()
        for v in self._views():
            v._rebuild()

    def _update_header(self):
        if self.three_way and self.bottom_view is not None:
            conflicts = sum(1 for vd in self.bottom_view.view_data if vd.is_conflict)
            self._header.setText(
                f" {self.path}  ·  ours={self.rev2 or '工作区'}  theirs={self.rev1 or '工作区'}   "
                f"{tr('tm_conflicts', '冲突')} {conflicts}")
            return
        added = sum(1 for vd in self.right_view.view_data if vd.is_added)
        removed = sum(1 for vd in self.left_view.view_data if vd.is_removed)
        solved = sum(1 for vd in self.right_view.view_data
                      if vd.state == DiffState.ConflictsResolved)
        self._header.setText(
            f" {self.path or ''}  ·  {(self.rev1 or '工作区')} → {(self.rev2 or '工作区')}   "
            f"+{added}/-{removed}   {tr('tm_resolved', '已解决')} {solved}")

    def _save_result(self):
        target = self._target_view()
        merged = target.merged_lines()
        if not merged:
            QMessageBox.information(self, tr("tm_save", "保存"),
                                    tr("tm_no_result", "没有可保存的合并结果。"))
            return
        dest = ""
        if self.repo is not None and self.path:
            dest = self.repo.full_path(self.path)
        elif self._local_right:
            dest = self._local_right
        if not dest:
            return self._save_as()
        try:
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(merged) + "\n")
            QMessageBox.information(self, tr("tm_save", "保存"),
                                    tr("tm_saved", "已写入 {}").format(dest))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("error"), str(exc))

    def _save_as(self):
        target = self._target_view()
        merged = target.merged_lines()
        path, _ = QFileDialog.getSaveFileName(self, tr("tm_saveas", "另存为"), self.path or "")
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(merged) + "\n")

    def exec(self):
        self.show()
        return QApplication.instance().exec() if QApplication.instance() else 0


def open_merge_window(repo: Repository, path: str, rev1: str | None,
                      rev2: str | None, parent=None):
    frm = MergeFrm(repo, path, rev1, rev2, parent)
    frm.show()
    return frm
