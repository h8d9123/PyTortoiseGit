"""shelldlg.py —— ShellDlg：右键菜单安装/卸载对话框。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..res.strings import tr
from ..shell_context import install, is_installed, status_text, uninstall


class ShellDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("shell_title", "右键菜单集成"))
        self.resize(560, 320)
        self._build_ui()
        self._refresh_state()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        from PySide6.QtCore import Qt
        self._status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._status)

        buttons = QDialogButtonBox(self)
        self._btn_install = buttons.addButton(
            tr("shell_install", "安装右键菜单"), QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_install.clicked.connect(self._do_install)
        self._btn_uninstall = buttons.addButton(
            tr("shell_uninstall", "卸载右键菜单"), QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_uninstall.clicked.connect(self._do_uninstall)
        closer = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        closer.setText(tr("close"))
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _refresh_state(self):
        self._status.setText(status_text())

    def _do_install(self):
        if not is_installed():
            n = install()
            self._refresh_state()
            QMessageBox.information(
                self, tr("information"),
                tr("shell_installed", f"已写入 {n} 个右键菜单项（重新打开资源管理器后生效）。"))
        else:
            QMessageBox.information(self, tr("information"),
                                    tr("shell_already", "右键菜单已安装。"))

    def _do_uninstall(self):
        if is_installed():
            n = uninstall()
            self._refresh_state()
            QMessageBox.information(
                self, tr("information"),
                tr("shell_uninstalled", f"已删除 {n} 个右键菜单项。"))
        else:
            QMessageBox.information(self, tr("information"),
                                    tr("shell_not_installed", "右键菜单未安装。"))

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
