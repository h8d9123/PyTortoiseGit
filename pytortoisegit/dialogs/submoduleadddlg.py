"""submoduleadddlg.py —— SubmoduleAddDlg：添加子模块（IDD_SUBMODULE_ADD 模板）。

对齐 TortoiseGit 的 CSubmoduleAddDlg：
  * 分组标题 "Submodule of Project: <仓库根>"；
  * Repository（URL/路径）+ 浏览；Path + 浏览（默认取仓库名）；
  * Branch（勾选后显示分支名输入）、Force、Load Putty Key（+ 密钥文件）；
  * OK/Cancel/Help。

调用方（SubmoduleDlg）用 OK 后的 ``repository/path/branch/force/putty_key``
执行 ``git submodule add``。
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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from ..utils.pick import pick_dir, pick_file
from .resize import AnchorLayout


class SubmoduleAddDlg(QDialog):
    def __init__(self, repo: Repository, parent=None, initial_path: str = ""):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._initial_path = initial_path or ""
        # 结果（exec() == Accepted 后有效）
        self.repository = ""
        self.path = ""
        self.branch = ""
        self.force = False
        self.putty_key = ""
        self._build_ui()

    # ---- UI ----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_SUBMODULE_ADD")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_horizontal_resize(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Submodule Add")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.grp_project = QGroupBox(self)
        self.repo_label = QLabel(tr("submodule_repository", "Repository:"), self)
        self.repo_combo = QComboBox(self)
        self.repo_combo.setEditable(True)
        self.btn_repo = QPushButton("...", self)
        self.btn_repo.clicked.connect(self._pick_repo)

        self.path_label = QLabel(tr("submodule_path_label", "Path:"), self)
        self.path_combo = QComboBox(self)
        self.path_combo.setEditable(True)
        self.path_combo.setEditText(self._initial_path)
        self.btn_path = QPushButton("...", self)
        self.btn_path.clicked.connect(self._pick_path)

        self.chk_branch = QCheckBox(tr("submodule_branch", "Branch"), self)
        self.chk_branch.toggled.connect(self._on_branch_toggled)
        self.branch_edit = QLineEdit(self)
        self.branch_edit.setVisible(False)

        self.chk_force = QCheckBox(tr("submodule_force", "&Force"), self)

        self.chk_putty = QCheckBox(
            tr("submodule_putty", "Load Putty &Key"), self)
        self.putty_combo = QComboBox(self)
        self.putty_combo.setEditable(True)
        self.btn_putty = QPushButton("...", self)
        self.btn_putty.clicked.connect(self._pick_putty_key)
        try:
            from ..utils.sshkeys import is_ssh_putty
            putty_ok = is_ssh_putty()
        except Exception:  # noqa: BLE001
            putty_ok = False
        self.chk_putty.setEnabled(putty_ok)
        self.chk_putty.toggled.connect(self._on_putty_toggled)
        self._set_putty_enabled(False)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)

        mapping = {
            "IDC_GROUP_SUBMODULE": self.grp_project,
            "IDC_STATIC": self.repo_label,
            "IDC_COMBOBOXEX_REPOSITORY": self.repo_combo,
            "IDC_REP_BROWSE": self.btn_repo,
            "IDC_COMBOBOXEX_PATH": self.path_combo,
            "IDC_BUTTON_PATH_BROWSE": self.btn_path,
            "IDC_BRANCH_CHECK": self.chk_branch,
            "IDC_SUBMODULE_BRANCH": self.branch_edit,
            "IDC_FORCE": self.chk_force,
            "IDC_PUTTYKEY_AUTOLOAD": self.chk_putty,
            "IDC_PUTTYKEYFILE": self.putty_combo,
            "IDC_PUTTYKEYFILE_BROWSE": self.btn_putty,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        # 分组标题：原版 "Submodule of Project: " + 仓库路径
        self.grp_project.setTitle(
            tr("submodule_add_group", "Submodule of Project: ")
            + os.path.abspath(self.repo.root))
        # 模板里 "Path:" 静态被去重（与 "Repository:" 同 IDC_STATIC），手工补一个
        self.path_label.move(self.repo_label.x(),
                             self.path_combo.y()
                             + max(0, (self.path_combo.height()
                                       - self.path_label.height()) // 2))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 交互 ----
    def _set_putty_enabled(self, on: bool):
        self.putty_combo.setEnabled(on)
        self.btn_putty.setEnabled(on)

    def _on_branch_toggled(self, on: bool):
        self.branch_edit.setVisible(bool(on))
        if on:
            self.branch_edit.setFocus()

    def _on_putty_toggled(self, on: bool):
        self._set_putty_enabled(bool(on))

    def _pick_repo(self):
        d = pick_dir(self, tr("submodule_repository", "Repository"),
                     self.repo_combo.currentText().strip() or self.repo.root)
        if d:
            self.repo_combo.setEditText(d)

    def _pick_path(self):
        start = self.path_combo.currentText().strip() or self.repo.root
        d = pick_dir(self, tr("submodule_path", "Path"), start)
        if not d:
            return
        name = os.path.basename(
            self.repo_combo.currentText().strip().rstrip("/\\"))
        if name.endswith(".git"):
            name = name[:-4]
        if name and d == self.repo.root:
            d = os.path.join(d, name)
        self.path_combo.setEditText(d)

    def _pick_putty_key(self):
        f = pick_file(self, tr("submodule_putty", "Load Putty Key"),
                      "*.ppk")
        if f:
            self.putty_combo.setEditText(f)

    def _on_help(self):
        QMessageBox.information(self, tr("help", "Help"),
                                tr("submodule_add_help", "Add a submodule"))

    def _on_ok(self):
        repository = self.repo_combo.currentText().strip()
        path = self.path_combo.currentText().strip()
        branch = self.branch_edit.text().strip()
        if not repository:
            QMessageBox.warning(self, tr("error", "Error"),
                                tr("submodule_repository_empty",
                                   "Repository must not be empty."))
            return
        if not path:
            QMessageBox.warning(self, tr("error", "Error"),
                                tr("submodule_path_empty",
                                   "Path must not be empty."))
            return
        if self.chk_branch.isChecked() and not branch:
            QMessageBox.warning(self, tr("error", "Error"),
                                tr("submodule_branch_empty",
                                   "Branch must not be empty."))
            return
        self.repository = repository
        self.path = path
        self.branch = branch if self.chk_branch.isChecked() else ""
        self.force = self.chk_force.isChecked()
        self.putty_key = (self.putty_combo.currentText().strip()
                          if self.chk_putty.isChecked() else "")
        self.accept()


_ANCHORS = {
    "IDC_COMBOBOXEX_REPOSITORY": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REP_BROWSE": ("TOP_RIGHT",),
    "IDC_COMBOBOXEX_PATH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_PATH_BROWSE": ("TOP_RIGHT",),
    "IDC_SUBMODULE_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_PUTTYKEYFILE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_PUTTYKEYFILE_BROWSE": ("TOP_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}
