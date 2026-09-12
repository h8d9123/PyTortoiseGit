"""rebasedlg.py —— RebaseDlg：变基对话框（IDD_REBASE 模板）。

Branch / Upstream 选择 + 交互式提交列表（pick/reword/edit/squash/fixup/drop、
上移/下移/添加）+ Preserve merges / Force Rebase 等选项 + Continue/Abort。
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
    QFrame,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..git.mergeop import abort_rebase
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .conflicts import ConflictsWidget
from .progress import ProgressDialog
from .resize import AnchorLayout

_ACTIONS = ["pick", "reword", "edit", "squash", "fixup", "drop"]


class RebaseDlg(QDialog):
    def __init__(self, repo: Repository, branch: str | None = None,
                 parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        self._load_refs(branch)

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_REBASE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(f"{self.repo.name} — {tr('rebase_title', 'Rebase')}")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.branch_label = QLabel(tr("rebase_branch", "&Branch:"), self)
        self.branch_combo = QComboBox(self)
        self.branch_combo.setEditable(True)
        self.btn_reverse = QPushButton(self)
        self.btn_reverse.setToolTip(tr("rebase_reverse", "Swap branch/upstream"))
        self.upstream_label = QLabel(tr("rebase_upstream", "&Upstream:"), self)
        self.upstream_combo = QComboBox(self)
        self.upstream_combo.setEditable(True)
        self.btn_browse = QPushButton("...", self)
        self.chk_onto = QCheckBox(tr("rebase_onto", "&Onto"), self)

        self.commit_list = QTreeWidget(self)
        self.commit_list.setColumnCount(2)
        self.commit_list.setHeaderLabels(
            [tr("rebase_action", "Action"), tr("rebase_commit", "Commit")])
        self.commit_list.setRootIsDecorated(False)
        self.commit_list.setColumnWidth(0, 72)

        self.btn_split = QPushButton(tr("rebase_splitall", "&Split/Options"), self)
        self.btn_up = QPushButton(tr("rebase_up", "&Up"), self)
        self.btn_down = QPushButton(tr("rebase_down", "&Down"), self)
        self.btn_add = QPushButton(tr("rebase_add", "&Add"), self)
        self.chk_preserve = QCheckBox(tr("rebase_preserve", "&Preserve merges"), self)
        self.chk_force = QCheckBox(tr("rebase_force", "&Force Rebase"), self)
        self.chk_cherry = QCheckBox(
            tr("rebase_cherry", '&add "cherry picked from"'), self)
        self.line = QFrame(self)
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.dummy = QPushButton("", self)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.status = QLabel("", self)
        self.chk_split = QCheckBox(tr("rebase_splitcommit", "&Edit/Split commit"), self)
        self.btn_continue = QPushButton(tr("rebase_continue", "Continue"), self)
        self.btn_continue.setDefault(True)
        self.btn_abort = QPushButton(tr("rebase_abort", "Abort"), self)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_post = QPushButton("", self)

        self.conflicts = ConflictsWidget(self.repo, self)
        self.conflicts.hide()

        mapping = {
            "IDC_REBASE_STATIC_BRANCH": self.branch_label,
            "IDC_REBASE_COMBOXEX_BRANCH": self.branch_combo,
            "IDC_BUTTON_REVERSE": self.btn_reverse,
            "IDC_REBASE_STATIC_UPSTREAM": self.upstream_label,
            "IDC_REBASE_COMBOXEX_UPSTREAM": self.upstream_combo,
            "IDC_BUTTON_BROWSE": self.btn_browse,
            "IDC_BUTTON_ONTO": self.chk_onto,
            "IDC_COMMIT_LIST": self.commit_list,
            "IDC_SPLITALLOPTIONS": self.btn_split,
            "IDC_BUTTON_UP": self.btn_up,
            "IDC_BUTTON_DOWN": self.btn_down,
            "IDC_BUTTON_ADD": self.btn_add,
            "IDC_REBASE_CHECK_PRESERVEMERGES": self.chk_preserve,
            "IDC_REBASE_CHECK_FORCE": self.chk_force,
            "IDC_CHECK_CHERRYPICKED_FROM": self.chk_cherry,
            "IDC_REBASE_SPLIT": self.line,
            "IDC_REBASE_DUMY_TAB": self.dummy,
            "IDC_REBASE_PROGRESS": self.progress,
            "IDC_STATUS_STATIC": self.status,
            "IDC_REBASE_SPLIT_COMMIT": self.chk_split,
            "IDC_REBASE_CONTINUE": self.btn_continue,
            "IDC_REBASE_ABORT": self.btn_abort,
            "IDHELP": self.btn_help,
            "IDC_REBASE_POST_BUTTON": self.btn_post,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            rc_mod.place_widget(self, fu, ctrl, wgt)
            self._ctl[ctrl.ctrl_id] = wgt

        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _REBASE_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        # 模板里默认隐藏的控件（cherry-pick 复选框与 Force 在模板坐标上重叠）
        self.chk_split.hide()
        self.dummy.hide()
        self.btn_post.hide()
        self.chk_cherry.hide()
        self.btn_reverse.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload))

        self.branch_combo.currentTextChanged.connect(self._reload_commits)
        self.upstream_combo.currentTextChanged.connect(self._reload_commits)
        self.btn_reverse.clicked.connect(self._on_reverse)
        self.btn_up.clicked.connect(lambda: self._move_commit(-1))
        self.btn_down.clicked.connect(lambda: self._move_commit(1))
        self.btn_add.clicked.connect(self._on_add)
        self.btn_split.clicked.connect(self._on_split_options)
        self.btn_continue.clicked.connect(self._on_continue)
        self.btn_abort.clicked.connect(self._on_abort)
        self.btn_help.clicked.connect(self._on_help)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 数据 ----
    def _load_refs(self, preset: str | None):
        out = self.repo.runner.run(
            "for-each-ref", "--format=%(refname)").stdout or ""
        branches = []
        for line in out.splitlines():
            r = line.strip()
            if r.startswith("refs/heads/"):
                branches.append(r[len("refs/heads/"):])
            elif r.startswith("refs/remotes/"):
                branches.append(r[len("refs/remotes/"):])
        self.branch_combo.clear()
        self.branch_combo.addItems(branches)
        self.upstream_combo.clear()
        self.upstream_combo.addItems(branches + ["HEAD"])
        cur = self.repo.current_branch()
        if preset:
            i = self.branch_combo.findText(preset)
            if i >= 0:
                self.branch_combo.setCurrentIndex(i)
        elif cur in branches:
            self.branch_combo.setCurrentText(cur)
        self._reload_commits()

    def _reload_commits(self, *_a):
        self.commit_list.clear()
        branch = self.branch_combo.currentText().strip()
        upstream = self.upstream_combo.currentText().strip()
        if not branch or not upstream or branch == upstream:
            return
        out = self.repo.runner.run(
            "log", "--format=%H\x1f%s", f"{upstream}..{branch}").stdout or ""
        for line in out.splitlines():
            if not line.strip():
                continue
            h, _, subj = line.partition("\x1f")
            it = QTreeWidgetItem(["pick", f"{h[:8]} {subj}"])
            it.setData(0, Qt.ItemDataRole.UserRole, h)
            self.commit_list.addTopLevelItem(it)

    # ---- 列表操作 ----
    def _move_commit(self, delta: int):
        it = self.commit_list.currentItem()
        if it is None:
            return
        row = self.commit_list.indexOfTopLevelItem(it)
        new = row + delta
        if new < 0 or new >= self.commit_list.topLevelItemCount():
            return
        self.commit_list.takeTopLevelItem(row)
        self.commit_list.insertTopLevelItem(new, it)
        self.commit_list.setCurrentItem(it)

    def _on_add(self):
        out = self.repo.runner.run(
            "log", "--format=%H\x1f%s", "-n", "200").stdout or ""
        menu = QMenu(self)
        existing = {
            self.commit_list.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(self.commit_list.topLevelItemCount())
        }
        acts = {}
        for line in out.splitlines():
            if not line.strip():
                continue
            h, _, subj = line.partition("\x1f")
            if h in existing:
                continue
            a = menu.addAction(f"{h[:8]} {subj}")
            acts[a] = (h, subj)
        if not acts:
            return
        chosen = menu.exec(self.btn_add.mapToGlobal(self.btn_add.rect().bottomLeft()))
        if chosen is None:
            return
        h, subj = acts[chosen]
        it = QTreeWidgetItem(["pick", f"{h[:8]} {subj}"])
        it.setData(0, Qt.ItemDataRole.UserRole, h)
        self.commit_list.addTopLevelItem(it)

    def _on_split_options(self):
        menu = QMenu(self)
        acts = {}
        for act_name in _ACTIONS:
            a = menu.addAction(act_name)
            acts[a] = act_name
        chosen = menu.exec(
            self.btn_split.mapToGlobal(self.btn_split.rect().bottomLeft()))
        if chosen is None:
            return
        act_name = acts[chosen]
        it = self.commit_list.currentItem()
        targets = [it] if it is not None else [
            self.commit_list.topLevelItem(i)
            for i in range(self.commit_list.topLevelItemCount())]
        for t in targets:
            if t is not None:
                t.setText(0, act_name)

    def _on_reverse(self):
        b = self.branch_combo.currentText()
        u = self.upstream_combo.currentText()
        self.branch_combo.setCurrentText(u)
        self.upstream_combo.setCurrentText(b)

    def _on_help(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, tr("help"), tr("rebase_title", "Rebase"))

    # ---- 动作 ----
    def _on_continue(self):
        branch = self.branch_combo.currentText().strip()
        upstream = self.upstream_combo.currentText().strip()
        if not branch or not upstream:
            return
        args = ["rebase"]
        if self.chk_preserve.isChecked():
            args.append("--rebase-merges")
        if self.chk_force.isChecked():
            args.append("--force-rebase")
        args.append(upstream)
        if branch != self.repo.current_branch():
            args.append(branch)
        self.progress.setVisible(True)
        dlg = ProgressDialog(title="git " + " ".join(args), parent=self)
        dlg.set_label("git " + " ".join(args))

        def _bg() -> bool:
            result = self.repo.runner.run(*args)
            if result.stdout:
                dlg.log(result.stdout)
            if result.stderr:
                dlg.log(result.stderr)
            return result.returncode == 0

        dlg.run(_bg)
        dlg.on_finish(self._after_action)
        dlg.exec()
        self.progress.setVisible(False)

    def _on_abort(self):
        abort_rebase(self.repo)
        self.status.setText(tr("rebase_aborted", "Rebase aborted."))
        self.conflicts.refresh()
        self._reload_commits()

    def _after_action(self, ok: bool):
        self.conflicts.refresh()
        if self.conflicts.count > 0:
            self.status.setText(tr("rebase_conflicts", "Conflicts detected."))
        elif ok:
            self.status.setText(tr("rebase_done", "Rebase finished."))
        self._reload_commits()


# AddAnchor：提交列表纵向拉伸，底部进度/状态/按钮固定
_REBASE_ANCHORS = {
    "IDC_REBASE_COMBOXEX_UPSTREAM": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE": ("TOP_RIGHT",),
    "IDC_BUTTON_ONTO": ("TOP_RIGHT",),
    "IDC_COMMIT_LIST": ("TOP_LEFT", "MIDDLE_RIGHT"),
    "IDC_SPLITALLOPTIONS": ("MIDDLE_LEFT",),
    "IDC_BUTTON_UP": ("MIDDLE_LEFT",),
    "IDC_BUTTON_DOWN": ("MIDDLE_LEFT",),
    "IDC_BUTTON_ADD": ("MIDDLE_LEFT",),
    "IDC_REBASE_CHECK_PRESERVEMERGES": ("MIDDLE_LEFT",),
    "IDC_REBASE_CHECK_FORCE": ("MIDDLE_LEFT",),
    "IDC_CHECK_CHERRYPICKED_FROM": ("MIDDLE_LEFT",),
    "IDC_REBASE_SPLIT": ("MIDDLE_LEFT", "MIDDLE_RIGHT"),
    "IDC_REBASE_PROGRESS": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_STATUS_STATIC": ("BOTTOM_LEFT",),
    "IDC_REBASE_CONTINUE": ("BOTTOM_RIGHT",),
    "IDC_REBASE_ABORT": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}
