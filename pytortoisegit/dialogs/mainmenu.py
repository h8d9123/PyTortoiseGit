"""mainmenu.py —— 主窗口：菜单栏 + Git 操作工具栏 + 左侧标签面板（仓库管理/目录树）。

GUI 入口（`python -m pytortoisegit` 无参数时打开此窗口），
或 `/command:menu` 显式打开。

布局（从顶部到底部）：
  1. 菜单栏（文件 / 视图 / 帮助）
  2. 工具栏：QToolButton 一排 Git 操作按钮（图标用 TortoiseGit icon）
  3. 主区：左侧标签面板（仓库管理树 + 目录树）+ 右侧命令列表 / 欢迎页
  4. 底部：仓库路径 + 按钮 + 状态栏
"""

from __future__ import annotations

import os
import string
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileIconProvider,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStyle,
    QTabWidget,
    QToolButton,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..cmdline import CommandLine
from ..git.admin import find_repo_root
from ..git.repo import Repository
from ..res.strings import format_string, tr
from .widgets import RepoPickerRow

_KEY_REPOS = "Browser/Repos"
# 树节点数据角色
ROLE_PATH = Qt.ItemDataRole.UserRole        # 仓库/子模块 绝对路径
ROLE_KIND = Qt.ItemDataRole.UserRole + 1    # "repo" / "submodule" / "drive" /
                                            #  "dir" / "placeholder"
ROLE_PARENT = Qt.ItemDataRole.UserRole + 2  # 子模块的父仓库根
ROLE_LOADED = Qt.ItemDataRole.UserRole + 3  # 节点是否已加载下级内容

# 经典 TortoiseGit 右键菜单：(命令名, 文案键, 默认文案)
_CLASSIC_MENU = [
    ("commit", "repo_menu_commit", "Commit…"),
    ("log", "repo_menu_log", "Show log"),
    ("pull", "repo_menu_pull", "Pull…"),
    ("push", "repo_menu_push", "Push…"),
    ("sync", "repo_menu_sync", "Sync"),
    ("revert", "repo_menu_revert", "Revert…"),
    ("cleanup", "repo_menu_cleanup", "Clean Up…"),
]


