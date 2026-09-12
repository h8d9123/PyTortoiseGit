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
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
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


def load_reflog(repo: Repository, ref: str = "HEAD",
                limit: int = 500) -> List[ReflogEntry]:
    """读取指定引用的 reflog。\x1f 为记录前缀，\x1e 为字段分隔（与 log 一致）。"""
    fmt = "--format=\x1f%h\x1e%gd\x1e%gs\x1e%ci\x1e%ce"
    args = ["reflog", "show", ref or "HEAD", "--date=iso", fmt]
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
        self._search_row = 0
        self._search_dlg: Optional["ReflogSearchDlg"] = None
        self.setWindowTitle(f"{repo.name} — {tr('reflog_title', 'Reference log (reflog)')}")
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
            [tr("reflog_selector", "Selector"), tr("log_revision", "Revision"),
             tr("log_date", "Date"), tr("log_message", "Message")])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_menu)
        self.table.currentCellChanged.connect(
            lambda row, *_a: self._sync_search_row(row))

        from PySide6.QtWidgets import QComboBox, QPushButton, QLabel
        self.ref_combo = QComboBox(self)
        self.ref_combo.setEditable(True)
        # IDC_STATIC_REF 模板文本为 "&Ref:"（27 DLU），不能放长描述，否则会被裁切。
        self.ref_label = QLabel(tr("reflog_ref", "&Ref:"), self)
        self.ref_label.setToolTip(tr("reflog_hint", "Reflog of the current branch"))
        self.ref_combo.activated.connect(lambda *_a: self._load())
        self.btn_search = QPushButton(tr("reflog_search", "&Search..."), self)
        self.btn_search.clicked.connect(self._on_search)
        self.btn_clearstash = QPushButton(tr("reflog_clearstash", "&Clear stash"), self)
        self.btn_clearstash.clicked.connect(self._on_clear_stash)
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

        # IDC_STATIC_REF 模板仅 27 DLU，中文标签（如 "引用(&R):"）会被裁切，
        # 按实际文本宽度放宽（不侵入右侧 combo）。
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.ref_label.font())
        need = fm.horizontalAdvance(self.ref_label.text()) + 4
        if self.ref_combo is not None:
            need = min(need, self.ref_combo.x() - self.ref_label.x() - 4)
        self.ref_label.setFixedWidth(max(self.ref_label.width(), need))

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
        ref = self.ref_combo.currentText().strip() or "HEAD"
        entries = load_reflog(self.repo, ref=ref)
        self.entries = entries
        self._search_row = 0
        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            cols = [e.selector, e.short, e.date, e.subject]
            for col, text in enumerate(cols):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.ItemDataRole.UserRole, e.hash_)
                self.table.setItem(row, col, item)

    def _sync_search_row(self, row: int):
        if 0 <= row < len(self.entries):
            self._search_row = row

    def _on_search(self):
        if self._search_dlg is None:
            self._search_dlg = ReflogSearchDlg(self)
        dlg = self._search_dlg
        dlg.adjustSize()
        # 居中于父窗口，避免出现在屏幕角落或被父窗口遮住。
        center = self.frameGeometry().center()
        dlg.move(center.x() - dlg.width() // 2, center.y() - dlg.height() // 2)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        dlg.edit.setFocus()
        dlg.edit.selectAll()

    @staticmethod
    def _entry_text(e: ReflogEntry) -> str:
        return "\n".join((e.selector, e.short, e.hash_, e.date,
                          e.subject, e.author_email))

    def find(self, text: str, match_case: bool = False,
             forward: bool = True) -> bool:
        """从当前行开始查找匹配的 reflog 条目，命中则选中并返回 True。

        与 TortoiseGit 一致：环绕查找，逐行匹配 选择器/哈希/日期/消息/作者。
        """
        if not text or not self.entries:
            return False
        needle = text if match_case else text.casefold()
        count = len(self.entries)
        step = 1 if forward else -1
        row = (self._search_row + step) % count
        for _ in range(count):
            hay = self._entry_text(self.entries[row])
            if not match_case:
                hay = hay.casefold()
            if needle in hay:
                self.table.setCurrentCell(row, 0)
                self.table.selectRow(row)
                item = self.table.item(row, 0)
                if item is not None:
                    self.table.scrollToItem(item)
                self._search_row = row
                return True
            row = (row + step) % count
        return False

    def _on_clear_stash(self):
        """IDC_REFLOG_BUTTONCLEARSTASH：清空所有 stash。"""
        resp = QMessageBox.question(
            self, tr("reflog_clearstash", "Clear stash"),
            tr("reflog_clearstash_confirm", "Delete all stash entries?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        self.repo.runner.run("stash", "clear")
        self._load()

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
        act_copy = menu.addAction(tr("log_copyhash", "Copy full hash"))
        act_checkout = menu.addAction(tr("log_checkout", "Checkout this commit…"))
        act_branch = menu.addAction(tr("log_newbranch", "Create branch here…"))
        act_diff = menu.addAction(tr("log_diff", "Compare with this commit…"))
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


class ReflogSearchDlg(QDialog):
    """Reflog 查找对话框：查找上一个 / 下一个（对齐原版 CFindReplaceDialog）。"""

    def __init__(self, reflog: ReflogDlg):
        # Tool 窗口：始终浮于父窗口之上（对齐原版 FindReplaceDialog）。
        super().__init__(reflog, Qt.WindowType.Tool)
        self.reflog = reflog
        self.setWindowTitle(tr("find_title", "Find/Replace"))
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("find_label", "Find what:"), self))
        self.edit = QLineEdit(self)
        row.addWidget(self.edit, 1)
        layout.addLayout(row)
        self.chk_case = QCheckBox(tr("find_case", "Match case"), self)
        layout.addWidget(self.chk_case)
        buttons = QHBoxLayout()
        self.btn_prev = QPushButton(tr("tm_find_prev", "Find Previous"), self)
        self.btn_next = QPushButton(tr("tm_find_next", "Find Next"), self)
        self.btn_close = QPushButton(tr("close", "Close"), self)
        for b in (self.btn_prev, self.btn_next, self.btn_close):
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self.status = QLabel("", self)
        layout.addWidget(self.status)

        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(lambda: self._do_find(True))
        self.btn_prev.clicked.connect(lambda: self._do_find(False))
        self.btn_close.clicked.connect(self.close)
        self.edit.returnPressed.connect(lambda: self._do_find(True))
        self.edit.textChanged.connect(self._reset_status)

    def _reset_status(self):
        self.status.clear()

    def _do_find(self, forward: bool):
        text = self.edit.text()
        if not text:
            return
        if self.reflog.find(text, self.chk_case.isChecked(), forward):
            self.status.clear()
        else:
            self.status.setText(tr("find_notfound", "Not found"))
