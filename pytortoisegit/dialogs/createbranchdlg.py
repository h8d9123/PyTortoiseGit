"""createbranchdlg.py —— 创建分支/标签的小对话框。

镜像 TortoiseGit 的 CreateBranchTagDlg 的简化版。
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

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from ..git.repo import Repository
from ..res.strings import tr


class CreateBranchDlg(QDialog):
    def __init__(self, repo: Repository, start: str = "HEAD", parent=None):
        super().__init__(parent)
        self.repo = repo
        self.start = start
        self.setWindowTitle(tr("branch_new", "New branch"))
        self.name: str = ""
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("feature/xxx")
        form.addRow(tr("branch_name", "Branch name"), self.name_edit)

        self.switch_box = QCheckBox(tr("branch_switch", "Switch to this branch after creating"), self)
        self.switch_box.setChecked(True)
        form.addRow("", self.switch_box)

        self.track_box = QCheckBox(tr("branch_track", "Base on current branch"), self)
        self.track_box.setChecked(self.start == "HEAD")
        self.track_box.setEnabled(False)
        form.addRow("", self.track_box)

        lay.addLayout(form)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self)
        box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("ok"))
        box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setFocus()
            return
        self.name = name
        args = ["branch"]
        if self.switch_box.isChecked():
            args.append("-b")
        args += [name, self.start]
        result = self.repo.runner.run(*args)
        if result.returncode != 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("error"), result.stderr or result.stdout)
            return
        self.accept()


class CreateTagDlg(QDialog):
    def __init__(self, repo: Repository, start: str = "HEAD", parent=None):
        super().__init__(parent)
        self.repo = repo
        self.start = start
        self.setWindowTitle(tr("tag_new", "New tag"))
        self.name: str = ""
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("v1.0.0")
        form.addRow(tr("tag_name", "Tag name"), self.name_edit)
        self.msg_edit = QLineEdit(self)
        self.msg_edit.setPlaceholderText(tr("tag_msg_hint", "Only needed for annotated tags"))
        form.addRow(tr("tag_message", "Annotation"), self.msg_edit)
        self.annotated_box = QCheckBox(tr("tag_annotated", "Create annotated tag"), self)
        form.addRow("", self.annotated_box)
        lay.addLayout(form)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self)
        box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("ok"))
        box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setFocus()
            return
        self.name = name
        args = ["tag"]
        if self.annotated_box.isChecked():
            args.append("-a")
        if self.msg_edit.text().strip():
            args += ["-m", self.msg_edit.text().strip()]
        args += [name, self.start]
        result = self.repo.runner.run(*args)
        if result.returncode != 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("error"), result.stderr or result.stdout)
            return
        self.accept()