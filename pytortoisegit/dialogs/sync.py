"""sync.py —— SyncDlg：同步（拉取/推送）对话框（镜像 TortoiseGit IDD_SYNC）。

严格按 IDD_SYNC 模板排版：顶部 Info 组（本地/远程分支、URL、进度）、
中部 Tab（命令 Log / 待拉取 / 待推送）、底部动作按钮行 + 状态行。
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

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..git.repo import Repository
from ..res.strings import format_string, tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .progress import ProgressDialog
from .resize import AnchorLayout


class SyncDlg(QDialog):
    def __init__(self, repo: Repository, remote: str | None = None,
                 parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        self._remote_name = remote or self._default_remote()
        self._refresh_remotes()
        self._refresh_status()

    # ---- UI（IDD_SYNC 模板）----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_SYNC")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or tr("sync_title", "Sync"))
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.info_group = QGroupBox(self)
        self.info_group.setObjectName("IDC_GROUP_INFO")
        self.local_label = QLabel(tr("sync_local", "&Local Branch:"), self)
        self.local_combo = QComboBox(self)
        self.local_combo.setEditable(True)
        self.btn_local = QPushButton("...", self)
        self.btn_local.setFixedHeight(23)
        self.remote_label = QLabel(tr("sync_remote", "&Remote Branch:"), self)
        self.remote_combo = QComboBox(self)
        self.remote_combo.setEditable(True)
        self.btn_remote = QPushButton("...", self)
        self.btn_remote.setFixedHeight(23)
        self.url_label = QLabel(tr("sync_url", "Remote &URL:"), self)
        self.url_combo = QComboBox(self)
        self.url_combo.setEditable(True)
        self.btn_manage = QPushButton(tr("sync_manage", "Manage"), self)
        self.btn_manage.clicked.connect(self._manage_remote)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.prog_label = QLabel("", self)
        self.chk_putty = QCheckBox(tr("sync_putty", "Autoload Putty &Key"), self)
        self.chk_force = QCheckBox(tr("sync_force", "&Force"), self)
        # 当前分支适配：branch_label 保留给 UI 扩展（测试只断言文本）
        self.branch_label = QLabel(self)
        self.branch_label.hide()
        self.branch_label.setText(self.repo.current_branch())

        # 中部 Tab：命令 Log / incoming / outgoing
        self.tab = QTabWidget(self)
        self.tab.setObjectName("IDC_SYNC_TAB")
        self.log_view = QPlainTextEdit(self.tab)
        self.log_view.setReadOnly(True)
        self.incoming_tree = QTreeWidget(self.tab)
        self.incoming_tree.setHeaderLabels([tr("sync_in", "Incoming")])
        self.outgoing_tree = QTreeWidget(self.tab)
        self.outgoing_tree.setHeaderLabels([tr("sync_out", "Outgoing")])
        self.tab.addTab(self.log_view, tr("log", "Log"))
        self.tab.addTab(self.incoming_tree, tr("sync_incoming", "Incoming"))
        self.tab.addTab(self.outgoing_tree, tr("sync_outgoing", "Outgoing"))

        # 动作按钮行
        from PySide6.QtWidgets import QMenu as _QMenu
        self.btn_pull = QPushButton(tr("sync_pull", "Pull"), self)
        pull_menu = _QMenu(self.btn_pull)
        self._act_pull = pull_menu.addAction(tr("sync_pull", "Pull"))
        self._act_pull_rebase = pull_menu.addAction(tr("sync_pull_rebase", "Pull && Rebase"))
        self._act_fetch = pull_menu.addAction(tr("sync_fetch", "Fetch"))
        self.btn_pull.setMenu(pull_menu)
        self._act_pull.triggered.connect(lambda *_: self._do("pull"))
        self._act_pull_rebase.triggered.connect(lambda *_: self._do("pull", rebase=True))
        self._act_fetch.triggered.connect(lambda *_: self._do("fetch"))

        self.btn_push = QPushButton(tr("sync_push", "Push"), self)
        push_menu = _QMenu(self.btn_push)
        self._act_push = push_menu.addAction(tr("sync_push", "Push"))
        self._act_push_upstream = push_menu.addAction(tr("sync_push_upstream", "Push & Set Upstream"))
        self._act_push_tags = push_menu.addAction(tr("sync_push_tags", "Push Tags"))
        self._act_push_all = push_menu.addAction(tr("sync_push_all", "Push All Branches"))
        self.btn_push.setMenu(push_menu)
        self._act_push.triggered.connect(lambda *_: self._do("push"))
        self._act_push_upstream.triggered.connect(lambda *_: self._do("push", upstream=True))
        self._act_push_tags.triggered.connect(lambda *_: self._do("push", tags=True))
        self._act_push_all.triggered.connect(lambda *_: self._do("push", all_branches=True))
        self.btn_submodule = QPushButton(tr("sync_submodule", "Submodule"), self)
        self.btn_submodule.clicked.connect(self._open_submodule)
        self.btn_stash = QPushButton(tr("sync_stash", "Stash"), self)
        self.btn_stash.clicked.connect(self._open_stash)
        self.btn_apply = QPushButton(tr("sync_apply", "&Apply Patch"), self)
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_email = QPushButton(tr("sync_email", "&Email Patch"), self)
        self.btn_email.clicked.connect(self._on_email)
        self.btn_log = QPushButton(tr("sync_log", "Show &log"), self)
        self.btn_log.clicked.connect(self._open_log)
        self.btn_commit = QPushButton(tr("sync_commit", "&Commit"), self)
        self.btn_commit.clicked.connect(self._open_commit)
        self.status_label = QLabel("", self)
        self.btn_close = QPushButton(tr("close"), self)
        self.btn_close.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(lambda: QMessageBox.information(
            self, tr("help"), tr("sync_help", "Choose the local/remote branch and remote URL, then pull or push.")))
        self._animate = QLabel("", self)
        self._animate.setObjectName("IDC_ANIMATE_SYNC")

        mapping = {
            "IDC_GROUP_INFO": self.info_group,
            "IDC_STATIC_LOCAL_BRANCH": self.local_label,
            "IDC_STATIC_REMOTE_BRANCH": self.remote_label,
            "IDC_STATIC_REMOTE_URL": self.url_label,
            "IDC_COMBOBOXEX_URL": self.url_combo,
            "IDC_COMBOBOXEX_LOCAL_BRANCH": self.local_combo,
            "IDC_COMBOBOXEX_REMOTE_BRANCH": self.remote_combo,
            "IDC_BUTTON_LOCAL_BRANCH": self.btn_local,
            "IDC_BUTTON_REMOTE_BRANCH": self.btn_remote,
            "IDC_BUTTON_MANAGE": self.btn_manage,
            "IDC_PROGRESS_SYNC": self.progress,
            "IDC_PROG_LABEL": self.prog_label,
            "IDC_CHECK_PUTTY_KEY": self.chk_putty,
            "IDC_CHECK_FORCE": self.chk_force,
            "IDC_BUTTON_TABCTRL": self.tab,
            "IDC_ANIMATE_SYNC": self._animate,
            "IDC_BUTTON_PULL": self.btn_pull,
            "IDC_BUTTON_PUSH": self.btn_push,
            "IDC_BUTTON_SUBMODULE": self.btn_submodule,
            "IDC_BUTTON_STASH": self.btn_stash,
            "IDC_BUTTON_APPLY": self.btn_apply,
            "IDC_BUTTON_EMAIL": self.btn_email,
            "IDC_LOG": self.btn_log,
            "IDC_BUTTON_COMMIT": self.btn_commit,
            "IDC_STATIC_STATUS": self.status_label,
            "IDOK": self.btn_close,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            _place(self, fu, ctrl, wgt)
            self._ctl[ctrl.ctrl_id] = wgt

        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _SYNC_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 数据 ----
    def _default_remote(self) -> str:
        out = self.repo.runner.run("remote").stdout or ""
        return out.splitlines()[0] if out.strip() else "origin"

    def _remote_names(self) -> List[str]:
        out = self.repo.runner.run("remote").stdout or ""
        return [ln.strip() for ln in out.splitlines() if ln.strip()]

    def _remote_branches(self, remote: str) -> List[str]:
        out = self.repo.runner.run("branch", "-r").stdout or ""
        prefix = remote + "/"
        result = []
        for ln in out.splitlines():
            name = ln.strip().split()[0]
            if name.startswith(prefix):
                result.append(name[len(prefix):])
        return result

    def _local_branches(self) -> List[str]:
        out = self.repo.runner.run("branch").stdout or ""
        return [ln.strip().lstrip("* ").strip() for ln in out.splitlines() if ln.strip()]

    def _refresh_remotes(self):
        cur = self.remote_combo.currentText().strip() or self._remote_name
        self.remote_combo.clear()
        names = self._remote_names()
        self.remote_combo.addItems(names or [cur])
        self.remote_combo.setCurrentText(cur if cur in names else (names[0] if names else cur))

        self.local_combo.clear()
        loc = self.repo.current_branch()
        self.local_combo.addItems(self._local_branches() or [loc])
        self.local_combo.setCurrentText(loc)

        self.remote_combo.currentIndexChanged.connect(self._refresh_status)
        url = self._remote_url(cur)
        self.url_combo.clear()
        if url:
            self.url_combo.addItem(url)
            self.url_combo.setCurrentText(url)

    def _remote_url(self, remote: str) -> str:
        res = self.repo.runner.run("remote", "get-url", remote)
        return (res.stdout or "").strip()

    def _refresh_status(self, *_args):
        rm = self.remote_combo.currentText().strip()
        br = self.local_combo.currentText().strip()
        self.url_combo.clear()
        url = self._remote_url(rm)
        if url:
            self.url_combo.addItem(url)
            self.url_combo.setCurrentText(url)
        self.remote_combo.blockSignals(False)
        if not rm:
            self.status_label.setText(tr("sync_no_remote", "No remote configured"))
            return
        self._populate_inout(rm, br)
        lines: List[str] = []
        remote_branches = self._remote_branches(rm)
        for rbr in remote_branches:
            ahead, behind = self._ahead_behind(rm, rbr)
            if ahead or behind:
                lines.append(format_string(
                    tr("sync_ab", "{branch}: ahead {ahead}, behind {behind}"),
                    branch=rbr, ahead=ahead, behind=behind))
        self.status_label.setText("\n".join(lines) or tr("sync_in_sync", "Up to date with remote"))

    def _ahead_behind(self, remote: str, branch: str) -> Tuple[int, int]:
        head = self.local_combo.currentText().strip() or self.repo.current_branch()
        result = self.repo.runner.run(
            "rev-list", "--left-right", "--count",
            f"{remote}/{branch}...{head}" if head else f"{remote}/{branch}")
        out = (result.stdout or "").split()
        if len(out) == 2:
            return int(out[0]), int(out[1])
        return 0, 0

    def _populate_inout(self, remote: str, branch: str):
        self.incoming_tree.clear()
        self.outgoing_tree.clear()
        head = branch or self.repo.current_branch()
        if not head:
            return
        inc = self.repo.runner.run("log", "--oneline", "-g",
                                   f"{remote}/{branch}..{head}").stdout or ""
        out = self.repo.runner.run("log", "--oneline", "-g",
                                   f"{head}..{remote}/{branch}").stdout or ""

        def fill(tree, text, empty_key):
            tree.clear()
            for ln in text.splitlines():
                tree.addTopLevelItem(QTreeWidgetItem([ln]))
            if not text.strip():
                tree.addTopLevelItem(QTreeWidgetItem([tr(empty_key, "—")]))

        fill(self.outgoing_tree, inc, "sync_out_empty")
        fill(self.incoming_tree, out, "sync_in_empty")

    # ---- 动作 ----
    def _do(self, action: str, rebase: bool = False, upstream: bool = False,
            tags: bool = False, all_branches: bool = False):
        rm = self.remote_combo.currentText().strip()
        br = self.local_combo.currentText().strip()
        if not rm:
            QMessageBox.warning(self, tr("warning"), tr("sync_no_remote", "No remote configured"))
            return
        rbr = self.remote_combo.currentText().strip()
        if rbr == rm:
            rbr = ""
        args = [action]
        if action == "pull":
            if rebase:
                args.append("--rebase")
        elif action == "push":
            if self.chk_force.isChecked():
                args.append("--force")
            if upstream:
                args.append("--set-upstream")
            if tags:
                args += ["--tags"]
            if all_branches:
                args.append("--all")
        args.append(rm)
        if br and not all_branches:
            args.append(f"{rbr}:{br}" if rbr else br)
        title = f"git {' '.join(args)}"
        dlg = ProgressDialog(title=title, parent=self)
        dlg.set_label(title)
        self.log_view.appendPlainText("$ " + title)
        dlg.run(lambda: _run_reporter(dlg, self.repo, args,
                                      log=self.log_view))
        dlg.on_finish(lambda ok: self._refresh_status() if ok else None)
        dlg.exec()

    def _manage_remote(self):
        from .addremotedlg import AddRemoteDlg
        dlg = AddRemoteDlg(self.repo, parent=self)
        if dlg.exec():
            names = self._remote_names()
            QMessageBox.information(self, tr("sync_manage_remote", "Manage Remotes"),
                                    (tr("sync_remote_list", "Remotes:\n") + "\n".join(names))
                                    if names else tr("sync_no_remote", "No remote configured"))
            self._refresh_remotes()

    def _open_commit(self):
        from .commitdlg import CommitDlg
        dlg = CommitDlg(self.repo, parent=self)
        dlg.exec()
        self._refresh_status()

    def _open_log(self):
        from .logdlg import LogDlg
        dlg = LogDlg(self.repo, pathspec=None, parent=self)
        dlg.exec()

    def _on_apply(self):
        from .applypatchdlg import ApplyPatchDlg
        dlg = ApplyPatchDlg(self.repo, parent=self)
        dlg.exec()

    def _on_email(self):
        from .sendmaildlg import SendMailDlg
        dlg = SendMailDlg(self.repo, parent=self)
        dlg.exec()

    def _open_submodule(self):
        from .submoduledlg import SubmoduleDlg
        dlg = SubmoduleDlg(self.repo, parent=self)
        dlg.exec()

    def _open_stash(self):
        from .stashdlg import StashDlg
        dlg = StashDlg(self.repo, parent=self)
        dlg.exec()


_SYNC_ANCHORS = {
    "IDC_GROUP_INFO": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_URL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_MANAGE": ("TOP_RIGHT",),
    "IDC_BUTTON_PULL": ("BOTTOM_LEFT",),
    "IDC_BUTTON_PUSH": ("BOTTOM_LEFT",),
    "IDC_BUTTON_SUBMODULE": ("BOTTOM_LEFT",),
    "IDC_BUTTON_STASH": ("BOTTOM_LEFT",),
    "IDC_BUTTON_APPLY": ("BOTTOM_RIGHT",),
    "IDC_BUTTON_EMAIL": ("BOTTOM_RIGHT",),
    "IDC_PROGRESS_SYNC": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
    "IDC_STATIC_STATUS": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_ANIMATE_SYNC": ("TOP_LEFT",),
    "IDC_BUTTON_COMMIT": ("BOTTOM_LEFT",),
    "IDC_LOG": ("BOTTOM_LEFT",),
    "IDC_COMBOBOXEX_LOCAL_BRANCH": ("TOP_LEFT", "TOP_CENTER"),
    "IDC_COMBOBOXEX_REMOTE_BRANCH": ("TOP_CENTER", "TOP_RIGHT"),
    "IDC_BUTTON_LOCAL_BRANCH": ("TOP_CENTER",),
    "IDC_BUTTON_REMOTE_BRANCH": ("TOP_RIGHT",),
    "IDC_STATIC_REMOTE_BRANCH": ("TOP_CENTER",),
    "IDC_PROG_LABEL": ("TOP_LEFT",),
    "IDC_SYNC_TAB": ("TOP_LEFT", "BOTTOM_RIGHT"),
}


def _place(dlg, fu, ctrl, wgt):
    rc_mod.place_widget(dlg, fu, ctrl, wgt)
    if isinstance(wgt, QComboBox) and 20 < wgt.height() < 200:
        wgt.setFixedHeight(23)
    if ctrl.hidden:
        wgt.hide()


def _run_reporter(dlg, repo, args, log=None) -> bool:
    result = repo.runner.run(*args)
    if result.stdout:
        dlg.log(result.stdout)
        if log is not None:
            log.appendPlainText(result.stdout.rstrip())
    if result.stderr:
        dlg.log(result.stderr)
        if log is not None:
            log.appendPlainText(result.stderr.rstrip())
    if result.returncode == 0:
        return True
    if result.returncode and not result.stderr:
        dlg.log(tr("sync_failed", "Sync failed"))
    return result.returncode == 0