"""credentialdlg.py —— 认证提示对话框（镜像 TortoiseGit 认证系列模板）。

包含 IDD_PROMPT / IDD_SIMPLEPROMPT / IDD_USER_PASSWD / IDD_CERTCHECK。
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
    QCheckBox, QDialog, QLabel, QLineEdit, QPushButton,
)
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class _BasePrompt(QDialog):
    def __init__(self, name: str, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self._spec = rc_mod.load_spec(name)
        self._fu = DialogUnits(self._spec.font_size or 9,
                               self._spec.font or "Segoe UI")
        r = self._fu.px(0, 0, self._spec.width, self._spec.height)
        self.resize(r.width(), r.height())

    def _place(self, mapping):
        for ctrl in self._spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, self._fu, ctrl, wgt)


class PromptDlg(_BasePrompt):
    """IDD_PROMPT：用户名 + save auth。"""

    def __init__(self, realm="", user="", parent=None):
        super().__init__("IDD_PROMPT", parent)
        self.setWindowTitle(tr("auth_title", "Authentication"))
        self.username_label = QLabel(tr("auth_user", "&Username:"), self)
        self.user_edit = QLineEdit(self)
        self.user_edit.setText(user)
        self.chk_save = QCheckBox(tr("auth_save", "&Save authentication"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self._place({
            "IDC_INFOTEXT": self.username_label,
            "IDC_PASSEDIT": self.user_edit,
            "IDC_SAVECHECK": self.chk_save,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        })
        self.username = ""
        self.accepted_ok = False

    def accept(self):
        self.username = self.user_edit.text().strip()
        self.accepted_ok = True
        super().accept()


class SimplePromptDlg(_BasePrompt):
    """IDD_SIMPLEPROMPT：realm + user + pass + save auth。"""

    def __init__(self, realm="", user="", parent=None):
        super().__init__("IDD_SIMPLEPROMPT", parent)
        self.setWindowTitle(tr("auth_title", "Authentication"))
        self.realm_label = QLabel(realm, self)
        self.static = QLabel(tr("auth_reqs", "Requests a username and a password"), self)
        self.user_edit = QLineEdit(self)
        self.user_edit.setText(user)
        self.pass_edit = QLineEdit(self)
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.chk_save = QCheckBox(tr("auth_save", "&Save authentication"), self)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self._place({
            "IDC_REALM": self.realm_label,
            "IDC_STATIC": self.static,
            "IDC_USEREDIT": self.user_edit,
            "IDC_PASSEDIT": self.pass_edit,
            "IDC_SAVECHECK": self.chk_save,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        })
        self.username = ""
        self.password = ""
        self.accepted_ok = False

    def accept(self):
        self.username = self.user_edit.text().strip()
        self.password = self.pass_edit.text()
        self.accepted_ok = True
        super().accept()


class UserPasswdDlg(_BasePrompt):
    """IDD_USER_PASSWD：用户名 + 密码。"""

    def __init__(self, user="", passwd="", parent=None):
        super().__init__("IDD_USER_PASSWD", parent)
        self.setWindowTitle(tr("auth_passwd", "Password"))
        self.user_label = QLabel(tr("auth_user", "&Username:"), self)
        self.pass_label = QLabel(tr("auth_passwd_label", "&Password:"), self)
        self.user_edit = QLineEdit(self)
        self.user_edit.setText(user)
        self.pass_edit = QLineEdit(self)
        self.pass_edit.setText(passwd)
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self._place({
            "IDC_LABEL": self.user_label,
            "IDC_LABEL2": self.pass_label,
            "IDC_USER_NAME": self.user_edit,
            "IDC_USER_PASSWORD": self.pass_edit,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        })
        self.username = ""
        self.password = ""
        self.accepted_ok = False

    def accept(self):
        self.username = self.user_edit.text().strip()
        self.password = self.pass_edit.text()
        self.accepted_ok = True
        super().accept()


class CertCheckDlg(_BasePrompt):
    """IDD_CERTCHECK：证书校验。"""

    def __init__(self, errordesc="", error="", commonname="", issuer="",
                 parent=None):
        super().__init__("IDD_CERTCHECK", parent)
        self.setWindowTitle(tr("certcheck_title", "TortoiseGit"))
        self.desc_label = QLabel(
            tr("certcheck_desc", "Certificate verification failed!"), self)
        self.errordesc = QLabel(errordesc, self)
        self.errordesc.setWordWrap(True)
        self.error = QLabel(error, self)
        self.error.setWordWrap(True)
        self.commonname_edit = QLineEdit(self)
        self.commonname_edit.setText(commonname)
        self.issuer_edit = QLineEdit(self)
        self.issuer_edit.setText(issuer)
        self.sha1_edit = QLineEdit(self)
        self.sha1_edit.setReadOnly(True)
        self.sha256_edit = QLineEdit(self)
        self.sha256_edit.setReadOnly(True)
        self.btn_opencert = QPushButton(tr("certcheck_open", "Open certificate"), self)
        self.btn_accept = QPushButton(tr("certcheck_accept", "Accept certificate"), self)
        self.btn_accept.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.setDefault(True)
        self.btn_cancel.clicked.connect(self.reject)
        self._place({
            "IDC_STATIC": self.desc_label,
            "IDC_ERRORDESC": self.errordesc,
            "IDC_ERROR": self.error,
            "IDC_COMMONNAME": self.commonname_edit,
            "IDC_ISSUER": self.issuer_edit,
            "IDC_SHA1": self.sha1_edit,
            "IDC_SHA256": self.sha256_edit,
            "IDC_OPENCERT": self.btn_opencert,
            "IDOK": self.btn_accept,
            "IDCANCEL": self.btn_cancel,
        })