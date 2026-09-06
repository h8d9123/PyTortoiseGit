"""mainmenu.py —— 主菜单窗口：列出所有支持的命令，选择仓库路径后执行。

GUI 入口（`python -m pytortoisegit` 无参数时打开此窗口），
或 `/command:menu` 显式打开。
"""

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
from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..cmdline import CommandLine
from ..res.strings import format_string, tr
from .widgets import RepoPickerRow


class MainMenuDlg(QDialog):
    """主菜单：命令列表 + 仓库路径 + 执行。"""

    def __init__(self, repo_path: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("menu_title", "PyTortoiseGit 主菜单"))
        self.resize(560, 480)
        try:
            from ..res import icons
            self.setWindowIcon(icons.app_icon())
        except Exception:
            pass
        self.commands: List[str] = []
        self._build_ui()
        self._populate_commands()
        if repo_path:
            self.path_row.setText(repo_path)

    def _build_ui(self):
        from ..commands.dispatcher import available_commands

        root = QVBoxLayout(self)

        # 顶部：选择/输入仓库路径
        self.path_row = RepoPickerRow(tr("menu_path_label", "仓库路径:"), self)
        self.path_row.setText(os.getcwd())
        root.addWidget(self.path_row)

        # 标题
        hint = QLabel(tr("menu_hint",
                         "双击命令或在下方选择后点击执行。未指定仓库时"
                         "部分命令会自动检测当前目录。"))
        hint.setWordWrap(True)
        root.addWidget(hint)

        # 命令列表
        self.command_list = QListWidget(self)
        # 排序展示由 available_commands 提供
        root.addWidget(self.command_list, 1)

        # 底部按钮
        btns = QHBoxLayout()
        self.btn_exec = QPushButton(tr("menu_exec", "执&行"), self)
        self.btn_exec.setDefault(True)
        self.btn_exec.clicked.connect(self._execute_selected)
        self.btn_about = QPushButton(tr("about_title", "关于"), self)
        self.btn_about.clicked.connect(self._on_about)
        self.btn_close = QPushButton(tr("close", "关&闭"), self)
        self.btn_close.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(self.btn_about)
        btns.addWidget(self.btn_exec)
        btns.addWidget(self.btn_close)
        root.addLayout(btns)

        # 状态栏
        self.status = QLabel("", self)
        root.addWidget(self.status)

        self.command_list.itemDoubleClicked.connect(
            lambda *_: self._execute_selected())

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
        """把命令名转成显示文本（保留原名小写，便于对齐 TGit）。"""
        return name

    def _selected_command(self) -> str | None:
        item = self.command_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _execute_selected(self):
        name = self._selected_command()
        if name is None:
            self.status.setText(tr("menu_select_first", "请先选择一个命令。"))
            return
        path = self.path_row.text()

        from ..commands.dispatcher import (CommandContext, dispatch,
                                           UnknownCommandError)
        from PySide6.QtCore import QTimer

        cl = CommandLine(verb=name)
        if path:
            cl.options["path"] = [path]
        ctx = CommandContext(qapp=None, cl=cl)
        self.status.setText(format_string(tr("menu_running", "正在执行：{name}"),
                                          name=name))
        try:
            # 延迟执行，让状态文本先刷新
            QTimer.singleShot(0, lambda: self._run(ctx, name))
        except UnknownCommandError:
            self.status.setText(format_string(tr("unknown_command"),
                                              command=name))

    def _run(self, ctx, name: str):
        from ..commands.dispatcher import dispatch, UnknownCommandError
        try:
            dispatch(name, ctx)
            self.status.setText(format_string(tr("menu_done", "完成：{name}"),
                                              name=name))
        except UnknownCommandError:
            self.status.setText(format_string(tr("unknown_command"),
                                              command=name))
        except Exception as exc:  # noqa: BLE001
            self.status.setText(format_string(tr("command_failed"),
                                              name=name, message=exc))
            from ..utils.logging_utils import get_logger
            get_logger().exception("menu 命令失败: %s", name)

    def _on_about(self):
        from ..dialogs.aboutdlg import AboutDlg
        dlg = AboutDlg(parent=self)
        dlg.exec()

    def exec_loop(self) -> int:
        return self.exec()