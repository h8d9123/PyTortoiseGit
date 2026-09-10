"""commitisonrefsdlg.py —— CommitIsOnRefsDlg：显示提交所在的引用（IDD_COMMITISONREFS 模板）。

301x194 "References commit is on"：提交哈希 + 引用列表 + Filter。
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
    QDialog, QLabel, QLineEdit, QMenu, QPushButton, QTreeWidget, QTreeWidgetItem,
)
from ..git.repo import Repository
from ..git.rev import GitRevLoglist
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class CommitIsOnRefsDlg(QDialog):
    def __init__(self, repo: Repository, commit: str = "HEAD", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.commit = commit
        spec = rc_mod.load_spec("IDD_COMMITISONREFS")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "References commit is on")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.commit_edit = QLineEdit(self)
        self.commit_edit.setText(commit)
        self.btn_sel_ref = QPushButton("...", self)
        self.subject_edit = QLineEdit(self)
        self.subject_edit.setReadOnly(True)
        self.btn_log = QPushButton(tr("showlog", "Show log"), self)
        self.btn_log.clicked.connect(self._show_log)
        self.ref_list = QTreeWidget(self)
        self.ref_list.setColumnCount(1)
        self.ref_list.setHeaderLabels([tr("commitref_ref", "Reference")])
        self.ref_list.setRootIsDecorated(False)
        self.ref_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ref_list.customContextMenuRequested.connect(self._on_menu)
        self.filter_label = QLabel(tr("commitref_filter", "Filter: "), self)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)

        mapping = {
            "IDC_COMMIT": self.commit_edit,
            "IDC_SELREF": self.btn_sel_ref,
            "IDC_STATIC_SUBJECT": self.subject_edit,
            "IDC_LOG": self.btn_log,
            "IDC_LIST_REF_LEAFS": self.ref_list,
            "IDC_LABEL_FILTER": self.filter_label,
            "IDC_FILTER": self.filter_edit,
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

        self._load()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _canon(self) -> str:
        r = self.repo.runner.run("rev-parse", "--verify", self.commit)
        return r.stdout.strip() or self.commit

    def _show_log(self):
        from .logdlg import LogDlg
        ref = self.commit_edit.text().strip()
        LogDlg(self.repo, pathspec=None, rev=ref, parent=self).exec()

    def _load(self):
        canonical = self._canon()
        out = self.repo.runner.run(
            "for-each-ref", "--format=%(refname:short)",
            f"%(objectname)".strip() and "--contains", canonical).stdout or ""
        # 更可靠：git branch -a --contains; git tag --contains
        refs = set()
        for sub in ("branch", "-a"):
            rr = self.repo.runner.run("branch", "-a", "--contains", canonical)
            for line in (rr.stdout or "").splitlines():
                s = line.strip().lstrip("* ").strip()
                if s:
                    refs.add(s)
        rt = self.repo.runner.run("tag", "--contains", canonical)
        for line in (rt.stdout or "").splitlines():
            if line.strip():
                refs.add(line.strip())
        subject = self.repo.runner.run("log", "-1", "--pretty=%s", canonical).stdout or ""
        self.subject_edit.setText(subject.strip())
        self.ref_list.clear()
        for ref in sorted(refs):
            it = QTreeWidgetItem([ref])
            it.setData(0, Qt.ItemDataRole.UserRole, ref)
            self.ref_list.addTopLevelItem(it)

    def _apply_filter(self, *_a):
        text = self.filter_edit.text().strip().lower()
        for i in range(self.ref_list.topLevelItemCount()):
            it = self.ref_list.topLevelItem(i)
            it.setHidden(bool(text) and text not in it.text(0).lower())

    def _on_menu(self, pos):
        item = self.ref_list.itemAt(pos)
        if item is None:
            return
        ref = item.text(0)
        menu = QMenu(self)
        act_copy = menu.addAction(tr("menu_copy_ref", "Copy reference name"))
        act_checkout = menu.addAction(tr("log_checkout", "Checkout this commit…"))
        chosen = menu.exec(self.ref_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(ref)
        elif chosen is act_checkout:
            self.repo.runner.run("checkout", ref)
            self._load()


_ANCHORS = {
    "IDC_FILTER": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_LABEL_FILTER": ("BOTTOM_LEFT",),
    "IDC_SELREF": ("TOP_RIGHT",),
    "IDC_COMMIT": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_STATIC_SUBJECT": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_LIST_REF_LEAFS": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_LOG": ("TOP_RIGHT",),
}