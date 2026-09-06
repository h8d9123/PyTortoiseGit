"""rebasedlg.py —— RebaseDlg：变基对话框（含冲突解决视图）。

镜像 TortoiseGit 的 RebaseDlg：目标分支选择、交互式/自动暂存、
开始/继续/中止变基，冲突用 ConflictsWidget 解决。
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

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from ..git.mergeop import (
    MergeInProgressError,
    abort_rebase,
    do_rebase,
    local_branches,
)
from ..git.repo import Repository
from ..res.strings import tr
from .conflicts import ConflictsWidget
from .progress import ProgressDialog


class RebaseDlg(QDialog):
    def __init__(self, repo: Repository, branch: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(f"{repo.name} — {tr('rebase_title')}")
        self.resize(560, 480)
        self._build_ui()
        self._load_branches(branch)

    def _build_ui(self):
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.branch_combo = QComboBox(self)
        self.branch_combo.setEditable(True)
        form.addRow(tr("rebase_target"), self.branch_combo)
        lay.addLayout(form)

        self.interactive_box = QCheckBox(tr("rebase_interactive"), self)
        lay.addWidget(self.interactive_box)
        self.autostash_box = QCheckBox(tr("rebase_autostash"), self)
        lay.addWidget(self.autostash_box)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        self._conflict_box = QGroupBox(tr("conflicts_title"), self)
        inner = QVBoxLayout(self._conflict_box)
        self.conflicts = ConflictsWidget(self.repo, self._conflict_box)
        self.conflicts.resolved.connect(self._after_continue)
        inner.addWidget(self.conflicts)
        lay.addWidget(self._conflict_box)
        self._conflict_box.setVisible(False)

        btns = QDialogButtonBox(self)
        self.btn_start = btns.addButton(tr("rebase_start"), QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_continue = btns.addButton(tr("rebase_continue"), QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_continue.clicked.connect(self._on_continue)
        self.btn_continue.setEnabled(False)
        self.btn_abort = btns.addButton(tr("rebase_abort"), QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_abort.clicked.connect(self._on_abort)
        self.btn_abort.setEnabled(False)
        btn_close = btns.addButton(QDialogButtonBox.StandardButton.Close)
        btn_close.setText(tr("close"))
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load_branches(self, preset: str | None):
        self.branch_combo.clear()
        self.branch_combo.addItems(local_branches(self.repo))
        if preset:
            idx = self.branch_combo.findText(preset)
            self.branch_combo.setCurrentIndex(max(0, idx))

    # ---- 动作 ----
    def _on_start(self):
        branch = self.branch_combo.currentText().strip()
        if not branch:
            return
        self.btn_start.setEnabled(False)
        self.btn_continue.setEnabled(False)
        self.btn_abort.setEnabled(False)
        dlg = ProgressDialog(title=f"git rebase {branch}", parent=self)
        dlg.set_label(f"git rebase {branch}")

        def _bg() -> bool:
            try:
                result = do_rebase(
                    self.repo, branch,
                    interactive=self.interactive_box.isChecked(),
                    autostash=self.autostash_box.isChecked(),
                )
            except MergeInProgressError as exc:
                dlg.log(str(exc))
                return False
            if result.stdout:
                dlg.log(result.stdout)
            if result.stderr:
                dlg.log(result.stderr)
            return result.ok

        dlg.run(_bg)
        dlg.on_finish(self._after_action)
        dlg.finished.connect(lambda _f: self.btn_start.setEnabled(True))
        dlg.exec()

    def _on_continue(self):
        self.btn_continue.setEnabled(False)
        dlg = ProgressDialog(title="git rebase --continue", parent=self)
        dlg.set_label("git rebase --continue")

        def _bg() -> bool:
            result = self.repo.runner.run("rebase", "--continue")
            if result.stdout:
                dlg.log(result.stdout)
            if result.stderr:
                dlg.log(result.stderr)
            return result.ok

        dlg.run(_bg)
        dlg.on_finish(self._after_action)
        dlg.exec()

    def _on_abort(self):
        if abort_rebase(self.repo):
            self._status.setText(tr("rebase_abort"))
        self._after_action(True)

    def _after_action(self, ok: bool):
        self.conflicts.refresh()
        if self.conflicts.count > 0:
            self._conflict_box.setVisible(True)
            self.btn_continue.setEnabled(True)
            self.btn_abort.setEnabled(True)
        else:
            self._conflict_box.setVisible(False)
            self.btn_continue.setEnabled(False)
            self.btn_abort.setEnabled(False)

    def _after_continue(self):
        if self.conflicts.count == 0:
            self.btn_continue.setEnabled(True)
            self._status.setText(tr("rebase_continue"))