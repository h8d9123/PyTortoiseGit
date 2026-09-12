"""firststartdlg.py —— FirstStartWizard：首次启动向导（镜像 TortoiseGit 5 页模板）。

页序（对齐原版 CFirstStartWizard）：Language → Start → Git → User → Authentication。
每页按 IDD_FIRSTSTARTWIZARD_* 模板绝对定位；模板中重复的 IDC_STATIC 标签
（解析时被去重）在此显式补回。
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
import shutil
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QWizard,
    QWizardPage,
)

from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class _WizardPage(QWizardPage):
    """按 IDD_FIRSTSTARTWIZARD_* 模板排版的一页。"""

    def __init__(self, template: str, parent=None):
        super().__init__(parent)
        self.template = template
        self._spec = rc_mod.load_spec(template)
        self._fu = DialogUnits(self._spec.font_size or 9,
                               self._spec.font or "Segoe UI")
        r = self._fu.px(0, 0, self._spec.width, self._spec.height)
        self.setMinimumSize(r.width(), r.height())

    def _place(self, wgt, x, y, w, h):
        wgt.setParent(self)
        wgt.setGeometry(self._fu.px(x, y, w, h))
        return wgt

    def _label(self, text, x, y, w, h, wrap=False):
        lbl = QLabel(text, self)
        lbl.setWordWrap(wrap)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return self._place(lbl, x, y, w, h)


class _StartPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_START", parent)
        self.setTitle(tr("firststart_title", "Welcome to PyTortoiseGit"))
        self._label(tr(
            "firststart_hint",
            "This wizard guides you through the basic Git configuration:\n"
            "1. Choose the interface language\n"
            "2. Locate git.exe\n"
            "3. Enter your name and e-mail address\n"
            "4. Choose the SSH client\n"), 17, 7, 289, 135, wrap=True)


class _LanguagePage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_LANGUAGE", parent)
        self.setTitle(tr("firststart_language", "Interface language"))
        self._label(tr("firststart_lang_hint",
                       "Choose the interface language."),
                    17, 7, 289, 67, wrap=True)
        self._label(tr("firststart_lang", "&Language:"), 17, 82, 86, 8)
        self.lang_combo = self._place(QComboBox(self), 111, 80, 129, 14)
        self.lang_combo.addItems(["English", "简体中文", "繁體中文", "Deutsch"])
        self._label(tr("fs_lang_download", "Download language packs:"),
                    17, 100, 289, 8)
        self.link_label = self._label("", 17, 110, 289, 10)
        self.btn_refresh = self._place(
            QPushButton(tr("refresh"), self), 245, 80, 61, 14)

    def selected_language(self) -> str:
        return {
            "English": "English",
            "简体中文": "zh_CN",
            "繁體中文": "zh_TW",
            "Deutsch": "Deutsch",
        }.get(self.lang_combo.currentText(), "English")


class _GitPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_GIT", parent)
        self.setTitle(tr("firststart_git", "Git executable"))
        self._label(tr(
            "fs_git_info",
            "TortoiseGit requires a git.exe for its operations. TortoiseGit "
            "tries to automatically detect a working git.exe, but if that "
            "doesn't work or you want to use a different one please specify "
            "the path manually!"), 17, 7, 289, 32, wrap=True)
        self._label(tr("fs_git_path_label", "&Git.exe Path:"), 18, 50, 58, 8)
        self.git_path = self._place(
            QLineEdit(shutil.which("git") or "", self), 80, 47, 202, 14)
        self.btn_browse = self._place(QPushButton("...", self), 287, 47, 19, 14)
        self._label(tr("fs_extra_path_label", "&Extra PATH:"), 17, 73, 58, 8)
        self.extern_path = self._place(QLineEdit("", self), 80, 70, 202, 14)
        self.git_ver = self._label("", 17, 94, 141, 8)
        self.btn_check = self._place(
            QPushButton(tr("firststart_check", "C&heck now"), self),
            210, 91, 72, 14)
        self.btn_check.clicked.connect(self._check)
        self._label(tr("fs_git_recommended", "Recommended: Git for Windows"),
                    17, 110, 289, 9)
        self.link_label = self._label("", 17, 121, 289, 10)
        # 原版这些项默认隐藏/禁用
        self.chk_workarounds = self._place(QCheckBox(tr(
            "fs_git_workarounds",
            "I don't use Git for Windows and need special workarounds"), self),
            17, 136, 289, 11)
        self.rad_cygwin = self._place(QRadioButton(tr(
            "fs_git_hack1", "Enable special hack for Cygwin git"), self),
            17, 150, 289, 11)
        self.rad_msys2 = self._place(QRadioButton(tr(
            "fs_git_hack2", "Enable special hack for Msys2 git"), self),
            17, 164, 289, 11)
        for w in (self.chk_workarounds, self.rad_cygwin, self.rad_msys2):
            w.setVisible(False)
            w.setEnabled(False)
        self._check()

    def _check(self):
        git = self.git_path.text().strip() or shutil.which("git")
        if git:
            try:
                out = subprocess.run([git, "--version"], capture_output=True,
                                     text=True).stdout.strip()
                self.git_ver.setText(f"Git: {out}")
            except Exception:  # noqa: BLE001
                self.git_ver.setText("")

    def isComplete(self):  # noqa: N802
        return bool(self.git_path.text().strip() or shutil.which("git"))


class _UserPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_USER", parent)
        self.setTitle(tr("firststart_user", "User information"))
        self._label(tr(
            "fs_user_intro",
            "Git requires that you set up a user name and email address. Both "
            "are used as meta data for your commits (not for authentication)."),
            17, 7, 289, 25, wrap=True)
        self._label(tr("firststart_name", "&Name:"), 17, 42, 47, 8)
        self.name_edit = self._place(QLineEdit("", self), 71, 40, 150, 12)
        self._label(tr("fs_email_label", "&Email:"), 17, 60, 50, 8)
        self.email_edit = self._place(QLineEdit("", self), 71, 57, 150, 12)
        self._label(tr(
            "fs_user_footer",
            "These settings will be stored to your global git configuration "
            "(%HOME%/.gitconfig) and will be used for all your git repositories "
            "as a default."), 17, 81, 289, 30, wrap=True)
        self.chk_dontsave = self._place(QCheckBox(
            tr("firststart_dontsave", "&Don't store these settings now."), self),
            17, 118, 289, 11)


class _AuthPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_AUTHENTICATION", parent)
        self.setTitle(tr("firststart_auth", "Authentication"))
        self._place(QGroupBox(tr(
            "firststart_ssh", 'SSH (URLs look like "git@example.com")'), self),
            7, 7, 308, 84)
        self.ssh_hint = self._label(tr(
            "firststart_ssh_hint", "Choose the SSH client."),
            17, 17, 289, 56, wrap=True)
        self.ssh_combo = self._place(QComboBox(self), 17, 74, 144, 14)
        self.ssh_combo.addItems(["PuTTY (TortoiseGitPlink)", "ssh.exe (OpenSSH)"])
        self.btn_genkey = self._place(
            QPushButton(tr("firststart_genkey", "&Generate PuTTY key pair"), self),
            169, 73, 137, 14)
        self._place(QGroupBox(tr(
            "fs_auth_http_group",
            'HTTP (URLs start with "http://" or "https://")'), self),
            7, 92, 308, 95)
        self._label(tr(
            "fs_auth_http_desc",
            "By default Git does not save/cache credentials. However, you can "
            "configure a credential helper (recommended) or manually use "
            "%HOME%/_netrc."), 17, 103, 289, 25, wrap=True)
        self._label(tr("fs_auth_cred_label", "&Credential helper:"),
                    17, 131, 145, 8)
        self.cred_combo = self._place(QComboBox(self), 189, 128, 117, 14)
        self.cred_combo.addItems(
            ["Automatic", "Store in memory", "Use credential helper"])
        self.chk_dontsave = self._place(QCheckBox(
            tr("firststart_dontsave", "&Don't store these settings now."), self),
            17, 145, 172, 11)
        self.btn_adv = self._place(
            QPushButton(tr("firststart_adv", "&Advanced..."), self),
            189, 144, 117, 14)
        self._label(tr(
            "fs_auth_footer",
            "These settings will be stored to your global git configuration "
            "(%HOME%/.gitconfig) and will be used for all your git repositories "
            "as a default."), 17, 160, 289, 25, wrap=True)


class FirstStartWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            tr("firststart_title", "First Start Wizard - PyTortoiseGit"))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self._language_page = _LanguagePage(self)
        self._start_page = _StartPage(self)
        # 页序对齐原版 CFirstStartWizard
        self._pages = [self._language_page, self._start_page,
                       _GitPage(self), _UserPage(self), _AuthPage(self)]
        for p in self._pages:
            self.addPage(p)
        self.language = "English"

    def exec_wizard(self) -> bool:
        result = self.exec()
        ok = (result == QWizard.DialogCode.Accepted
              if hasattr(QWizard, "DialogCode") else result == 1)
        if ok:
            self.language = self._language_page.selected_language()
            from ..res.strings import set_language
            set_language(self.language)
            try:
                from .settingsdlg import general_settings
                general_settings().setValue("language", self.language)
            except Exception:  # noqa: BLE001
                pass
        return ok
