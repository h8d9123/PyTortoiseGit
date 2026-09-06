"""statgraphdlg.py —— StatGraphDlg：提交统计（IDD_STATGRAPH 模板）。

363x249 "Statistics"：Graph type + 统计信息（提交/作者/文件变更等）。
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
    QComboBox, QDialog, QLabel, QPushButton,
)
from ..asyncfw import run_async
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class StatGraphDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        self._load()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_STATGRAPH")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Statistics")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.type_label = QLabel(tr("stat_type", "Graph type:"), self)
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["Commits per author", "Commits per week",
                                  "Authors"]) 
        self.type_combo.currentIndexChanged.connect(self._load)
        self.graph_label = QLabel(tr("stat_graph", ""), self)
        self.graph_label.setWordWrap(True)
        self.num_weeks_label = QLabel(tr("stat_numweeks", "Number of weeks:"), self)
        self.num_weeks_value = QLabel("", self)
        self.num_author_label = QLabel(tr("stat_numauthor", "Number of authors:"), self)
        self.num_author_value = QLabel("", self)
        self.num_commits_label = QLabel(tr("stat_numcommits", "Total commits analyzed:"), self)
        self.num_commits_value = QLabel("", self)
        self.num_filechanges_label = QLabel(tr("stat_numfiles", "Total file changes:"), self)
        self.num_filechanges_value = QLabel("", self)
        self.btn_calc = QPushButton(tr("stat_calc", "Calculate"), self)
        self.btn_calc.clicked.connect(self._load)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)

        mapping = {
            "IDC_GRAPHTYPELABEL": self.type_label,
            "IDC_GRAPHCOMBO": self.type_combo,
            "IDC_GRAPH": self.graph_label,
            "IDC_NUMWEEK": self.num_weeks_label,
            "IDC_NUMWEEKVALUE": self.num_weeks_value,
            "IDC_NUMAUTHOR": self.num_author_label,
            "IDC_NUMAUTHORVALUE": self.num_author_value,
            "IDC_NUMCOMMITS": self.num_commits_label,
            "IDC_NUMCOMMITSVALUE": self.num_commits_value,
            "IDC_NUMFILECHANGES": self.num_filechanges_label,
            "IDC_NUMFILECHANGESVALUE": self.num_filechanges_value,
            "IDC_CALC_DIFF": self.btn_calc,
            "IDOK": self.btn_ok,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _load(self):
        out = self.repo.runner.run(
            "log", "--pretty=%an|%ad", "--date=short").stdout or ""
        lines = [l for l in out.splitlines() if l.strip()]
        authors = {}
        weeks = {}
        for line in lines:
            author, _, date = line.partition("|")
            authors[author] = authors.get(author, 0) + 1
            wk = (date or "")[:-2]
            weeks[wk] = weeks.get(wk, 0) + 1
        commits = len(lines)
        top = []
        if self.type_combo.currentIndex() == 0:
            top = sorted(authors.items(), key=lambda kv: -kv[1])
        elif self.type_combo.currentIndex() == 1:
            top = sorted(weeks.items(), key=lambda kv: kv[0])[-16:]
        else:
            top = sorted(authors.items(), key=lambda kv: kv[0])
        n = 12
        rows = [f"{name}: {count}" for name, count in top[:n]]
        self.graph_label.setText("\n".join(rows))
        self.num_commits_value.setText(str(commits))
        self.num_author_value.setText(str(len(authors)))
        self.num_weeks_value.setText(str(len(weeks)))