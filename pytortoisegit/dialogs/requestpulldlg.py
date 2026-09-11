"""requestpulldlg.py —— RequestPullDlg：请求拉取（IDD_REQUESTPULL 模板）。

314x92 "Request pull"：本地分支 + 仓库 URL + End 分支 + Send Mail。
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
    QCheckBox, QComboBox, QDialog, QLabel, QLineEdit, QPushButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout
from .progress import ProgressDialog


class RequestPullDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        spec = rc_mod.load_spec("IDD_REQUESTPULL")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_horizontal_resize(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Request pull")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.local_label = QLabel(tr("req_start", "&Start"), self)
        self.local_combo = QComboBox(self)
        self.local_combo.setEditable(True)
        self.btn_local = QPushButton("...", self)
        self.url_label = QLabel(tr("req_url", "Repository &URL"), self)
        self.url_combo = QComboBox(self)
        self.url_combo.setEditable(True)
        self.remote_label = QLabel(tr("req_end", "End"), self)
        self.remote_edit = QLineEdit(self)
        self.chk_mail = QCheckBox(tr("req_mail", "Send Mail after create"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_request)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_STATIC_LOCAL_BRANCH": self.local_label,
            "IDC_COMBOBOXEX_LOCAL_BRANCH": self.local_combo,
            "IDC_BUTTON_LOCAL_BRANCH": self.btn_local,
            "IDC_STATIC_REMOTE_URL": self.url_label,
            "IDC_COMBOBOXEX_URL": self.url_combo,
            "IDC_STATIC_REMOTE_BRANCH": self.remote_label,
            "IDC_REMOTE_BRANCH": self.remote_edit,
            "IDC_CHECK_SENDMAIL": self.chk_mail,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        out = self.repo.runner.run("for-each-ref",
                                   "--format=%(refname:short)").stdout or ""
        refs = [x.strip() for x in out.splitlines() if x.strip()]
        self.local_combo.addItems([r for r in refs if r.startswith("heads/")])
        url = self.repo.runner.run("remote", "get-url", "origin").stdout or ""
        self.url_combo.addItem(url.strip() or "origin")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _on_request(self):
        local = self.local_combo.currentText().strip()
        url = self.url_combo.currentText().strip()
        remote = self.remote_edit.text().strip()
        # RequestPull 在本地生成一个请求分支并推送，这里简化为创建请求分支提示
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label(f"git refspec {local} -> {url} ({remote})")
        def _bg():
            return True
        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_COMBOBOXEX_LOCAL_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_URL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}