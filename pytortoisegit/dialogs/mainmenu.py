"""mainmenu.py —— 主窗口：菜单栏 + 左侧标签面板（仓库管理/目录树）。

GUI 入口（`python -m pytortoisegit` 无参数时打开此窗口），
或 `/command:menu` 显式打开。

布局（从顶部到底部）：
  1. 菜单栏（文件 / 视图 / 命令 / 帮助）
  2. 主区：左侧标签面板（仓库管理树 + 目录树）+ 右侧命令列表 / 欢迎页
  3. 底部：仓库路径 + 按钮 + 状态栏
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

# 命令名 → TortoiseGit 菜单图标 ID（参考 TortoiseShell/resourceshell.rc 的 IDI_* ↔ 资源文件映射）
_CMD_ICON = {
    "commit": "IDI_COMMIT",          # menucommit.ico
    "log": "IDI_LOG",                # menulog.ico
    "pull": "IDI_PULL",              # pull1.ico
    "push": "IDI_PUSH",              # Push.ico
    "sync": "IDI_RELOCATE",          # menurelocate.ico
    "revert": "IDI_REVERT",          # menurevert.ico
    "cleanup": "IDI_CLEANUP",        # menucleanup.ico
    "add": "IDI_ADD",                # menuadd.ico
    "remove": "IDI_DELETE",          # menudelete.ico
    "rename": "IDI_RENAME",          # menurename.ico
    "resolve": "IDI_RESOLVE",        # menuresolve.ico
    "ignore": "IDI_IGNORE",          # menuignore.ico
    "unignore": "IDI_IGNORE",        # menuignore.ico
    "svnignore": "IDI_IGNORE",       # menuignore.ico
    "diff": "IDI_DIFF",              # menucompare.ico
    "prevdiff": "IDI_DIFF",          # menucompare.ico
    "repostatus": "IDI_SHOWCHANGED", # menushowchanged.ico
    "blame": "IDI_BLAME",            # TortoiseGitBlame.ico
    "revisiongraph": "IDI_REVISIONGRAPH",  # menurevisiongraph.ico
    "repobrowser": "IDI_REPOBROWSE", # menurepobrowse.ico
    "reflog": "IDI_LOG",             # menulog.ico
    "fetch": "IDI_UPDATE",           # menuupdate.ico
    "sendmail": "IDI_MENUSENDMAIL",  # menusendmail.ico
    "subsync": "IDI_MENUSYNC",       # menusync.ico
    "branch": "IDI_COPY",            # menucopy.ico
    "merge": "IDI_MERGE",            # menumerge.ico
    "merge3": "IDI_MERGE",           # menumerge.ico
    "mergeabort": "IDI_MERGEABORT",  # menumergeabort.ico
    "rebase": "IDI_REBASE",          # menurebase.ico
    "switch": "IDI_SWITCH",          # menuswitch.ico
    "bisect": "IDI_BISECT",          # menubisect.ico
    "stash": "IDI_SHELVE",           # menushelve.ico
    "stashsave": "IDI_SHELVE",       # menushelve.ico
    "stashpop": "IDI_UNSHELVE",      # menuunshelve.ico
    "stashapply": "IDI_UNSHELVE",    # menuunshelve.ico
    "stashlist": "IDI_LOG",          # menulog.ico
    "clone": "IDI_CLONE",            # menucheckout.ico
    "addremote": "IDI_ADD",          # menuadd.ico
    "submodule": "IDI_UPDATE",       # menuupdate.ico
    "repocreate": "IDI_CREATEREPOS", # menucreaterepos.ico
    "export": "IDI_EXPORT",          # menuexport.ico
    "formatpatch": "IDI_CREATEPATCH",  # menudiff.ico
    "importpatch": "IDI_PATCH",      # menupatch.ico
    "showcompare": "IDI_DIFF",       # menucompare.ico
    "settings": "IDI_SETTINGS",      # menusettings.ico
    "help": "IDI_HELP",              # menuhelp.ico
    "daemon": "IDI_DAEMON",          # menudaemon.ico
    "changed": "IDI_SHOWCHANGED",    # menushowchanged.ico
    "lfslock": "IDI_LFSLOCK",        # menulock.ico
    "lfsunlock": "IDI_LFSUNLOCK",    # menuunlock.ico
}


class MainMenuDlg(QMainWindow):
    """主窗口：菜单栏 + 标签面板（仓库管理 / 目录树）+ 命令面板。"""

    # 菜单栏“命令(&C)”分组：组名 → 该组包含的命令
    MENU_GROUPS = [
        ("menu_grp_changes", "Local Changes",
         ["commit", "revert", "cleanup", "add", "remove", "ignore",
          "unignore", "rename", "resolve", "conflicteditor"]),
        ("menu_grp_inspect", "Inspect/Compare",
         ["log", "diff", "prevdiff", "review", "blame", "repostatus",
          "revisiongraph", "repobrowser", "cat", "reflog"]),
        ("menu_grp_syncing", "Sync/Publish",
         ["sync", "pull", "push", "fetch", "requestpull", "sendmail",
          "subsync"]),
        ("menu_grp_branch", "Branch/Merge",
         ["branch", "merge", "merge3", "mergeabort", "rebase", "switch",
          "bisect", "reset", "stash", "stashsave", "stashpop", "stashapply",
          "stashlist", "worktreelist", "worktreecreate", "newworktree"]),
        ("menu_grp_clone", "Repository",
         ["clone", "addremote", "submodule", "repocreate", "lfslock",
          "lfslocks", "lfsunlock"]),
        ("menu_grp_format", "Patch/Export",
         ["export", "formatpatch", "importpatch", "showcompare"]),
        ("menu_grp_utils", "Tools/Other",
         ["settings", "firststart", "updatecheck", "help", "shell",
          "daemon", "rtfm", "changed", "revision"]),
    ]

    @staticmethod
    def _set_action_icon(action, icon_id: str):
        """给 QAction 设置 TortoiseGit 菜单图标（读取失败时静默忽略）。"""
        try:
            from ..res import icons
            ic = icons.icon(icon_id)
            if ic is not None and not ic.isNull():
                action.setIcon(ic)
        except Exception:  # noqa: BLE001
            pass

    def __init__(self, repo_path: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("menu_title", "PyTortoiseGit Main Window"))
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
        self._status_cache: dict = {}   # 仓库根 -> (时间戳, 状态条目)
        self._cut_paths: list[str] = []  # 剪切中的路径（粘贴时移动）
        self._build_menu()
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
        m_file = bar.addMenu(tr("menu_file", "&File"))
        act_open = QAction(tr("menu_open_repo", "Open Repository…"), self)
        act_open.triggered.connect(self._open_repo_dialog)
        m_file.addAction(act_open)
        m_file.addSeparator()
        act_exit = QAction(tr("close", "E&xit"), self)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)
        # 视图
        m_view = bar.addMenu(tr("menu_view", "&View"))
        act_repo = QAction(tr("menu_left_panel", "Left Panel"), self)
        act_repo.setCheckable(True)
        act_repo.setChecked(True)
        act_repo.toggled.connect(lambda on: self.manager_tabs.setVisible(on))
        m_view.addAction(act_repo)
        # 命令（列出所有已注册命令，按功能分组）
        m_cmd = bar.addMenu(tr("menu_commands", "&Commands"))
        self._build_command_menu(m_cmd)
        # 设置
        m_settings = bar.addMenu(tr("menu_settings", "&Settings"))
        act_settings = QAction(tr("menu_cmd_settings", "Settings…"), self)
        self._set_action_icon(act_settings, "IDI_SETTINGS")
        act_settings.triggered.connect(lambda: self._dispatch("settings"))
        m_settings.addAction(act_settings)
        act_firststart = QAction(
            tr("menu_cmd_firststart", "First Start Wizard…"), self)
        act_firststart.triggered.connect(lambda: self._dispatch("firststart"))
        m_settings.addAction(act_firststart)
        m_settings.addSeparator()
        act_update = QAction(
            tr("menu_cmd_updatecheck", "Check for updates…"), self)
        act_update.triggered.connect(lambda: self._dispatch("updatecheck"))
        m_settings.addAction(act_update)
        # 帮助
        m_help = bar.addMenu(tr("menu_help", "&Help"))
        act_about = QAction(tr("about_title", "About"), self)
        act_about.triggered.connect(self._on_about)
        m_help.addAction(act_about)

    def _build_command_menu(self, m_cmd):
        """把全部已注册命令按功能分组挂到“命令”菜单。"""
        from ..commands.dispatcher import available_commands
        from ..commands.dispatcher import _ensure_imports
        _ensure_imports()
        available = set(available_commands())
        # 人工分组；余下的命令放进“其他”
        placed: set[str] = set()
        for grp_key, grp_label, names in self.MENU_GROUPS:
            items = [n for n in names if n in available]
            if not items:
                continue
            placed.update(items)
            sub = m_cmd.addMenu(tr(grp_key, grp_label))
            for name in items:
                act = sub.addAction(tr("menu_cmd_" + name, name))
                icon_id = _CMD_ICON.get(name)
                if icon_id:
                    self._set_action_icon(act, icon_id)
                act.triggered.connect(
                    lambda _=False, n=name: self._dispatch(n))
        other = sorted(available - placed)
        if other:
            sub = m_cmd.addMenu(tr("menu_grp_other", "Other"))
            for name in other:
                act = sub.addAction(tr("menu_cmd_" + name, name))
                icon_id = _CMD_ICON.get(name)
                if icon_id:
                    self._set_action_icon(act, icon_id)
                act.triggered.connect(
                    lambda _=False, n=name: self._dispatch(n))

    # ---- 主区：左侧标签页（仓库管理 + 目录树）+ 右侧内容浏览 ----
    def _build_central(self):
        split = QSplitter(Qt.Orientation.Horizontal, self)
        # 标签页 1：仓库管理
        self.repo_manager_panel = QWidget(self)
        panel_lay = QVBoxLayout(self.repo_manager_panel)
        panel_lay.setContentsMargins(4, 4, 4, 4)
        panel_lay.addWidget(
            QLabel(tr("repo_manager_title", "Repository Manager"), self.repo_manager_panel))
        self.repo_tree = QTreeWidget(self.repo_manager_panel)
        self.repo_tree.setColumnCount(3)
        self.repo_tree.setHeaderLabels([
            tr("submodule_path", "Path"),
            tr("submodule_status", "Status"),
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
            tr("repo_manager_hint", "Double-click a repository to switch; expand to view submodules"),
            self.repo_manager_panel))
        # 标签页 2：目录树
        self.folder_tree_panel = QWidget(self)
        folder_lay = QVBoxLayout(self.folder_tree_panel)
        folder_lay.setContentsMargins(4, 4, 4, 4)
        folder_lay.addWidget(
            QLabel(tr("browser_tab_folder", "Folder Tree"), self.folder_tree_panel))
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
            tr("folder_hint", "Double-click a repository folder to open; right-click to add and run actions"),
            self.folder_tree_panel))
        # 合并为左面板标签组
        self.manager_tabs = QTabWidget(self)
        self.manager_tabs.addTab(
            self.repo_manager_panel, tr("browser_tab_repo", "Repository Manager"))
        self.manager_tabs.addTab(
            self.folder_tree_panel, tr("browser_tab_folder", "Folder Tree"))
        split.addWidget(self.manager_tabs)

        right = QWidget(self)
        right_lay = QVBoxLayout(right)
        self.path_row = RepoPickerRow(tr("menu_path_label", "Repository path:"), right)
        self.path_row.setText(os.getcwd())
        self.path_row.connect_editingFinished(self._on_path_changed)
        right_lay.addWidget(self.path_row)
        self._welcome = QLabel(
            tr("content_hint", "Click a folder/repository on the left to view subfolders; double-click to enter or open."),
            right)
        self._welcome.setWordWrap(True)
        right_lay.addWidget(self._welcome)
        nav = QHBoxLayout()
        self.btn_back = QPushButton(tr("menu_nav_back", "←"), right)
        self.btn_back.setToolTip(tr("menu_nav_back_tip", "Back"))
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)
        self.btn_forward = QPushButton(tr("menu_nav_forward", "→"), right)
        self.btn_forward.setToolTip(tr("menu_nav_forward_tip", "Forward"))
        self.btn_forward.clicked.connect(self._go_forward)
        nav.addWidget(self.btn_forward)
        self.btn_up = QPushButton(tr("menu_nav_up", "↑"), right)
        self.btn_up.setToolTip(tr("menu_nav_up_tip", "Up"))
        self.btn_up.clicked.connect(self._go_up)
        nav.addWidget(self.btn_up)
        self.btn_refresh = QPushButton(tr("menu_nav_refresh", "⟳"), right)
        self.btn_refresh.setToolTip(tr("menu_nav_refresh_tip", "Refresh"))
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
        # 强制刷新图标缓存：stash push/pop 会删除再重建目录，Qt 的
        # QFileSystemModel 可能保留旧的目录图标（例如误用 git 文件夹图标）。
        # 重新设置 iconProvider 会让模型重新请求图标。
        # 同时在 GUI 线程预构建「基础图标 + 状态覆盖」，供后台线程查表使用。
        provider = _GitIconProvider(self)
        provider.set_icons(self._build_overlay_icons(abspath))
        self.fs_model.setIconProvider(provider)
        self.fs_model.setRootPath(abspath)
        self.content_list.setRootIndex(self.fs_model.index(abspath))
        self._nav_current = abspath
        self.path_row.setText(abspath)
        self._update_nav_buttons()

    def _status_entries(self, root: str) -> list:
        """取仓库状态条目（带 2 秒缓存，避免频繁 git status）。"""
        import time
        now = time.time()
        cached = self._status_cache.get(root)
        if cached and now - cached[0] < 2.0:
            return cached[1]
        entries: list = []
        try:
            from ..git.repo import Repository
            from ..git.status import GitStatus
            entries = GitStatus(Repository.open(root)).get_status()
        except Exception:  # noqa: BLE001
            entries = []
        self._status_cache[root] = (now, entries)
        return entries

    def _build_overlay_icons(self, directory: str) -> dict:
        """为 directory 下的条目构建 规范化路径 -> 合成图标（GUI 线程）。"""
        out: dict = {}
        root = find_repo_root(directory)
        if not root:
            return out
        try:
            from PySide6.QtCore import QFileInfo
            from PySide6.QtWidgets import QFileIconProvider
            from ..res import icons, overlays
        except Exception:  # noqa: BLE001
            return out
        root_nc = os.path.normcase(os.path.abspath(root))
        file_state: dict = {}
        dir_state: dict = {}
        for e in self._status_entries(root):
            key = e.overlay_key
            p = os.path.normcase(os.path.abspath(os.path.join(root, e.path)))
            file_state[p] = overlays.worse(file_state.get(p), key)
            d = os.path.dirname(p)
            while d.startswith(root_nc) and len(d) > len(root_nc):
                dir_state[d] = overlays.worse(dir_state.get(d), key)
                d = os.path.dirname(d)
        try:
            names = os.listdir(directory)
        except OSError:
            return out
        base_provider = QFileIconProvider()
        git_icon = None
        for name in names:
            full = os.path.join(directory, name)
            nc = os.path.normcase(os.path.abspath(full))
            try:
                is_dir = os.path.isdir(full)
            except OSError:
                continue
            if is_dir:
                status = dir_state.get(nc, "normal")
                if nc == root_nc:
                    if git_icon is None:
                        git_icon = icons.icon("IDI_GITFOLDER")
                    base = git_icon
                else:
                    base = base_provider.icon(QFileInfo(full))
            else:
                status = file_state.get(nc, "normal")
                base = base_provider.icon(QFileInfo(full))
            ic = overlays.compose(base, status)
            if ic is not None:
                out[nc] = ic
        return out

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

    def _build_dir_menu(self, path: str, parent=None) -> "QMenu":
        """目录右键菜单：基本操作 + TortoiseGit 两级。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(parent or self.content_list)
        self._add_basic_ops(menu, path)
        tg = self._add_tortoisegit_submenu(menu, path)
        if not self._inside_repo(path):
            act_clone = tg.addAction(tr("repo_menu_clone", "Git Clone…"))
            self._set_action_icon(act_clone, "IDI_CLONE")
            act_clone.triggered.connect(
                lambda _=False, p=path: self._run_clone_in(p))
            act_set = tg.addAction(tr("repo_menu_settings", "Settings"))
            self._set_action_icon(act_set, "IDI_SETTINGS")
            act_set.triggered.connect(
                lambda _=False, p=path:
                self._dispatch("settings", extra={"path": p}))
        return menu

    def _build_blank_menu(self, path: str, parent=None) -> "QMenu":
        """内容区空白处右键菜单：基本操作 + TortoiseGit 两级。"""
        if not self._inside_repo(path):
            return self._build_dir_menu(path, parent)
        from PySide6.QtWidgets import QMenu
        menu = QMenu(parent or self.content_list)
        self._add_basic_ops(menu, path)
        self._add_tortoisegit_submenu(menu, path)
        return menu

    @staticmethod
    def _shift_pressed() -> bool:
        """右键时是否按住 Shift（对应原版 CMF_EXTENDEDVERBS / ITEMIS_EXTENDED）。"""
        from PySide6.QtWidgets import QApplication
        return bool(QApplication.keyboardModifiers()
                    & Qt.KeyboardModifier.ShiftModifier)

    def _build_tortoisegit_menu(self, path: str, parent=None,
                                shift: bool | None = None) -> "QMenu":
        """按原版 TortoiseGit 状态驱动引擎构建右键菜单。

        path 是当前被右击的路径（文件/目录/仓库根）。从 menuitems 计算其
        itemStates，再结合 Shift 依次插入匹配的菜单项（含分隔线）。
        """
        from PySide6.QtWidgets import QMenu
        menu = QMenu(parent or self.repo_tree)
        self._populate_tortoisegit_menu(menu, path, shift)
        return menu

    def _populate_tortoisegit_menu(self, menu, path: str,
                                   shift: bool | None = None):
        """把状态驱动的 TortoiseGit 菜单项填入给定菜单。"""
        from .. import menuitems as mi
        if shift is None:
            shift = self._shift_pressed()
        states = mi.compute_item_states(path, extended=shift)
        for entry in mi.menu_entries(states, extended=shift):
            if entry.command == "separator":
                menu.addSeparator()
                continue
            act = menu.addAction(tr(entry.label_key, entry.label))
            icon_id = entry.icon_id or _CMD_ICON.get(entry.command)
            if icon_id:
                self._set_action_icon(act, icon_id)
            act.triggered.connect(
                lambda _=False, c=entry.command, p=path:
                self._dispatch(c, extra={"path": p}))

    @staticmethod
    def _add_submenu(menu, title: str):
        """添加子菜单（用 QMenu(title, parent)，addMenu(str) 会被 GC 删除）。"""
        from PySide6.QtWidgets import QMenu
        sub = QMenu(title, menu)
        menu.addMenu(sub)
        return sub

    def _add_basic_ops(self, menu, path: str):
        """在菜单顶层添加基本文件操作（不折叠）。

        打开 / 显示位置 / 复制 / 剪切 / 粘贴 / 删除 / 新建文件 / 新建文件夹。
        """
        is_dir = os.path.isdir(path)
        target_dir = path if is_dir else (os.path.dirname(path) or path)
        act_open = menu.addAction(tr("file_menu_open", "Open"))
        self._set_action_icon(act_open, "IDI_OPEN")
        act_open.triggered.connect(
            lambda _=False, p=path: self._open_with_system(p))
        act_show = menu.addAction(tr("file_menu_show_in", "Show in Explorer"))
        act_show.triggered.connect(
            lambda _=False, p=path: self._show_in_explorer(p))
        menu.addSeparator()
        act_copy = menu.addAction(tr("menu_copy", "Copy"))
        act_copy.triggered.connect(
            lambda _=False, p=path: self._copy_files([p]))
        act_cut = menu.addAction(tr("menu_cut", "Cut"))
        act_cut.triggered.connect(
            lambda _=False, p=path: self._cut_files([p]))
        act_paste = menu.addAction(tr("menu_paste", "Paste"))
        act_paste.triggered.connect(
            lambda _=False, d=target_dir: self._paste_files(d))
        menu.addSeparator()
        act_del = menu.addAction(tr("menu_delete", "Delete"))
        act_del.triggered.connect(
            lambda _=False, p=path: self._delete_path(p))
        menu.addSeparator()
        act_newf = menu.addAction(tr("menu_new_file", "New File"))
        act_newf.triggered.connect(
            lambda _=False, d=target_dir: self._new_file(d))
        act_newd = menu.addAction(tr("menu_new_folder", "New Folder"))
        act_newd.triggered.connect(
            lambda _=False, d=target_dir: self._new_folder(d))
        menu.addSeparator()

    def _copy_files(self, paths):
        from PySide6.QtCore import QMimeData, QUrl
        from PySide6.QtWidgets import QApplication
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(os.path.abspath(p)) for p in paths])
        QApplication.clipboard().setMimeData(mime)
        self._cut_paths = []

    def _cut_files(self, paths):
        self._copy_files(paths)
        self._cut_paths = [os.path.abspath(p) for p in paths]

    def _paste_files(self, target_dir: str):
        import shutil
        from PySide6.QtWidgets import QApplication
        mime = QApplication.clipboard().mimeData()
        if mime is None or not mime.hasUrls():
            return
        cut = set(getattr(self, "_cut_paths", []) or [])
        for url in mime.urls():
            src = url.toLocalFile()
            if not src or not os.path.exists(src):
                continue
            name = os.path.basename(src.rstrip("/\\"))
            dst = os.path.join(target_dir, name)
            if os.path.exists(dst):
                continue
            try:
                if os.path.abspath(src) in cut:
                    shutil.move(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            except OSError:
                continue
        self._cut_paths = []
        self._refresh_content()

    def _delete_path(self, path: str):
        import shutil
        from PySide6.QtWidgets import QMessageBox
        resp = QMessageBox.question(
            self, tr("confirm", "Confirm"),
            tr("menu_delete_q", 'Delete "{name}"?').format(
                name=os.path.basename(path.rstrip("/\\"))),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError:
            pass
        self._refresh_content()

    def _new_file(self, directory: str):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, tr("menu_new_file", "New File"),
            tr("menu_new_file_prompt", "File name:"))
        if not ok or not name.strip():
            return
        try:
            open(os.path.join(directory, name.strip()), "x").close()
        except OSError:
            pass
        self._refresh_content()

    def _new_folder(self, directory: str):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, tr("menu_new_folder", "New Folder"),
            tr("menu_new_folder_prompt", "Folder name:"))
        if not ok or not name.strip():
            return
        try:
            os.makedirs(os.path.join(directory, name.strip()), exist_ok=False)
        except OSError:
            pass
        self._refresh_content()

    def _add_tortoisegit_submenu(self, menu, path: str):
        """「TortoiseGit」子菜单（状态驱动）。"""
        tg = self._add_submenu(menu, tr("menu_tortoisegit", "TortoiseGit"))
        if self._inside_repo(path):
            self._populate_tortoisegit_menu(tg, path)
        return tg

    def _copy_path(self, path: str):
        from ..utils.clipboard import ClipboardHelper
        ClipboardHelper().copy_text(os.path.abspath(path))

    def _build_context_menu_for(self, index) -> "QMenu | None":
        path = self._path_of_index(index)
        if not path or not os.path.exists(path):
            return None
        if not self._is_dir_index(index):
            return self._build_file_menu(path, self.content_list)
        return self._build_dir_menu(path, self.content_list)

    def _on_content_context_menu(self, pos):
        index = self.content_list.indexAt(pos)
        if index.isValid() and self.content_list.visualRect(index).contains(pos):
            self._show_context_menu_for(index, pos)
            return
        # 空白处：对当前浏览目录弹右键菜单（TortoiseGit 行为）
        cur = self._current_dir()
        if cur and os.path.exists(cur):
            menu = self._build_blank_menu(cur, self.content_list)
            menu.exec(self.content_list.viewport().mapToGlobal(pos))

    def _show_context_menu_for(self, index, pos=None):
        menu = self._build_context_menu_for(index)
        if menu is None:
            return
        if pos is None:
            rect = self.content_list.visualRect(index)
            pos = rect.center()
        menu.exec(self.content_list.viewport().mapToGlobal(pos))

    def _build_file_menu(self, path: str, parent=None) -> "QMenu":
        """文件右键菜单：基本操作 + TortoiseGit 两级。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(parent or self.content_list)
        self._add_basic_ops(menu, path)
        self._add_tortoisegit_submenu(menu, path)
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
        """经典 TortoiseGit 右键菜单（作用于给定仓库路径，由状态引擎驱动）。"""
        return self._build_tortoisegit_menu(path, parent)

    def _on_repo_context_menu(self, pos):
        item = self.repo_tree.itemAt(pos)
        if item is None:
            return
        if item.data(0, ROLE_KIND) == "repo":
            # 仓库节点：经典 TortoiseGit 菜单 + 移除
            path = item.data(0, ROLE_PATH)
            menu = self._build_classic_menu(path, self.repo_tree)
            menu.addSeparator()
            act_rem = menu.addAction(tr("repo_menu_remove", "Remove from list"))
            act_rem.triggered.connect(
                lambda _=False, it=item: self._remove_repo_from_list(it))
        else:
            # 子模块节点：打开子模块
            from PySide6.QtWidgets import QMenu
            menu = QMenu(self.repo_tree)
            sub_path = item.data(0, ROLE_PATH)
            act = menu.addAction(tr("repo_menu_open_sub", "Open submodule"))
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
        """目录树仓库节点右键菜单：添加到仓库管理 + 基本操作 + TortoiseGit。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self.folder_tree)
        act_add = menu.addAction(tr("menu_add_to_repo_list", "Add to repository manager"))
        act_add.triggered.connect(
            lambda _=False, p=path: self._ensure_in_repo_list(p))
        menu.addSeparator()
        self._add_basic_ops(menu, path)
        self._add_tortoisegit_submenu(menu, path)
        if item is not None:
            menu.addSeparator()
            act_refresh = menu.addAction(tr("refresh"))
            self._set_action_icon(act_refresh, "IDI_REFRESH")
            act_refresh.triggered.connect(
                lambda _=False, it=item: self._refresh_folder_item(it))
        return menu

    def _build_folder_nonrepo_menu(self, path: str, item=None) -> "QMenu":
        """目录树非仓库目录/分区右键菜单：基本操作 + TortoiseGit(Clone/Settings)。"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self.folder_tree)
        self._add_basic_ops(menu, path)
        tg = self._add_submenu(menu, tr("menu_tortoisegit", "TortoiseGit"))
        act_clone = tg.addAction(tr("repo_menu_clone", "Git Clone…"))
        self._set_action_icon(act_clone, "IDI_CLONE")
        act_clone.triggered.connect(
            lambda _=False, p=path: self._run_clone_in(p))
        act_set = tg.addAction(tr("repo_menu_settings", "Settings"))
        self._set_action_icon(act_set, "IDI_SETTINGS")
        act_set.triggered.connect(
            lambda _=False, p=path: self._dispatch("settings", extra={"path": p}))
        menu.addSeparator()
        act_refresh = menu.addAction(tr("refresh"))
        self._set_action_icon(act_refresh, "IDI_REFRESH")
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
        self.status.setText(format_string(tr("menu_running", "Running: {name}"), name="clone"))
        QTimer.singleShot(0, lambda: self._run(ctx, "clone"))

    # ---- 仓库 ----
    def open_repo(self, path: str):
        try:
            self.repo = Repository.open(path)
        except Exception as exc:
            self.status.setText(
                format_string(tr("menu_not_repo", "Not a Git repository: {msg}"), msg=exc))
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
            self, tr("menu_open_repo", "Open Repository…"), self.path_row.text())
        if d:
            self.open_repo(d)

    # ---- 命令执行 ----
    def _dispatch(self, name: str, extra=None):
        extra_path = bool(extra and extra.get("path"))
        if not (self.repo or self.path_row.text().strip() or extra_path):
            self.status.setText(tr("menu_select_first", "Please select a repository path first."))
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
            format_string(tr("menu_running", "Running: {name}"), name=name))
        QTimer.singleShot(0, lambda: self._run(ctx, name))

    def _run_async_command(self, name: str, extra=None):
        self._dispatch(name, extra=extra)

    def _run(self, ctx, name: str):
        from ..commands.dispatcher import dispatch, UnknownCommandError
        try:
            dispatch(name, ctx)
            self.status.setText(
                format_string(tr("menu_done", "Done: {name}"), name=name))
        except UnknownCommandError:
            self.status.setText(
                format_string(tr("unknown_command"), command=name))
        except Exception as exc:  # noqa: BLE001
            self.status.setText(
                format_string(tr("command_failed"), name=name, message=exc))
            from ..utils.logging_utils import get_logger
            get_logger().exception("menu command failed: %s", name)

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
    """QFileSystemModel 图标提供者：仓库根用 git 图标，版本控制文件叠加状态覆盖。

    注意：QFileSystemModel 会在后台线程调用 icon()，而 QPixmap 只能在 GUI
    线程创建（在 Linux/X11 下跨线程创建会段错误）。因此所有合成图标都在
    GUI 线程预先构建并存入 self._icons，icon() 只做查表返回。
    """

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self._git_icon = None
        self._icons: dict = {}
        try:
            from ..res import icons
            self._git_icon = icons.icon("IDI_GITFOLDER")
        except Exception:  # noqa: BLE001
            pass

    def set_icons(self, mapping: dict) -> None:
        """在 GUI 线程设置 规范化路径 -> 合成图标。"""
        self._icons = mapping

    def icon(self, info):  # noqa: A003 - 覆写基类成员名
        key = os.path.normcase(info.absoluteFilePath())
        ic = self._icons.get(key)
        if ic is not None:
            return ic
        if info.isDir() and self._git_icon is not None and not self._git_icon.isNull():
            p = info.absoluteFilePath()
            # 仅仓库工作树根目录显示 git 图标；其余目录（含未受版本管理的
            # 子目录）一律使用普通文件夹图标。
            if p and find_repo_root(p) == os.path.abspath(p):
                return self._git_icon
        return super().icon(info)
