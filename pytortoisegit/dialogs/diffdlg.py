"""diffdlg.py —— DiffDlg：文本 diff 查看对话框。

支持：
  - 比较两个修订 rev1、rev2
  - 只比较工作区（rev1=None, rev2=None → git diff HEAD）
  - 可限定文件路径
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

from typing import List, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMenu,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..git.repo import Repository
from ..git.rev import GitRev
from ..res.strings import format_string, tr
from ..asyncfw import run_async
from .widgets import DiffView


class DiffDlg(QDialog):
    def __init__(self, repo: Repository, rev1: str | None = None,
                 rev2: str | None = None, paths: Sequence[str] | None = None,
                 parent=None, title: str = ""):
        super().__init__(parent)
        self.repo = repo
        self.rev1 = rev1
        self.rev2 = rev2
        self.paths = list(paths or [])
        self.patches: list = []
        local = repo.name
        if title:
            self.setWindowTitle(title)
        else:
            self.setWindowTitle(f"{local} — diff")
        self.resize(920, 640)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        header = QLabel(self)
        self._header = header
        lay.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.file_tree = QTreeWidget(splitter)
        self.file_tree.setColumnCount(4)
        self.file_tree.setHeaderLabels([tr("file"), tr("status"),
                                        tr("log_file_changes", "增"), tr("删")])
        self.file_tree.setColumnWidth(0, 360)
        self.file_tree.setColumnWidth(1, 70)
        self.file_tree.setColumnWidth(2, 40)
        self.file_tree.setColumnWidth(3, 40)
        self.file_tree.itemClicked.connect(self._on_file_clicked)
        self.file_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._on_menu)
        splitter.addWidget(self.file_tree)

        self.view = DiffView(splitter)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        lay.addWidget(splitter, 1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.StandardButton.Close).setText(tr("close"))
        lay.addWidget(box)

    # ---- 加载 ----
    def _load(self):
        self.setWindowTitle(f"{self.repo.name} — {tr('loading')}")
        run_async(self._build_patch, on_done=self._on_loaded,
                  on_error=self._on_error, parent=self)

    def _build_patch(self) -> tuple:
        from ..udiff import parse_diff
        args: List[str] = ["diff", "--no-color", "-U3"]
        if self.rev1 and self.rev2:
            args += [self.rev1, self.rev2]
        elif self.rev2:
            args += [self.rev2]
        if self.paths:
            args += ["--", *self.paths]
        else:
            args.append("--")
        out = self.repo.runner.run_checked(*args)
        patches = parse_diff(out)
        total = sum(p.added + p.removed for p in patches)
        return patches, total

    def _on_loaded(self, payload):
        patches, total = payload
        self.patches = patches
        self._header.setText(
            f" {len(patches)} 个文件，+{total} 行改动"
            f"  {self.rev1 or 'HEAD'} … {self.rev2 or '工作区'}")
        self.file_tree.clear()
        for p in patches:
            status = "已修改"
            if p.is_new:
                status = "新增"
            elif p.is_deleted:
                status = "删除"
            elif p.is_rename:
                status = "重命名"
            item = QTreeWidgetItem([p.filename_display, status,
                                    str(p.added) if p.added else "",
                                    str(p.removed) if p.removed else ""])
            item.setData(0, Qt.ItemDataRole.UserRole, p)
            self.file_tree.addTopLevelItem(item)
        self.setWindowTitle(f"{self.repo.name} — diff")
        if patches:
            self.file_tree.setCurrentItem(self.file_tree.topLevelItem(0))
            self._show_patch(patches[0])

    def _on_error(self, message: str, _tb: str):
        self.setWindowTitle(self.repo.name)
        self._header.setText(str(message))
        self.view.display_text(str(message))

    def _on_file_clicked(self, item, _col):
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is not None:
            self._show_patch(p)

    def _show_patch(self, patch):
        self.view.display_patch(patch.raw, title=f"═══ {patch.filename_display} ═══")

    def _on_file_double_clicked(self, item, _col):
        """双击文件：在系统编辑器中打开文件。"""
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is None:
            return
        full = self._full_path(p.filename_display)
        import os
        if full and os.path.isfile(full):
            try:
                os.startfile(full)  # noqa: S606
            except OSError:
                pass

    # ---- 右键菜单 ----
    def _on_menu(self, pos):
        item = self.file_tree.itemAt(pos)
        if item is None:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is None:
            return
        path = p.filename_display
        menu = QMenu(self)
        act_open = menu.addAction(tr("menu_open", "在编辑器打开"))
        act_copy = menu.addAction(tr("menu_copy_path", "复制路径"))
        menu.addSeparator()
        act_diff = menu.addAction(tr("menu_diff_file", "显示该文件 diff"))
        act_blame = menu.addAction(tr("menu_blame", "在此文件上运行 Blame"))
        act_ext = menu.addAction(tr("menu_ext_tool", "外部 diff 工具打开"))
        chosen = menu.exec(self.file_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        full = self._full_path(path)
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_open:
            if full and os.path.isfile(full):
                import subprocess
                os.startfile(full)  # noqa: S606
        elif chosen is act_diff:
            self._show_patch(p)
        elif chosen is act_blame:
            from .blamedlg import BlameDlg
            BlameDlg(self.repo, path, rev=self.rev2, parent=self).exec()
        elif chosen is act_ext:
            self._open_external(path)

    def _full_path(self, path: str) -> str:
        import os
        root = self.repo.root
        return os.path.join(root, path.replace("/", os.sep))

    def _open_external(self, path: str):
        """用外部工具打开文件 diff（配置了 tortoisegit.externaldiff 时）。"""
        import subprocess
        import os
        full = self._full_path(path)
        cmd = ""
        try:
            r = self.repo.runner.run("config", "--get", "diff.external")
            cmd = (r.stdout or "").strip()
        except Exception:
            pass
        if cmd:
            subprocess.Popen(cmd.replace("{path}", full), shell=False)
        elif os.path.isfile(full):
            os.startfile(full)  # noqa: S606


def diff_dialog(repo: Repository, rev1=None, rev2=None, paths=None,
                parent=None) -> DiffDlg:
    return DiffDlg(repo, rev1, rev2, paths, parent)