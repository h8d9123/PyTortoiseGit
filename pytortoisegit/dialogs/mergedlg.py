"""mergedlg.py —— MergeDlg：合并对话框（含冲突解决视图）。

镜像 TortoiseGit 的 MergeDlg：选择分支、合并选项、执行合并；
产生冲突时切换到 ConflictsWidget 解决。
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
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from ..git.mergeop import (
    MergeInProgressError,
    abort_merge,
    do_merge,
    local_branches,
)
from ..git.repo import Repository
from ..res.strings import tr
from .conflicts import ConflictsWidget
from .progress import ProgressDialog


class MergeDlg(QDialog):
    def __init__(self, repo: Repository, branch: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(f"{repo.name} — {tr('merge_title')}")
        self.resize(560, 500)
        self._build_ui()
        self._load_branches(branch)
    def _build_ui(self):
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.branch_combo = QComboBox(self)
        self.branch_combo.setEditable(True)
        self.branch_combo.currentTextChanged.connect(self._prefill_message)
        form.addRow(tr("merge_branch"), self.branch_combo)
        self.message_edit = QPlainTextEdit(self)
        self.message_edit.setPlaceholderText(tr("merge_message"))
        self.message_edit.setFixedHeight(72)
        form.addRow(tr("merge_message"), self.message_edit)
        lay.addLayout(form)

        self.noff_box = QCheckBox(tr("merge_noff"), self)
        lay.addWidget(self.noff_box)
        self.squash_box = QCheckBox(tr("merge_squash"), self)
        lay.addWidget(self.squash_box)
        self.nocommit_box = QCheckBox(tr("merge_nocommit"), self)
        lay.addWidget(self.nocommit_box)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        self._conflict_box = QGroupBox(tr("conflicts_title"), self)
        inner = QVBoxLayout(self._conflict_box)
        self.conflicts = ConflictsWidget(self.repo, self._conflict_box)
        self.conflicts.resolved.connect(self._on_conflicts_resolved)
        inner.addWidget(self.conflicts)
        lay.addWidget(self._conflict_box)
        self._conflict_box.setVisible(False)

        btns = QDialogButtonBox(self)
        self.btn_start = btns.addButton(tr("merge_perform"), QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_abort = btns.addButton(tr("merge_abort"), QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_abort.clicked.connect(self._on_abort)
        self.btn_abort.setEnabled(False)
        btn_close = btns.addButton(QDialogButtonBox.StandardButton.Close)
        btn_close.setText(tr("close"))
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load_branches(self, preset: str | None):
        branches = local_branches(self.repo)
        self.branch_combo.clear()
        self.branch_combo.addItems(branches)
        if preset:
            idx = self.branch_combo.findText(preset)
            self.branch_combo.setCurrentIndex(max(0, idx))
        self._prefill_message()

    def _prefill_message(self):
        """分支选择变化时预填默认合并消息（TGit：Merge branch 'X' into 'Y'）。"""
        branch = self.branch_combo.currentText().strip()
        if not branch or self.message_edit.toPlainText().strip():
            return
        cur = self.repo.current_branch()
        self.message_edit.setPlainText(f"Merge branch '{branch}' into '{cur}'")

    # ---- 动作 ----
    def _on_start(self):
        branch = self.branch_combo.currentText().strip()
        if not branch:
            return
        self.btn_start.setEnabled(False)
        dlg = ProgressDialog(title=f"git merge {branch}", parent=self)
        dlg.set_label(f"git merge {branch}")

        def _bg() -> bool:
            try:
                result = do_merge(
                    self.repo, branch,
                    no_ff=self.noff_box.isChecked(),
                    squash=self.squash_box.isChecked(),
                    no_commit=self.nocommit_box.isChecked(),
                    message=self.message_edit.toPlainText().strip() or None,
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

    def _on_abort(self):
        if abort_merge(self.repo):
            self._status.setText(tr("merge_aborted"))
        self._after_action(True)

    def _on_conflicts_resolved(self):
        self._status.setText(tr("merge_conflicts"))

    def _after_action(self, ok: bool):
        self._conflict_box.setVisible(False)
        self.conflicts.refresh()
        if self.conflicts.count > 0:
            self._conflict_box.setVisible(True)
            self._status.setText(tr("merge_conflicts"))
            self.btn_abort.setEnabled(True)
        elif ok:
            self._status.setText(tr("merge_merged"))
            self.btn_abort.setEnabled(False)
            self.accept()