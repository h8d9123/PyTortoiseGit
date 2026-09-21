"""submoduleupdatedlg.py —— SubmoduleUpdateDlg：更新子模块（IDD_SUBMODULE_UPDATE）。

对齐 TortoiseGit 的 CSubmoduleUpdateDlg：
  * 子模块路径列表（多选）+「全选/取消全选」+「整个项目」；
  * 选项组：Initialize submodules (--init)、Recursive、Force、No fetch、
    Merge、Rebase、Remote tracking branch；
  * OK/Cancel/Help；未选中任何路径时 OK 置灰。

调用方用 OK 后的属性构造 ``git submodule update ...`` 命令。
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

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QGroupBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
)

from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.submodule import GitSubmodule
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class SubmoduleUpdateDlg(QDialog):
    def __init__(self, repo: Repository, parent=None, init: bool = True,
                 recursive: bool = False,
                 path_filter: Optional[List[str]] = None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.sub = GitSubmodule(repo)
        self._path_filter = list(path_filter or [])
        # 结果
        self.init = bool(init)
        self.recursive = bool(recursive)
        self.force = False
        self.no_fetch = False
        self.merge = False
        self.rebase = False
        self.remote = False
        self.paths: List[str] = []
        self.all_selected = True
        self._all_paths: List[str] = []
        self._build_ui()

    # ---- UI ----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_SUBMODULE_UPDATE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Submodule Update")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.path_label = QLabel(tr("submodule_update_path", "Path:"), self)
        self.list = QListWidget(self)
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._on_selection_changed)
        self.chk_selectall = QCheckBox(
            tr("submodule_update_selectall", "Select/deselect all"), self)
        self.chk_selectall.toggled.connect(self._on_select_all)
        self.chk_whole = QCheckBox(
            tr("submodule_update_whole", "&Whole Project"), self)
        self.chk_whole.setChecked(not self._path_filter)
        self.chk_whole.setEnabled(bool(self._path_filter))
        self.chk_whole.toggled.connect(lambda *_: self._reload())

        self.grp_info = QGroupBox(
            tr("submodule_update_options", "Submodule Update Options"), self)
        self.chk_init = QCheckBox(
            tr("submodule_update_init", "Initialize submodules (--init)"), self)
        self.chk_init.setChecked(self.init)
        self.chk_recursive = QCheckBox(tr("submodule_update_recursive",
                                          "&Recursive"), self)
        self.chk_recursive.setChecked(self.recursive)
        self.chk_force = QCheckBox(
            tr("submodule_update_force", "&Force"), self)
        self.chk_nofetch = QCheckBox(
            tr("submodule_update_nofetch", "&No fetch"), self)
        self.chk_merge = QCheckBox(
            tr("submodule_update_merge", "&Merge"), self)
        self.chk_rebase = QCheckBox(
            tr("submodule_update_rebase", "Re&base"), self)
        self.chk_remote = QCheckBox(tr("submodule_update_remote",
                                       "Remote &tracking branch"), self)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)

        mapping = {
            "IDC_STATIC": self.path_label,
            "IDC_LIST_PATH": self.list,
            "IDC_SELECTALL": self.chk_selectall,
            "IDC_WHOLE_PROJECT": self.chk_whole,
            "IDC_GROUP_INFO": self.grp_info,
            "IDC_CHECK_SUBMODULE_INIT": self.chk_init,
            "IDC_CHECK_SUBMODULE_RECURSIVE": self.chk_recursive,
            "IDC_FORCE": self.chk_force,
            "IDC_CHECK_SUBMODULE_NOFETCH": self.chk_nofetch,
            "IDC_CHECK_SUBMODULE_MERGE": self.chk_merge,
            "IDC_CHECK_SUBMODULE_REBASE": self.chk_rebase,
            "IDC_CHECK_SUBMODULE_REMOTE": self.chk_remote,
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

        self._reload()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 数据 ----
    def _reload(self):
        self.list.clear()
        run_async(self._list_bg, on_done=self._on_listed,
                  on_error=lambda m, _tb: None, parent=self)

    def _list_bg(self) -> List[str]:
        entries = self.sub.list()
        paths = [e.path for e in entries]
        if self._path_filter and not self.chk_whole.isChecked():
            allowed = [p.rstrip("/") for p in self._path_filter if p]
            paths = [p for p in paths
                     if any(p == a or p.startswith(a + "/") for a in allowed)]
        return sorted(paths, key=str.casefold)

    def _on_listed(self, paths: List[str]):
        self._all_paths = list(paths)
        self.list.clear()
        for p in paths:
            self.list.addItem(p)
        # 默认全选（对齐原版：默认选中全部）
        for i in range(self.list.count()):
            self.list.item(i).setSelected(True)
        self.chk_selectall.setChecked(bool(paths))
        self._on_selection_changed()

    # ---- 选择 ----
    def _selected_paths(self) -> List[str]:
        return [it.text() for it in self.list.selectedItems()]

    def _on_select_all(self, on: bool):
        for i in range(self.list.count()):
            self.list.item(i).setSelected(bool(on))
        self._on_selection_changed()

    def _on_selection_changed(self):
        count = len(self._selected_paths())
        self.btn_ok.setEnabled(count > 0)
        if count == 0:
            self.chk_selectall.setChecked(False)
        elif count == self.list.count():
            self.chk_selectall.setChecked(True)

    # ---- OK ----
    def _on_help(self):
        QMessageBox.information(self, tr("help", "Help"),
                                tr("submodule_update_options",
                                   "Submodule Update Options"))

    def _on_ok(self):
        paths = self._selected_paths()
        if not paths:
            return
        self.paths = paths
        self.all_selected = (len(paths) == self.list.count())
        self.init = self.chk_init.isChecked()
        self.recursive = self.chk_recursive.isChecked()
        self.force = self.chk_force.isChecked()
        self.no_fetch = self.chk_nofetch.isChecked()
        self.merge = self.chk_merge.isChecked()
        self.rebase = self.chk_rebase.isChecked()
        self.remote = self.chk_remote.isChecked()
        self.accept()


_ANCHORS = {
    "IDC_LIST_PATH": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_SELECTALL": ("BOTTOM_LEFT",),
    "IDC_WHOLE_PROJECT": ("BOTTOM_LEFT",),
    "IDC_GROUP_INFO": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_CHECK_SUBMODULE_INIT": ("BOTTOM_LEFT",),
    "IDC_CHECK_SUBMODULE_RECURSIVE": ("BOTTOM_LEFT",),
    "IDC_FORCE": ("BOTTOM_LEFT",),
    "IDC_CHECK_SUBMODULE_REMOTE": ("BOTTOM_LEFT",),
    "IDC_CHECK_SUBMODULE_NOFETCH": ("BOTTOM_RIGHT",),
    "IDC_CHECK_SUBMODULE_MERGE": ("BOTTOM_RIGHT",),
    "IDC_CHECK_SUBMODULE_REBASE": ("BOTTOM_RIGHT",),
}
