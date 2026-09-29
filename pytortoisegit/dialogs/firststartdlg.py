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
from ..utils.proc import no_window_kwargs
from .settingsdlg import _LANGUAGES


class _WizardPage(QWizardPage):
    """按 IDD_FIRSTSTARTWIZARD_* 模板排版的一页。

    页内所有文案在创建时用 `_text()` 登记「字符串键 + 英文原文」，
    这样切换界面语言时可以 `retranslate()` 就地重刷（不必重建页面，
    用户已填的姓名/邮箱路径不会丢）。
    """

    def __init__(self, template: str, parent=None):
        super().__init__(parent)
        self.template = template
        self._spec = rc_mod.load_spec(template)
        self._fu = DialogUnits(self._spec.font_size or 9,
                               self._spec.font or "Segoe UI")
        r = self._fu.px(0, 0, self._spec.width, self._spec.height)
        self.setMinimumSize(r.width(), r.height())
        self._texts: list = []          # (字符串键, 英文原文, 控件, 设置函数)

    # -- 文案登记 / 重刷 ------------------------------------------------
    def _text(self, key: str, default: str, widget) -> str:
        """登记可翻译文本并返回本次应显示的文案。"""
        setter = widget.setText
        self._texts.append((key, default, widget, setter))
        return tr(key, default)

    def _title(self, widget, key: str, default: str):
        """登记页面标题（QString setTitle）并立即应用。"""
        self._texts.append((key, default, widget, widget.setTitle))
        widget.setTitle(tr(key, default))

    def _apply_text(self, widget, key: str, default: str):
        """给按钮等控件设置并登记文案。"""
        widget.setText(self._text(key, default, widget))

    def _group_box(self, key: str, default: str, x, y, w, h):
        """分组框：文案用 setTitle（QGroupBox 没有 setText）。"""
        gb = QGroupBox("", self)
        self._texts.append((key, default, gb, gb.setTitle))
        gb.setTitle(tr(key, default))
        return self._place(gb, x, y, w, h)

    def retranslate(self):
        """按当前界面语言重刷本页文案（保留用户已填内容）。"""
        for key, default, widget, setter in self._texts:
            setter(tr(key, default))

    def _place(self, wgt, x, y, w, h):
        wgt.setParent(self)
        wgt.setGeometry(self._fu.px(x, y, w, h))
        return wgt

    def _label(self, key, default, x, y, w, h, wrap=False):
        """按模板位置放一个 QLabel，并登记文案以便切换语言时重刷。"""
        lbl = QLabel(tr(key, default), self)
        self._texts.append((key, default, lbl, lbl.setText))
        lbl.setWordWrap(wrap)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return self._place(lbl, x, y, w, h)


class _StartPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_START", parent)
        self._title(self, "firststart_title", "Welcome to PyTortoiseGit")
        self._label(
            "firststart_hint",
            "This wizard guides you through the basic Git configuration:\n"
            "1. Choose the interface language\n"
            "2. Locate git.exe\n"
            "3. Enter your name and e-mail address\n"
            "4. Choose the SSH client\n", 17, 7, 289, 135, wrap=True)


class _LanguagePage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_LANGUAGE", parent)
        self._title(self, "firststart_language", "Interface language")
        self._label("firststart_lang_hint",
                    "Choose the interface language.", 17, 7, 289, 67, wrap=True)
        self._label("firststart_lang", "&Language:", 17, 82, 86, 8)
        self.lang_combo = self._place(QComboBox(self), 111, 80, 129, 14)
        for text, key in _LANGUAGES:
            self.lang_combo.addItem(text, key)
        self._label("fs_lang_download", "Download language packs:",
                    17, 100, 289, 8)
        self.link_label = self._label("", "", 17, 110, 289, 10)
        self.btn_refresh = self._place(
            QPushButton("", self), 245, 80, 61, 14)
        self._apply_text(self.btn_refresh, "refresh", "Refresh")

    def selected_language(self) -> str:
        """当前选择对应的语言键（与设置页下拉共用同一套值）。"""
        return self.lang_combo.currentData() or "English"


