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

默认对齐 TortoiseGitMergeRibbon.xml（UseRibbons=TRUE）：
Application Menu + Edit 页的 Edit/Navigate/Blocks/Whitespaces/Diff/View。
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QSplitter, QVBoxLayout, QWidget,
)

from ..git.mergeop import mark_resolved
from ..git.repo import Repository
from ..res.strings import tr
from .baseview import BaseView, BottomView, LeftView, RightView
from .blocks import (
    first_conflict_index, serialize_view, use_both_blocks, use_both_left_first,
    use_both_right_first,
)
from .diffdata import DiffData, IgnoreWS
from .linediffbar import LineDiffBar
from .locatorbar import LocatorBar
from .ribbon import MergeRibbon
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
        self.ignore_eol = True
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
        self._marked_as_resolved = False
        self._search = ""
        self._search_down = True
        self._case = False
        self.setWindowTitle(tr("tm_title", "TortoiseGitMerge - {}").format(path or ""))
        self.resize(1100, 720 if not three_way else 820)
        self.setAcceptDrops(True)
        self._recent_files: List[str] = []
        self._load_recent_files()
        try:
            from ..res import icons
            self.setWindowIcon(icons.app_icon())
        except Exception:
            pass
        self._create_actions()
        self.ribbon = MergeRibbon(self._acts, self)
        self.setMenuWidget(self.ribbon)
        self.toolbar = self.ribbon
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
            v.caret_line_changed.connect(self._on_caret_line)
            v.verticalScrollBar().valueChanged.connect(self._sync_from)
            v.horizontalScrollBar().valueChanged.connect(self._sync_h_from)

    def _build_statusbar(self):
        self._status = QLabel("")
        self.statusBar().addWidget(self._status, 1)
        self._eol_lab = QLabel("")
        self.statusBar().addPermanentWidget(self._eol_lab)
        self._enc_lab = QLabel("")
        self.statusBar().addPermanentWidget(self._enc_lab)
        self._col_lab = QLabel(tr("tm_col", "列: 0"))
        self.statusBar().addPermanentWidget(self._col_lab)

    def _update_statusbar_encoding(self):
        """状态栏显示行尾与编码（对齐 CMainFrame 的 EOL/编码面板）。"""
        from .eol import get_eol_name
        from .filetextlines import get_encoding_name
        v = self.left_view
        self._eol_lab.setText(get_eol_name(v.get_line_endings()))
        self._enc_lab.setText(get_encoding_name(v.get_text_type()))

    def ask_user_for_new_line_endings_and_text_type(self, text_id: int = 0) -> bool:
        """打开编码/行尾对话框并应用到目标视图（对齐 AskUserForNewLineEndingsAndTextType）。"""
        v = self._target_view()
        if v.is_readonly():
            return False
        from .encodingdlg import EncodingDlg
        from .filetextlines import UnicodeType
        dlg = EncodingDlg(self, texttype=int(v.get_text_type().value),
                          eol=v.get_line_endings())
        if not dlg.exec():
            return False
        try:
            v.set_text_type(UnicodeType(dlg.texttype))
        except ValueError:
            pass
        v.replace_line_endings(dlg.lineendings)
        self._update_statusbar_encoding()
        return True

    def _views(self) -> List[BaseView]:
        out = [self.left_view, self.right_view]
        if self.bottom_view is not None:
            out.append(self.bottom_view)
        return out

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
        self.addAction(act)
        return act

    def _create_actions(self):
        """命令集对齐 TortoiseGitMergeRibbon.xml 的 Application.Commands。"""
        a: dict[str, QAction] = {}
        a["open"] = self._act(tr("tm_open", "打开"), self._file_open, "Ctrl+O", icon="IDI_OPEN")
        a["save"] = self._act(tr("tm_save", "保存"), self._save_result, "Ctrl+S", icon="IDI_SAVE")
        a["saveas"] = self._act(tr("tm_saveas", "另存为"), self._save_as, icon="IDI_SAVEAS")
        a["patch"] = self._act(tr("tm_patch", "创建补丁文件"), self._create_patch, icon="IDI_TORTOISEUDIFF")
        a["filelist"] = self._act(tr("tm_filelist", "显示/隐藏补丁文件列表"), self._show_filelist)
        a["settings"] = self._act(tr("tm_settings", "设置"), self._settings, icon="IDI_GENERAL")
        a["about"] = self._act(tr("tm_about", "关于 TortoiseGitMerge..."), self._about)
        a["exit"] = self._act(tr("tm_exit", "退出"), self.close, "Ctrl+Q")
        a["reload"] = self._act(tr("tm_reload", "重新加载"), self._load, "F5", icon="IDI_REFRESH")
        a["undo"] = self._act(tr("tm_undo", "撤销"), self._undo, "Ctrl+Z", icon="IDI_RESET")
        a["redo"] = self._act(tr("tm_redo", "重做"), self._redo, "Ctrl+Y", icon="IDI_RESTORE")
        self._act_edit_en = a["enable_edit"] = self._act(
            tr("tm_enable_edit", "允许编辑"), self._toggle_edit, checkable=True, icon="IDI_NOTEPAD")
        a["copy"] = self._act(tr("tm_copy", "复制"), self._copy, "Ctrl+C", icon="IDI_BLAME_POPUP_COPY")
        a["paste"] = self._act(tr("tm_paste", "粘贴"), self._paste, "Ctrl+V")
        a["find"] = self._act(tr("tm_find", "查找"), self._find, "Ctrl+F", icon="IDI_FILTEREDIT")
        a["find_next"] = self._act(tr("tm_find_next", "查找下一个"), self._find_next, "F3")
        a["find_prev"] = self._act(tr("tm_find_prev", "查找上一个"), self._find_prev, "Shift+F3")
        a["goto"] = self._act(tr("tm_goto", "跳转到行"), self._goto_line, "Ctrl+G")
        a["mark"] = self._act(tr("tm_mark", "标记为已解决"), self._mark_resolved, icon="IDI_MERGEACTIVE")
        a["prev_diff"] = self._act(tr("tm_prev_diff", "上一处差异"),
                                   lambda: self._goto_diff(-1), "Ctrl+Up", icon="IDI_JUMPUP")
        a["next_diff"] = self._act(tr("tm_next_diff", "下一处差异"),
                                   lambda: self._goto_diff(1), "Ctrl+Down", icon="IDI_JUMPDOWN")
        a["prev_conf"] = self._act(tr("tm_prev_conf", "上一处冲突"),
                                   lambda: self._goto_conflict(-1), icon="IDI_ACTIONCONFLICTED")
        a["next_conf"] = self._act(tr("tm_next_conf", "下一处冲突"),
                                   lambda: self._goto_conflict(1), icon="IDI_CONFLICTEDLINE")
        a["prev_inline"] = self._act(tr("tm_prev_inline", "上一处行内差异"),
                                     lambda: self._goto_inline(-1))
        a["next_inline"] = self._act(tr("tm_next_inline", "下一处行内差异"),
                                     lambda: self._goto_inline(1))
        a["use_left_block"] = self._act(tr("tm_use_left_block", "使用左侧块"),
                                        self._on_use_left_block)
        a["use_left_file"] = self._act(tr("tm_use_left_file", "使用左侧文件"),
                                       self._on_use_left_file)
        a["use_left_before"] = self._act(tr("tm_use_left_before", "先左后右"),
                                         self._on_use_both_left_first)
        a["use_right_before"] = self._act(tr("tm_use_right_before", "先右后左"),
                                          self._on_use_both_right_first)
        a["use_theirs"] = self._act(tr("tm_use_theirs", "使用左侧文本块"),
                                    self._on_use_theirs)
        a["use_mine"] = self._act(tr("tm_use_mine", "使用右侧文本块"),
                                  self._on_use_mine)
        a["use_theirs_then"] = self._act(tr("tm_use_theirs_then", "先左后右文本块"),
                                         self._on_use_theirs_then)
        a["use_mine_then"] = self._act(tr("tm_use_mine_then", "先右后左文本块"),
                                       self._on_use_mine_then)
        self._act_show_ws = a["show_ws"] = self._act(
            tr("tm_show_ws", "显示空白"), self._toggle_show_ws, checkable=True)
        ws_group = QActionGroup(self)
        ws_group.setExclusive(True)
        self._act_cmp_ws = a["cmp_ws"] = self._act(
            tr("tm_cmp_ws", "比较空白"),
            lambda on: on and self._set_ws(IgnoreWS.None_), checkable=True, checked=True)
        self._act_ign_ws = a["ign_ws"] = self._act(
            tr("tm_ign_ws", "忽略空白变化"),
            lambda on: on and self._set_ws(IgnoreWS.WhiteSpaces), checkable=True)
        self._act_ign_all_ws = a["ign_all_ws"] = self._act(
            tr("tm_ign_all_ws", "忽略全部空白变化"),
            lambda on: on and self._set_ws(IgnoreWS.AllWhiteSpaces), checkable=True)
        for key in ("cmp_ws", "ign_ws", "ign_all_ws"):
            ws_group.addAction(a[key])
        self._act_inline = a["inline"] = self._act(
            tr("tm_inline", "行内差异"), self._toggle_inline, checkable=True, checked=True)
        self._act_inline_w = a["inline_word"] = self._act(
            tr("tm_inline_word", "按词行内差异"), self._toggle_inline_word,
            checkable=True, checked=True)
        a["regex"] = self._act(tr("tm_regex", "正则过滤"), self._regex_filter, icon="IDI_FILTEREDIT")
        self._act_ign_cmt = a["ignore_comments"] = self._act(
            tr("tm_ignore_comments", "忽略注释"), self._toggle_ignore_comments, checkable=True)
        self._act_ign_cmt2 = self._act_ign_cmt
        self._act_ign_eol = a["ignore_eol"] = self._act(
            tr("tm_ignore_eol", "忽略换行符"), self._toggle_ignore_eol,
            checkable=True, checked=True)
        a["view_bars"] = self._act(tr("tm_view_bars", "栏"), lambda: None)
        self._act_ldb = a["linediffbar"] = self._act(
            tr("tm_linediffbar", "行差异条"), self._toggle_linediff, checkable=True, checked=True)
        self._act_loc = a["locator"] = self._act(
            tr("tm_locator", "定位条"), self._toggle_locator, checkable=True, checked=True)
        self._act_sb = a["statusbar"] = self._act(
            tr("tm_statusbar", "状态栏"), self._toggle_statusbar, checkable=True, checked=True)
        self._act_wrap = a["wrap"] = self._act(
            tr("tm_wrap", "折行"), self._toggle_wrap, checkable=True)
        self._act_oneway = a["oneway"] = self._act(
            tr("tm_oneway", "单栏/双栏切换"), self._toggle_oneway, checkable=True)
        a["switch"] = self._act(tr("tm_switch", "左右视图对调"), self._switch_left,
                                icon="IDI_SWITCHLEFTRIGHT")
        self._act_collapse = a["collapse"] = self._act(
            tr("tm_collapse", "折叠"), self._toggle_collapse, checkable=True)
        a["help"] = self._act(tr("tm_help_topics", "帮助主题"), self._help, "F1")
        self._act_moved = self._act(tr("tm_moved", "移动块"), self._toggle_moved,
                                    checkable=True, checked=True)
        self._acts = a

    # ---- 数据加载 ----
    def _engine(self) -> DiffData:
        dd = DiffData(self.repo)
        dd.ignore_ws = self.ignore_ws
        dd.ignore_eol = self.ignore_eol
        dd.ignore_case = self.ignore_case
        dd.ignore_comments = self.ignore_comments
        if self.ignore_comments:
            from .diffdata import default_comment_tokens
            dd.set_comment_tokens(*default_comment_tokens(self.path))
        return dd

    def _apply_view_flags(self):
        for v in self._views():
            v.inline_diff = self.inline_diff
            v.inline_word = self.inline_word
            v.show_whitespaces = self.show_ws
            v.collapsed = self.collapsed
            v.show_eol_diff = not self.ignore_eol
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
                mark_moved_blocks(left, right, min_block=3)
            self._apply_view_flags()
            # 先给两侧都赋数据，再统一重建：否则先重建的一侧看不到对侧数据，
            # 行内差异高亮会缺失（左侧不会显示部分差异色）
            self.left_view.set_view_data(left, rebuild=False)
            self.right_view.set_view_data(right, rebuild=False)
            self.bottom_view.set_view_data(bottom, rebuild=False)
            for v in self._views():
                v._rebuild()
            self.bottom_view.set_writable(True)
            self._reset_edit_flags()
            self._undo_stack = get_undo()
            self._undo_stack.clear()
            self.locator.set_states(
                [vd.state for vd in left], [vd.state for vd in right],
                [vd.state for vd in bottom])
            self._sync_scrolls()
            conflicts = sum(1 for vd in bottom if vd.is_conflict)
            self._header.setText(
                f" {self.path}  ·  ours={self.rev2 or '工作区'}  theirs={self.rev1 or '工作区'}   "
                f"{tr('tm_conflicts', '冲突')} {conflicts}")
            self._refresh_linebar()
            self._update_command_ui()
            return
        else:
            left, right = dd.load(self.path, self.rev1, self.rev2)
        if self.view_moved:
            mark_moved_blocks(left, right, min_block=3)
        self._apply_view_flags()
        # 先赋数据再统一重建，保证行内差异两侧都能看到对侧内容
        self.left_view.set_view_data(left, rebuild=False)
        self.right_view.set_view_data(right, rebuild=False)
        self.left_view._rebuild()
        self.right_view._rebuild()
        self._reset_edit_flags()
        self._undo_stack = get_undo()
        self._undo_stack.clear()
        self.locator.set_states([vd.state for vd in left],
                                [vd.state for vd in right])
        self._sync_scrolls()
        added = sum(1 for vd in right if vd.is_added)
        removed = sum(1 for vd in left if vd.is_removed)
        self._header.setText(
            f" {self.path or self._local_left}  ·  "
            f"{(self.rev1 or self._local_left or '工作区')} → "
            f"{(self.rev2 or self._local_right or '工作区')}   +{added}/-{removed}")
        self._refresh_linebar()
        self._update_command_ui()

    def _sync_scrolls(self):
        # 只连一次：用 blockSignals 避免递归由 valueChanged 自己处理
        pass

    def _sync_from(self, value: int):
        sender = self.sender()
        for v in self._views():
            if v.verticalScrollBar() is sender:
                continue
            bar = v.verticalScrollBar()
            # 不 blockSignals：否则 QAbstractScrollArea 收不到 valueChanged，
            # 视口不会真正滚动（只是滚动条数值变了）。值相同则跳过，避免递归。
            if bar.value() != value:
                bar.setValue(value)
        self._update_locator_viewport()

    def _sync_h_from(self, value: int):
        """水平滚动同步（对齐 CBaseView::ScrollAllSide）。"""
        sender = self.sender()
        for v in self._views():
            bar = v.horizontalScrollBar()
            if bar is sender:
                continue
            if bar.value() != value:
                bar.setValue(value)

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
        self._sync_edit_action()
        first, last = self.left_view.block_range(line)
        for v in self._views():
            v.set_current_block(first, last)

    def _on_caret_line(self, view_line: int):
        """光标行跨视图同步高亮（对齐 CBaseView 的 caret 同步）。"""
        for v in self._views():
            v.set_current_line(view_line)

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

    def _bottom_data(self):
        return self.bottom_view.view_data if self.bottom_view is not None else None

    def _save_undo_step(self):
        st = AllViewState().snapshot(
            self.left_view.view_data, self.right_view.view_data, self._bottom_data())
        self._undo_stack.add_state(st)

    def _rebuild_views(self):
        for v in self._views():
            v._rebuild()
        self.locator.set_states(
            [vd.state for vd in self.left_view.view_data],
            [vd.state for vd in self.right_view.view_data],
            ([vd.state for vd in self.bottom_view.view_data]
             if self.bottom_view is not None else None))
        self._update_header()
        self._refresh_linebar()
        self._update_command_ui()

    def _target_view(self) -> BaseView:
        return self.bottom_view if self.bottom_view is not None else self.right_view

    def _block_range(self) -> tuple:
        view = self._target_view()
        return view.block_range(view.current_view_line())

    def _on_use_left_block(self):
        # 三路：底栏取上右（mine）；双向：右栏取左。对齐 OnEditUseleftblock。
        first, last = self._block_range()
        if last < first:
            return
        self._save_undo_step()
        if self.bottom_view is not None:
            self.bottom_view.use_resolved_block(self.right_view, first, last)
        else:
            self.right_view.take_block(first, self.left_view, marked_other=False)
        self._rebuild_views()

    def _on_use_left_file(self):
        self._save_undo_step()
        if self.bottom_view is not None:
            self.bottom_view.use_resolved_file(self.right_view)
        else:
            self.right_view.take_file(self.left_view)
        self._rebuild_views()

    def _on_use_both_left_first(self):
        first, last = self._block_range()
        if last < first:
            return
        self._save_undo_step()
        others = [self.bottom_view.view_data] if self.bottom_view is not None else None
        use_both_left_first(self.right_view.view_data, self.left_view.view_data,
                            first, last, others)
        self.right_view.set_modified()
        self._rebuild_views()

    def _on_use_both_right_first(self):
        first, last = self._block_range()
        if last < first:
            return
        self._save_undo_step()
        others = [self.bottom_view.view_data] if self.bottom_view is not None else None
        use_both_right_first(self.right_view.view_data, self.left_view.view_data,
                             first, last, others)
        self.right_view.set_modified()
        self._rebuild_views()

    def _on_use_theirs(self):
        if self.bottom_view is None:
            return
        first, last = self._block_range()
        if last < first:
            return
        self._save_undo_step()
        self.bottom_view.use_resolved_block(self.left_view, first, last)
        self._rebuild_views()

    def _on_use_mine(self):
        if self.bottom_view is None:
            return
        first, last = self._block_range()
        if last < first:
            return
        self._save_undo_step()
        self.bottom_view.use_resolved_block(self.right_view, first, last)
        self._rebuild_views()

    def _on_use_theirs_then(self):
        if self.bottom_view is None:
            return
        first, last = self._block_range()
        if last < first:
            return
        self._save_undo_step()
        use_both_blocks(
            self.bottom_view.view_data, self.left_view.view_data,
            self.right_view.view_data, first, last,
            self.left_view.view_data, self.right_view.view_data)
        self.bottom_view.set_modified()
        self._rebuild_views()

    def _on_use_mine_then(self):
        if self.bottom_view is None:
            return
        first, last = self._block_range()
        if last < first:
            return
        self._save_undo_step()
        use_both_blocks(
            self.bottom_view.view_data, self.right_view.view_data,
            self.left_view.view_data, first, last,
            self.right_view.view_data, self.left_view.view_data)
        self.bottom_view.set_modified()
        self._rebuild_views()

    def _has_unresolved(self) -> bool:
        view = self.bottom_view or self.right_view
        return first_conflict_index(view.view_data) >= 0

    def _goto_first_conflict(self):
        view = self.bottom_view or self.right_view
        idx = first_conflict_index(view.view_data)
        if idx >= 0:
            self.left_view.go_to_diff(idx, self.right_view)
            if self.bottom_view is not None:
                self.bottom_view.scroll_to_line(idx)

    def _conflicts_wont_keep(self) -> bool:
        """对齐 HasConflictsWontKeep：有冲突则询问，取消则返回 True。"""
        if self.bottom_view is None:
            return False
        idx = first_conflict_index(self.bottom_view.view_data)
        if idx < 0:
            return False
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("tm_title_plain", "TortoiseGitMerge"))
        box.setText(tr("tm_has_conflicts",
                       "文件仍有未解决冲突（约第 {} 行）。").format(idx + 1))
        keep = box.addButton(tr("tm_save_anyway", "仍然保存"),
                             QMessageBox.ButtonRole.AcceptRole)
        goto = box.addButton(tr("tm_goto_conflict", "转到冲突处"),
                             QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(goto)
        box.exec()
        if box.clickedButton() is keep:
            return False
        self._goto_first_conflict()
        return True

    def _mark_as_resolved_git(self) -> bool:
        if self._marked_as_resolved:
            return True
        if self.repo is None or not self.path:
            QMessageBox.warning(self, tr("tm_mark", "标记为已解决"),
                                tr("tm_mark_no_repo", "没有仓库路径，无法 git add。"))
            return False
        if not mark_resolved(self.repo, self.path):
            QMessageBox.warning(self, tr("tm_mark", "标记为已解决"),
                                tr("tm_mark_fail", "git add 失败，未能标记已解决。"))
            return False
        self._marked_as_resolved = True
        return True

    def _mark_resolved(self):
        if self.bottom_view is None:
            QMessageBox.information(self, tr("tm_mark", "标记为已解决"),
                                    tr("tm_mark_need_merge", "仅三路合并可将结果标记为已解决。"))
            return
        if self._conflicts_wont_keep():
            return
        if not self._save_merged(check_resolved=False):
            return
        if self._mark_as_resolved_git():
            QMessageBox.information(self, tr("tm_mark", "标记为已解决"),
                                    tr("tm_mark_ok", "已保存并 git add，冲突已标记解决。"))
        self._update_header()

    def _undo(self):
        if self._undo_stack.undo(
                self.left_view.view_data, self.right_view.view_data, self._bottom_data()):
            self._rebuild_views()

    def _redo(self):
        if self._undo_stack.redo(
                self.left_view.view_data, self.right_view.view_data, self._bottom_data()):
            self._rebuild_views()

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
            view._find_selections = extra
            view._apply_extra_selections()

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

    def _reset_edit_flags(self):
        self._marked_as_resolved = False
        self.left_view.set_writable(False)
        self.left_view.set_modified(False)
        self.right_view.set_writable(False)
        self.right_view.set_modified(False)
        if self.bottom_view is not None:
            self.bottom_view.set_writable(True)
            self.bottom_view.set_modified(False)
        self.edit_enabled = False
        if hasattr(self, "_act_edit_en"):
            self._act_edit_en.blockSignals(True)
            self._act_edit_en.setChecked(self._target_view().is_writable())
            self._act_edit_en.blockSignals(False)

    def _sync_edit_action(self):
        if not hasattr(self, "_act_edit_en"):
            return
        v = self._active_view()
        self._act_edit_en.blockSignals(True)
        self._act_edit_en.setChecked(v.is_writable())
        self._act_edit_en.blockSignals(False)

    def _update_command_ui(self):
        three = self.bottom_view is not None
        for key in ("use_theirs", "use_mine", "use_theirs_then", "use_mine_then"):
            self._acts[key].setEnabled(three)
        self._acts["mark"].setEnabled(three and not self._marked_as_resolved)
        self._sync_edit_action()
        self._update_statusbar_encoding()

    def _toggle_edit(self, on: bool):
        v = self._active_view()
        v.set_writable(on)
        self.edit_enabled = on

    def _toggle_toolbar(self, on: bool):
        if hasattr(self, "ribbon"):
            self.ribbon.setVisible(on)

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
        self.left_view.set_view_data(rd, rebuild=False)
        self.right_view.set_view_data(ld, rebuild=False)
        self.left_view._rebuild()
        self.right_view._rebuild()
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

    def _view_save_path(self, view: BaseView) -> str:
        if view is self.left_view:
            return self._local_left
        if view is self.bottom_view:
            if self.repo is not None and self.path:
                return self.repo.full_path(self.path)
            return self._local_right
        if self._local_right:
            return self._local_right
        if self.repo is not None and self.path:
            return self.repo.full_path(self.path)
        return ""

    def _view_text(self, view: BaseView) -> list:
        return serialize_view(view.view_data, self.left_view.view_data,
                              self.right_view.view_data)

    def _write_view(self, view: BaseView, dest: str = "") -> bool:
        dest = dest or self._view_save_path(view)
        if not dest:
            return self._save_view_as(view)
        lines = self._view_text(view)
        try:
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(lines))
                if lines:
                    fh.write("\n")
            view.set_modified(False)
            return True
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("error"), str(exc))
            return False

    def _save_view_as(self, view: BaseView) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("tm_saveas", "另存为"), self._view_save_path(view) or self.path or "")
        if not path:
            return False
        return self._write_view(view, path)

    def _ask_save_which(self, left_mod: bool, right_mod: bool) -> str:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("tm_save", "保存"))
        box.setText(tr("tm_save_which", "多个栏可写，保存哪一侧？"))
        btn_left = box.addButton(tr("tm_save_left", "保存左侧"),
                                 QMessageBox.ButtonRole.ActionRole)
        btn_right = box.addButton(tr("tm_save_right", "保存右侧"),
                                  QMessageBox.ButtonRole.ActionRole)
        btn_all = box.addButton(tr("tm_save_all", "全部保存"),
                                QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        if right_mod:
            box.setDefaultButton(btn_right)
        elif left_mod:
            box.setDefaultButton(btn_left)
        else:
            box.setDefaultButton(btn_all)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_left:
            return "left"
        if clicked is btn_right:
            return "right"
        if clicked is btn_all:
            return "all"
        return ""

    def _save_merged(self, check_resolved: bool = True) -> bool:
        if check_resolved and self._conflicts_wont_keep():
            return False
        target = self._target_view()
        dest = self._view_save_path(target)
        if not dest:
            return self._save_view_as(target)
        if not self._write_view(target, dest):
            return False
        if (check_resolved and self.bottom_view is not None
                and not self._has_unresolved() and not self._marked_as_resolved
                and self.repo is not None and self.path):
            ask = QMessageBox.question(
                self, tr("tm_mark", "标记为已解决"),
                tr("tm_ask_mark", "冲突已解决，是否 git add 标记该文件？"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if ask == QMessageBox.StandardButton.Yes:
                self._mark_as_resolved_git()
        return True

    def _save_result(self):
        writable = [v for v in self._views() if v.is_writable()]
        modified = [v for v in writable if v.modified]
        if len(writable) > 1:
            if len(modified) == 1:
                view = modified[0]
                if view is self.left_view:
                    ok = self._write_view(view) if self._view_save_path(view) else self._save_view_as(view)
                else:
                    ok = self._save_merged()
                if ok:
                    QMessageBox.information(self, tr("tm_save", "保存"),
                                            tr("tm_saved", "已写入 {}").format(
                                                self._view_save_path(view) or ""))
                return
            if modified or writable:
                choice = self._ask_save_which(
                    self.left_view.modified, self.right_view.modified)
                if not choice:
                    return
                ok = True
                if choice in ("left", "all"):
                    dest = self._view_save_path(self.left_view)
                    ok = (self._write_view(self.left_view, dest) if dest
                          else self._save_view_as(self.left_view)) and ok
                if choice in ("right", "all"):
                    ok = self._save_merged() and ok
                if ok:
                    QMessageBox.information(
                        self, tr("tm_save", "保存"),
                        tr("tm_saved_ok", "已保存。"))
                return
        if self._save_merged():
            dest = self._view_save_path(self._target_view())
            QMessageBox.information(self, tr("tm_save", "保存"),
                                    tr("tm_saved", "已写入 {}").format(dest))

    def _save_as(self):
        writable = [v for v in self._views() if v.is_writable()]
        view = self._active_view() if self._active_view().is_writable() else self._target_view()
        if len(writable) > 1 and self.left_view.is_writable() and view is not self.left_view:
            choice = self._ask_save_which(True, True)
            if not choice:
                return
            if choice == "left":
                view = self.left_view
            elif choice == "all":
                self._save_view_as(self.left_view)
                view = self._target_view()
        self._save_view_as(view)

    # ---- 拖放（对齐 MainFrm 文件拖放）----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.isLocalFile()]
        paths = [p for p in paths if p]
        if len(paths) >= 2:
            self._local_left = paths[0]
            self._local_right = paths[1]
            self.path = paths[1]
            self.three_way = False
            self._load()
            self.add_recent_file(paths[1])
        elif len(paths) == 1:
            self.add_recent_file(paths[0])
        event.acceptProposedAction()

    # ---- 最近文件（对齐 MainFrm 最近文件列表）----
    _RECENT_KEY = "TortoiseGitMerge/RecentFiles"

    def _load_recent_files(self):
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("TortoiseGit", "TortoiseGitMerge")
            self._recent_files = list(s.value(self._RECENT_KEY, [], type=list) or [])
        except Exception:  # noqa: BLE001
            self._recent_files = []

    def _save_recent_files(self):
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("TortoiseGit", "TortoiseGitMerge")
            s.setValue(self._RECENT_KEY, self._recent_files[:10])
        except Exception:  # noqa: BLE001
            pass

    def add_recent_file(self, path: str):
        if not path:
            return
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:10]
        self._save_recent_files()

    def recent_files(self) -> List[str]:
        return list(self._recent_files)

    def exec(self):
        self.show()
        return QApplication.instance().exec() if QApplication.instance() else 0


def open_merge_window(repo: Repository, path: str, rev1: str | None,
                      rev2: str | None, parent=None):
    frm = MergeFrm(repo, path, rev1, rev2, parent)
    frm.show()
    return frm
