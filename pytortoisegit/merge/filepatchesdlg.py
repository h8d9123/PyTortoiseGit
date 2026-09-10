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

"""filepatchesdlg.py —— TortoiseMerge 的 FilePatchesDlg（补丁文件列表）。

翻译 FilePatchesDlg.h：列出补丁涉及的文件，双击触发回调 PatchFile/
ShowDiff。用 QTreeWidget 呈现（CListCtrl 语义）。
"""

from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from ..res.strings import tr

# 文件状态（对齐 FPDLG_FILESTATE_*）
FPDLG_FILESTATE_GOOD = 0
FPDLG_FILESTATE_ERROR = -1
FPDLG_FILESTATE_PATCHED = -2
FPDLG_FILESTATE_CONFLICT = -3


class _PatchEntry:
    """补丁条目。"""

    def __init__(self, path: str, content_mods: bool = False,
                 prop_mods: bool = False, version: str = ""):
        self.path = path
        self.content_mods = content_mods
        self.prop_mods = prop_mods
        self.version = version


class FilePatchesDlg(QDialog):
    """补丁文件列表对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("filepatches_title", "补丁文件"))
        self.resize(620, 420)
        self._entries: List[_PatchEntry] = []
        self._file_states: List[int] = []
        self._patch = None
        self._path = ""
        self._patch_cb: Optional[Callable] = None
        self._diff_cb: Optional[Callable] = None
        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        lay = QVBoxLayout(self)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([
            tr("filepatches_path", "文件"),
            tr("filepatches_content", "内容"),
            tr("filepatches_version", "版本")])
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        lay.addWidget(self.tree, 1)
        btns = QHBoxLayout()
        self.btn_patch_all = QPushButton(tr("filepatches_patchall", "全部应用"), self)
        self.btn_patch_all.clicked.connect(self.patch_all)
        self.btn_patch_sel = QPushButton(tr("filepatches_patchsel", "应用选中"), self)
        self.btn_patch_sel.clicked.connect(self.patch_selected)
        btns.addWidget(self.btn_patch_all)
        btns.addWidget(self.btn_patch_sel)
        btns.addStretch(1)
        lay.addLayout(btns)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def set_callback(self, patch_cb=None, diff_cb=None):
        self._patch_cb = patch_cb
        self._diff_cb = diff_cb

    def init(self, patch, callback=None, path: str = "") -> bool:
        """从 Patch 填充文件列表（对齐 CFilePatchesDlg::Init）。"""
        self.clear()
        self._patch = patch
        self._path = path
        if callback is not None:
            self.set_callback(callback)
        n = patch.get_number_of_files() if patch is not None else 0
        for i in range(n):
            entry = _PatchEntry(
                patch.get_filename(i), content_mods=True,
                prop_mods=False, version=patch.get_revision(i))
            self.add_entry(entry)
            self._file_states.append(FPDLG_FILESTATE_GOOD)
        return n > 0

    def has_files(self) -> bool:
        return len(self._entries) > 0

    def add_entry(self, entry: "_PatchEntry"):
        self._entries.append(entry)
        it = QTreeWidgetItem([
            entry.path,
            tr("yes") if entry.content_mods else tr("no"),
            entry.version])
        it.setData(0, Qt.ItemDataRole.UserRole, len(self._entries) - 1)
        self.tree.addTopLevelItem(it)

    def clear(self):
        self._entries.clear()
        self._file_states.clear()
        self.tree.clear()

    def set_file_status_as_patched(self, path: str) -> bool:
        """把某文件标记为已应用（对齐 SetFileStatusAsPatched）。"""
        for i, e in enumerate(self._entries):
            if e.path == path:
                self._file_states[i] = FPDLG_FILESTATE_PATCHED
                return True
        return False

    def patch_all(self):
        for e in self._entries:
            if self._patch_cb:
                self._patch_cb(e.path, e.content_mods, e.prop_mods,
                               e.version, True)

    def patch_selected(self):
        item = self.tree.currentItem()
        if item is None:
            return
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._entries):
            return
        e = self._entries[idx]
        if self._patch_cb:
            self._patch_cb(e.path, e.content_mods, e.prop_mods, e.version, False)

    def _on_double_click(self, item, _col):
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._entries):
            return
        e = self._entries[idx]
        if self._patch_cb:
            self._patch_cb(e.path, e.content_mods, e.prop_mods, e.version)