"""revisiongraphdlg.py —— RevisionGraphDlg：修订图（IDD_REVISIONGRAPH 模板）。

264x230 "Revision Graph"（模板无控件=整窗）：
以 git log --graph 渲染提交图。
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
from ..asyncfw import run_async
from ..git.repo import Repository
from ..res.strings import tr
from .statgraphdlg import StatGraphDlg


class RevisionGraphDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.setWindowTitle(tr("revgraph_title", "Revision Graph"))
        self.resize(720, 520)

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels([tr("revgraph_graph", "图 / 提交")])
        self.tree.setUniformRowHeights(True)
        mono = self.tree.font()
        mono.setFamily("Consolas")
        self.tree.setFont(mono)
        self.tree.setGeometry(0, 0, 720, 470)

        self.btn_stats = QPushButton(tr("revgraph_stats", "统计"), self)
        self.btn_stats.setGeometry(560, 480, 150, 30)
        self.btn_stats.clicked.connect(self._open_stats)
        self._load()

    def _load(self):
        self.tree.clear()
        out = self.repo.runner.run("log", "--graph", "--oneline",
                                   "--decorate").stdout or ""
        for line in out.splitlines():
            if line.strip():
                self.tree.addTopLevelItem(QTreeWidgetItem([line]))

    def _open_stats(self):
        StatGraphDlg(self.repo, parent=self).exec()