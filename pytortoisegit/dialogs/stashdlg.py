"""stashdlg.py —— StashDlg：stash 保存对话框（镜像 TortoiseGit 的 StashSave 对话框）。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ..git.repo import Repository
from ..res.strings import tr


class StashDlg(QDialog):
    """镜像原版 TortoiseGit 的 Stash Changes 对话框（IDD_STASH）。

    布局：
      - "Stash Message" 分组框 + 单行输入
      - "Options" 分组框：include untracked / --all（互斥）
      - OK / Cancel 按钮
    """

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(f"{repo.name} — {tr('stash_title')}")
        self.setMinimumWidth(350)
        self._build_ui()

    # ---- UI ----
    def _build_ui(self):
        root = QVBoxLayout(self)

        grp_msg = QGroupBox(tr("stash_message_group", "Stash &Message"), self)
        msg_layout = QHBoxLayout(grp_msg)
        self.msg_edit = QLineEdit(grp_msg)
        msg_layout.addWidget(self.msg_edit)
        root.addWidget(grp_msg)

        grp_opt = QGroupBox(tr("stash_options_group", "Options"), self)
        opt_layout = QVBoxLayout(grp_opt)
        self.untracked_box = QCheckBox(
            tr("stash_include_untracked", "include &untracked"), grp_opt)
        self.untracked_box.toggled.connect(self._on_untracked_toggled)
        opt_layout.addWidget(self.untracked_box)
        self.all_box = QCheckBox(
            tr("stash_all", "--&all"), grp_opt)
        self.all_box.toggled.connect(self._on_all_toggled)
        opt_layout.addWidget(self.all_box)
        root.addWidget(grp_opt)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = self._make_button(tr("ok"), self._on_ok, primary=True)
        btn_layout.addWidget(self._ok_btn)
        cancel_btn = self._make_button(tr("cancel"), self.reject)
        btn_layout.addWidget(cancel_btn)
        root.addLayout(btn_layout)

    @staticmethod
    def _make_button(text, handler, primary=False):
        from PySide6.QtWidgets import QPushButton
        btn = QPushButton(text)
        if primary:
            btn.setDefault(True)
        btn.clicked.connect(handler)
        return btn

    # ---- 互斥逻辑 ----
    def _on_untracked_toggled(self, checked):
        if checked:
            self.all_box.setChecked(False)
            self.all_box.setEnabled(False)
        else:
            self.all_box.setEnabled(True)

    def _on_all_toggled(self, checked):
        if checked:
            self.untracked_box.setChecked(False)
            self.untracked_box.setEnabled(False)
        else:
            self.untracked_box.setEnabled(True)

    # ---- 确认 ----
    def _on_ok(self):
        if self.untracked_box.isChecked():
            resp = QMessageBox.warning(
                self,
                tr("warning"),
                tr("stash_untracked_warning",
                   "Including untracked files will also add untracked files to the stash. "
                   "Are you sure you want to continue?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        self.accept()

    # ---- 返回值 ----
    @property
    def message(self) -> str:
        return self.msg_edit.text().strip()

    @property
    def include_untracked(self) -> bool:
        return self.untracked_box.isChecked()

    @property
    def use_all(self) -> bool:
        return self.all_box.isChecked()

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
