"""applypatchdlg.py —— ApplyPatchDlg：应用补丁（IDD_APPLY_PATCH_LIST 模板）。

376x265 "Apply Patches"：补丁文件列表（Add/Up/Down/Remove）+ 选项
（3way/ignore-space/sign-off/keep-cr）+ Apply 执行 git am。
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
    QCheckBox, QDialog, QMenu, QPushButton, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QWidget,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from ..utils.pick import pick_open_files
from .resize import AnchorLayout
from .progress import ProgressDialog


class ApplyPatchDlg(QDialog):
    def __init__(self, repo: Repository, patches=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        if patches:
            for p in patches:
                self._add_patch(p)

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_APPLY_PATCH_LIST")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Apply Patches")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.patch_list = QTreeWidget(self)
        self.patch_list.setColumnCount(1)
        self.patch_list.setHeaderLabels([tr("apply_patch_file", "Patch 文件")])
        self.patch_list.setRootIsDecorated(False)
        self.patch_list.setIndentation(0)
        self.patch_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.patch_list.customContextMenuRequested.connect(self._on_menu)
        self.btn_add = QPushButton(tr("apply_add", "&Add"), self)
        self.btn_add.clicked.connect(self._add_files)
        self.btn_up = QPushButton(tr("apply_up", "&Up"), self)
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down = QPushButton(tr("apply_down", "&Down"), self)
        self.btn_down.clicked.connect(lambda: self._move(1))
        self.btn_remove = QPushButton(tr("apply_remove", "&Remove"), self)
        self.btn_remove.clicked.connect(self._remove_selected)

        self.chk_3way = QCheckBox(tr("apply_3way", "&3 way merge"), self)
        self.chk_ignorespace = QCheckBox(tr("apply_ignore_space", "&ignore space change"), self)
        self.chk_signoff = QCheckBox(tr("apply_sign_off", 'Add "&Signed-off-by"'), self)
        self.chk_keepcr = QCheckBox(tr("apply_keep_cr", "&Keep CR"), self)
        self.tabs = QTabWidget(self)
        # IDC_AM_SPLIT 占位 → 直接实现为 tab 页（第一页是选项组占位）
        page = QWidget(self)
        self.tabs.addTab(page, tr("apply_tab_patches", "Patches"))

        self.btn_apply = QPushButton(tr("apply_apply", "A&pply"), self)
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_cancel = QPushButton(tr("apply_cancel", "&Cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_LIST_PATCH": self.patch_list,
            "IDC_BUTTON_ADD": self.btn_add,
            "IDC_BUTTON_UP": self.btn_up,
            "IDC_BUTTON_DOWN": self.btn_down,
            "IDC_BUTTON_REMOVE": self.btn_remove,
            "IDC_CHECK_3WAY": self.chk_3way,
            "IDC_CHECK_IGNORE_SPACE": self.chk_ignorespace,
            "IDC_SIGN_OFF": self.chk_signoff,
            "IDC_KEEP_CR": self.chk_keepcr,
            "IDC_AM_SPLIT": self.tabs,
            "IDOK": self.btn_apply,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
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
            a = _ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _add_files(self):
        files = pick_open_files(self, tr("apply_add", "选择补丁"), "*.patch *.diff" )
        if files:
            for f in files:
                self._add_patch(f)

    def _add_patch(self, path: str):
        for i in range(self.patch_list.topLevelItemCount()):
            if self.patch_list.topLevelItem(i).text(0) == path:
                return
        it = QTreeWidgetItem([os.path.normpath(path)])
        it.setData(0, Qt.ItemDataRole.UserRole, os.path.normpath(path))
        self.patch_list.addTopLevelItem(it)

    def _remove_selected(self):
        item = self.patch_list.currentItem()
        if item is not None:
            self.patch_list.takeTopLevelItem(
                self.patch_list.indexOfTopLevelItem(item))

    def _move(self, delta: int):
        item = self.patch_list.currentItem()
        if item is None:
            return
        idx = self.patch_list.indexOfTopLevelItem(item)
        new = idx + delta
        if 0 <= new < self.patch_list.topLevelItemCount():
            self.patch_list.takeTopLevelItem(idx)
            self.patch_list.insertTopLevelItem(new, item)
            self.patch_list.setCurrentItem(item)

    def _on_menu(self, pos):
        item = self.patch_list.itemAt(pos)
        if item is None:
            return
        path = item.text(0)
        menu = QMenu(self)
        act_open = menu.addAction(tr("menu_open", "在编辑器打开"))
        act_copy = menu.addAction(tr("menu_copy_path", "复制路径"))
        menu.addSeparator()
        act_up = menu.addAction(tr("apply_up", "&Up"))
        act_down = menu.addAction(tr("apply_down", "&Down"))
        act_remove = menu.addAction(tr("apply_remove", "&Remove"))
        chosen = menu.exec(self.patch_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        import os
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_open:
            if os.path.isfile(path):
                os.startfile(path)  # noqa: S606
        elif chosen is act_up:
            self._move(-1)
        elif chosen is act_down:
            self._move(1)
        elif chosen is act_remove:
            self._remove_selected()

    def _on_apply(self):
        patches = []
        for i in range(self.patch_list.topLevelItemCount()):
            patches.append(self.patch_list.topLevelItem(i).text(0))
        if not patches:
            return
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label(f"git apply ({len(patches)} 个补丁)")
        args = ["apply"]
        if self.chk_3way.isChecked():
            args.append("--3way")
        if self.chk_ignorespace.isChecked():
            args.append("--ignore-space-change")
        if self.chk_keepcr.isChecked():
            args.append("--keep-cr")

        def _bg():
            total = 0
            for p in patches:
                r = self.repo.runner.run(*(args + [p]))
                dlg.log(r.stdout or "")
                dlg.log(r.stderr or "")
                total += r.returncode
            return total == 0

        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_LIST_PATCH": ("TOP_LEFT", "MIDDLE_RIGHT"),
    "IDC_BUTTON_ADD": ("TOP_RIGHT",),
    "IDC_BUTTON_UP": ("TOP_RIGHT",),
    "IDC_BUTTON_DOWN": ("TOP_RIGHT",),
    "IDC_BUTTON_REMOVE": ("TOP_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}