"""resolvedlg.py —— ResolveDlg：解决冲突（IDD_RESOLVE 模板）。

289x154 "Resolve"：冲突文件复选列表 + Select all + OK（git add 标记已解决）。
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
    QCheckBox, QDialog, QLabel, QMenu, QPushButton, QTreeWidget, QTreeWidgetItem,
)
from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.statuslist import GitStatusList
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class ResolveDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        self._populate()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_RESOLVE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Resolve")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.resolve_list = QTreeWidget(self)
        self.resolve_list.setColumnCount(2)
        self.resolve_list.setHeaderLabels([tr("resolve_path", "Path"),
                                           tr("resolve_status", "Status")])
        self.resolve_list.setColumnWidth(0, 180)
        self.resolve_list.setRootIsDecorated(False)
        self.resolve_list.setIndentation(0)
        self.resolve_list.itemDoubleClicked.connect(self._on_resolve_one)
        self.resolve_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.resolve_list.customContextMenuRequested.connect(self._on_resolve_menu)
        self.chk_selectall = QCheckBox(tr("resolve_selectall", "Select/deselect &all"), self)
        self.chk_selectall.toggled.connect(self._on_select_all)
        self.reminder = QLabel(tr("resolve_reminder", "Reminder: Commit your change after resolve"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_resolve)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_RESOLVELIST": self.resolve_list,
            "IDC_SELECTALL": self.chk_selectall,
            "IDC_STATIC_REMINDER": self.reminder,
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _populate(self):
        self.resolve_list.clear()
        rows = GitStatusList(self.repo).fetch()
        self._rows = [r for r in rows if r.state == "conflicted"]
        for r in self._rows:
            it = QTreeWidgetItem([r.path, r.action])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked)
            it.setData(0, Qt.ItemDataRole.UserRole, r.path)
            self.resolve_list.addTopLevelItem(it)

    def _on_select_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.resolve_list.topLevelItemCount()):
            self.resolve_list.topLevelItem(i).setCheckState(0, state)

    def _resolve_paths(self) -> list:
        out = []
        for i in range(self.resolve_list.topLevelItemCount()):
            it = self.resolve_list.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                out.append(it.data(0, Qt.ItemDataRole.UserRole))
        return out

    def _on_resolve(self):
        paths = self._resolve_paths()
        if not paths:
            self.reject()
            return
        self._do_resolve(paths)

    def _on_resolve_one(self, item, _col):
        p = item.data(0, Qt.ItemDataRole.UserRole)
        self._do_resolve([p])

    def _on_resolve_menu(self, pos):
        item = self.resolve_list.itemAt(pos)
        if item is None:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if not p:
            return
        menu = QMenu(self)
        act_open = menu.addAction(tr("menu_open", "Open in editor"))
        act_copy = menu.addAction(tr("menu_copy_path", "Copy path"))
        act_edit = menu.addAction(tr("resolve_edit", "Resolve/Mark as resolved"))
        menu.addSeparator()
        act_merge = menu.addAction(tr("resolve_merge", "Resolve with merge tool"))
        act_diff = menu.addAction(tr("resolve_diff", "View conflict"))
        chosen = menu.exec(self.resolve_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        full = self.repo.full_path(p)
        if chosen is act_copy:
            ClipboardHelper().copy_text(p)
        elif chosen is act_open:
            import os
            if os.path.isfile(full):
                os.startfile(full)  # noqa: S606
        elif chosen is act_edit:
            self._do_resolve([p])
        elif chosen is act_merge:
            self._launch_merge(p)
        elif chosen is act_diff:
            self._show_conflict(p)

    def _launch_merge(self, path: str):
        try:
            from ..utils import externaltools
            d = externaltools.from_repo(self.repo)
            externaltools.launch_merge_for_conflict(d, self.repo, path)
        except Exception:
            pass

    def _show_conflict(self, path: str):
        from .diffdlg import DiffDlg
        DiffDlg(self.repo, rev1="MERGE_HEAD", rev2=None, paths=[path],
                parent=self).show()

    def _do_resolve(self, paths):
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label("git add " + " ".join(paths[:2]) +
                      ("…" if len(paths) > 2 else ""))
        def _bg():
            r = self.repo.runner.run("add", "--", *paths)
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0
        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_RESOLVELIST": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_SELECTALL": ("BOTTOM_LEFT",),
    "IDC_STATIC_REMINDER": ("BOTTOM_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}