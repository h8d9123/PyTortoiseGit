"""firststartdlg.py —— FirstStartWizard：首次启动向导（镜像 TortoiseGit 5 页模板）。

页序：Start → Language → Git → User → Authentication。
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
    QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton, QWizard,
    QWizardPage,
)
from ..git.git import GitRunner
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class _WizardPage(QWizardPage):
    def __init__(self, template: str, parent=None):
        super().__init__(parent)
        self.template = template


class _StartPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_START", parent)
        self.title = tr("firststart_title", "Welcome to PyTortoiseGit")
        self.setTitle(self.title)
        spec = rc_mod.load_spec("IDD_FIRSTSTARTWIZARD_START")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        hint = QLabel(tr("firststart_hint",
            "This wizard guides you through basic Git configuration:\n"
            "1. Choose the interface language\n2. Locate git.exe\n"
            "3. Enter name/e-mail\n4. Choose the SSH client\n"), self)
        hint.setWordWrap(True)
        ctrl = spec.controls[0]
        hint.setGeometry(fu.px(ctrl.x, ctrl.y, ctrl.w, ctrl.h))


class _LanguagePage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_LANGUAGE", parent)
        self.setTitle(tr("firststart_language", "Interface language"))
        spec = rc_mod.load_spec("IDD_FIRSTSTARTWIZARD_LANGUAGE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")

        def placed(id_, wgt):
            for c in spec.controls:
                if c.ctrl_id == id_:
                    wgt.setGeometry(fu.px(c.x, c.y, c.w, c.h))
                    break
            return wgt
        hint = placed("IDC_FIRSTSTART_HINT", QLabel(
            tr("firststart_lang_hint", "Choose the interface language."), self))
        hint.setWordWrap(True)
        self.lang_label = placed("IDC_STATIC", QLabel(tr("firststart_lang", "&Language:"), self))
        self.lang_combo = placed("IDC_LANGUAGECOMBO", QComboBox(self))
        self.lang_combo.addItems(["English", "简体中文", "繁體中文", "Deutsch"])
        self.btn_refresh = placed("IDC_REFRESH", QPushButton(tr("refresh"), self))
        self.link_label = QLabel("", self)
        for c in spec.controls:
            if c.ctrl_id == "IDC_LINK":
                self.link_label.setGeometry(fu.px(c.x, c.y, c.w, c.h))

    def selected_language(self) -> str:
        """下拉显示名 → 设置里的语言键。"""
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
        spec = rc_mod.load_spec("IDD_FIRSTSTARTWIZARD_GIT")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")

        def placed(id_, wgt):
            for c in spec.controls:
                if c.ctrl_id == id_:
                    wgt.setGeometry(fu.px(c.x, c.y, c.w, c.h))
                    break
            return wgt
        self.info = placed("IDC_STATIC", QLabel(tr("firststart_git_hint", "TortoiseGit requires a git.exe."), self))
        self.info.setWordWrap(True)
        self.git_path = placed("IDC_MSYSGIT_PATH", QLineEdit(
            shutil.which("git") or "", self))
        self.btn_browse = placed("IDC_MSYSGIT_BROWSE", QPushButton("...", self))
        self.extern_path = placed("IDC_MSYSGIT_EXTERN_PATH", QLineEdit("", self))
        self.git_ver = placed("IDC_MSYSGIT_VER", QLabel("", self))
        self.btn_check = placed("IDC_MSYSGIT_CHECK",
                                QPushButton(tr("firststart_check", "C&heck now"), self))
        self.btn_check.clicked.connect(self._check)
        self.link_label = QLabel("", self)
        for c in spec.controls:
            if c.ctrl_id == "IDC_LINK":
                self.link_label.setGeometry(fu.px(c.x, c.y, c.w, c.h))
        self._check()

    def _check(self):
        git = self.git_path.text().strip() or shutil.which("git")
        if git:
            try:
                out = subprocess.run([git, "--version"], capture_output=True,
                                     text=True).stdout.strip()
                self.git_ver.setText(f"Git: {out}")
            except Exception:
                self.git_ver.setText("")

    def isComplete(self):
        g = self.git_path.text().strip() or shutil.which("git")
        return bool(g)


class _UserPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_USER", parent)
        self.setTitle(tr("firststart_user", "User information"))
        spec = rc_mod.load_spec("IDD_FIRSTSTARTWIZARD_USER")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")

        def placed(id_, wgt):
            for c in spec.controls:
                if c.ctrl_id == id_:
                    wgt.setGeometry(fu.px(c.x, c.y, c.w, c.h))
                    break
            return wgt
        self.name_label = placed("IDC_STATIC", QLabel(tr("firststart_name", "&Name:"), self))
        self.name_edit = placed("IDC_GIT_USERNAME", QLineEdit("", self))
        self.email_edit = placed("IDC_GIT_USEREMAIL", QLineEdit("", self))
        self.chk_dontsave = placed("IDC_DONTSAVE", QCheckBox(
            tr("firststart_dontsave", "&Don't store these settings now."), self))


class _AuthPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_AUTHENTICATION", parent)
        self.setTitle(tr("firststart_auth", "Authentication"))
        spec = rc_mod.load_spec("IDD_FIRSTSTARTWIZARD_AUTHENTICATION")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")

        def placed(id_, wgt):
            for c in spec.controls:
                if c.ctrl_id == id_:
                    wgt.setGeometry(fu.px(c.x, c.y, c.w, c.h))
                    break
            return wgt
        self.ssh_label = placed("IDC_STATIC", QLabel(tr(
            "firststart_ssh", 'SSH (URLs look like "git@example.com")'), self))
        self.ssh_hint = placed("IDC_FIRSTSTART_SSHHINT", QLabel(
            tr("firststart_ssh_hint", "Choose the SSH client."), self))
        self.ssh_hint.setWordWrap(True)
        self.ssh_combo = placed("IDC_COMBO_SSHCLIENT", QComboBox(self))
        self.ssh_combo.addItems(["PuTTY (TortoiseGitPlink)", "ssh.exe (OpenSSH)"])
        self.btn_genkey = placed("IDC_GENERATEPUTTYKEY",
                                 QPushButton(tr("firststart_genkey", "&Generate PuTTY key pair"), self))
        self.cred_combo = placed("IDC_COMBO_SIMPLECREDENTIAL", QComboBox(self))
        self.cred_combo.addItems(["Automatic", "Store in memory", "Use credential helper"])
        self.chk_dontsave = placed("IDC_DONTSAVE", QCheckBox(
            tr("firststart_dontsave", "&Don't store these settings now."), self))
        self.btn_adv = placed("IDC_ADVANCEDCONFIGURATION",
                              QPushButton(tr("firststart_adv", "&Advanced..."), self))


class FirstStartWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("firststart_title", "First Start Wizard - PyTortoiseGit"))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self._start_page = _StartPage(self)
        self._language_page = _LanguagePage(self)
        self._pages = [self._start_page, self._language_page,
                       _GitPage(self), _UserPage(self), _AuthPage(self)]
        for p in self._pages:
            self.addPage(p)
        self.language = "English"

    def exec_wizard(self) -> bool:
        result = self.exec()
        ok = result == QWizard.DialogCode.Accepted if hasattr(QWizard, "DialogCode") else result == 1
        if ok:
            self.language = self._language_page.selected_language()
            from ..res.strings import set_language
            set_language(self.language)
            try:
                from .settingsdlg import general_settings
                general_settings().setValue("language", self.language)
            except Exception:
                pass
        return ok