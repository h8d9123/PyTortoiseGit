"""mergedlg.py —— MergeDlg：合并对话框（IDD_MERGE 模板）。

镜像 TortoiseGit 的 MergeDlg：Current branch + From（Branch/Tag/Commit）+
Option（squash/messages/no-ff/ff-only/no-commit/strategy）+ Merge Message。
产生冲突时弹出冲突解决视图。
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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
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
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .conflicts import ConflictsWidget
from .progress import ProgressDialog
from .resize import AnchorLayout


class MergeDlg(QDialog):
    def __init__(self, repo: Repository, branch: str | None = None,
                 parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        self._load_refs(branch)

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_MERGE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(f"{self.repo.name} — {tr('merge_title')}")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.cur_label = QLabel(tr("merge_current", "Current branch:"), self)
        self.cur_edit = QLineEdit(self)
        self.cur_edit.setReadOnly(True)
        self.cur_edit.setText(self.repo.current_branch())

        self.grp_from = QGroupBox(tr("merge_from", "From"), self)
        self.rd_branch = QRadioButton(tr("switch_branch", "&Branch"), self)
        self.branch_combo = QComboBox(self)
        self.btn_browse_ref = QPushButton("...", self)
        self.rd_tags = QRadioButton(tr("switch_tag", "&Tag"), self)
        self.tags_combo = QComboBox(self)
        self.rd_version = QRadioButton(tr("switch_commit", "&Commit"), self)
        self.version_combo = QComboBox(self)
        self.btn_show = QPushButton("...", self)

        self.grp_option = QGroupBox(tr("merge_option", "Option"), self)
        self.chk_squash = QCheckBox(tr("merge_squash", "&Squash"), self)
        self.chk_log = QCheckBox(tr("merge_log", "Messages"), self)
        self.log_num = QLineEdit(self)
        self.chk_noff = QCheckBox(tr("merge_noff", "No &Fast Forward"), self)
        self.chk_ffonly = QCheckBox(tr("merge_ffonly", "Fast Forward O&nly"), self)
        self.chk_nocommit = QCheckBox(tr("merge_nocommit", "No Co&mmit"), self)
        self.strategy_combo = QComboBox(self)
        self.strategy_opt_combo = QComboBox(self)
        self.strategy_param = QLineEdit(self)

        self.grp_message = QGroupBox(tr("merge_message", "Merge &Message"), self)
        self.message_edit = QPlainTextEdit(self)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_start)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)

        # 冲突解决控件：默认不显示，冲突时弹窗
        self.conflicts = ConflictsWidget(self.repo, self)
        self.conflicts.resolved.connect(self._on_conflicts_resolved)

        mapping = {
            "IDC_STATIC": self.cur_label,
            "IDC_CURRENTBRANCH": self.cur_edit,
            "IDC_GROUP_BASEON": self.grp_from,
            "IDC_RADIO_BRANCH": self.rd_branch,
            "IDC_COMBOBOXEX_BRANCH": self.branch_combo,
            "IDC_BUTTON_BROWSE_REF": self.btn_browse_ref,
            "IDC_RADIO_TAGS": self.rd_tags,
            "IDC_COMBOBOXEX_TAGS": self.tags_combo,
            "IDC_RADIO_VERSION": self.rd_version,
            "IDC_COMBOBOXEX_VERSION": self.version_combo,
            "IDC_BUTTON_SHOW": self.btn_show,
            "IDC_GROUP_OPTION": self.grp_option,
            "IDC_CHECK_SQUASH": self.chk_squash,
            "IDC_CHECK_MERGE_LOG": self.chk_log,
            "IDC_EDIT_MERGE_LOGNUM": self.log_num,
            "IDC_CHECK_NOFF": self.chk_noff,
            "IDC_CHECK_FFONLY": self.chk_ffonly,
            "IDC_CHECK_NOCOMMIT": self.chk_nocommit,
            "IDC_COMBO_MERGESTRATEGY": self.strategy_combo,
            "IDC_COMBO_STRATEGYOPTION": self.strategy_opt_combo,
            "IDC_EDIT_STRATEGYPARAM": self.strategy_param,
            "IDC_STATIC_MERGE_MESSAGE": self.grp_message,
            "IDC_LOGMESSAGE": self.message_edit,
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
            a = _MERGE_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        self.strategy_combo.addItems(
            ["", "resolve", "recursive", "octopus", "ours", "subtree"])
        self.strategy_opt_combo.addItems(
            ["", "ours", "theirs", "patience", "diff-algorithm"])
        self.log_num.setText("20")
        for rd in (self.rd_branch, self.rd_tags, self.rd_version):
            rd.toggled.connect(self._update_radios)
        self.rd_branch.setChecked(True)
        self._update_radios()
        self.branch_combo.currentTextChanged.connect(self._prefill_message)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 数据 ----
    def _load_refs(self, preset: str | None):
        out = self.repo.runner.run(
            "for-each-ref", "--format=%(refname)").stdout or ""
        full = [x.strip() for x in out.splitlines() if x.strip()]
        branches, tags = [], []
        for r in full:
            if r.startswith("refs/heads/"):
                branches.append(r[len("refs/heads/"):])
            elif r.startswith("refs/remotes/"):
                branches.append(r[len("refs/remotes/"):])
            elif r.startswith("refs/tags/"):
                tags.append(r[len("refs/tags/"):])
        current = self.repo.current_branch()
        branches = [b for b in branches if b != current]
        self.branch_combo.clear()
        self.branch_combo.addItems(branches)
        self.tags_combo.clear()
        self.tags_combo.addItems(tags)
        self.version_combo.clear()
        self.version_combo.addItems(branches + tags + ["HEAD"])
        if preset:
            idx = self.branch_combo.findText(preset)
            if idx >= 0:
                self.branch_combo.setCurrentIndex(idx)
        self._prefill_message()

    def _update_radios(self, *_a):
        self.branch_combo.setEnabled(self.rd_branch.isChecked())
        self.btn_browse_ref.setEnabled(self.rd_branch.isChecked())
        self.tags_combo.setEnabled(self.rd_tags.isChecked())
        self.version_combo.setEnabled(self.rd_version.isChecked())
        self.btn_show.setEnabled(self.rd_version.isChecked())

    def _target(self) -> str:
        if self.rd_tags.isChecked():
            return self.tags_combo.currentText()
        if self.rd_version.isChecked():
            return self.version_combo.currentText()
        return self.branch_combo.currentText()

    def _prefill_message(self, *_a):
        branch = self.branch_combo.currentText().strip()
        if not branch or self.message_edit.toPlainText().strip():
            return
        cur = self.repo.current_branch()
        self.message_edit.setPlainText(f"Merge branch '{branch}' into '{cur}'")

    # ---- 动作 ----
    def _on_help(self):
        QMessageBox.information(self, tr("help"), tr("merge_title"))

    def _on_start(self):
        target = self._target().strip()
        if not target:
            return
        self.btn_ok.setEnabled(False)
        dlg = ProgressDialog(title=f"git merge {target}", parent=self)
        dlg.set_label(f"git merge {target}")

        def _bg() -> bool:
            try:
                result = do_merge(
                    self.repo, target,
                    no_ff=self.chk_noff.isChecked(),
                    squash=self.chk_squash.isChecked(),
                    no_commit=self.chk_nocommit.isChecked(),
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
        dlg.finished.connect(lambda _f: self.btn_ok.setEnabled(True))
        dlg.exec()

    def _on_abort(self):
        abort_merge(self.repo)
        self._after_action(True)

    def _on_conflicts_resolved(self):
        self.conflicts.refresh()

    def _after_action(self, ok: bool):
        self.conflicts.refresh()
        if self.conflicts.count > 0:
            QMessageBox.information(self, tr("merge_title"), tr("merge_conflicts"))
            self._show_conflicts()
        elif ok:
            self.accept()

    def _show_conflicts(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("conflicts_title"))
        dlg.resize(760, 520)
        lay = QVBoxLayout(dlg)
        lay.addWidget(self.conflicts)
        dlg.exec()


# 锚点：可拉伸的控件（右缘/底部随窗口）
_MERGE_ANCHORS = {
    "IDC_CURRENTBRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_GROUP_BASEON": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_REF": ("TOP_RIGHT",),
    "IDC_COMBOBOXEX_TAGS": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_VERSION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_SHOW": ("TOP_RIGHT",),
    "IDC_GROUP_OPTION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_STATIC_MERGE_MESSAGE": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_LOGMESSAGE": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}