class _GitPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_GIT", parent)
        self._title(self, "firststart_git", "Git executable")
        self._label(
            "fs_git_info",
            "TortoiseGit requires a git.exe for its operations. TortoiseGit "
            "tries to automatically detect a working git.exe, but if that "
            "doesn't work or you want to use a different one please specify "
            "the path manually!", 17, 7, 289, 32, wrap=True)
        self._label("fs_git_path_label", "&Git.exe Path:", 18, 50, 58, 8)
        self.git_path = self._place(
            QLineEdit(shutil.which("git") or "", self), 80, 47, 202, 14)
        self.btn_browse = self._place(QPushButton("...", self), 287, 47, 19, 14)
        self._label("fs_extra_path_label", "&Extra PATH:", 17, 73, 58, 8)
        self.extern_path = self._place(QLineEdit("", self), 80, 70, 202, 14)
        self.git_ver = self._label("", "", 17, 94, 141, 8)
        self.btn_check = self._place(QPushButton("", self), 210, 91, 72, 14)
        self._apply_text(self.btn_check, "firststart_check", "C&heck now")
        self.btn_check.clicked.connect(self._check)
        self._label("fs_git_recommended", "Recommended: Git for Windows",
                    17, 110, 289, 9)
        self.link_label = self._label("", "", 17, 121, 289, 10)
        # 原版这些项默认隐藏/禁用
        self.chk_workarounds = self._place(QCheckBox("", self), 17, 136, 289, 11)
        self._apply_text(self.chk_workarounds, "fs_git_workarounds",
                         "I don't use Git for Windows and need special workarounds")
        self.rad_cygwin = self._place(QRadioButton("", self), 17, 150, 289, 11)
        self._apply_text(self.rad_cygwin, "fs_git_hack1",
                         "Enable special hack for Cygwin git")
        self.rad_msys2 = self._place(QRadioButton("", self), 17, 164, 289, 11)
        self._apply_text(self.rad_msys2, "fs_git_hack2",
                         "Enable special hack for Msys2 git")
        for w in (self.chk_workarounds, self.rad_cygwin, self.rad_msys2):
            w.setVisible(False)
            w.setEnabled(False)
        self._check()

    def _check(self):
        git = self.git_path.text().strip() or shutil.which("git")
        if git:
            try:
                out = subprocess.run([git, "--version"], capture_output=True,
                                     text=True,
                                     **no_window_kwargs()).stdout.strip()
                self.git_ver.setText(f"Git: {out}")
            except Exception:  # noqa: BLE001
                self.git_ver.setText("")

    def isComplete(self):  # noqa: N802
        return bool(self.git_path.text().strip() or shutil.which("git"))


class _UserPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_USER", parent)
        self._title(self, "firststart_user", "User information")
        self._label(
            "fs_user_intro",
            "Git requires that you set up a user name and email address. Both "
            "are used as meta data for your commits (not for authentication).",
            17, 7, 289, 25, wrap=True)
        self._label("firststart_name", "&Name:", 17, 42, 47, 8)
        self.name_edit = self._place(
            QLineEdit(self._detect("user.name"), self), 71, 40, 150, 12)
        self._label("fs_email_label", "&Email:", 17, 60, 50, 8)
        self.email_edit = self._place(
            QLineEdit(self._detect("user.email"), self), 71, 57, 150, 12)
        self._label(
            "fs_user_footer",
            "These settings will be stored to your global git configuration "
            "(%HOME%/.gitconfig) and will be used for all your git repositories "
            "as a default.", 17, 81, 289, 30, wrap=True)
        self.chk_dontsave = self._place(QCheckBox("", self), 17, 118, 289, 11)
        self._apply_text(self.chk_dontsave, "firststart_dontsave",
                         "&Don't store these settings now.")

    @staticmethod
    def _detect(key: str) -> str:
        """从系统/全局 git 配置读取 user.name / user.email；没有则留空。"""
        try:
            from ..git.git import GitRunner
            r = GitRunner(cwd=os.path.expanduser("~")).run(
                "config", "--get", key)
            if r.returncode == 0 and r.stdout:
                return r.stdout.strip()
        except Exception:  # noqa: BLE001
            pass
        return ""


def _launch_puttygen(path: str) -> None:
    import subprocess
    try:
        subprocess.Popen([path])
    except OSError:
        pass


# 内部语言码（strings.get_language()）→ 下拉框选项键
_LANG_ALIASES = {"zh": "zh_CN", "zh_tw": "zh_TW", "en": "English"}


