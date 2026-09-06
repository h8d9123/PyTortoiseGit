"""sendmaildlg.py —— SendMailDlg：发送补丁邮件（IDD_SENDMAIL 模板）。

381x229 "Send Patch"：To/Cc/Subject + Patch As Attachment/Combine + 补丁列表。
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
    QCheckBox, QDialog, QLabel, QLineEdit, QPushButton, QTreeWidget,
    QTreeWidgetItem,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class SendMailDlg(QDialog):
    def __init__(self, repo: Repository, patches=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        spec = rc_mod.load_spec("IDD_SENDMAIL")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Send Patch")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.to_label = QLabel(tr("mail_to", "To:"), self)
        self.to_edit = QLineEdit(self)
        self.cc_edit = QLineEdit(self)
        self.subject_edit = QLineEdit(self)
        self.chk_attach = QCheckBox(tr("mail_attach", "Patch As Attachment"), self)
        self.chk_combine = QCheckBox(tr("mail_combine", "Combine One Mail"), self)
        self.setup_label = QLabel(tr("mail_setup", "eMail settings"), self)
        self.patch_list = QTreeWidget(self)
        self.patch_list.setColumnCount(1)
        self.patch_list.setRootIsDecorated(False)
        self.btn_send = QPushButton(tr("mail_send", "Send"), self)
        self.btn_send.setDefault(True)
        self.btn_send.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_STATIC": self.to_label,
            "IDC_SENDMAIL_TO": self.to_edit,
            "IDC_SENDMAIL_CC": self.cc_edit,
            "IDC_SENDMAIL_SUBJECT": self.subject_edit,
            "IDC_SENDMAIL_ATTACHMENT": self.chk_attach,
            "IDC_SENDMAIL_COMBINE": self.chk_combine,
            "IDC_SENDMAIL_SETUP": self.setup_label,
            "IDC_SENDMAIL_PATCHS": self.patch_list,
            "IDOK": self.btn_send,
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

        for p in (patches or []):
            self.patch_list.addTopLevelItem(QTreeWidgetItem([p]))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())


_ANCHORS = {
    "IDC_SENDMAIL_TO": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_SENDMAIL_CC": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_SENDMAIL_SUBJECT": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_SENDMAIL_PATCHS": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}