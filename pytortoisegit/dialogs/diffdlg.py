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

import os
from typing import List, Optional, Sequence

from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileIconProvider,
    QHeaderView,
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
from .loglists import ChangedFile, filediff_action_color, status_text
from .widgets import DiffView

# CFileDiffDlg：File / Extension / Action / Lines added / Lines removed
DIFF_COL_FILE = 0
DIFF_COL_EXT = 1
DIFF_COL_ACTION = 2
DIFF_COL_ADD = 3
DIFF_COL_DEL = 4


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
        self.file_tree.setColumnCount(5)
        self.file_tree.setHeaderLabels([
            tr("filediff_file", "文件"),
            tr("filediff_ext", "扩展名"),
            tr("filediff_action", "动作"),
            tr("filediff_add", "增加"),
            tr("filediff_del", "删除"),
        ])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setIndentation(0)
        self.file_tree.setUniformRowHeights(True)
        self.file_tree.header().setSectionResizeMode(DIFF_COL_FILE, QHeaderView.ResizeMode.Stretch)
        self.file_tree.setColumnWidth(DIFF_COL_EXT, 64)
        self.file_tree.setColumnWidth(DIFF_COL_ACTION, 72)
        self.file_tree.setColumnWidth(DIFF_COL_ADD, 48)
        self.file_tree.setColumnWidth(DIFF_COL_DEL, 48)
        align_r = int(Qt.AlignmentFlag.AlignRight)
        self.file_tree.headerItem().setTextAlignment(DIFF_COL_ADD, align_r)
        self.file_tree.headerItem().setTextAlignment(DIFF_COL_DEL, align_r)
        self._file_icons = QFileIconProvider()
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
        from ..merge.diffdata import normalize_revs
        old_rev, new_rev = normalize_revs(self.rev1, self.rev2)
        args: List[str] = ["diff", "--no-color", "-U3"]
        if old_rev and new_rev:
            args += [old_rev, new_rev]
        elif old_rev:
            args += [old_rev]
        if self.paths:
            args += ["--", *self.paths]
        else:
            args.append("--")
        out = self.repo.runner.run_checked(*args)
        patches = parse_diff(out)
        total = sum(p.added + p.removed for p in patches)
        return patches, total

    def _on_loaded(self, payload):
        from ..merge.diffdata import normalize_revs
        patches, total = payload
        self.patches = patches
        old_rev, new_rev = normalize_revs(self.rev1, self.rev2)
        self._header.setText(
            f" {len(patches)} 个文件，+{total} 行改动"
            f"  {old_rev or 'HEAD'} … {new_rev or '工作区'}")
        self.file_tree.clear()
        align_r = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for p in patches:
            row = ChangedFile(
                p.git_path, p.status_code,
                added="-" if p.is_binary else str(p.added),
                deleted="-" if p.is_binary else str(p.removed),
                old_path=p.old_path if p.is_rename else "",
            )
            item = QTreeWidgetItem([
                row.display_name(),
                p.ext,
                status_text(p.status_code),
                row.added,
                row.deleted,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, p)
            item.setIcon(0, self._file_icons.icon(QFileInfo(p.git_path)))
            item.setTextAlignment(DIFF_COL_ADD, align_r)
            item.setTextAlignment(DIFF_COL_DEL, align_r)
            rgb = filediff_action_color(p.status_code)
            brush = QBrush(QColor(*rgb))
            for c in range(item.columnCount()):
                item.setForeground(c, brush)
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
        """双击：对齐 CFileDiffDlg::DoDiff，打开并排比较。"""
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is not None:
            self._open_compare(p)

    def _open_compare(self, p):
        from ..merge.mergefrm import MergeFrm
        frm = MergeFrm(self.repo, p.git_path, self.rev1, self.rev2, parent=self)
        frm.show()

    # ---- 右键菜单（对齐 CFileDiffDlg::OnContextMenu）----
    def _on_menu(self, pos):
        item = self.file_tree.itemAt(pos)
        if item is None:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is None:
            return
        path = p.git_path
        menu = QMenu(self)
        act_cmp = menu.addAction(tr("log_compare_two", "比较两个修订"))
        act_gnu = menu.addAction(tr("log_gnudiff", "显示统一差异"))
        menu.addSeparator()
        act_log = menu.addAction(tr("log_show_log", "显示日志"))
        act_blame = menu.addAction(tr("log_blame", "Blame"))
        menu.addSeparator()
        act_copy = menu.addAction(tr("log_copy_rel", "相对路径"))
        chosen = menu.exec(self.file_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_cmp:
            self._open_compare(p)
        elif chosen is act_gnu:
            self._show_patch(p)
        elif chosen is act_log:
            from .logdlg import LogDlg
            LogDlg(self.repo, pathspec=path, rev=self.rev2, parent=self).exec()
        elif chosen is act_blame:
            from .blamedlg import BlameDlg
            BlameDlg(self.repo, path, rev=self.rev2 or self.rev1, parent=self).exec()

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