def _combo_key(lang: str) -> str:
    """把当前语言码规范成下拉可选项的键（zh → zh_CN，en → English…）。"""
    v = (lang or "").strip()
    return _LANG_ALIASES.get(v.lower(), v or "English")


class _AuthPage(_WizardPage):
    def __init__(self, parent=None):
        super().__init__("IDD_FIRSTSTARTWIZARD_AUTHENTICATION", parent)
        self._title(self, "firststart_auth", "Authentication")
        gb_ssh = self._group_box("firststart_ssh",
                                 'SSH (URLs look like "git@example.com")',
                                 7, 7, 308, 84)
        self.ssh_hint = self._label(
            "firststart_ssh_hint", "Choose the SSH client.",
            17, 17, 289, 56, wrap=True)
        self.ssh_combo = self._place(QComboBox(self), 17, 74, 144, 14)
        self.ssh_combo.addItems(["PuTTY (TortoiseGitPlink)", "ssh.exe (OpenSSH)"])
        self.btn_genkey = self._place(QPushButton("", self), 169, 73, 137, 14)
        self._apply_text(self.btn_genkey, "firststart_genkey",
                         "&Generate PuTTY key pair")
        # 未安装 puttygen 时置灰（对齐原版仅在 PuTTY 环境提供）
        from ..utils.sshkeys import find_puttygen
        _puttygen = find_puttygen()
        self.btn_genkey.setEnabled(bool(_puttygen))
        if _puttygen:
            self.btn_genkey.clicked.connect(
                lambda _=False, p=_puttygen: _launch_puttygen(p))
        gb_http = self._group_box("fs_auth_http_group",
                                  'HTTP (URLs start with "http://" or "https://")',
                                  7, 92, 308, 95)
        self._label(
            "fs_auth_http_desc",
            "By default Git does not save/cache credentials. However, you can "
            "configure a credential helper (recommended) or manually use "
            "%HOME%/_netrc.", 17, 103, 289, 25, wrap=True)
        self._label("fs_auth_cred_label", "&Credential helper:",
                    17, 131, 145, 8)
        self.cred_combo = self._place(QComboBox(self), 189, 128, 117, 14)
        self.cred_combo.addItems(
            ["Automatic", "Store in memory", "Use credential helper"])
        self.chk_dontsave = self._place(QCheckBox("", self), 17, 145, 172, 11)
        self._apply_text(self.chk_dontsave, "firststart_dontsave",
                         "&Don't store these settings now.")
        self.btn_adv = self._place(QPushButton("", self), 189, 144, 117, 14)
        self._apply_text(self.btn_adv, "firststart_adv", "&Advanced...")
        self._label(
            "fs_auth_footer",
            "These settings will be stored to your global git configuration "
            "(%HOME%/.gitconfig) and will be used for all your git repositories "
            "as a default.", 17, 160, 289, 25, wrap=True)


class FirstStartWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._wizard_title_key = ("firststart_title",
                                  "First Start Wizard - PyTortoiseGit")
        self.setWindowTitle(tr(*self._wizard_title_key))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self._language_page = _LanguagePage(self)
        self._start_page = _StartPage(self)
        # 页序对齐原版 CFirstStartWizard
        self._pages = [self._language_page, self._start_page,
                       _GitPage(self), _UserPage(self), _AuthPage(self)]
        for p in self._pages:
            self.addPage(p)
        # 下拉框回显当前界面语言，避免「显示 English 但界面是中文」
        self._sync_language_combo()
        self.language = self._language_page.selected_language()
        # 语言一改就立刻重刷向导内所有页面（含本页与后续页）
        self._language_page.lang_combo.currentIndexChanged.connect(
            self._on_language_changed)

    # -- 语言即时生效 ----------------------------------------------------
    def _sync_language_combo(self):
        """把当前界面语言反查到下拉框选项（zh → zh_CN）。"""
        from ..res.strings import get_language
        combo = self._language_page.lang_combo
        idx = combo.findData(_combo_key(get_language()))
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_language_changed(self, _index: int):
        """界面语言随选择立即切换：重刷向导标题与所有页面文案。"""
        from ..res.strings import set_language
        self.language = self._language_page.selected_language()
        set_language(self.language)
        self.setWindowTitle(tr(*self._wizard_title_key))
        for page in self._pages:
            page.retranslate()

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
