"""pushdlg.py —— PushDlg：推送到远端（IDD_PUSH 模板）。

311x277 "Push"：Ref 组（push all/本地分支/远端分支）+
Destination 组（Remote/URL）+ Options 组（force/tags/putty/upstream/submodules/push option）。
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
    QButtonGroup, QCheckBox, QComboBox, QDialog, QGroupBox, QLabel,
    QMessageBox, QPushButton, QRadioButton,
)
from ..git.push import PushOpts, build_push_args, get_remote_push_branch
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .progress import ProgressDialog
from .resize import AnchorLayout


def run_push(repo: Repository, opts: PushOpts, parent=None) -> bool:
    """对齐 CAppUtils::DoPush：关 Push 对话框后再跑进度窗。"""
    args = build_push_args(opts)
    dlg = ProgressDialog(parent=parent)

    def _after(ok: bool):
        if ok:
            return
        text = dlg.output.toPlainText()
        if "! [rejected]" in text:
            def _pull():
                from .pulldlg import PullFetchDlg
                PullFetchDlg(repo, fetch_only=False, parent=parent).exec()

            def _fetch():
                from .pulldlg import PullFetchDlg
                PullFetchDlg(repo, fetch_only=True, parent=parent).exec()

            dlg.add_post_action(tr("menu_pull"), _pull)
            dlg.add_post_action(tr("menu_fetch"), _fetch)

        def _repush():
            again = PushDlg(repo, parent=parent, local_branch=opts.local_branch)
            if again.exec() == QDialog.DialogCode.Accepted:
                run_push(repo, again.push_opts(), parent=parent)

        dlg.add_post_action(tr("menu_push"), _repush)

    dlg.on_finish(_after)
    dlg.run_git(repo.runner, *args)
    return dlg.exec() == QDialog.DialogCode.Accepted and dlg._exit_code == 0


def do_push_after_commit(repo: Repository, parent=None, amend: bool = False) -> bool:
    """对齐 CCommitDlg::DoPush。"""
    from ..git.push import should_open_push_dialog

    head = repo.current_branch()
    remote, rbranch = get_remote_push_branch(repo, head)
    if should_open_push_dialog(amend, remote, rbranch):
        dlg = PushDlg(repo, parent=parent, local_branch=head)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        return run_push(repo, dlg.push_opts(), parent=parent)
    return run_push(
        repo,
        PushOpts(remote=remote, local_branch=head, remote_branch=rbranch),
        parent=parent,
    )


class PushDlg(QDialog):
    def __init__(self, repo: Repository, parent=None, local_branch: str = ""):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._initial_local = local_branch
        self._opts: PushOpts | None = None
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_PUSH")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Push")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        # 分组框（与其它控件同级，按 rc 顺序先放在底层）
        self.ref_group = QGroupBox(tr("push_ref_group", "Ref"), self)
        self.dest_group = QGroupBox(tr("push_dest_group", "Destination"), self)
        self.opt_group = QGroupBox(tr("push_opt_group", "Options"), self)

        # Ref group
        self.chk_push_all = QCheckBox(tr("push_all", "&Push all branches"), self)
        self.local_label = QLabel(tr("push_local", "&Local:"), self)
        self.local_combo = QComboBox(self)
        self.local_combo.setEditable(True)
        self.btn_browse_local = QPushButton("...", self)
        self.remote_label = QLabel(tr("push_remote", "&Remote:"), self)
        self.remote_combo = QComboBox(self)
        self.remote_combo.setEditable(True)
        self.btn_browse_remote = QPushButton("...", self)

        # Destination group（原版是单选）
        self.rd_remote = QRadioButton(tr("push_rd_remote", "Re&mote:"), self)
        self.remote_name_combo = QComboBox(self)
        self.btn_manage = QPushButton(tr("push_manage", "Mana&ge"), self)
        self.rd_url = QRadioButton(tr("push_rd_url", "Arbitrary &URL:"), self)
        self.url_edit = QComboBox(self)
        self.url_edit.setEditable(True)
        dest_btns = QButtonGroup(self)
        dest_btns.addButton(self.rd_remote)
        dest_btns.addButton(self.rd_url)
        self.rd_remote.setChecked(True)
        self.rd_remote.toggled.connect(self._on_dest_toggled)

        # Options group
        self.chk_force_with_lease = QCheckBox(tr("push_force_lease", "Force &with lease"), self)
        self.chk_force = QCheckBox(tr("push_force", "&Force"), self)
        self.chk_tags = QCheckBox(tr("push_tags", "Include &Tags"), self)
        self.chk_putty = QCheckBox(tr("push_putty", "&Autoload Putty Key"), self)
        self.chk_set_upstream = QCheckBox(tr("push_upstream", "&Set upstream/track remote branch"), self)
        self.chk_push_remote = QCheckBox(tr("push_push_remote", "Always push to selected remote archive"), self)
        self.chk_push_branch = QCheckBox(tr("push_push_branch", "Always push to selected remote branch"), self)
        self.sub_label = QLabel(tr("push_sub", "Recurse submodule"), self)
        self.sub_combo = QComboBox(self)
        self.sub_combo.addItems(["On-demand", "Check", "Off"])
        self.push_option_label = QLabel(tr("push_option", "Push &option:"), self)
        self.push_option_edit = QComboBox(self)
        self.push_option_edit.setEditable(True)

        # Buttons
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self._status = QLabel(self)
        self._status.setText(tr("push_ready", "就绪"))
        self._details = QLabel(self)

        mapping = {
            "IDC_BRANCH_GROUP": self.ref_group,
            "IDC_URL_GROUP": self.dest_group,
            "IDC_OPTION_GROUP": self.opt_group,
            "IDC_PUSHALL": self.chk_push_all,
            "IDC_STATIC_SOURCE": self.local_label,
            "IDC_BRANCH_SOURCE": self.local_combo,
            "IDC_BUTTON_BROWSE_SOURCE_BRANCH": self.btn_browse_local,
            "IDC_STATIC_REMOTE": self.remote_label,
            "IDC_BRANCH_REMOTE": self.remote_combo,
            "IDC_BUTTON_BROWSE_DEST_BRANCH": self.btn_browse_remote,
            "IDC_RD_REMOTE": self.rd_remote,
            "IDC_REMOTE": self.remote_name_combo,
            "IDC_REMOTE_MANAGE": self.btn_manage,
            "IDC_RD_URL": self.rd_url,
            "IDC_URL": self.url_edit,
            "IDC_FORCE_WITH_LEASE": self.chk_force_with_lease,
            "IDC_FORCE": self.chk_force,
            "IDC_TAGS": self.chk_tags,
            "IDC_PUTTYKEY_AUTOLOAD": self.chk_putty,
            "IDC_PROC_PUSH_SET_UPSTREAM": self.chk_set_upstream,
            "IDC_PROC_PUSH_SET_PUSHREMOTE": self.chk_push_remote,
            "IDC_PROC_PUSH_SET_PUSHBRANCH": self.chk_push_branch,
            "IDC_STATIC_RECURSE_SUBMODULES": self.sub_label,
            "IDC_COMBOBOX_RECURSE_SUBMODULES": self.sub_combo,
            "IDC_STATIC_PUSHOPTION": self.push_option_label,
            "IDC_PUSHOPTION": self.push_option_edit,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        self._status.setObjectName("IDC_STATIC_STATUS")
        self._status.setParent(self)

        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _PUSH_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        self.chk_push_all.toggled.connect(self._on_push_all)
        self.local_combo.currentTextChanged.connect(self._on_local_changed)
        self._on_dest_toggled()
        self._populate()

    def _on_dest_toggled(self, _checked: bool = False):
        use_remote = self.rd_remote.isChecked()
        self.remote_name_combo.setEnabled(use_remote)
        self.btn_manage.setEnabled(use_remote)
        self.url_edit.setEnabled(not use_remote)

    def _populate(self):
        heads = self.repo.runner.run(
            "for-each-ref", "--format=%(refname:short)", "refs/heads").stdout or ""
        refs = [b.strip() for b in heads.splitlines() if b.strip()]
        cur = self._initial_local or self.repo.current_branch()
        self.local_combo.blockSignals(True)
        self.local_combo.addItems(refs or [cur])
        if cur:
            self.local_combo.setCurrentText(cur)
        self.local_combo.blockSignals(False)
        remotes = [r.strip() for r in self.repo.get_remotes() if r.strip()]
        self.remote_name_combo.addItems(remotes or ["origin"])
        self._fill_dest_from_local(cur)
        track_remote = self.repo.config(f"branch.{cur}.remote")
        track_merge = self.repo.config(f"branch.{cur}.merge")
        if not track_remote and not track_merge:
            self.chk_set_upstream.setChecked(True)

    def _fill_dest_from_local(self, local: str):
        push_remote, push_branch = get_remote_push_branch(self.repo, local)
        remotes = [self.remote_name_combo.itemText(i)
                   for i in range(self.remote_name_combo.count())]
        if push_remote and push_remote in remotes:
            self.remote_name_combo.setCurrentText(push_remote)
        dest = push_branch or local
        if dest and dest == (push_remote or self.remote_name_combo.currentText()):
            dest = local
        self.remote_combo.clear()
        if dest:
            self.remote_combo.addItem(dest)
            self.remote_combo.setCurrentText(dest)

    def _on_local_changed(self, text: str):
        if text.strip():
            self._fill_dest_from_local(text.strip())

    def _on_push_all(self, checked: bool):
        for wgt in (self.local_combo, self.remote_combo,
                    self.btn_browse_local, self.btn_browse_remote):
            wgt.setEnabled(not checked)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def push_opts(self) -> PushOpts:
        if self._opts is None:
            self._opts = self._collect_opts() or PushOpts(remote="")
        return self._opts

    def _collect_opts(self) -> PushOpts | None:
        if self.rd_url.isChecked():
            remote = self.url_edit.currentText().strip()
        else:
            remote = self.remote_name_combo.currentText().strip()
        if not remote:
            QMessageBox.warning(self, tr("warning"), tr("push_no_remote"))
            return None
        recurse_map = {"On-demand": "on-demand", "Check": "check", "Off": ""}
        return PushOpts(
            remote=remote,
            local_branch=self.local_combo.currentText().strip(),
            remote_branch=self.remote_combo.currentText().strip(),
            all_branches=self.chk_push_all.isChecked(),
            force=self.chk_force.isChecked(),
            force_with_lease=self.chk_force_with_lease.isChecked(),
            tags=self.chk_tags.isChecked(),
            set_upstream=self.chk_set_upstream.isChecked(),
            push_option=self.push_option_edit.currentText().strip(),
            recurse=recurse_map.get(self.sub_combo.currentText(), ""),
        )

    def _on_ok(self):
        opts = self._collect_opts()
        if opts is None:
            return
        self._opts = opts
        self.accept()


_PUSH_ANCHORS = {
    "IDC_BRANCH_GROUP": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_URL_GROUP": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_OPTION_GROUP": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_PUSHALL": ("TOP_LEFT",),
    "IDC_STATIC_SOURCE": ("TOP_LEFT",),
    "IDC_BRANCH_SOURCE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_SOURCE_BRANCH": ("TOP_RIGHT",),
    "IDC_STATIC_REMOTE": ("TOP_LEFT",),
    "IDC_BRANCH_REMOTE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_DEST_BRANCH": ("TOP_RIGHT",),
    "IDC_RD_REMOTE": ("TOP_LEFT",),
    "IDC_REMOTE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REMOTE_MANAGE": ("TOP_RIGHT",),
    "IDC_RD_URL": ("TOP_LEFT",),
    "IDC_URL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_FORCE_WITH_LEASE": ("TOP_LEFT",),
    "IDC_FORCE": ("TOP_LEFT",),
    "IDC_TAGS": ("TOP_LEFT",),
    "IDC_PUTTYKEY_AUTOLOAD": ("TOP_LEFT",),
    "IDC_PROC_PUSH_SET_UPSTREAM": ("TOP_LEFT",),
    "IDC_PROC_PUSH_SET_PUSHREMOTE": ("TOP_LEFT",),
    "IDC_PROC_PUSH_SET_PUSHBRANCH": ("TOP_LEFT",),
    "IDC_STATIC_RECURSE_SUBMODULES": ("TOP_LEFT",),
    "IDC_COMBOBOX_RECURSE_SUBMODULES": ("TOP_LEFT",),
    "IDC_STATIC_PUSHOPTION": ("TOP_LEFT",),
    "IDC_PUSHOPTION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}