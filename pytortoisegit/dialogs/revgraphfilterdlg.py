"""revgraphfilterdlg.py —— RevGraphFilterDlg：修订图过滤（IDD_REVGRAPHFILTER 模板）。

303x108 "Revision Graph Filter"：从/到修订范围 + Only Current Branch / Local Branches。

对齐 RevGraphFilterDlg.cpp：
  * 勾选 Only Current Branch / Only Local Branches 互斥，并禁用并清空 To 字段；
  * From 始终可用；
  * Reset filter 清空后**立即接受对话框**，使过滤马上生效（原版 Reset 里直接
    调 OnOK）。
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
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QLabel, QLineEdit, QPushButton,
)

from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout

# 原版 rc 里 "From:"/"To:" 两个 LTEXT 都用 IDC_STATIC，提取模板时被去重丢弃，
# 这里按 rc 的 DLU 坐标补回（IDD_REVGRAPHFILTER: LTEXT 12,24,30,8 / 12,46,30,8）。
_EXTRA_LABELS = (
    ("revf_from", "From:", 12, 24, 30, 8),
    ("revf_to", "To:", 12, 46, 30, 8),
)


class RevGraphFilterDlg(QDialog):
    """修订图过滤对话框。"""

    def __init__(self, repo: Repository, parent=None,
                 state: Optional[dict] = None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._syncing = False
        spec = rc_mod.load_spec("IDD_REVGRAPHFILTER")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Revision Graph Filter")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.hint = QLabel(tr("revf_hint", "Include only the following revision range:"), self)
        self.from_edit = QLineEdit(self)
        self.btn_from = QPushButton("RefBrowser", self)
        self.btn_from.clicked.connect(self._browse_from)
        self.to_edit = QLineEdit(self)
        self.btn_to = QPushButton("RefBrowser", self)
        self.btn_to.clicked.connect(self._browse_to)
        self.chk_current = QCheckBox(tr("revf_current", "Only Current Branch"), self)
        self.chk_local = QCheckBox(tr("revf_local", "Only Local Branches"), self)
        self.btn_ok = QPushButton(tr("revf_ok", "&OK"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_reset = QPushButton(tr("revf_reset", "&Reset filter"), self)
        self.btn_reset.clicked.connect(self._reset)

        mapping = {
            "IDC_STATIC": self.hint,
            "IDC_FROMREV": self.from_edit,
            "IDC_REV1BTN1": self.btn_from,
            "IDC_TOREV": self.to_edit,
            "IDC_REV1BTN2": self.btn_to,
            "IDC_CURRENT_BRANCH": self.chk_current,
            "IDC_LOCAL_BRANCHES": self.chk_local,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDC_RESETFILTER": self.btn_reset,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        for key, text, x, y, w, h in _EXTRA_LABELS:
            lbl = QLabel(tr(key, text), self)
            rc_mod.place_widget(self, fu, _label_spec(key, text, x, y, w, h), lbl)
            self._ctl[key] = lbl
            self._anchors.add(lbl, "TOP_LEFT")

        self.chk_current.toggled.connect(self._on_toggle)
        self.chk_local.toggled.connect(self._on_toggle)

        self.set_state(state or {})

    # ---- 状态 ----
    def state(self) -> dict:
        """当前过滤条件（供调用方拼 git 修订范围）。"""
        return {
            "from_rev": self.from_edit.text().strip(),
            "to_rev": self.to_edit.text().strip(),
            "current_branch": self.chk_current.isChecked(),
            "local_branches": self.chk_local.isChecked(),
        }

    def set_state(self, state: dict) -> None:
        self._syncing = True
        try:
            self.from_edit.setText(str(state.get("from_rev", "") or ""))
            self.to_edit.setText(str(state.get("to_rev", "") or ""))
            self.chk_current.setChecked(bool(state.get("current_branch")))
            self.chk_local.setChecked(bool(state.get("local_branches")))
        finally:
            self._syncing = False
        self._sync_enabled()

    def _on_toggle(self, _checked: bool) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            # 两者互斥：勾上一个就取消另一个
            if self.sender() is self.chk_current and self.chk_current.isChecked():
                self.chk_local.setChecked(False)
            elif self.sender() is self.chk_local and self.chk_local.isChecked():
                self.chk_current.setChecked(False)
        finally:
            self._syncing = False
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        cur = self.chk_current.isChecked()
        loc = self.chk_local.isChecked()
        self.chk_current.setEnabled(not loc)
        self.chk_local.setEnabled(not cur)
        # 勾上任一分支选项后，To 字段被禁用并清空（From 始终可用）
        to_enabled = not (cur or loc)
        self.to_edit.setEnabled(to_enabled)
        self.btn_to.setEnabled(to_enabled)
        if not to_enabled:
            self.to_edit.clear()

    # ---- RefBrowser ----
    def _pick_ref(self) -> str:
        from .browserefs import BrowseRefsDlg
        dlg = BrowseRefsDlg(self.repo, parent=self)
        if not dlg.exec():
            return ""
        picked = dlg._selected()
        ref = picked[0] if picked else None
        return str(ref) if ref else ""

    def _browse_from(self):
        ref = self._pick_ref()
        if ref:
            self.from_edit.setText(ref)

    def _browse_to(self):
        ref = self._pick_ref()
        if ref:
            self.to_edit.setText(ref)

    def _reset(self):
        """原版 Reset：清空后立即 OnOK，使过滤马上生效。"""
        self.set_state({})
        self.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())


def _label_spec(key: str, text: str, x: int, y: int, w: int, h: int):
    from ..ui.rc import Control
    return Control(kind="LTEXT", text=text, ctrl_id=key, cls="", style="",
                   x=x, y=y, w=w, h=h)
