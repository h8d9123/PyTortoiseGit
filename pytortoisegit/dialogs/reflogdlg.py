"""reflogdlg.py —— ReflogDlg：reflog 查看/操作对话框。

镜像 TortoiseGit 的 ReflogDlg 的简化实现：
  - 列出 reflog 条目（选择器/修订/时间/消息）
  - 右键：复制哈希、检出、在此创建分支、与此提交比较
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

from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from ..git.repo import Repository
from ..res.strings import tr
from .diffdlg import DiffDlg


@dataclass
class ReflogEntry:
    selector: str = ""        # HEAD@{0}
    hash_: str = ""           # 新提交哈希（短）
    date: str = ""            # iso 时间
    subject: str = ""         # reflog 消息（动作描述）
    author_email: str = ""

    @property
    def short(self) -> str:
        return self.hash_[:8]

    @property
    def full_line(self) -> str:
        return f"{self.short} {self.subject}"


def load_reflog(repo: Repository, limit: int = 500) -> List[ReflogEntry]:
    """读取 reflog。\x1f 为记录前缀，\x1e 为字段分隔（与 log 一致）。"""
    fmt = "--format=\x1f%h\x1e%gd\x1e%gs\x1e%ci\x1e%ce"
    args = ["reflog", "--date=iso", fmt]
    if limit > 0:
        args += ["-n", str(limit)]
    out = repo.runner.run(*args).stdout or ""
    entries: List[ReflogEntry] = []
    for record in out.split("\x1f"):
        record = record.strip()
        if not record:
            continue
        fields = record.split("\x1e")
        if len(fields) < 4:
            continue
        entries.append(ReflogEntry(
            selector=fields[1] if len(fields) > 1 else "",
            hash_=fields[0],
            subject=fields[2] if len(fields) > 2 else "",
            date=fields[3] if len(fields) > 3 else "",
            author_email=fields[4] if len(fields) > 4 else "",
        ))
    return entries


class ReflogDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.entries: List[ReflogEntry] = []
        self.setWindowTitle(f"{repo.name} — {tr('reflog_title', '引用日志 (reflog)')}")
        self.resize(820, 520)
        self._build_ui()
        self._load()

    def _build_ui(self):
        from ..ui import rc as rc_mod
        from ..ui.rc import DialogUnits
        spec = rc_mod.load_spec("IDD_REFLOG")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(
            [tr("reflog_selector", "选择器"), tr("log_revision", "修订"),
             tr("log_date", "日期"), tr("log_message", "消息")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_menu)

        from PySide6.QtWidgets import QComboBox, QPushButton, QLabel
        self.ref_combo = QComboBox(self)
        self.ref_combo.setEditable(True)
        self.ref_label = QLabel(tr("reflog_hint", "当前分支的 reflog"), self)
        self.ref_combo.editTextChanged.connect(lambda *_a: self._load())
        self.btn_search = QPushButton(tr("reflog_search", "&Search..."), self)
        self.btn_search.clicked.connect(self._load)
        self.btn_clearstash = QPushButton(tr("reflog_clearstash", "&Clear stash"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_STATIC_REF": self.ref_label,
            "IDC_COMBOBOXEX_REF": self.ref_combo,
            "IDC_REFLOG_LIST": self.table,
            "IDC_SEARCH": self.btn_search,
            "IDC_REFLOG_BUTTONCLEARSTASH": self.btn_clearstash,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)

        # ref 列表填充
        try:
            refs = self.repo.runner.run(
                "for-each-ref", "--format=%(refname:short)").stdout or ""
            refs = [r.strip() for r in refs.splitlines() if r.strip()]
            self.ref_combo.addItems([r for r in refs
                                     if not r.startswith(("tags/", "remotes/"))])
            self.ref_combo.addItem("HEAD")
            self.ref_combo.setCurrentText("HEAD")
        except Exception:
            pass

    def _load(self):
        entries = load_reflog(self.repo)
        self.entries = entries
        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            cols = [e.selector, e.short, e.date, e.subject]
            for col, text in enumerate(cols):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.ItemDataRole.UserRole, e.hash_)
                self.table.setItem(row, col, item)

    def _current_entry(self) -> Optional[ReflogEntry]:
        row = self.table.currentRow()
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None

    def _on_menu(self, pos):
        entry = self._current_entry()
        if entry is None:
            return
        menu = QMenu(self)
        act_copy = menu.addAction(tr("log_copyhash", "复制完整哈希"))
        act_checkout = menu.addAction(tr("log_checkout", "检出此提交…"))
        act_branch = menu.addAction(tr("log_newbranch", "在此创建分支…"))
        act_diff = menu.addAction(tr("log_diff", "与此提交比较…"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(entry.hash_)
        elif chosen is act_checkout:
            result = self.repo.runner.run("checkout", entry.hash_)
            if result.returncode != 0:
                QMessageBox.warning(self, tr("error"), result.stderr)
            else:
                self._load()
        elif chosen is act_branch:
            from .createbranchdlg import CreateBranchDlg
            dlg = CreateBranchDlg(self.repo, start=entry.hash_, parent=self)
            dlg.exec()
        elif chosen is act_diff:
            parent = f"{entry.hash_}^"
            has_parent = self.repo.runner.run("rev-parse", "--verify",
                                              parent + "^{commit}").returncode == 0
            DiffDlg(self.repo, parent if has_parent else entry.hash_,
                    entry.hash_ if has_parent else None,
                    parent=self).exec()