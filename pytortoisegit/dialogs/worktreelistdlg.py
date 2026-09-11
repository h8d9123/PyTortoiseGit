"""worktreelistdlg.py —— WorktreeListDlg：工作树列表（IDD_WORKTREE_LIST 模板）。

350x134 "Worktree List"：工作树列表 + Add/Prune + OK/Help。
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
    QDialog, QPushButton, QTreeWidget, QTreeWidgetItem,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class WorktreeListDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        self._populate()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_WORKTREE_LIST")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Worktree List")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([
            tr("wt_path", "Path"), tr("wt_branch", "Branch"),
            tr("wt_head", "HEAD")])
        self.tree.setColumnWidth(0, 220)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.btn_add = QPushButton(tr("wt_add", "&Add"), self)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_prune = QPushButton(tr("wt_prune", "&Prune"), self)
        self.btn_prune.clicked.connect(self._on_prune)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_WORKTREE_LIST": self.tree,
            "IDC_BUTTON_ADD": self.btn_add,
            "IDC_BUTTON_PRUNE": self.btn_prune,
            "IDOK": self.btn_ok,
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _populate(self):
        self.tree.clear()
        out = self.repo.runner.run(
            "worktree", "list", "--porcelain").stdout or ""
        current = None
        entries = []
        for line in out.splitlines():
            if line.startswith("worktree "):
                current = {"path": line[9:], "branch": "", "head": ""}
                entries.append(current)
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
        for e in entries:
            it = QTreeWidgetItem([e["path"], e["branch"] or "", e["head"][:7]])
            it.setData(0, Qt.ItemDataRole.UserRole, e["path"])
            self.tree.addTopLevelItem(it)

    def _on_add(self):
        from .worktreecreatedlg import WorktreeCreateDlg
        dlg = WorktreeCreateDlg(self.repo, parent=self)
        if dlg.exec():
            self._populate()

    def _on_prune(self):
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label("git worktree prune")
        def _bg():
            r = self.repo.runner.run("worktree", "prune")
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0
        dlg.run(_bg)
        dlg.exec()
        self._populate()


_ANCHORS = {
    "IDC_WORKTREE_LIST": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_BUTTON_ADD": ("BOTTOM_LEFT",),
    "IDC_BUTTON_PRUNE": ("BOTTOM_LEFT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}