class MainMenuDlg(QMainWindow):
    """主窗口：菜单栏 + 工具栏 + 标签面板（仓库管理 / 目录树）+ 命令面板。"""

    # 工具栏按钮：(命令名, 资源图标 IDI, 标签)
    TOOLBAR = [
        ("commit", "IDI_COMMIT_BKG", "Commit"),
        ("log", "IDI_DIALOGS", "Log"),
        ("diff", "IDI_SWITCHLEFTRIGHT", "Diff"),
        ("clone", "IDI_GITFOLDER", "Clone"),
        ("sync", "IDI_GITREMOTE", "Sync"),
        ("pull", "IDI_REFRESH", "Pull"),
        ("push", "IDI_REFRESH", "Push"),
        ("fetch", "IDI_REFRESH", "Fetch"),
        ("submodule", "IDI_GITFOLDER", "Submodule"),
        ("stash", "IDI_SAVE", "Stash"),
        ("branch", "IDI_GITREMOTE", "Branch"),
        ("blame", "IDI_TORTOISEBLAME", "Blame"),
        ("settings", "IDI_GENERAL", "Settings"),
    ]

    def __init__(self, repo_path: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("menu_title", "PyTortoiseGit 主窗口"))
        self.resize(920, 620)
        try:
            from ..res import icons
            self.setWindowIcon(icons.app_icon())
        except Exception:
            pass
        self.repo: Repository | None = None
        self.commands: List[str] = []
        self._repo_list: list[str] = []
        self._nav_stack: list[str] = []   # 后退历史
        self._nav_forward: list[str] = []  # 前进历史
        self._nav_current: str = ""
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        # 从 QSettings 加载已添加仓库并刷新树
        self._repo_list = self._load_repo_list()
        self._refresh_repo_tree()
        if repo_path:
            self.path_row.setText(repo_path)
            self.open_repo(repo_path)

    # ---- 菜单栏 ----
    def _build_menu(self):
        bar = self.menuBar()
        # 文件
        m_file = bar.addMenu(tr("menu_file", "文件(&F)"))
        act_open = QAction(tr("menu_open_repo", "打开仓库…"), self)
        act_open.triggered.connect(self._open_repo_dialog)
        m_file.addAction(act_open)
        m_file.addSeparator()
        act_exit = QAction(tr("close", "退出(&Q)"), self)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)
        # 视图
        m_view = bar.addMenu(tr("menu_view", "视图(&V)"))
        act_repo = QAction(tr("menu_left_panel", "左侧面板"), self)
        act_repo.setCheckable(True)
        act_repo.setChecked(True)
        act_repo.toggled.connect(lambda on: self.manager_tabs.setVisible(on))
        m_view.addAction(act_repo)
        act_tool = QAction(tr("menu_toolbar", "工具栏"), self)
        act_tool.setCheckable(True)
        act_tool.setChecked(True)
        act_tool.toggled.connect(lambda on: self.toolbar.setVisible(on))
        m_view.addAction(act_tool)
        # 帮助
        m_help = bar.addMenu(tr("menu_help", "帮助(&H)"))
        act_about = QAction(tr("about_title", "关于"), self)
        act_about.triggered.connect(self._on_about)
        m_help.addAction(act_about)

    # ---- 工具栏（QToolButton 一排 Git 操作）----
    def _build_toolbar(self):
        self.toolbar = self.addToolBar(tr("menu_toolbar", "Git 操作"))
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        for name, icon_id, label in self.TOOLBAR:
            btn = QToolButton(self.toolbar)
            btn.setText(tr(name, label))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            try:
                from ..res import icons
                ic = icons.icon(icon_id)
                if ic and not ic.isNull():
                    btn.setIcon(ic)
            except Exception:
                pass
            btn.clicked.connect(lambda _=False, n=name: self._dispatch(n))
            self.toolbar.addWidget(btn)
            self.toolbar.addSeparator()

    # ---- 主区：左侧标签页（仓库管理 + 目录树）+ 右侧内容浏览 ----
    def _build_central(self):
        split = QSplitter(Qt.Orientation.Horizontal, self)
        # 标签页 1：仓库管理
        self.repo_manager_panel = QWidget(self)
        panel_lay = QVBoxLayout(self.repo_manager_panel)
        panel_lay.setContentsMargins(4, 4, 4, 4)
        panel_lay.addWidget(
            QLabel(tr("repo_manager_title", "仓库管理"), self.repo_manager_panel))
        self.repo_tree = QTreeWidget(self.repo_manager_panel)
        self.repo_tree.setColumnCount(3)
        self.repo_tree.setHeaderLabels([
            tr("submodule_path", "路径"),
            tr("submodule_status", "状态"),
            tr("submodule_sha", "SHA"),
        ])
        self.repo_tree.setRootIsDecorated(True)
        self.repo_tree.setIndentation(16)
        self.repo_tree.itemClicked.connect(self._on_repo_clicked)
        self.repo_tree.itemDoubleClicked.connect(self._on_repo_double_clicked)
        self.repo_tree.itemExpanded.connect(self._on_item_expanded)
        self.repo_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.repo_tree.customContextMenuRequested.connect(self._on_repo_context_menu)
        panel_lay.addWidget(self.repo_tree)
        panel_lay.addWidget(QLabel(
            tr("repo_manager_hint", "双击仓库切换；展开可查看子模块"),
            self.repo_manager_panel))
        # 标签页 2：目录树
        self.folder_tree_panel = QWidget(self)
        folder_lay = QVBoxLayout(self.folder_tree_panel)
        folder_lay.setContentsMargins(4, 4, 4, 4)
        folder_lay.addWidget(
            QLabel(tr("browser_tab_folder", "目录树"), self.folder_tree_panel))
        self.folder_tree = QTreeWidget(self.folder_tree_panel)
        self.folder_tree.setColumnCount(1)
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setRootIsDecorated(True)
        self.folder_tree.itemClicked.connect(self._on_folder_clicked)
        self.folder_tree.itemExpanded.connect(self._on_folder_expanded)
        self.folder_tree.itemDoubleClicked.connect(self._on_folder_double_clicked)
        self.folder_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_tree.customContextMenuRequested.connect(
            self._on_folder_context_menu)
        folder_lay.addWidget(self.folder_tree)
        folder_lay.addWidget(QLabel(
            tr("folder_hint", "双击仓库目录打开；右键仓库目录可添加并执行操作"),
            self.folder_tree_panel))
        # 合并为左面板标签组
        self.manager_tabs = QTabWidget(self)
        self.manager_tabs.addTab(
            self.repo_manager_panel, tr("browser_tab_repo", "仓库管理"))
        self.manager_tabs.addTab(
            self.folder_tree_panel, tr("browser_tab_folder", "目录树"))
        split.addWidget(self.manager_tabs)

        right = QWidget(self)
        right_lay = QVBoxLayout(right)
        self.path_row = RepoPickerRow(tr("menu_path_label", "仓库路径:"), right)
        self.path_row.setText(os.getcwd())
        self.path_row.connect_editingFinished(self._on_path_changed)
        right_lay.addWidget(self.path_row)
        self._welcome = QLabel(
            tr("content_hint", "单击左侧目录/仓库查看子文件夹；双击进入或打开。"),
            right)
        self._welcome.setWordWrap(True)
        right_lay.addWidget(self._welcome)
        nav = QHBoxLayout()
        self.btn_back = QPushButton(tr("menu_nav_back", "←"), right)
        self.btn_back.setToolTip(tr("menu_nav_back_tip", "后退"))
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)
        self.btn_forward = QPushButton(tr("menu_nav_forward", "→"), right)
        self.btn_forward.setToolTip(tr("menu_nav_forward_tip", "前进"))
        self.btn_forward.clicked.connect(self._go_forward)
        nav.addWidget(self.btn_forward)
        self.btn_up = QPushButton(tr("menu_nav_up", "↑"), right)
        self.btn_up.setToolTip(tr("menu_nav_up_tip", "上一级"))
        self.btn_up.clicked.connect(self._go_up)
        nav.addWidget(self.btn_up)
        self.btn_refresh = QPushButton(tr("menu_nav_refresh", "⟳"), right)
        self.btn_refresh.setToolTip(tr("menu_nav_refresh_tip", "刷新"))
        self.btn_refresh.clicked.connect(self._refresh_content)
        nav.addWidget(self.btn_refresh)
        nav.addStretch(1)
        right_lay.addLayout(nav)
        self.fs_model = QFileSystemModel(right)
        self.fs_model.setIconProvider(_GitIconProvider(self))
        self.content_list = QTreeView(right)
        self.content_list.setModel(self.fs_model)
        self.content_list.setRootIsDecorated(False)
        self.content_list.setItemsExpandable(False)
        self.content_list.setHeaderHidden(True)
        # 只需要名称列
        for c in range(self.fs_model.columnCount()):
            if c != 0:
                self.content_list.setColumnHidden(c, True)
        self.content_list.doubleClicked.connect(self._on_content_double_clicked)
        self.content_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.content_list.customContextMenuRequested.connect(
            self._on_content_context_menu)
        right_lay.addWidget(self.content_list, 1)
        last = QHBoxLayout()
        self.btn_open = QPushButton(tr("menu_open_content", "打&开"), right)
        self.btn_open.clicked.connect(self._open_content_selected)
        self.btn_about = QPushButton(tr("about_title", "关于"), right)
        self.btn_about.clicked.connect(self._on_about)
        self.btn_close = QPushButton(tr("close", "关&闭"), right)
        self.btn_close.clicked.connect(self.close)
        last.addStretch(1)
        last.addWidget(self.btn_open)
        last.addWidget(self.btn_about)
        last.addWidget(self.btn_close)
        right_lay.addLayout(last)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        split.setSizes([350, 570])
        self.setCentralWidget(split)
        self._populate_folder_tree()

    def _build_statusbar(self):
        self.status = QLabel("")
        self.statusBar().addWidget(self.status)

    # ---- 右侧内容浏览（资源管理器中间窗格，基于 QFileSystemModel）----
    def _show_content(self, path: str):
        """让右侧显示给定目录的内容（含子文件夹与文件），并同步路径栏。"""
        abspath = os.path.abspath(path)
        self.fs_model.setRootPath(abspath)
        self.content_list.setRootIndex(self.fs_model.index(abspath))
        self._nav_current = abspath
        self.path_row.setText(abspath)
        self._update_nav_buttons()

    def _navigate(self, path: str):
        """进入目录并记录导航历史（后退可回退）。"""
        abspath = os.path.abspath(path)
        if self._nav_current:
            self._nav_stack.append(self._nav_current)
        self._nav_forward.clear()
        self._show_content(abspath)

    def _refresh_content(self):
        """刷新当前目录内容（不改变历史）。"""
        cur = self._current_dir()
        if cur:
            self._show_content(cur)

    def _go_back(self):
        if not self._nav_stack:
            return
        cur = self._nav_current
        self._nav_forward.append(cur)
        self._show_content(self._nav_stack.pop())

    def _go_forward(self):
        if not self._nav_forward:
            return
        cur = self._nav_current
        self._nav_stack.append(cur)
        self._show_content(self._nav_forward.pop())

    def _update_nav_buttons(self):
        self.btn_back.setEnabled(bool(self._nav_stack))
        self.btn_forward.setEnabled(bool(self._nav_forward))

    def _path_of_index(self, index) -> str:
        return self.fs_model.filePath(index)

    def _on_repo_clicked(self, item, _col):
        """单击仓库节点：右侧显示仓库根内子文件夹与文件。"""
        path = item.data(0, ROLE_PATH)
        if path:
            self._navigate(path)

    def _on_folder_clicked(self, item, _col):
        """单击目录树节点：右侧显示该目录内子文件夹与文件。"""
        path = item.data(0, ROLE_PATH)
        if path and os.path.isdir(path):
            self._navigate(path)

    def _current_dir(self) -> str:
        """当前内容浏览所在的目录（根索引对应路径）。"""
        index = self.content_list.rootIndex()
        if index.isValid():
            return self.fs_model.filePath(index)
        return ""

    def _go_up(self):
        """返回上级目录（纳入导航历史）。"""
        cur = self._current_dir()
        parent = os.path.dirname(cur) if cur else ""
        if parent and os.path.isdir(parent):
            self._navigate(parent)

    def _is_dir_index(self, index) -> bool:
        try:
            return self.fs_model.isDir(index)
        except Exception:
            return False

    def _on_content_double_clicked(self, index, _col=0):
        """右侧双击目录（含仓库根）→进入浏览；文件→不做。"""
        path = self._path_of_index(index)
        if not path:
            return
        if self._is_dir_index(index):
            self._navigate(path)

    def _open_content_selected(self):
        """“打开”按钮：与双击一致。"""
        index = self.content_list.currentIndex()
        if index.isValid():
            self._on_content_double_clicked(index, 0)

    def _on_content_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        index = self.content_list.indexAt(pos)
        if not index.isValid():
            return
        path = self._path_of_index(index)
        if not os.path.exists(path):
            return
        if not self._is_dir_index(index):
            self._build_file_menu(path, self.content_list).exec(
                self.content_list.viewport().mapToGlobal(pos))
            return
        if self._inside_repo(path):
            menu = self._build_classic_menu(path, self.content_list)
        else:
            menu = QMenu(self.content_list)
            act_clone = menu.addAction(tr("repo_menu_clone", "Git Clone…"))
            act_clone.triggered.connect(
                lambda _=False, p=path: self._run_clone_in(p))
            act_set = menu.addAction(tr("repo_menu_settings", "Settings"))
            act_set.triggered.connect(
                lambda _=False, p=path: self._dispatch("settings", extra={"path": p}))
        menu.exec(self.content_list.viewport().mapToGlobal(pos))

    def _build_file_menu(self, path: str, parent=None) -> "QMenu":
        """文件右键菜单：系统打开 + TortoiseGit 命令（仿 TortoiseGit 经典菜单）。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(parent or self.content_list)
        act_open = menu.addAction(tr("file_menu_open", "打开"))
        act_open.triggered.connect(lambda _=False, p=path: self._open_with_system(p))
        act_show = menu.addAction(tr("file_menu_show_in", "显示位置"))
        act_show.triggered.connect(lambda _=False, p=path: self._show_in_explorer(p))
        if self._inside_repo(path):
            menu.addSeparator()
            tg = menu.addMenu(tr("file_menu_tg", "TortoiseGit"))
            act_diff = tg.addAction(
                tr("file_menu_diff", "与 HEAD 比较（Diff）…"))
            act_diff.triggered.connect(
                lambda _=False, p=path: self._dispatch("diff", extra={"path": p}))
            act_blame = tg.addAction(tr("file_menu_blame", "追溯（Blame）…"))
            act_blame.triggered.connect(
                lambda _=False, p=path: self._dispatch("blame", extra={"path": p}))
            act_log = tg.addAction(tr("file_menu_log", "显示日志（Log）…"))
            act_log.triggered.connect(
                lambda _=False, p=path: self._dispatch("log", extra={"path": p}))
            act_rem = tg.addAction(tr("file_menu_remove", "删除（Remove）…"))
            act_rem.triggered.connect(
                lambda _=False, p=path: self._dispatch("remove", extra={"path": p}))
        return menu

    def _open_with_system(self, path: str):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))

    def _show_in_explorer(self, path: str):
        import subprocess
        subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])

    # ---- QSettings 持久化 ----
    @staticmethod
    def _load_repo_list() -> list[str]:
        from .settingsdlg import general_settings
        return general_settings().value(_KEY_REPOS, [], type=list)

    def _save_repo_list(self):
        from .settingsdlg import general_settings
        general_settings().setValue(_KEY_REPOS, self._repo_list)

    def _ensure_in_repo_list(self, path: str):
        """打开仓库成功后自动加入管理列表并刷新树。"""
        norm = os.path.abspath(path)
        if os.path.normcase(norm) not in {os.path.normcase(p) for p in self._repo_list}:
            self._repo_list.append(norm)
            self._save_repo_list()
        self._refresh_repo_tree()

    def _refresh_repo_tree(self):
        """重建仓库管理树（保留展开状态）。"""
        # 记录当前展开状态
        expanded_paths: set[str] = set()
        for i in range(self.repo_tree.topLevelItemCount()):
            it = self.repo_tree.topLevelItem(i)
            if it.isExpanded():
                p = it.data(0, ROLE_PATH)
                if p:
                    expanded_paths.add(p)
        self.repo_tree.clear()
        for path in self._repo_list:
            # 路径失效则静默清理
            try:
                repo = Repository.open(path)
            except Exception:
                continue
            display = f"{repo.name}  ({path})"
            item = QTreeWidgetItem([display])
            item.setData(0, ROLE_PATH, path)
            item.setData(0, ROLE_KIND, "repo")
            self.repo_tree.addTopLevelItem(item)
            if path in expanded_paths:
                item.setExpanded(True)
        # 确保当前仓库节点被选中并展开
        if self.repo:
            cur_path = os.path.normcase(os.path.abspath(self.repo.root))
            for i in range(self.repo_tree.topLevelItemCount()):
                it = self.repo_tree.topLevelItem(i)
                if os.path.normcase(it.data(0, ROLE_PATH)) == cur_path:
                    self.repo_tree.setCurrentItem(it)
                    # 确保子模块已加载（触发展开）
                    if not it.isExpanded():
                        it.setExpanded(True)
                    break

    # ---- 树控件行为 ----
    def _on_item_expanded(self, item):
        """仓库节点展开时懒加载子模块。"""
        if item.data(0, ROLE_KIND) != "repo" or item.data(0, ROLE_LOADED):
            return
        repo_path = item.data(0, ROLE_PATH)
        if not repo_path:
            return
        try:
            from ..git.repo import Repository as _Repo
            from ..git.submodule import GitSubmodule
            repo = _Repo.open(repo_path)
            for e in GitSubmodule(repo).list(recursive=False):
                sub_abs = os.path.join(repo_path, e.path)
                sub = QTreeWidgetItem([e.path, e.status_text, (e.sha1 or "")[:8]])
                sub.setData(0, ROLE_PATH, sub_abs)
                sub.setData(0, ROLE_KIND, "submodule")
                sub.setData(0, ROLE_PARENT, repo_path)
                item.addChild(sub)
        except Exception:
            pass
        item.setData(0, ROLE_LOADED, True)

    def _on_repo_double_clicked(self, item, _col):
        """双击仓库→切换；双击子模块→打开。"""
        if item.data(0, ROLE_KIND) == "submodule":
            sub_path = item.data(0, ROLE_PATH)
            self._run_async_command("submodule", extra={"path": sub_path})
        else:
            path = item.data(0, ROLE_PATH)
            if path:
                self.open_repo(path)

    def _build_classic_menu(self, path: str, parent=None) -> "QMenu":
        """经典 TortoiseGit 右键菜单（作用于给定仓库路径）。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(parent or self.repo_tree)
        for cmd, key, label in _CLASSIC_MENU:
            act = menu.addAction(tr(key, label))
            act.triggered.connect(
                lambda _=False, c=cmd, p=path: self._dispatch(c, extra={"path": p}))
        menu.addSeparator()
        act_set = menu.addAction(tr("repo_menu_settings", "Settings"))
        act_set.triggered.connect(
            lambda _=False, p=path: self._dispatch("settings", extra={"path": p}))
        return menu

    def _on_repo_context_menu(self, pos):
        item = self.repo_tree.itemAt(pos)
        if item is None:
            return
        if item.data(0, ROLE_KIND) == "repo":
            # 仓库节点：经典 TortoiseGit 菜单 + 移除
            path = item.data(0, ROLE_PATH)
            menu = self._build_classic_menu(path, self.repo_tree)
            menu.addSeparator()
            act_rem = menu.addAction(tr("repo_menu_remove", "从列表移除"))
            act_rem.triggered.connect(
                lambda _=False, it=item: self._remove_repo_from_list(it))
        else:
            # 子模块节点：打开子模块
            from PySide6.QtWidgets import QMenu
            menu = QMenu(self.repo_tree)
            sub_path = item.data(0, ROLE_PATH)
            act = menu.addAction(tr("repo_menu_open_sub", "打开子模块"))
            act.triggered.connect(
                lambda _=False, p=sub_path:
                self._run_async_command("submodule", extra={"path": p}))
        menu.exec(self.repo_tree.viewport().mapToGlobal(pos))

    def _remove_repo_from_list(self, item):
        """从持久化列表中移除指定仓库。"""
        path = item.data(0, ROLE_PATH)
        norm = os.path.normcase(os.path.abspath(path))
        self._repo_list = [
            p for p in self._repo_list
            if os.path.normcase(os.path.abspath(p)) != norm
        ]
        self._save_repo_list()
        self._refresh_repo_tree()

    # ---- 目录树（左侧第二标签）----
    @staticmethod
    def _list_drives() -> list[str]:
        if os.name == "nt":
            return [f"{c}:\\" for c in string.ascii_uppercase
                    if os.path.isdir(f"{c}:\\")]
        return ["/"]

    def _populate_folder_tree(self):
        self.folder_tree.clear()
        for drive in self._list_drives():
            it = QTreeWidgetItem([drive])
            it.setData(0, ROLE_PATH, drive)
            it.setData(0, ROLE_KIND, "drive")
            it.setIcon(0, self._drive_icon())
            self._add_placeholder(it)
            self.folder_tree.addTopLevelItem(it)

    @staticmethod
    def _add_placeholder(item: QTreeWidgetItem):
        holder = QTreeWidgetItem([""])
        holder.setData(0, ROLE_KIND, "placeholder")
        item.addChild(holder)

    def _on_folder_expanded(self, item):
        """目录节点展开时懒加载子目录。"""
        if item.data(0, ROLE_LOADED):
            return
        for i in reversed(range(item.childCount())):
            child = item.child(i)
            if child.data(0, ROLE_KIND) == "placeholder":
                item.removeChild(child)
        self._load_dir_item(item)
        item.setData(0, ROLE_LOADED, True)

    def _load_dir_item(self, item):
        """列出某目录的直接子目录并建节点，标记其中的仓库根。"""
        path = item.data(0, ROLE_PATH)
        try:
            names = sorted(os.listdir(path), key=str.casefold)
        except OSError:
            return
        for name in names:
            sub = os.path.join(path, name)
            if not os.path.isdir(sub):
                continue
            child = QTreeWidgetItem([name])
            child.setData(0, ROLE_PATH, sub)
            if self._is_repo_root(sub):
                child.setData(0, ROLE_KIND, "repo")
                self._apply_repo_icon(child)
            else:
                child.setData(0, ROLE_KIND, "dir")
                child.setIcon(0, self._dir_icon())
            self._add_placeholder(child)
            item.addChild(child)

    @staticmethod
    def _is_repo_root(path: str) -> bool:
        """目录本身是否为仓库工作树根。"""
        try:
            return find_repo_root(path) == os.path.abspath(path)
        except Exception:
            return False

    @staticmethod
    def _inside_repo(path: str) -> bool:
        """路径是否位于某仓库工作树内（含根）。"""
        try:
            return find_repo_root(path) is not None
        except Exception:
            return False

    def _apply_repo_icon(self, item: QTreeWidgetItem):
        try:
            from ..res import icons
            ic = icons.icon("IDI_GITFOLDER")
            if ic and not ic.isNull():
                item.setIcon(0, ic)
        except Exception:
            item.setIcon(0, self._dir_icon())

    def _dir_icon(self):
        return self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)

    def _drive_icon(self):
        return self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)

    def _on_folder_double_clicked(self, item, _col):
        """双击仓库目录则在主窗口打开；其余目录走默认展开。"""
        if item.data(0, ROLE_KIND) == "repo":
            path = item.data(0, ROLE_PATH)
            if path:
                self.open_repo(path)

    def _refresh_folder_item(self, item: QTreeWidgetItem):
        """重新扫描某目录节点（或分区/仓库节点）的直接子目录。"""
        if item is None:
            return
        for i in reversed(range(item.childCount())):
            item.removeChild(item.child(i))
        item.setData(0, ROLE_LOADED, False)
        if item.isExpanded():
            self._load_dir_item(item)
            item.setData(0, ROLE_LOADED, True)
        else:
            self._add_placeholder(item)

    def _build_folder_repo_menu(self, path: str, item=None) -> "QMenu":
        """目录树中仓库节点的右键菜单：添加 + 经典 TortoiseGit 命令（含设置）。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self.folder_tree)
        act_add = menu.addAction(tr("menu_add_to_repo_list", "添加到仓库管理"))
        act_add.triggered.connect(
            lambda _=False, p=path: self._ensure_in_repo_list(p))
        menu.addSeparator()
        for cmd, key, label in _CLASSIC_MENU:
            act = menu.addAction(tr(key, label))
            act.triggered.connect(
                lambda _=False, c=cmd, p=path: self._dispatch(c, extra={"path": p}))
        menu.addSeparator()
        act_set = menu.addAction(tr("repo_menu_settings", "Settings"))
        act_set.triggered.connect(
            lambda _=False, p=path: self._dispatch("settings", extra={"path": p}))
        if item is not None:
            menu.addSeparator()
            act_refresh = menu.addAction(tr("refresh"))
            act_refresh.triggered.connect(
                lambda _=False, it=item: self._refresh_folder_item(it))
        return menu

    def _build_folder_nonrepo_menu(self, path: str, item=None) -> "QMenu":
        """目录树中非仓库目录/分区的右键菜单：Git Clone… + Settings + 刷新。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self.folder_tree)
        act_clone = menu.addAction(tr("repo_menu_clone", "Git Clone…"))
        act_clone.triggered.connect(
            lambda _=False, p=path: self._run_clone_in(p))
        menu.addSeparator()
        act_set = menu.addAction(tr("repo_menu_settings", "Settings"))
        act_set.triggered.connect(
            lambda _=False, p=path: self._dispatch("settings", extra={"path": p}))
        menu.addSeparator()
        act_refresh = menu.addAction(tr("refresh"))
        act_refresh.triggered.connect(
            lambda _=False, it=item: self._refresh_folder_item(it))
        return menu

    def _on_folder_context_menu(self, pos):
        item = self.folder_tree.itemAt(pos)
        if item is None or item.data(0, ROLE_KIND) in (None, "placeholder"):
            return
        path = item.data(0, ROLE_PATH)
        if self._inside_repo(path):
            self._build_folder_repo_menu(path, item).exec(
                self.folder_tree.viewport().mapToGlobal(pos))
        else:
            self._build_folder_nonrepo_menu(path, item).exec(
                self.folder_tree.viewport().mapToGlobal(pos))

    def _run_clone_in(self, path: str):
        """以指定目录为默认目标打开 Git Clone 对话框（不阻塞窗口）。"""
        from PySide6.QtCore import QTimer
        from ..commands.dispatcher import CommandContext
        cl = CommandLine(verb="clone")
        cl.options["url"] = [""]
        cl.options["dir"] = [os.path.abspath(path)]
        ctx = CommandContext(qapp=None, cl=cl)
        self.status.setText(format_string(tr("menu_running", "正在执行：{name}"), name="clone"))
        QTimer.singleShot(0, lambda: self._run(ctx, "clone"))

    # ---- 仓库 ----
    def open_repo(self, path: str):
        try:
            self.repo = Repository.open(path)
        except Exception as exc:
            self.status.setText(
                format_string(tr("menu_not_repo", "不是 Git 仓库：{msg}"), msg=exc))
            return
        self.path_row.setText(path)
        self.status.setText(f" {path} · {self.repo.current_branch()}")
        self._ensure_in_repo_list(path)

    def _on_path_changed(self):
        p = self.path_row.text().strip()
        if p:
            self.open_repo(p)

    def _open_repo_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(
            self, tr("menu_open_repo", "打开仓库"), self.path_row.text())
        if d:
            self.open_repo(d)

    # ---- 命令执行 ----
    def _dispatch(self, name: str, extra=None):
        extra_path = bool(extra and extra.get("path"))
        if not (self.repo or self.path_row.text().strip() or extra_path):
            self.status.setText(tr("menu_select_first", "请先选择仓库路径。"))
            return
        from PySide6.QtCore import QTimer
        path = self.path_row.text().strip()
        cl = CommandLine(verb=name)
        if path:
            cl.options["path"] = [path]
        if extra:
            for k, v in extra.items():
                cl.options[k] = [v]
        from ..commands.dispatcher import CommandContext
        ctx = CommandContext(qapp=None, cl=cl)
        self.status.setText(
            format_string(tr("menu_running", "正在执行：{name}"), name=name))
        QTimer.singleShot(0, lambda: self._run(ctx, name))

    def _run_async_command(self, name: str, extra=None):
        self._dispatch(name, extra=extra)

    def _run(self, ctx, name: str):
        from ..commands.dispatcher import dispatch, UnknownCommandError
        try:
            dispatch(name, ctx)
            self.status.setText(
                format_string(tr("menu_done", "完成：{name}"), name=name))
        except UnknownCommandError:
            self.status.setText(
                format_string(tr("unknown_command"), command=name))
        except Exception as exc:  # noqa: BLE001
            self.status.setText(
                format_string(tr("command_failed"), name=name, message=exc))
            from ..utils.logging_utils import get_logger
            get_logger().exception("menu 命令失败: %s", name)

    def _on_about(self):
        from .aboutdlg import AboutDlg
        AboutDlg(parent=self).exec()

    # ---- 兼容 QDialog 测试接口 ----
    def reject(self):
        self.close()

    def exec_loop(self) -> int:
        from PySide6.QtWidgets import QApplication
        self.show()
        return QApplication.instance().exec() if QApplication.instance() else 0

    def exec(self):
        from PySide6.QtWidgets import QApplication
        self.show()
        return QApplication.instance().exec() if QApplication.instance() else 0


def _noop(*_a, **_k):
    return None


class _GitIconProvider(QFileIconProvider):
    """QFileSystemModel 图标提供者：把 git 仓库根目录标为 Git 图标。"""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def icon(self, info):  # noqa: A003 - 覆写基类成员名
        if info.isDir():
            p = info.absoluteFilePath()
            if p and find_repo_root(p) == os.path.abspath(p):
                try:
                    from ..res import icons
                    ic = icons.icon("IDI_GITFOLDER")
                    if ic and not ic.isNull():
                        return ic
                except Exception:
                    pass
        return super().icon(info)
