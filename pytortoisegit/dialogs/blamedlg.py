"""blamedlg.py —— BlameDlg：逐行标注视图。"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..asyncfw import run_async
from ..blame import BlameLine, GitBlame
from ..git.repo import Repository
from ..res.strings import tr
from .widgets import author_color


class BlameDlg(QDialog):
    def __init__(self, repo: Repository, filepath: str,
                 rev: str | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.filepath = filepath
        self.rev = rev
        self.setWindowTitle(f"{repo.name} — {self.filepath}")
        self.resize(980, 640)
        self._build_ui()
        run_async(self._blame_bg, on_done=self._on_loaded,
                  on_error=lambda msg, _tb: self._header_set(f"★ {tr('blame_error', 'Error')}: {msg}"),
                  parent=self)

    def _build_ui(self):
        from PySide6.QtWidgets import QLabel
        lay = QVBoxLayout(self)
        self._header = QLabel("-", self)
        lay.addWidget(self._header)
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([tr("blame_col_line", "Line"), tr("blame_col_commit", "Commit"),
                tr("blame_col_author", "Author"), tr("blame_col_date", "Date"),
                tr("blame_col_code", "Code")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.table.setFont(font)
        lay.addWidget(self.table, 1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.StandardButton.Close).setText(tr("close"))
        lay.addWidget(box)

    def _header_set(self, text: str):
        self._header.setText(text)

    def _blame_bg(self) -> List[BlameLine]:
        return GitBlame(self.repo).blame(self.filepath, rev=self.rev)

    def _on_loaded(self, lines: List[BlameLine]):
        color = author_color("")
        root = Qt.ItemDataRole.BackgroundRole
        self.table.setRowCount(len(lines))
        for row, bl in enumerate(lines):
            c = author_color(bl.author)
            brush = QBrush(QColor(c))
            items = [
                QTableWidgetItem(str(row + 1)),
                QTableWidgetItem(bl.short_sha),
                QTableWidgetItem(bl.author),
                QTableWidgetItem(bl.date_span()),
                QTableWidgetItem(bl.content),
            ]
            for it in items:
                it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                it.setBackground(brush)
            self.table.setItem(row, 0, items[0])
            self.table.setItem(row, 1, items[1])
            self.table.setItem(row, 2, items[2])
            self.table.setItem(row, 3, items[3])
            self.table.setItem(row, 4, items[4])
            items[1].setData(Qt.ItemDataRole.UserRole, bl.sha)
        self._header_set(f" {self.filepath} — {len(lines)} {tr('blame_lines', 'lines')}")

    def _on_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        sha_item = self.table.item(row, 1)
        if sha_item is None:
            return
        sha = sha_item.data(Qt.ItemDataRole.UserRole) or sha_item.text()
        menu = QMenu(self)
        act_copy = menu.addAction(tr("log_copyhash", "Copy full hash"))
        act_log = menu.addAction(tr("menu_show_log", "Show log for this commit"))
        act_copy_short = menu.addAction(tr("log_copyshort", "Copy short hash"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(sha)
        elif chosen is act_copy_short:
            ClipboardHelper().copy_text(sha[:8])
        elif chosen is act_log:
            from .logdlg import LogDlg
            LogDlg(self.repo, pathspec=None, rev=str(sha), parent=self).exec()

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
