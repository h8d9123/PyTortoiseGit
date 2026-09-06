"""mainmenu.py —— 主窗口：菜单栏 + Git 操作工具栏 + 左侧子模块管理树。

GUI 入口（`python -m pytortoisegit` 无参数时打开此窗口），
或 `/command:menu` 显式打开。

布局（从顶部到底部）：
  1. 菜单栏（文件 / 视图 / 帮助）
  2. 工具栏：QToolButton 一排 Git 操作按钮（图标用 TortoiseGit icon）
  3. 主区：左侧子模块管理树(QTreeWidget) + 右侧命令列表 / 欢迎页
  4. 底部：仓库路径 + 按钮 + 状态栏
"""

from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..cmdline import CommandLine
from ..git.repo import Repository
from ..res.strings import format_string, tr
from .widgets import RepoPickerRow


class MainMenuDlg(QMainWindow):
    """主窗口：菜单栏 + 工具栏 + 子模块树 + 命令面板。"""

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
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._populate_commands()
        self._build_statusbar()
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
        act_sub = QAction(tr("menu_submodule", "子模块面板"), self)
        act_sub.setCheckable(True)
        act_sub.setChecked(True)
        act_sub.toggled.connect(lambda on: self.sub_module_dock.setVisible(on))
        m_view.addAction(act_sub)
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

    # ---- 主区：左侧子模块树 + 右侧命令列表 ----
    def _build_central(self):
        split = QSplitter(Qt.Orientation.Horizontal, self)
        self.sub_module_dock = QWidget(self)
        sub_lay = QVBoxLayout(self.sub_module_dock)
        sub_lay.setContentsMargins(4, 4, 4, 4)
        sub_lay.addWidget(QLabel(tr("menu_submodule", "子模块"), self.sub_module_dock))
        self.sub_tree = QTreeWidget(self.sub_module_dock)
        self.sub_tree.setColumnCount(3)
        self.sub_tree.setHeaderLabels([
            tr("submodule_path", "路径"), tr("submodule_status", "状态"),
            tr("submodule_sha", "SHA")])
        self.sub_tree.setRootIsDecorated(False)
        self.sub_tree.setIndentation(0)
        self.sub_tree.itemDoubleClicked.connect(self._on_submodule_open)
        self.sub_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        sub_lay.addWidget(self.sub_tree)
        sub_lay.addWidget(QLabel(
            tr("menu_submodule_hint", "双击子模块打开其窗口"), self.sub_module_dock))
        split.addWidget(self.sub_module_dock)

        right = QWidget(self)
        right_lay = QVBoxLayout(right)
        self.path_row = RepoPickerRow(tr("menu_path_label", "仓库路径:"), right)
        self.path_row.setText(os.getcwd())
        self.path_row.connect_editingFinished(self._on_path_changed)
        right_lay.addWidget(self.path_row)
        self._welcome = QLabel(tr("menu_welcome",
                                  "双击命令或选择后点击执行；左侧为子模块管理树。"),
                              right)
        self._welcome.setWordWrap(True)
        right_lay.addWidget(self._welcome)
        self.command_list = QListWidget(right)
        right_lay.addWidget(self.command_list, 1)
        self.command_list.itemDoubleClicked.connect(lambda *_: self._execute_selected())
        last = QHBoxLayout()
        self.btn_exec = QPushButton(tr("menu_exec", "执&行"), right)
        self.btn_exec.clicked.connect(self._execute_selected)
        self.btn_about = QPushButton(tr("about_title", "关于"), right)
        self.btn_about.clicked.connect(self._on_about)
        self.btn_close = QPushButton(tr("close", "关&闭"), right)
        self.btn_close.clicked.connect(self.close)
        last.addStretch(1)
        last.addWidget(self.btn_about)
        last.addWidget(self.btn_exec)
        last.addWidget(self.btn_close)
        right_lay.addLayout(last)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        split.setSizes([350, 570])
        self.setCentralWidget(split)

    def _build_statusbar(self):
        self.status = QLabel("")
        self.statusBar().addWidget(self.status)

    # ---- 数据 ----
    def _populate_commands(self):
        from ..commands.dispatcher import available_commands, _ensure_imports
        _ensure_imports()
        self.commands = available_commands()
        self.command_list.clear()
        for name in self.commands:
            item = QListWidgetItem(self._display_of(name))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.command_list.addItem(item)

    @staticmethod
    def _display_of(name: str) -> str:
        return name

    def _selected_command(self) -> str | None:
        item = self.command_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ---- 仓库与子模块 ----
    def open_repo(self, path: str):
        try:
            self.repo = Repository.open(path)
        except Exception as exc:
            self.status.setText(format_string(tr("menu_not_repo", "不是 Git 仓库：{msg}"), msg=exc))
            self.sub_tree.clear()
            return
        self.path_row.setText(path)
        self._load_submodules()
        self.status.setText(f" {path} · {self.repo.current_branch()}")

    def _load_submodules(self):
        self.sub_tree.clear()
        if self.repo is None:
            return
        try:
            from ..git.submodule import GitSubmodule
            for e in GitSubmodule(self.repo).list(recursive=False):
                it = QTreeWidgetItem([e.path, e.status_text, (e.sha1 or "")[:8]])
                it.setData(0, Qt.ItemDataRole.UserRole, e.path)
                self.sub_tree.addTopLevelItem(it)
        except Exception:
            pass

    def _on_submodule_open(self, item, _col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self._run_async_command("submodule", extra={"path": path})

    def _on_path_changed(self):
        p = self.path_row.text().strip()
        if p:
            self.open_repo(p)

    def _open_repo_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, tr("menu_open_repo", "打开仓库"), self.path_row.text())
        if d:
            self.open_repo(d)

    # ---- 命令执行 ----
    def _dispatch(self, name: str, extra=None):
        if not (self.repo or self.path_row.text().strip()):
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
        self.status.setText(format_string(tr("menu_running", "正在执行：{name}"), name=name))
        QTimer.singleShot(0, lambda: self._run(ctx, name))

    def _execute_selected(self):
        name = self._selected_command()
        if name is None:
            self.status.setText(tr("menu_select_first", "请先选择一个命令。"))
            return
        self._dispatch(name)

    def _run_async_command(self, name: str, extra=None):
        self._dispatch(name, extra=extra)

    def _run(self, ctx, name: str):
        from ..commands.dispatcher import dispatch, UnknownCommandError
        try:
            dispatch(name, ctx)
            self.status.setText(format_string(tr("menu_done", "完成：{name}"), name=name))
        except UnknownCommandError:
            self.status.setText(format_string(tr("unknown_command"), command=name))
        except Exception as exc:  # noqa: BLE001
            self.status.setText(format_string(tr("command_failed"), name=name, message=exc))
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