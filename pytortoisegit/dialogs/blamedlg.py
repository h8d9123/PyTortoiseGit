"""blamedlg.py —— BlameDlg：逐行标注视图。

镜像 TortoiseGitBlame 的 CMainFrame（SDI）布局：

    +---------------------------------------------------------------+
    | 菜单栏 File / Edit / View / Help                                |
    | 工具栏 [打开][上一个][下一个][复制][关于]                        |
    +----------------------------------------------+----------------+
    |  左侧 blame 栏（hash/author/date/origline）   | Commit Info    |
    |  + 右侧代码视图（只读）                       | （属性面板）   |
    +----------------------------------------------+----------------+
    |  Git Revision List（提交列表，dock 底部）                       |
    +---------------------------------------------------------------+
    |  状态栏                                          编码 |
    +---------------------------------------------------------------+
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QBrush, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..asyncfw import run_async
from ..blame import (
    DETECT_MOVED_OR_COPIED_LINES_DISABLED,
    DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES,
    DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES_AT_FILE_CREATION,
    DETECT_MOVED_OR_COPIED_LINES_FROM_MODIFIED_FILES,
    DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE,
    DETECT_NUM_CHARACTERS_FROM_FILES_DEFAULT,
    BlameData,
    BlameLine,
    GitBlame,
)
from ..git.repo import Repository
from ..res.strings import tr
from .settingsdlg import general_settings

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

_DETECT_ITEMS = (
    ("blame_menu_detect_disabled", DETECT_MOVED_OR_COPIED_LINES_DISABLED),
    ("blame_menu_detect_within", DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE),
    ("blame_menu_detect_modified", DETECT_MOVED_OR_COPIED_LINES_FROM_MODIFIED_FILES),
    ("blame_menu_detect_creation",
     DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES_AT_FILE_CREATION),
    ("blame_menu_detect_existing", DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES),
)

_PROP_ROWS = (
    ("blame_col_commit", "sha"),
    ("blame_col_author", "author_name"),
    ("blame_col_date", "author_date"),
    ("blame_col_email", "author_email"),
    ("blame_col_committer", "committer_name"),
    ("blame_col_committeremail", "committer_email"),
    ("blame_col_committerdate", "committer_date"),
    ("blame_col_subject", "subject"),
    ("blame_col_body", "body"),
)


def _to_int(value, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _inter_color(c1: QColor, c2: QColor, slider: int) -> QColor:
    """在 c1(0%) 与 c2(100%) 间插值（对齐 InterColor）。"""
    slider = max(0, min(100, slider))
    return QColor(
        (c1.red() * (100 - slider) + c2.red() * slider) // 100,
        (c1.green() * (100 - slider) + c2.green() * slider) // 100,
        (c1.blue() * (100 - slider) + c2.blue() * slider) // 100,
    )


class BlameDlg(QMainWindow):
    # 代码视图子列（左侧 blame 栏等价原版自绘栏）
    COL_LINE = 0
    COL_COMMIT = 1
    COL_AUTHOR = 2
    COL_DATE = 3
    COL_CONTENT = 4
    COL_FILE = 5
    COL_ORIG = 6
    _COLUMN_COUNT = 7

    # 底部提交列表列
    LOG_COL_ID = 0
    LOG_COL_SUBJECT = 1
    LOG_COL_AUTHOR = 2
    LOG_COL_DATE = 3
    LOG_COL_HASH = 4

    def __init__(self, repo: Repository, filepath: str,
                 rev: str | None = None, line: int = 0, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.filepath = filepath
        self.rev = rev
        self._start_line = int(line or 0)
        self._lines: List[BlameLine] = []
        self._data: Optional[BlameData] = None
        self._sha_order: List[str] = []
        self._load_prefs()
        self.setWindowTitle(
            tr("blame_title", "{name} — {path} @ {rev}").format(
                name=repo.name, path=self.filepath, rev=rev or "HEAD"))
        self.resize(1120, 760)
        self._build_ui()
        self._update_actions()
        run_async(self._blame_bg, on_done=self._on_loaded,
                  on_error=self._on_error, parent=self)

    # ---- 设置（对齐 SettingsTBlame / 注册表项） ----
    def _load_prefs(self):
        s = general_settings()
        self._font_name = str(s.value("BlameFontName", "Consolas"))
        self._font_size = _to_int(s.value("BlameFontSize", 10), 10)
        self._detect = _to_int(s.value("DetectMovedOrCopiedLines", 0), 0)
        self._chars_within = _to_int(
            s.value("DetectMovedOrCopiedLinesNumCharactersWithinFile", 20), 20)
        self._chars_from = _to_int(
            s.value("DetectMovedOrCopiedLinesNumCharactersFromFiles",
                    DETECT_NUM_CHARACTERS_FROM_FILES_DEFAULT),
            DETECT_NUM_CHARACTERS_FROM_FILES_DEFAULT)
        self._ignore_whitespace = bool(
            s.value("IgnoreWhitespace", False, type=bool))
        self._color_by_age = bool(s.value("ColorAge", True, type=bool))
        self._show_author = bool(s.value("ShowAuthor", True, type=bool))
        self._show_date = bool(s.value("ShowDate", False, type=bool))
        self._show_filename = bool(s.value("ShowFilename", False, type=bool))
        self._show_orig_line = bool(
            s.value("ShowOriginalLineNumber", False, type=bool))
        self._show_log_id = bool(s.value("ShowLogID", False, type=bool))
        self._wrap = bool(s.value("WrapLongLines", False, type=bool))
        new = str(s.value("BlameNewColor", "#ffff88"))
        old = str(s.value("BlameOldColor", "#ffffff"))
        self._new_color = QColor(new) if QColor.isValidColorName(new) else QColor("#ffff88")
        self._old_color = QColor(old) if QColor.isValidColorName(old) else QColor("#ffffff")
        self._selected_color = _inter_color(self._new_color, self._old_color, 40)

    def _save_pref(self, key: str, value):
        s = general_settings()
        s.setValue(key, value)
        s.sync()

    # ---- UI ----
    def _build_ui(self):
        self._build_actions()
        self._build_menu()
        self._build_toolbar()

        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(2, 2, 2, 0)
        outer.setSpacing(2)

        bar = QHBoxLayout()
        bar.addWidget(QLabel(tr("blame_find", "Find") + ":", central))
        self.find_edit = QLineEdit(central)
        self.find_edit.returnPressed.connect(lambda: self._find(True))
        bar.addWidget(self.find_edit, 1)
        self.btn_find_prev = _mk_button(tr("blame_find_prev", "Find previous"),
                                        lambda: self._find(False), central)
        self.btn_find_next = _mk_button(tr("blame_find_next", "Find next"),
                                        lambda: self._find(True), central)
        self.btn_goto = _mk_button(tr("blame_menu_goto", "Go to…"),
                                   self._goto, central)
        for b in (self.btn_find_prev, self.btn_find_next, self.btn_goto):
            bar.addWidget(b)
        outer.addLayout(bar)

        self.table = QTableWidget(0, self._COLUMN_COUNT, central)
        self.table.setHorizontalHeaderLabels([
            tr("blame_col_line", "Line"), tr("blame_col_commit", "Commit"),
            tr("blame_col_author", "Author"), tr("blame_col_date", "Date"),
            tr("blame_col_code", "Code"), tr("blame_col_filename", "File"),
            tr("blame_col_origline", "Original line")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_menu)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.setWordWrap(self._wrap)
        header = self.table.horizontalHeader()
        for col in (self.COL_LINE, self.COL_COMMIT, self.COL_AUTHOR,
                    self.COL_DATE, self.COL_ORIG):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_CONTENT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_FILE, QHeaderView.ResizeMode.ResizeToContents)
        font = QFont(self._font_name, self._font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(font)

        # 右侧 Commit Info 属性面板 + 底部 Git Revision List（对齐原版两个 dock 面板）
        self.props = self._build_properties(central)
        self.log_table = self._build_log_list(central)

        middle = QSplitter(Qt.Orientation.Horizontal, central)
        middle.addWidget(_titled(self.table, "", central))
        middle.addWidget(_titled(self.props, tr("blame_pane_properties", "Commit Info"), central))
        middle.setStretchFactor(0, 4)
        middle.setStretchFactor(1, 1)
        middle.setSizes([780, 260])
        self._middle_splitter = middle

        vertical = QSplitter(Qt.Orientation.Vertical, central)
        vertical.addWidget(middle)
        vertical.addWidget(_titled(self.log_table, tr("blame_pane_loglist", "Git Revision List"),
                                   central))
        vertical.setStretchFactor(0, 4)
        vertical.setStretchFactor(1, 1)
        vertical.setSizes([560, 180])
        self._splitter = vertical
        outer.addWidget(vertical, 1)

        self.setCentralWidget(central)
        self._build_statusbar()
        self._apply_column_visibility()

    def _build_actions(self):
        self.act_open = QAction(tr("blame_menu_open", "Open…"), self)
        self.act_settings = QAction(tr("blame_menu_settings", "Settings…"), self)
        self.act_settings.triggered.connect(self._open_settings)
        self.act_exit = QAction(tr("blame_menu_exit", "Exit"), self)
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)

        self.act_copy = QAction(tr("blame_menu_copy", "Copy"), self)
        self.act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.act_copy.triggered.connect(self._copy_selection)
        self.act_find = QAction(tr("blame_menu_find", "Find"), self)
        self.act_find.setShortcut(QKeySequence.StandardKey.Find)
        self.act_find.triggered.connect(self._focus_find)
        self.act_find_next = QAction(tr("blame_find_next", "Find next"), self)
        self.act_find_next.setShortcut(QKeySequence("F3"))
        self.act_find_next.triggered.connect(lambda: self._find(True))
        self.act_find_prev = QAction(tr("blame_find_prev", "Find previous"), self)
        self.act_find_prev.setShortcut(QKeySequence("Shift+F3"))
        self.act_find_prev.triggered.connect(lambda: self._find(False))
        self.act_goto = QAction(tr("blame_menu_goto", "Go to"), self)
        self.act_goto.setShortcut(QKeySequence("Ctrl+G"))
        self.act_goto.triggered.connect(self._goto)

        self.act_next = QAction(tr("blame_menu_next", "Next"), self)
        self.act_next.triggered.connect(lambda: self._navigate_block(False))
        self.act_prev = QAction(tr("blame_menu_prev", "Previous"), self)
        self.act_prev.triggered.connect(lambda: self._navigate_block(True))

        # 勾选项（对齐 ID_VIEW_*）
        self.act_show_log_id = self._check(tr("blame_menu_showlogid", "Show log ID instead of SHA-1"),
                                           "ShowLogID", self._show_log_id)
        self.act_show_author = self._check(tr("blame_menu_showauthor", "Show author"),
                                           "ShowAuthor", self._show_author)
        self.act_show_date = self._check(tr("blame_menu_showdate", "Show date"),
                                         "ShowDate", self._show_date)
        self.act_show_filename = self._check(tr("blame_menu_showfilename", "Show file name"),
                                             "ShowFilename", self._show_filename)
        self.act_show_orig = self._check(tr("blame_menu_showorigline", "Show original line number"),
                                         "ShowOriginalLineNumber", self._show_orig_line)
        self.act_ignore_ws = self._check(tr("blame_menu_ignorews", "Ignore whitespace"),
                                         "IgnoreWhitespace", self._ignore_whitespace,
                                         reload=True)
        self.act_color_age = self._check(tr("blame_menu_colorbyage", "Color by age, continuous"),
                                         "ColorAge", self._color_by_age, repaint_only=True)
        self.act_wrap = self._check(tr("blame_menu_wrap", "Wrap long lines"),
                                    "WrapLongLines", self._wrap, wrap_only=True)

        # 检测移动/复制行（单选组）
        self.detect_group = QActionGroup(self)
        self.detect_group.setExclusive(True)
        self._detect_actions = {}
        for key, value in _DETECT_ITEMS:
            act = QAction(tr(key, key), self)
            act.setCheckable(True)
            act.setChecked(value == self._detect)
            act.triggered.connect(lambda _c=False, v=value: self._set_detect(v))
            self.detect_group.addAction(act)
            self._detect_actions[value] = act

        # 占位项：原版尚未接线/或不适用（保持勾选状态但禁用）
        self.act_complete_log = self._check(
            tr("blame_menu_completelog", "Show complete log"), "ShowCompleteLog", True)
        self.act_follow_renames = self._check(
            tr("blame_menu_followrenames", "Follow renames"), "FollowRenames", False)
        self.act_first_parent = self._check(
            tr("blame_menu_firstparent", "Only consider first parents on blame"),
            "OnlyFirstParent", False)
        self.act_lexer = self._check(tr("blame_menu_lexer", "Enable syntax highlighting"),
                                     "EnableLexer", True)
        self.act_dark = QAction(tr("blame_menu_darkmode", "Dark Mode"), self)
        self.act_dark.setCheckable(True)
        self.act_dark.triggered.connect(self._toggle_dark)
        self.act_about = QAction(tr("blame_menu_about", "About TortoiseGitBlame…"), self)
        self.act_about.triggered.connect(self._about)

    def _check(self, text, setting_key, checked, reload=False,
               repaint_only=False, wrap_only=False):
        act = QAction(text, self)
        act.setCheckable(True)
        act.setChecked(bool(checked))
        if reload:
            act.triggered.connect(
                lambda c, k=setting_key: self._toggle_reload(k, c))
        elif repaint_only:
            act.triggered.connect(
                lambda c, k=setting_key: self._toggle_paint(k, c))
        elif wrap_only:
            act.triggered.connect(
                lambda c, k=setting_key: self._toggle_wrap(k, c))
        else:
            act.triggered.connect(
                lambda c, k=setting_key: self._toggle_column(k, c))
        return act

    def _build_menu(self):
        mb = self.menuBar()

        m_file = mb.addMenu(tr("blame_menu_file", "&File"))
        m_file.addAction(self.act_open)
        m_file.addSeparator()
        m_file.addAction(self.act_settings)
        m_file.addSeparator()
        m_file.addAction(self.act_exit)

        m_edit = mb.addMenu(tr("blame_menu_edit", "&Edit"))
        m_edit.addAction(self.act_copy)
        m_edit.addAction(self.act_find)
        m_edit.addAction(self.act_goto)
        m_edit.addSeparator()
        sub = m_edit.addMenu("Encode")
        sub.addAction("UTF-8")
        sub.addAction("UTF-16 LE")
        sub.addAction("UTF-16 BE")

        m_view = mb.addMenu(tr("blame_menu_view", "&View"))
        m_view.addAction(self.act_next)
        m_view.addAction(self.act_prev)
        m_view.addSeparator()
        sub2 = m_view.addMenu(tr("blame_menu_detect", "Detect moved or copied lines"))
        for value in (DETECT_MOVED_OR_COPIED_LINES_DISABLED,
                      DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE,
                      DETECT_MOVED_OR_COPIED_LINES_FROM_MODIFIED_FILES,
                      DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES_AT_FILE_CREATION,
                      DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES):
            sub2.addAction(self._detect_actions[value])
        m_view.addSeparator()
        m_view.addAction(self.act_show_log_id)
        m_view.addAction(self.act_show_author)
        m_view.addAction(self.act_show_date)
        m_view.addAction(self.act_show_filename)
        m_view.addAction(self.act_show_orig)
        m_view.addAction(self.act_ignore_ws)
        m_view.addSeparator()
        m_view.addAction(self.act_complete_log)
        m_view.addAction(self.act_follow_renames)
        m_view.addAction(self.act_first_parent)
        m_view.addSeparator()
        m_view.addAction(self.act_color_age)
        m_view.addAction(self.act_lexer)
        m_view.addAction(self.act_dark)
        m_view.addSeparator()
        m_view.addAction(self.act_wrap)
        self._view_menu = m_view

        m_help = mb.addMenu(tr("blame_menu_help", "&Help"))
        m_help.addAction(self.act_about)

    def _build_toolbar(self):
        tb = QToolBar("Standard", self)
        tb.setObjectName("IDR_TORTOISE_GIT_BLAME_MAINFRAME")
        tb.setMovable(False)
        tb.addAction(self.act_open)
        tb.addSeparator()
        tb.addAction(self.act_prev)
        tb.addAction(self.act_next)
        tb.addSeparator()
        tb.addAction(self.act_copy)
        tb.addSeparator()
        tb.addAction(self.act_about)
        self.addToolBar(tb)
        self._toolbar = tb

    def _build_properties(self, parent) -> QTreeWidget:
        tree = QTreeWidget(parent)
        tree.setColumnCount(2)
        tree.setHeaderLabels([tr("blame_prop_basicinfo", "Basic Info"),
                              tr("blame_col_code", "Code")])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        group = QTreeWidgetItem([tr("blame_prop_basicinfo", "Basic Info"), ""])
        group.setFirstColumnSpanned(True)
        group.setExpanded(True)
        tree.addTopLevelItem(group)
        self._prop_items: Dict[str, QTreeWidgetItem] = {}
        for key, field in _PROP_ROWS:
            item = QTreeWidgetItem([tr(key, field), ""])
            group.addChild(item)
            self._prop_items[field] = item
        self._parent_item = QTreeWidgetItem([tr("blame_prop_parents", "Parent(s)"), ""])
        self._parent_item.setExpanded(True)
        tree.addTopLevelItem(self._parent_item)
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._on_prop_menu)
        return tree

    def _build_log_list(self, parent) -> QTableWidget:
        table = QTableWidget(0, 5, parent)
        table.setHorizontalHeaderLabels([
            tr("blame_col_line", "ID"), tr("blame_col_subject", "Subject"),
            tr("blame_col_author", "Author"), tr("blame_col_date", "Date"),
            tr("blame_col_commit", "Commit")])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tfont = QFont(self._font_name, max(8, self._font_size - 1))
        table.setFont(tfont)
        header = table.horizontalHeader()
        for col in (0, 1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setColumnHidden(4, True)
        table.itemSelectionChanged.connect(self._on_log_selection)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_log_menu)
        return table

    def _build_statusbar(self):
        sb = self.statusBar()
        self._status_label = QLabel(tr("blame_status_ready", "Ready"), self)
        sb.addWidget(self._status_label, 1)
        self._encoding_label = QLabel("", self)
        sb.addPermanentWidget(self._encoding_label)

    def _apply_column_visibility(self):
        self.table.setColumnHidden(self.COL_AUTHOR, not self._show_author)
        self.table.setColumnHidden(self.COL_DATE, not self._show_date)
        self.table.setColumnHidden(self.COL_FILE, not self._show_filename)
        self.table.setColumnHidden(self.COL_ORIG, not self._show_orig_line)

    # ---- 加载 ----
    def _blame_bg(self) -> BlameData:
        return GitBlame(self.repo).load(
            self.filepath, rev=self.rev,
            ignore_whitespace=self._ignore_whitespace,
            detect=self._detect, chars_within=self._chars_within,
            chars_from=self._chars_from)

    def _on_error(self, msg, _tb):
        # 不在后台回调里弹模态框（无头环境/无事件循环时会永久阻塞）；
        # 状态栏提示 + 交给上层日志（对齐原版只报错不阻塞）。
        text = f"★ {tr('blame_error', 'Error')}: {msg}"
        self._status_label.setText(text)
        try:
            from ..utils.logging_utils import get_logger
            get_logger().error(text)
        except Exception:  # noqa: BLE001
            pass

    def _on_loaded(self, data):
        if isinstance(data, BlameData):
            self._data = data
            lines = data.lines
        else:  # 兼容旧调用（测试直接传列表）
            self._data = None
            lines = list(data or [])
        self._lines = list(lines)
        self._rebuild_sha_order()
        self._compute_brushes()
        self._fill_table()
        self._populate_log_list()
        self._update_header()
        self._encoding_label.setText(
            tr("blame_status_encoding", "Encoding: {enc}").format(
                enc=(self._data.encoding if self._data else "utf-8")))
        if self._start_line > 0 and self._lines:
            self._select_row(min(self._start_line, len(self._lines)) - 1)

    def _update_header(self):
        self._status_label.setText(
            f"{self.filepath} @ {self.rev or 'HEAD'}  —  "
            f"{len(self._lines)} {tr('blame_lines', 'lines')}")

    def _rebuild_sha_order(self):
        """按 blame 行首次出现的顺序记录提交（日志 ID 显示用）。"""
        order: List[str] = []
        for bl in self._lines:
            if bl.sha not in order:
                order.append(bl.sha)
        self._sha_order = order

    def _compute_brushes(self):
        distinct = sorted({ln.author_date for ln in self._lines if ln.author_date})
        self._brushes: List[QBrush] = []
        count = len(distinct)
        for ln in self._lines:
            if not self._color_by_age or count <= 1 or not ln.author_date:
                color = self._new_color
            else:
                rank = distinct.index(ln.author_date)
                color = _inter_color(self._old_color, self._new_color,
                                     rank * 100 // (count - 1))
            self._brushes.append(QBrush(color))

    def _fill_table(self):
        self.table.setRowCount(len(self._lines))
        mono = self.table.font()
        for row, bl in enumerate(self._lines):
            brush = self._brushes[row] if row < len(self._brushes) else QBrush(self._old_color)
            id_text = (str(self._sha_order.index(bl.sha) + 1)
                       if self._show_log_id else bl.short_sha)
            items = [
                QTableWidgetItem(str(row + 1)),
                QTableWidgetItem(id_text),
                QTableWidgetItem(bl.author),
                QTableWidgetItem(bl.date_span()),
                QTableWidgetItem(bl.content),
                QTableWidgetItem(bl.filename),
                QTableWidgetItem(str(bl.original_line)),
            ]
            for it in items:
                it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                it.setBackground(brush)
                it.setFont(mono)
            tip = f"{bl.sha}\n{bl.author} <{bl.author_email}>\n{bl.date_span()}\n{bl.summary}"
            items[self.COL_COMMIT].setToolTip(tip)
            items[self.COL_COMMIT].setData(Qt.ItemDataRole.UserRole, bl.sha)
            for col, it in enumerate(items):
                self.table.setItem(row, col, it)

    def _populate_log_list(self):
        self.log_table.setRowCount(len(self._sha_order))
        for row, sha in enumerate(self._sha_order):
            info = (self._data.commits.get(sha) if self._data else None)
            subject = info.subject if info else next(
                (bl.summary for bl in self._lines if bl.sha == sha), "")
            author = info.author_name if info else next(
                (bl.author for bl in self._lines if bl.sha == sha), "")
            date = (info.author_date if info else "").split(" ")[0]
            cells = [str(row + 1), subject, author, date, sha]
            for col, text in enumerate(cells):
                it = QTableWidgetItem(text)
                it.setData(Qt.ItemDataRole.UserRole, sha)
                self.log_table.setItem(row, col, it)

    def _line_of_row(self, row: int) -> Optional[BlameLine]:
        if 0 <= row < len(self._lines):
            return self._lines[row]
        return None

    # ---- 选择 / 高亮 ----
    def _on_selection(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._lines):
            return
        sha = self._lines[row].sha
        for r, bl in enumerate(self._lines):
            brush = (QBrush(self._selected_color) if bl.sha == sha
                     else (self._brushes[r] if r < len(self._brushes)
                           else QBrush(self._old_color)))
            for col in range(self._COLUMN_COUNT):
                item = self.table.item(r, col)
                if item is not None:
                    item.setBackground(brush)
        self._update_properties(sha)

    def _select_row(self, row: int):
        if row < 0 or row >= self.table.rowCount():
            return
        self.table.selectRow(row)
        item = self.table.item(row, self.COL_CONTENT)
        if item is not None:
            self.table.scrollToItem(
                item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _update_properties(self, sha: str):
        info = (self._data.commits.get(sha) if self._data else None)
        values = {}
        if info is not None:
            values = {
                "sha": info.sha,
                "author_name": info.author_name,
                "author_date": info.author_date,
                "author_email": info.author_email,
                "committer_name": info.committer_name,
                "committer_email": info.committer_email,
                "committer_date": info.committer_date,
                "subject": info.subject,
                "body": info.body,
            }
        for field, item in self._prop_items.items():
            item.setText(1, values.get(field, ""))
        self._parent_item.takeChildren()
        if info is not None:
            for i, parent in enumerate(info.parents):
                pinfo = self._data.commits.get(parent)
                text = f"{i} - {parent[:8]}"
                if pinfo:
                    text += f"\n{pinfo.subject}"
                self._parent_item.addChild(QTreeWidgetItem([parent, text]))
        self._status_label.setText(
            f"{sha}  —  {values.get('subject', '')}")

    # ---- 查找 / 跳转 / 导航 ----
    def _focus_find(self):
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def _find(self, forward: bool = True):
        text = self.find_edit.text()
        if not text:
            return
        needle = text.casefold()
        n = len(self._lines)
        if n == 0:
            return
        start = self.table.currentRow()
        order = list(range(start + 1, n)) + list(range(0, max(start, 0)))
        if not forward:
            order = list(range(start - 1, -1, -1)) + list(range(n - 1, start, -1))
        for i in order:
            ln = self._lines[i]
            if needle in ln.content.casefold() or needle in ln.author.casefold():
                self._select_row(i)
                return
        self._status_label.setText(
            tr("blame_not_found", "Not found: {text}").format(text=text))

    def _goto(self):
        if not self._lines:
            return
        current = self.table.currentRow() + 1
        number, ok = QInputDialog.getInt(
            self, tr("blame_menu_goto", "Go to line…"),
            tr("blame_goto_prompt", "Line number:"),
            max(1, current), 1, len(self._lines))
        if ok:
            self._select_row(number - 1)

    def _navigate_block(self, up: bool):
        if not self._data:
            return
        start = self.table.currentRow()
        idx = self._data.find_next_line([self._lines[start].sha], start, up) \
            if 0 <= start < len(self._lines) else -1
        if idx >= 0:
            self._select_row(idx)

    def _copy_selection(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._lines):
            return
        from ..utils.clipboard import ClipboardHelper
        ClipboardHelper().copy_text(self._lines[row].content)

    # ---- 菜单动作 ----
    def _open_settings(self):
        from .settingsdlg import SettingsDlg
        SettingsDlg(self.repo, parent=self).exec()

    def _about(self):
        from .aboutdlg import AboutDlg
        AboutDlg(self).exec()

    def _toggle_column(self, key: str, checked: bool):
        setattr(self, {
            "ShowLogID": "_show_log_id", "ShowAuthor": "_show_author",
            "ShowDate": "_show_date", "ShowFilename": "_show_filename",
            "ShowOriginalLineNumber": "_show_orig_line",
        }.get(key, "_show_author"), bool(checked))
        self._save_pref(key, bool(checked))
        self._apply_column_visibility()
        if key == "ShowLogID":
            self._fill_table()
        if not self.table.isColumnHidden(self.COL_FILE):
            pass

    def _toggle_reload(self, key: str, checked: bool):
        self._save_pref(key, bool(checked))
        changed = (key == "IgnoreWhitespace"
                   and bool(checked) != self._ignore_whitespace)
        setattr(self, {"IgnoreWhitespace": "_ignore_whitespace"}.get(key, key),
                bool(checked))
        if changed:
            self.reload()
        self._update_actions()

    def _toggle_paint(self, key: str, checked: bool):
        self._color_by_age = bool(checked)
        self._save_pref(key, bool(checked))
        self._compute_brushes()
        self._fill_table()
        self._apply_column_visibility()
        if 0 <= self.table.currentRow() < len(self._lines):
            self._on_selection()

    def _toggle_wrap(self, key: str, checked: bool):
        self._wrap = bool(checked)
        self._save_pref(key, bool(checked))
        self.table.setWordWrap(self._wrap)

    def _set_detect(self, value: int):
        self._detect = int(value)
        self._save_pref("DetectMovedOrCopiedLines", int(value))
        self.reload()

    def _toggle_dark(self, checked: bool):
        try:
            from ..ui import theme
            setter = getattr(theme, "set_dark_mode", None)
            if setter is not None:
                setter(bool(checked))
        except Exception:  # noqa: BLE001
            pass
        self._save_pref("DarkMode", bool(checked))

    def _update_actions(self):
        if not hasattr(self, "_detect_actions"):
            return
        self._detect_actions[self._detect].setChecked(True)
        self.act_ignore_ws.setChecked(self._ignore_whitespace)
        self.act_show_log_id.setChecked(self._show_log_id)
        self.act_show_author.setChecked(self._show_author)
        self.act_show_date.setChecked(self._show_date)
        self.act_show_filename.setChecked(self._show_filename)
        self.act_show_orig.setChecked(self._show_orig_line)
        self.act_color_age.setChecked(self._color_by_age)
        self.act_wrap.setChecked(self._wrap)

    def reload(self):
        self._status_label.setText(tr("loading", "Loading…"))
        run_async(self._blame_bg, on_done=self._on_loaded,
                  on_error=self._on_error, parent=self)

    # ---- 代码视图右键菜单 ----
    def _sha_at(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return None
        sha_item = self.table.item(item.row(), self.COL_COMMIT)
        if sha_item is None:
            return None
        return sha_item.data(Qt.ItemDataRole.UserRole) or sha_item.text()

    def _current_line(self) -> Optional[BlameLine]:
        row = self.table.currentRow()
        if 0 <= row < len(self._lines):
            return self._lines[row]
        return None

    def _build_menu_context(self):
        """构建代码视图右键菜单，返回 (menu, {action: key})，便于测试。"""
        menu = QMenu(self)
        acts = {}
        acts[menu.addAction(tr("log_copyhash", "Copy full hash"))] = "copy"
        acts[menu.addAction(tr("log_copyshort", "Copy short hash"))] = "copy_short"
        acts[menu.addAction(tr("blame_copy_log", "Copy log"))] = "copy_log"
        menu.addSeparator()
        acts[menu.addAction(tr("blame_prev", "Blame previous revision"))] = "blame_prev"
        acts[menu.addAction(tr("blame_compare_prev", "Compare with previous revision"))] = "compare_prev"
        menu.addSeparator()
        acts[menu.addAction(tr("menu_show_log", "Show log for this commit"))] = "log"
        return menu, acts

    def _handle_menu(self, key: str, sha):
        from ..utils.clipboard import ClipboardHelper
        if key == "copy":
            ClipboardHelper().copy_text(sha)
        elif key == "copy_short":
            ClipboardHelper().copy_text(str(sha)[:8])
        elif key == "copy_log":
            ClipboardHelper().copy_text(self._log_text())
        elif key == "blame_prev":
            line = self._current_line()
            if line and line.previous_sha:
                from .modeless import show_modeless
                show_modeless(BlameDlg(
                    self.repo, line.previous_filename or self.filepath,
                    rev=line.previous_sha, parent=self))
        elif key == "compare_prev":
            line = self._current_line()
            if line and line.previous_sha:
                from .diffdlg import DiffDlg
                from .modeless import show_modeless
                show_modeless(DiffDlg(
                    self.repo, rev1=line.previous_sha, rev2=line.sha,
                    paths=[line.previous_filename or line.filename], parent=self))
        elif key == "log":
            from .logdlg import LogDlg
            from .modeless import show_modeless
            show_modeless(LogDlg(self.repo, pathspec=None, rev=str(sha),
                                 parent=self))

    def _log_text(self) -> str:
        line = self._current_line()
        if line is None:
            return ""
        return (f"{line.sha}\n{line.author} <{line.author_email}>\n"
                f"{line.date_span()}\n{line.summary}")

    def _on_menu(self, pos):
        sha = self._sha_at(pos)
        if sha is None:
            return
        self.table.selectRow(self.table.itemAt(pos).row())
        menu, acts = self._build_menu_context()
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        key = acts.get(chosen)
        if key:
            self._handle_menu(key, sha)

    def _on_log_selection(self):
        items = self.log_table.selectedItems()
        if not items:
            return
        sha = items[0].data(Qt.ItemDataRole.UserRole)
        if not sha or not self._data:
            return
        row = self._data.find_first_line(sha, 0)
        if row >= 0:
            self._select_row(row)

    def _on_log_menu(self, pos):
        item = self.log_table.itemAt(pos)
        if item is None:
            return
        sha = item.data(Qt.ItemDataRole.UserRole)
        if not sha:
            return
        from ..utils.clipboard import ClipboardHelper
        menu = QMenu(self)
        copy_hash = menu.addAction(tr("log_copyhash", "Copy full hash"))
        copy_log = menu.addAction(tr("blame_copy_log", "Copy log"))
        chosen = menu.exec(self.log_table.viewport().mapToGlobal(pos))
        if chosen is copy_hash:
            ClipboardHelper().copy_text(sha)
        elif chosen is copy_log:
            info = self._data.commits.get(sha) if self._data else None
            if info:
                ClipboardHelper().copy_text(
                    f"{info.sha}\n{info.author_name} <{info.author_email}>\n"
                    f"{info.author_date}\n{info.subject}\n{info.body}")

    def _on_prop_menu(self, pos):
        item = self.props.itemAt(pos)
        if item is None:
            return
        value = item.text(1)
        if not value:
            return
        from ..utils.clipboard import ClipboardHelper
        menu = QMenu(self)
        copy = menu.addAction(tr("blame_menu_copy", "Copy"))
        if menu.exec(self.props.viewport().mapToGlobal(pos)) is copy:
            ClipboardHelper().copy_text(value)


def _mk_button(text: str, slot, parent):
    from PySide6.QtWidgets import QPushButton
    btn = QPushButton(text, parent)
    btn.clicked.connect(slot)
    return btn


def _titled(widget: QWidget, title: str, parent=None) -> QWidget:
    """给控件加上 dock 面板式标题（对齐原版 CDockablePane 的窗格标题）。"""
    if not title:
        return widget
    box = QWidget(parent)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    label = QLabel(title, box)
    label.setObjectName("blame_pane_title")
    label.setStyleSheet(
        "background:#e8e8e8; border:1px solid #b0b0b0; padding:2px 6px; font-weight:bold;")
    lay.addWidget(label)
    lay.addWidget(widget, 1)
    return box
