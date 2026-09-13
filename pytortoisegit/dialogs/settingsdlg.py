"""settingsdlg.py —— SettingsDlg：设置对话框（属性页，镜像 TortoiseGit）。

用 QTreeWidget + QStackedWidget 复刻 CTreePropSheet。
页面树对齐 CSettings::AddPropPages，各页按 IDD_SETTINGS* 模板排版。
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
import sys
from typing import List, Tuple

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..git.git import GitRunner
from ..git.repo import Repository
from ..res.strings import set_language, tr, tr_settings
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


def _is_win11() -> bool:
    if sys.platform != "win32":
        return False
    return sys.getwindowsversion().build >= 22000


# ---------------------------------------------------------------------------
# 页面基类：按 rc 模板排版
# ---------------------------------------------------------------------------


def _parse_proxy(proxy: str):
    """把 git http.proxy 拆成 (host, port, user, password)。"""
    if not proxy:
        return "", "", "", ""
    s = proxy.split("://", 1)[1] if "://" in proxy else proxy
    user = pwd = ""
    if "@" in s:
        auth, s = s.rsplit("@", 1)
        if ":" in auth:
            user, pwd = auth.split(":", 1)
        else:
            user = auth
    host, port = s, ""
    if ":" in s:
        host, port = s.rsplit(":", 1)
    return host, port, user, pwd


class _SettingPage(QWidget):
    """一个设置页：按 IDD_SETTINGS* 模板绝对定位控件。"""

    TEMPLATE: str = ""
    READONLY: bool = False  # 功能暂未开发：整页置灰不可编辑

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctl: dict = {}
        self._build_ui()
        if self.READONLY:
            self.setEnabled(False)

    def _build_ui(self):
        if not self.TEMPLATE:
            return
        spec = rc_mod.load_spec(self.TEMPLATE)
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.setMinimumSize(r.width(), r.height())
        self._fu = fu
        self._spec = spec
        # 生成控件
        for ctrl in spec.controls:
            wgt = self._make_control(ctrl)
            if wgt is None:
                continue
            wgt.setParent(self)
            rc_mod.place_widget(self, fu, ctrl, wgt)
            self._ctl[ctrl.ctrl_id] = wgt

    def _make_control(self, ctrl):
        """按 rc 生成控件并翻译文本，子类可覆盖映射。"""
        wgt = rc_mod.make_widget(ctrl, self)
        if ctrl.text:
            text = tr_settings(ctrl.text)
            from PySide6.QtWidgets import (
                QCheckBox, QGroupBox, QLabel, QPushButton, QRadioButton)
            if isinstance(wgt, QGroupBox):
                wgt.setTitle(text)
            elif isinstance(wgt, (QCheckBox, QRadioButton, QPushButton)):
                wgt.setText(text)
            elif isinstance(wgt, QLabel):
                wgt.setText(text)
        return wgt


    def _place(self, ctrl_id, wgt):
        for c in self._spec.controls:
            if c.ctrl_id == ctrl_id:
                rc_mod.place_widget(self, self._fu, c, wgt)
                break
        self._ctl[ctrl_id] = wgt
        return wgt

    def value(self, key: str) -> str:
        return ""

    def set(self, key: str, value: str):
        pass

    # -- 通用 QSettings 持久化：子类定义 _SETTINGS 列表 ----------------
    # 每项 (setting_key, ctrl_id, kind, default)，kind ∈ {bool,int,text,index}
    def _get_widget_text(self, w) -> str:
        if hasattr(w, "toPlainText"):
            return w.toPlainText()
        if hasattr(w, "currentText"):
            return w.currentText()
        if hasattr(w, "text"):
            return w.text()
        return ""

    def _set_widget_text(self, w, val: str):
        if hasattr(w, "setPlainText"):
            w.setPlainText(val)
        elif hasattr(w, "setCurrentText"):
            w.setCurrentText(val)
        elif hasattr(w, "setText"):
            w.setText(val)

    def load_settings(self):
        s = general_settings()
        for key, cid, kind, default in getattr(self, "_SETTINGS", []):
            w = self._ctl.get(cid)
            if w is None:
                continue
            if kind == "bool":
                w.setChecked(bool(s.value(key, default, type=bool)))
            elif kind == "index":
                w.setCurrentIndex(int(s.value(key, default)))
            else:
                self._set_widget_text(w, str(s.value(key, default)))
        for key, ids, default in getattr(self, "_RADIO_GROUPS", []):
            idx = int(s.value(key, default))
            if 0 <= idx < len(ids):
                w = self._ctl.get(ids[idx])
                if w is not None:
                    w.setChecked(True)

    def save_settings(self):
        s = general_settings()
        for key, cid, kind, default in getattr(self, "_SETTINGS", []):
            w = self._ctl.get(cid)
            if w is None:
                continue
            if kind == "bool":
                s.setValue(key, w.isChecked())
            elif kind == "index":
                s.setValue(key, w.currentIndex())
            else:
                s.setValue(key, self._get_widget_text(w))
        for key, ids, default in getattr(self, "_RADIO_GROUPS", []):
            for i, cid in enumerate(ids):
                w = self._ctl.get(cid)
                if w is not None and w.isChecked():
                    s.setValue(key, i)
                    break
        s.sync()


# ---------------------------------------------------------------------------
# General 页（IDD_SETTINGSMAIN）
# ---------------------------------------------------------------------------

_APP_NAME = "PyTortoiseGit"


def general_settings() -> QSettings:
    """General 页的应用级配置（跨平台，Windows 下写注册表）。"""
    return QSettings(_APP_NAME, _APP_NAME)


# ---------------------------------------------------------------------------
# 颜色按钮页通用基类
# ---------------------------------------------------------------------------


def _set_swatch(btn, color_hex: str):
    btn.setText(color_hex)
    btn.setStyleSheet(f"background-color: {color_hex};")


def _pick_color(parent, current: str):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog
    col = QColorDialog.getColor(QColor(current), parent)
    return col.name() if col.isValid() else None


class _ColorPage(_SettingPage):
    """颜色按钮页通用基类：_COLORS = [(设置键, 控件ID, 默认#RRGGBB), ...]。"""

    _COLORS: list = []

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)
        for _key, cid, _default in self._COLORS:
            b = self._ctl.get(cid)
            if b is not None:
                b.clicked.connect(lambda _=False, c=cid: self._on_pick(c))
        if r := self._ctl.get("IDC_RESTORE"):
            r.clicked.connect(self._restore_defaults)

    def _on_pick(self, cid):
        b = self._ctl.get(cid)
        cur = b.text().strip() if b is not None else ""
        picked = _pick_color(self, cur or "#ffffff")
        if picked and b is not None:
            _set_swatch(b, picked)

    def _restore_defaults(self):
        for _key, cid, default in self._COLORS:
            b = self._ctl.get(cid)
            if b is not None:
                _set_swatch(b, default)

    def load_settings(self):
        super().load_settings()
        s = general_settings()
        for key, cid, default in self._COLORS:
            b = self._ctl.get(cid)
            if b is not None:
                _set_swatch(b, str(s.value(key, default)))

    def save_settings(self):
        s = general_settings()
        for key, cid, default in self._COLORS:
            b = self._ctl.get(cid)
            if b is not None:
                s.setValue(key, b.text().strip() or default)
        s.sync()
        super().save_settings()


# 语言下拉可选项（文本, 语言键）
_LANGUAGES = [
    ("English", "English"),
    ("简体中文", "zh_CN"),
    ("繁體中文", "zh_TW"),
    ("Deutsch", "Deutsch"),
]


class _GeneralPage(_SettingPage):
    """IDD_SETTINGSMAIN —— General：语言、Git 可执行文件等最常用设置。"""

    TEMPLATE = "IDD_SETTINGSMAIN"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._add_static_labels()

    # -- 静态标签：RC 中多个标签共用 IDC_STATIC 被去重丢弃，手动补回 -----
    def _add_static_labels(self):
        # (x, y, w, h, 字符串键, 默认文本) —— 坐标来自 TortoiseProcENG.rc
        # 注意：RC 中首个 IDC_STATIC（"TortoiseGit" 分组框）未被去重，勿重复添加
        groups = [
            (7, 113, 286, 98, "set_group_gitwin", "Git for Windows"),
        ]
        for x, y, w, h, key, default in groups:
            gb = QGroupBox(tr(key, default), self)
            gb.setGeometry(self._fu.px(x, y, w, h))
            gb.lower()
            self._ctl[f"group_{key}"] = gb
        labels = [
            (14, 20, 86, 8, "set_lang", "&Language:"),
            (16, 132, 58, 8, "set_gitexe", "&Git.exe Path:"),
            (15, 155, 58, 8, "set_extrapath", "&Extra PATH:"),
        ]
        for x, y, w, h, key, default in labels:
            lbl = QLabel(tr(key, default), self)
            lbl.setGeometry(self._fu.px(x, y, w, h))
            self._ctl[f"label_{key}"] = lbl

    @property
    def language_combo(self) -> QComboBox:
        return self._ctl.get("IDC_LANGUAGECOMBO")

    @property
    def check_newer_checkbox(self) -> QCheckBox:
        return self._ctl.get("IDC_CHECKNEWERVERSION")

    @property
    def git_path_edit(self) -> QLineEdit:
        return self._ctl.get("IDC_MSYSGIT_PATH")

    @property
    def extern_path_edit(self) -> QLineEdit:
        return self._ctl.get("IDC_MSYSGIT_EXTERN_PATH")

    @property
    def version_label(self) -> QLabel:
        return self._ctl.get("IDC_MSYSGIT_VER")

    def setup(self):
        """填充语言下拉并绑定按钮动作。"""
        combo = self.language_combo
        if combo is not None:
            combo.clear()
            for text, key in _LANGUAGES:
                combo.addItem(text, key)

        if gb := self._ctl.get("IDC_MSYSGIT_BROWSE"):
            gb.clicked.connect(self._on_browse)
        if gc := self._ctl.get("IDC_MSYSGIT_CHECK"):
            gc.clicked.connect(self._check_git)
        if se := self._ctl.get("IDC_BUTTON_SHOW_ENV"):
            se.clicked.connect(self._show_env)
        if wiz := self._ctl.get("IDC_RUNFIRSTSTARTWIZARD"):
            wiz.clicked.connect(self._run_firststart)
        if lib := self._ctl.get("IDC_CREATELIB"):
            lib.clicked.connect(self._create_library)
        if upd := self._ctl.get("IDC_CHECKNEWERBUTTON"):
            upd.clicked.connect(self._check_newer_now)

        if self.git_path_edit is not None:
            self.git_path_edit.textChanged.connect(self._on_path_changed)

    # -- 动作 -----------------------------------------------------------
    def _on_browse(self):
        start = self.git_path_edit.text() if self.git_path_edit else ""
        if not start:
            start = shutil.which("git") or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, tr("set_browse", "Select Git directory"), start)
        if path and self.git_path_edit is not None:
            self.git_path_edit.setText(path)

    def _check_git(self):
        git = (self.git_path_edit.text().strip()
               if self.git_path_edit else "") or shutil.which("git")
        if not git:
            if self.version_label is not None:
                self.version_label.setText("")
            return
        try:
            out = subprocess.run([git, "--version"], capture_output=True,
                                 text=True).stdout.strip()
            if self.version_label is not None:
                self.version_label.setText(out or tr("set_ver", "Version:"))
        except Exception:
            if self.version_label is not None:
                self.version_label.setText("")

    def _show_env(self):
        lines = ["%s=%s" % (k, v) for k, v in sorted(os.environ.items())]
        QMessageBox.information(self, tr("set_env", "Environment variables"),
                                "\n".join(lines) or tr("none", "(none)"))

    def _run_firststart(self):
        try:
            from ..dialogs.firststartdlg import FirstStartWizard
        except Exception:
            QMessageBox.information(self, tr("set_firststart", "First Start Wizard"),
                                    tr("firststart_unavailable", "First Start Wizard is not available."))
        else:
            FirstStartWizard(self).exec_wizard()

    def _create_library(self):
        # Git 随附库（git-extras 等）在 Python 版中无对应概念，仅提示已就绪。
        QMessageBox.information(self, tr("set_library", "Create Library"),
                                tr("set_library_done", "No additional library needs to be created."))

    def _check_newer_now(self):
        try:
            from ..__init__ import __version__
        except Exception:
            __version__ = "0.0.0"
        QMessageBox.information(self, tr("set_checknewer", "Check for updates"),
                                tr("set_checknewer_msg", "Current version: {ver}. This feature is a placeholder; automatic online checks are not supported yet.").format(ver=__version__))

    def _on_path_changed(self):
        path = self.git_path_edit.text().strip() if self.git_path_edit else ""
        # 首次输入时带出可推测的 extra path（镜像 GuessExtraPath 的简化实现）
        extra = self.extern_path_edit.text().strip() if self.extern_path_edit else ""
        if path and not extra:
            guessed = self._guess_extra_path(path)
            if guessed and self.extern_path_edit is not None:
                self.extern_path_edit.setText(guessed)

    @staticmethod
    def _guess_extra_path(path: str) -> str:
        """若路径指向 bin/cmd 等常见目录，给出其相邻的 user 目录猜测。"""
        base = os.path.normpath(path)
        userhome = os.path.expanduser("~")
        tail = os.path.basename(base).casefold()
        if tail in ("bin", "cmd", "usr") and not base.casefold().startswith(userhome.casefold()):
            return os.path.join(os.path.dirname(base), "usr", "bin")
        return ""

    def load_from_settings(self):
        s = general_settings()
        combo = self.language_combo
        if combo is not None:
            lang = s.value("language", "zh_CN")
            idx = combo.findData(lang)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        if cb := self.check_newer_checkbox:
            cb.setChecked(bool(s.value("checkNewer", True, type=bool)))
        git = s.value("gitPath", shutil.which("git") or "")
        if self.git_path_edit is not None:
            self.git_path_edit.setText(git or "")
        if self.extern_path_edit is not None:
            self.extern_path_edit.setText(s.value("extraPath", "") or "")
        self._check_git()

    def apply_to_settings(self):
        s = general_settings()
        combo = self.language_combo
        if combo is not None:
            lang = combo.currentData() or combo.currentText()
            s.setValue("language", lang)
            set_language(lang)
        if cb := self.check_newer_checkbox:
            s.setValue("checkNewer", cb.isChecked())
        if self.git_path_edit is not None:
            s.setValue("gitPath", self.git_path_edit.text().strip())
        if self.extern_path_edit is not None:
            s.setValue("extraPath", self.extern_path_edit.text().strip())
        s.sync()


class _RcPage(_SettingPage):
    """按模板 ID 生成的通用设置页。"""

    def __init__(self, template: str, parent=None, readonly: bool = False):
        self.TEMPLATE = template
        self.READONLY = readonly
        super().__init__(parent)


class _GitPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGIT_CONFIG"

    # 注意：RC 中首个 IDC_STATIC（"|" 分隔符）未被去重，勿重复添加
    _GROUPS = [
        (7, 7, 286, 26, "set_config_source", "Config source"),
        (7, 35, 286, 68, "set_git_userinfo_group", "User Info"),
        (7, 106, 286, 29, "set_git_autocrlf_group", "Auto CrLf convert"),
    ]
    _LABELS = [
        (153, 18, 13, 11, None, "<<"),
        (218, 18, 13, 11, None, "<<"),
        (14, 49, 47, 8, "set_git_name", "&Name:"),
        (14, 67, 50, 8, "set_git_email", "&Email:"),
        (14, 84, 49, 8, "set_git_signingkey", "&Signing key ID:"),
        (14, 119, 37, 8, "set_git_autocrlf", "Auto&CrLf:"),
        (112, 119, 32, 8, "set_git_safecrlf", "Sa&feCrLf:"),
        (14, 157, 98, 11, "set_save_to", "Save to:"),
    ]

    def _build_ui(self):
        super()._build_ui()
        _add_static_labels(self)
        if c := self._ctl.get("IDC_COMBO_AUTOCRLF"):
            c.addItems(["", "input", "true", "false"])
        if c := self._ctl.get("IDC_COMBO_SAFECRLF"):
            c.addItems(["", "warn", "true", "false"])
        if c := self._ctl.get("IDC_COMBO_SETTINGS_SAFETO"):
            c.addItems([
                tr("set_save_local", "Local"),
                tr("set_save_project", "Project"),
                tr("set_save_global", "Global"),
                tr("set_save_system", "System"),
            ])

    @property
    def name_edit(self):
        return self._ctl.get("IDC_GIT_USERNAME")

    @property
    def email_edit(self):
        return self._ctl.get("IDC_GIT_USEREMAIL")

    @property
    def signingkey_edit(self):
        return self._ctl.get("IDC_GIT_USERESINGNINGKEY")

    @property
    def autocrlf_combo(self):
        return self._ctl.get("IDC_COMBO_AUTOCRLF")

    @property
    def safecrlf_combo(self):
        return self._ctl.get("IDC_COMBO_SAFECRLF")

    @property
    def quotepath_check(self):
        return self._ctl.get("IDC_CHECK_QUOTEPATH")

    @property
    def prune_check(self):
        return self._ctl.get("IDC_CHECK_PRUNE")


class _DiffPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSPROGSDIFF"

    # 注意：RC 中首个 IDC_STATIC（第一个分组框）未被去重，勿重复添加
    _GROUPS = [
        (7, 104, 286, 63, "set_viewer_group",
         "Configure viewer program for GNU diff files (patch files)"),
    ]
    _LABELS = [
        (16, 65, 160, 25, "set_diff_adv_hint",
         'Click on "Advanced" to specify alternate diff programs based on file extension'),
    ]
    _RADIO_GROUPS = [
        ("DiffUseExternal",
         ["IDC_EXTDIFF_OFF", "IDC_EXTDIFF_ON"], 0),
        ("DiffViewerUseExternal",
         ["IDC_DIFFVIEWER_OFF", "IDC_DIFFVIEWER_ON"], 0),
    ]

    def _build_ui(self):
        super()._build_ui()
        _add_static_labels(self)
        self._group("IDC_EXTDIFF_OFF", "IDC_EXTDIFF_ON")
        self._group("IDC_DIFFVIEWER_OFF", "IDC_DIFFVIEWER_ON")
        # 默认选中 TortoiseGitMerge / TortoiseGitUDiff（对齐原版）
        if self._ctl.get("IDC_EXTDIFF_OFF") is not None:
            self._ctl["IDC_EXTDIFF_OFF"].setChecked(True)
        if self._ctl.get("IDC_DIFFVIEWER_OFF") is not None:
            self._ctl["IDC_DIFFVIEWER_OFF"].setChecked(True)

    def _group(self, *ids):
        from PySide6.QtWidgets import QButtonGroup
        g = QButtonGroup(self)
        for i in ids:
            w = self._ctl.get(i)
            if w is not None:
                g.addButton(w)

    @property
    def diff_edit(self):
        return self._ctl.get("IDC_EXTDIFF")

    @property
    def viewer_edit(self):
        return self._ctl.get("IDC_DIFFVIEWER")


class _MergePage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSPROGSMERGE"

    # 注意：RC 中首个 IDC_STATIC 提示未被去重，勿重复添加
    _LABELS = [
        (7, 108, 160, 33, "set_merge_adv_hint",
         'Click on "Advanced" to specify alternate merge programs based on file extension'),
    ]
    _RADIO_GROUPS = [
        ("MergeUseExternal", ["IDC_EXTMERGE_OFF", "IDC_EXTMERGE_ON"], 0),
    ]

    def _build_ui(self):
        super()._build_ui()
        _add_static_labels(self)
        from PySide6.QtWidgets import QButtonGroup
        g = QButtonGroup(self)
        for i in ("IDC_EXTMERGE_OFF", "IDC_EXTMERGE_ON"):
            w = self._ctl.get(i)
            if w is not None:
                g.addButton(w)
        if self._ctl.get("IDC_EXTMERGE_OFF") is not None:
            self._ctl["IDC_EXTMERGE_OFF"].setChecked(True)

    @property
    def merge_edit(self):
        return self._ctl.get("IDC_EXTMERGE")


class _NetworkPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSPROXY"
    READONLY = True

    def _build_ui(self):
        super()._build_ui()
        if b := self._ctl.get("IDC_SSHBROWSE"):
            b.clicked.connect(self._browse_ssh)

    @property
    def enable(self):
        return self._ctl.get("IDC_ENABLE")

    @property
    def server_edit(self):
        return self._ctl.get("IDC_SERVERADDRESS")

    @property
    def port_edit(self):
        return self._ctl.get("IDC_SERVERPORT")

    @property
    def username_edit(self):
        return self._ctl.get("IDC_USERNAME")

    @property
    def password_edit(self):
        return self._ctl.get("IDC_PASSWORD")

    @property
    def ssh_edit(self):
        return self._ctl.get("IDC_SSHCLIENT")

    def _browse_ssh(self):
        from ..utils.pick import pick_file
        p = pick_file(self, tr("set_selectssh", "Select SSH client"), "")
        if p and self.ssh_edit is not None:
            self.ssh_edit.setText(p)


class _SmtpPage(_SettingPage):
    """IDD_SETTINGSMTP —— Email：映射 git sendemail.* 配置。"""

    TEMPLATE = "IDD_SETTINGSMTP"

    # 注意：RC 中首个 IDC_STATIC（"Delivery:"）未被去重，勿重复添加
    _GROUPS = [(17, 97, 268, 51, "set_smtp_credentials", "Credentials")]
    _LABELS = [(7, 47, 47, 8, "set_smtp_from", "From")]

    def _build_ui(self):
        super()._build_ui()
        _add_static_labels(self)
        if c := self._ctl.get("IDC_SMTPDELIVERYCOMBO"):
            c.addItems(["", "smtp", "smtps", "sendmail", "mailto", "auto"])
        if c := self._ctl.get("IDC_SMTPENCRYPTIONCOMBO"):
            c.addItems(["", "none", "ssl", "tls"])

    @property
    def delivery_combo(self):
        return self._ctl.get("IDC_SMTPDELIVERYCOMBO")

    @property
    def server_edit(self):
        return self._ctl.get("IDC_SMTP_SERVER")

    @property
    def port_edit(self):
        return self._ctl.get("IDC_SMTP_PORT")

    @property
    def from_edit(self):
        return self._ctl.get("IDC_SEND_ADDRESS")

    @property
    def encryption_combo(self):
        return self._ctl.get("IDC_SMTPENCRYPTIONCOMBO")

    @property
    def auth_check(self):
        return self._ctl.get("IDC_SMTP_AUTH")

    @property
    def user_edit(self):
        return self._ctl.get("IDC_SMTP_USER")


class _AlternativeEditorPage(_SettingPage):
    """IDD_SETTINGSPROGSALTERNATIVEEDITOR —— 备用编辑器。"""

    TEMPLATE = "IDD_SETTINGSPROGSALTERNATIVEEDITOR"

    _RADIO_GROUPS = [
        ("AlternativeEditorUseCustom",
         ["IDC_ALTERNATIVEEDITOR_OFF", "IDC_ALTERNATIVEEDITOR_ON"], 0),
    ]
    _SETTINGS = [
        ("AlternativeEditor", "IDC_ALTERNATIVEEDITOR", "text", ""),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        if b := self._ctl.get("IDC_ALTERNATIVEEDITORBROWSE"):
            b.clicked.connect(self._browse)
        for cid in ("IDC_ALTERNATIVEEDITOR_OFF", "IDC_ALTERNATIVEEDITOR_ON"):
            if w := self._ctl.get(cid):
                w.toggled.connect(self._update_enabled)
        self._update_enabled()

    def _update_enabled(self, *_):
        on = self._ctl.get("IDC_ALTERNATIVEEDITOR_ON")
        enabled = bool(on is not None and on.isChecked())
        for cid in ("IDC_ALTERNATIVEEDITOR", "IDC_ALTERNATIVEEDITORBROWSE"):
            if w := self._ctl.get(cid):
                w.setEnabled(enabled)

    def _browse(self):
        from ..utils.pick import pick_file
        p = pick_file(self, tr("set_select_editor", "Select editor"), "")
        if p and (w := self._ctl.get("IDC_ALTERNATIVEEDITOR")):
            w.setText(p)


class _OverlayPage(_SettingPage):
    """IDD_SETTINGSOVERLAY —— Icon Overlays（补回被去重的标签/分组框）。"""

    TEMPLATE = "IDD_SETTINGSOVERLAY"

    # 注意：RC 中首个 IDC_STATIC（"Icon Overlays" 分组框）未被去重，勿重复添加
    _GROUPS = [(12, 78, 274, 22, "set_overlay_status_group", "Status cache")]
    _LABELS = [
        (18, 172, 95, 8, "set_overlay_exclude", "E&xclude paths:"),
        (18, 198, 95, 8, "set_overlay_include", "I&nclude paths:"),
    ]
    _SETTINGS = [
        ("LoadDllOnlyInExplorer", "IDC_ONLYEXPLORER", "bool", False),
        ("UnversionedAsModified", "IDC_UNVERSIONEDASMODIFIED", "bool", False),
        ("TGitCacheRecurseSubmodules", "IDC_RECURSIVESUBMODULES", "bool", False),
        ("ShowOverlaysOnlyNonElevated", "IDC_ONLYNONELEVATED", "bool", False),
        ("DriveMaskFloppy", "IDC_FLOPPY", "bool", False),
        ("DriveMaskRemovable", "IDC_REMOVABLE", "bool", False),
        ("DriveMaskRemote", "IDC_NETWORK", "bool", False),
        ("DriveMaskFixed", "IDC_FIXED", "bool", True),
        ("DriveMaskCDROM", "IDC_CDROM", "bool", False),
        ("DriveMaskRAM", "IDC_RAM", "bool", False),
        ("DriveMaskUnknown", "IDC_UNKNOWN", "bool", False),
        ("OverlayExcludeList", "IDC_EXCLUDEPATHS", "text", ""),
        ("OverlayIncludeList", "IDC_INCLUDEPATHS", "text", ""),
        ("ShowExcludedAsNormal", "IDC_SHOWEXCLUDEDASNORMAL", "bool", True),
    ]
    _RADIO_GROUPS = [
        ("CacheType",
         ["IDC_CACHEDEFAULT", "IDC_CACHESHELL2", "IDC_CACHESHELL",
          "IDC_CACHENONE"], 1),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


class _OverlayHandlersPage(_SettingPage):
    """IDD_SETTINGSOVERLAYHANDLERS —— Overlay Handlers。"""

    TEMPLATE = "IDD_SETTINGSOVERLAYHANDLERS"

    # 注意：RC 中首个 IDC_STATIC（分组框）未被去重，勿重复添加
    _LABELS = [
        (14, 18, 270, 32, "set_overlayhandlers_hint",
         "You can disable specific Overlay handlers here.\n"
         "Disabled handlers won't use up an overlay slot and give other "
         "shell extensions a chance to show their overlays."),
        (14, 54, 270, 8, "set_overlayhandlers_note",
         "Note: this affects all Tortoise clients, not just TortoiseGit!"),
    ]
    _SETTINGS = [
        ("ShowIgnoredOverlay", "IDC_SHOWIGNOREDOVERLAY", "bool", True),
        ("ShowUnversionedOverlay", "IDC_SHOWUNVERSIONEDOVERLAY", "bool", True),
        ("ShowAddedOverlay", "IDC_SHOWADDEDOVERLAY", "bool", True),
        ("ShowLockedOverlay", "IDC_SHOWLOCKEDOVERLAY", "bool", True),
        ("ShowReadonlyOverlay", "IDC_SHOWREADONLYOVERLAY", "bool", True),
        ("ShowDeletedOverlay", "IDC_SHOWDELETEDOVERLAY", "bool", True),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)
        if b := self._ctl.get("IDC_REGEDT"):
            b.clicked.connect(self._open_regedit)

    def _open_regedit(self):
        from PySide6.QtCore import QProcess
        QProcess.startDetached("regedit.exe", [])


class _OverlayIconsPage(_SettingPage):
    """IDD_SETOVERLAYICONS —— Icon Set。"""

    TEMPLATE = "IDD_SETOVERLAYICONS"

    _SETTINGS = [
        ("IconSet", "IDC_ICONSETCOMBO", "text", "TortoiseGit"),
    ]
    _RADIO_GROUPS = [
        ("IconSetListView", ["IDC_LISTRADIO", "IDC_SYMBOLRADIO"], 0),
    ]

    _ICON_NAMES = ["Normal", "Modified", "Conflict", "ReadOnly", "Deleted",
                   "Locked", "Added", "Ignored", "Unversioned"]

    def __init__(self, parent=None):
        super().__init__(parent)
        if c := self._ctl.get("IDC_ICONSETCOMBO"):
            c.addItem("TortoiseGit")
        tree = self._ctl.get("IDC_ICONLIST")
        if tree is not None:
            tree.setColumnCount(1)
            tree.setHeaderHidden(True)
            tree.setRootIsDecorated(False)
            for name in self._ICON_NAMES:
                tree.addTopLevelItem(QTreeWidgetItem([name]))


class _Win11MenuPage(_SettingPage):
    """IDD_SETTINGSWIN11CONTEXTMENU —— Windows 11 Context Menu。"""

    TEMPLATE = "IDD_SETTINGSWIN11CONTEXTMENU"

    # 注意：RC 中首个 IDC_STATIC（分组框）未被去重，勿重复添加
    _LABELS = [
        (12, 16, 274, 18, "set_win11_hint",
         "Unchecked items are not shown in the top menu but only in the "
         "original menu"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


class _GitRemotePage(_SettingPage):
    """IDD_SETTINREMOTE —— Remote（功能暂未开发，整页置灰）。"""

    TEMPLATE = "IDD_SETTINREMOTE"
    READONLY = True

    # 注意：RC 中首个 IDC_STATIC（"Remote:"）未被去重，勿重复添加
    _LABELS = [
        (96, 47, 48, 8, "set_remote_url", "URL:"),
        (96, 64, 48, 8, "set_remote_pushurl", "Push URL:"),
        (96, 82, 48, 8, "set_remote_puttykey", "Putty Key:"),
        (96, 103, 40, 8, "set_remote_tags", "Tags:"),
        (7, 10, 76, 8, "set_remote_label", "Remote:"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


class _CredentialPage(_SettingPage):
    """IDD_SETTINGSCREDENTIAL —— Credential（功能暂未开发，整页置灰）。"""

    TEMPLATE = "IDD_SETTINGSCREDENTIAL"
    READONLY = True

    # 注意：RC 中首个 IDC_STATIC（"Credential helper:"）未被去重，勿重复添加
    _LABELS = [
        (7, 24, 76, 8, "set_cred_helpers", "Helpers:"),
        (97, 38, 40, 8, "set_cred_configtype", "Config type:"),
        (97, 58, 16, 8, "set_cred_url", "URL:"),
        (97, 74, 40, 8, "set_cred_helper", "Helper:"),
        (97, 92, 36, 8, "set_cred_username", "Username:"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


class _BugtraqConfigPage(_SettingPage):
    """IDD_SETTINGSBUGTRAQ_CONFIG —— Issue Tracker Config。"""

    TEMPLATE = "IDD_SETTINGSBUGTRAQ_CONFIG"

    # 注意：RC 中首个 IDC_STATIC（"|" 分隔符）未被去重，勿重复添加
    _GROUPS = [
        (7, 7, 287, 26, "set_config_source", "Config source"),
        (7, 34, 287, 153, "set_bugtraq_group", "BugTraq"),
    ]
    _LABELS = [
        (173, 18, 13, 11, None, "<<"),
        (233, 18, 13, 11, None, "<<"),
        (112, 18, 13, 11, None, "<<"),
        (14, 44, 89, 8, None, "bugtraq.url"),
        (14, 60, 91, 10, None, "bugtraq.warningifnoissue"),
        (14, 77, 86, 10, None, "bugtraq.message"),
        (14, 94, 84, 10, None, "bugtraq.append"),
        (14, 111, 77, 10, None, "bugtraq.label"),
        (14, 128, 72, 10, None, "bugtraq.number"),
        (14, 144, 79, 10, None, "bugtraq.logregex"),
        (14, 256, 99, 11, "set_save_to", "Save to:"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)
        for cid in ("IDC_BUGTRAQ_WARNINGIFNOISSUE", "IDC_BUGTRAQ_APPEND",
                    "IDC_BUGTRAQ_NUMBER"):
            if c := self._ctl.get(cid):
                c.addItems(["", "true", "false"])
        if c := self._ctl.get("IDC_COMBO_SETTINGS_SAFETO"):
            c.addItems([
                tr("set_save_local", "Local"),
                tr("set_save_project", "Project"),
                tr("set_save_global", "Global"),
                tr("set_save_system", "System"),
            ])

    def _text(self, cid):
        w = self._ctl.get(cid)
        return w.text().strip() if w is not None else ""

    def _set(self, cid, val: str):
        w = self._ctl.get(cid)
        if w is not None:
            w.setText(val)

    def _combo(self, cid):
        w = self._ctl.get(cid)
        return w.currentText().strip() if w is not None else ""

    def _set_combo(self, cid, val: str):
        w = self._ctl.get(cid)
        if w is not None:
            i = w.findText(val)
            w.setCurrentIndex(i if i >= 0 else 0)


class _SavedDataPage(_SettingPage):
    """IDD_SETTINGSSAVEDDATA —— Saved Data（补回被去重的标签/分组框）。"""

    TEMPLATE = "IDD_SETTINGSSAVEDDATA"

    # 注意：RC 中首个 IDC_STATIC（"Temp files..." 标签）未被去重，勿重复添加
    _GROUPS = [(7, 173, 286, 30, "set_saved_actionlog_group", "Action log")]
    _LABELS = [
        (13, 185, 120, 16, "set_saved_maxlines", "Max. lines in action log"),
    ]
    _SETTINGS = [
        ("MaxActionLogLines", "IDC_MAXLINES", "text", "100"),
    ]
    # (按钮 ID, 对应的 QSettings 键, 名称 tr 键, 默认名称)
    _CLEAR_BUTTONS = [
        ("IDC_URLHISTCLEAR", "UrlHistory", "set_saved_clear_url", "URL history"),
        ("IDC_LOGHISTCLEAR", "LogHistory", "set_saved_clear_log",
         "Log messages (Input dialog)"),
        ("IDC_REPOLOGCLEAR", "RepoLogHistory", "set_saved_clear_repolog",
         "Log messages (Show log dialog)"),
        ("IDC_RESIZABLEHISTCLEAR", "ResizableHistory",
         "set_saved_clear_resizable", "Dialog sizes and positions"),
        ("IDC_AUTHHISTCLEAR", "AuthHistory", "set_saved_clear_auth",
         "Authentication data"),
        ("IDC_TEMPFILESCLEAR", "TempFiles", "set_saved_clear_temp",
         "Temp files"),
        ("IDC_STOREDDECISIONSCLEAR", "StoredDecisions",
         "set_saved_clear_decisions", "Stored decisions"),
        ("IDC_ACTIONLOGCLEAR", "ActionLog", "set_saved_clear_actionlog",
         "Action log"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)
        for cid, key, tr_key, default in self._CLEAR_BUTTONS:
            if b := self._ctl.get(cid):
                b.clicked.connect(
                    lambda _=False, k=key, t=tr_key, d=default:
                    self._clear(k, t, d))
        if b := self._ctl.get("IDC_ACTIONLOGSHOW"):
            b.clicked.connect(self._show_actionlog)

    def _clear(self, key: str, tr_key: str, default: str):
        s = general_settings()
        s.remove(key)
        s.sync()
        name = tr(tr_key, default)
        QMessageBox.information(
            self, tr("set_saved_clear_title", "Clear"),
            tr("set_saved_cleared", "Cleared: {name}").format(name=name))

    def _show_actionlog(self):
        s = general_settings()
        lines = s.value("ActionLog", [], type=list) or []
        QMessageBox.information(
            self, tr("set_saved_show_title", "Action log"),
            "\n".join(str(x) for x in lines)
            or tr("set_saved_show_empty", "The action log is empty."))


class _AdvancedPage(_SettingPage):
    """IDD_SETTINGS_CONFIG —— Advanced：列出/编辑全局 git config。"""

    TEMPLATE = "IDD_SETTINGS_CONFIG"
    READONLY = True

    def _build_ui(self):
        super()._build_ui()
        tree = self.config_tree
        if tree is not None:
            tree.setColumnCount(2)
            tree.setHeaderLabels([tr("set_adv_key", "Key"),
                                  tr("set_adv_value", "Value")])
            tree.setRootIsDecorated(False)
            tree.setColumnWidth(0, self._fu.px(0, 0, 150, 0).width())

    @property
    def config_tree(self):
        return self._ctl.get("IDC_CONFIG")


class _BlamePage(_ColorPage):
    """IDD_SETTINGSTBLAME —— TortoiseGitBlame：字体/颜色/移动行检测。"""

    TEMPLATE = "IDD_SETTINGSTBLAME"

    # 注意：RC 中首个 IDC_STATIC（"Colors" 分组框）未被去重，勿重复添加
    _GROUPS = [
        (7, 77, 286, 46, "set_blame_font_group", "Font"),
        (7, 126, 286, 79, "set_blame_group", "Blame"),
        (7, 208, 286, 42, "set_blame_log_group", "Log"),
    ]
    _LABELS = [
        (14, 21, 148, 8, "set_blame_recent", "Recently modified lines"),
        (14, 37, 148, 8, "set_blame_older", "Older lines"),
        (14, 85, 92, 17, "set_blame_font", "&Font:"),
        (14, 108, 92, 8, "set_blame_tabsize", "Tab size:"),
        (14, 136, 108, 12, "set_blame_detect",
         "&Detect moved or copied lines:"),
        (14, 153, 247, 8, "set_blame_detect_chars",
         "Number of characters required for moved or copied line detection:"),
        (32, 165, 60, 8, "set_blame_within", "Within a file:"),
        (172, 165, 70, 8, "set_blame_between", "Between files:"),
    ]

    _COLORS = [
        ("BlameNewColor", "IDC_NEWLINESCOLOR", "#ffff88"),
        ("BlameOldColor", "IDC_OLDLINESCOLOR", "#ffffff"),
    ]
    _SETTINGS = [
        ("BlameFontName", "IDC_FONTNAMES", "text", "Consolas"),
        ("BlameFontSize", "IDC_FONTSIZES", "text", "10"),
        ("BlameTabSize", "IDC_TABSIZE", "text", "4"),
        ("DetectMovedOrCopiedLines", "IDC_DETECT_MOVED_OR_COPIED_LINES",
         "index", 0),
        ("DetectMovedOrCopiedLinesNumCharactersWithinFile",
         "IDC_DETECT_MOVED_OR_COPIED_LINES_NUM_CHARACTERS_WITHIN_FILE",
         "text", "20"),
        ("DetectMovedOrCopiedLinesNumCharactersFromFiles",
         "IDC_DETECT_MOVED_OR_COPIED_LINES_NUM_CHARACTERS_FROM_FILES",
         "text", "20"),
        ("IgnoreWhitespace", "IDC_IGNORE_WHITESPACE", "bool", False),
        ("ShowCompleteLog", "IDC_SHOWCOMPLETELOG", "bool", True),
        ("OnlyFirstParent", "IDC_BLAME_ONLYFIRSTPARENT", "bool", False),
        ("FollowRenames", "IDC_FOLLOWRENAMES", "bool", False),
    ]

    def _build_ui(self):
        super()._build_ui()
        self._fill_fonts()
        if c := self._ctl.get("IDC_DETECT_MOVED_OR_COPIED_LINES"):
            c.addItems(["", "0", "1", "2"])

    def _fill_fonts(self):
        from PySide6.QtGui import QFontDatabase
        if c := self._ctl.get("IDC_FONTNAMES"):
            c.addItems(QFontDatabase.families())
        if c := self._ctl.get("IDC_FONTSIZES"):
            c.addItems([str(s) for s in range(6, 73)])


class _UDiffPage(_ColorPage):
    """IDD_SETTINGSUDIFF —— TortoiseGitUDiff：字体/颜色。"""

    TEMPLATE = "IDD_SETTINGSUDIFF"

    # 注意：RC 中首个 IDC_STATIC（"Colors" 分组框）未被去重，勿重复添加
    _GROUPS = [(7, 148, 286, 40, "set_udiff_font_group", "Font")]
    _LABELS = [
        (126, 15, 76, 8, "set_udiff_foreground", "Foreground"),
        (209, 14, 75, 8, "set_udiff_background", "Background"),
        (14, 32, 112, 8, "set_udiff_command", "Diff command"),
        (14, 48, 112, 8, "set_udiff_position", "Diff position"),
        (14, 64, 112, 8, "set_udiff_header", "Diff header"),
        (14, 80, 112, 8, "set_udiff_comment", "Diff comment"),
        (14, 96, 112, 8, "set_udiff_added", "Diff added lines"),
        (14, 112, 112, 8, "set_udiff_removed", "Diff removed lines"),
        (14, 156, 92, 14, "set_udiff_font", "&Font:"),
        (14, 174, 92, 8, "set_udiff_tabsize", "Tab size:"),
        (7, 193, 287, 46, "set_udiff_note",
         "Note: These settings also apply to the Patch Viewer dialog.\n"
         "To select whether you would like to use the build-in or any "
         "alternative diff viewer program go to \"Diff Viewer\" preferences "
         "section in the leftward tree."),
    ]

    # 对齐 DiffView.LIGHT 默认配色
    _COLORS = [
        ("UDiffForeCommandColor", "IDC_FORECOMMANDCOLOR", "#0a2436"),
        ("UDiffBackCommandColor", "IDC_BACKCOMMANDCOLOR", "#ffffff"),
        ("UDiffForePositionColor", "IDC_FOREPOSITIONCOLOR", "#ff0000"),
        ("UDiffBackPositionColor", "IDC_BACKPOSITIONCOLOR", "#ffffff"),
        ("UDiffForeHeaderColor", "IDC_FOREHEADERCOLOR", "#800000"),
        ("UDiffBackHeaderColor", "IDC_BACKHEADERCOLOR", "#ffff80"),
        ("UDiffForeCommentColor", "IDC_FORECOMMENTCOLOR", "#008000"),
        ("UDiffBackCommentColor", "IDC_BACKCOMMENTCOLOR", "#ffffff"),
        ("UDiffForeAddedColor", "IDC_FOREADDEDCOLOR", "#000000"),
        ("UDiffBackAddedColor", "IDC_BACKADDEDCOLOR", "#ccffcc"),
        ("UDiffForeRemovedColor", "IDC_FOREREMOVEDCOLOR", "#000000"),
        ("UDiffBackRemovedColor", "IDC_BACKREMOVEDCOLOR", "#ffdddd"),
    ]
    _SETTINGS = [
        ("UDiffFontName", "IDC_FONTNAMES", "text", "Consolas"),
        ("UDiffFontSize", "IDC_FONTSIZES", "text", "10"),
        ("UDiffTabSize", "IDC_TABSIZE", "text", "4"),
    ]

    def _build_ui(self):
        super()._build_ui()
        from PySide6.QtGui import QFontDatabase
        if c := self._ctl.get("IDC_FONTNAMES"):
            c.addItems(QFontDatabase.families())
        if c := self._ctl.get("IDC_FONTSIZES"):
            c.addItems([str(s) for s in range(6, 73)])


class _MenuListPage(_SettingPage):
    """Context Menu / Context Menu 2 通用：菜单项复选列表。"""

    SETTINGS_KEY = ""
    # 未保存时的默认勾选集合；None 表示全部勾选
    DEFAULT_CHECKED_COMMANDS: set | None = None

    def _build_ui(self):
        super()._build_ui()
        _add_static_labels(self)
        tree = self._ctl.get("IDC_MENULIST")
        if tree is not None:
            tree.setColumnCount(1)
            tree.setHeaderHidden(True)
            tree.setRootIsDecorated(False)
            self._populate_menu_list(tree)
        if cb := self._ctl.get("IDC_SELECTALL"):
            cb.clicked.connect(self._on_select_all)
        if b := self._ctl.get("IDC_RESTORE"):
            b.clicked.connect(self._on_restore)

    def _populate_menu_list(self, tree):
        from .. import menuitems as mi
        saved = general_settings().value(self.SETTINGS_KEY, [], type=list) or []
        tree.clear()
        seen = set()
        for e in mi.MENU_INFO:
            if not e.command or e.command == "separator":
                continue
            if e.menu_id in seen:
                continue
            seen.add(e.menu_id)
            it = QTreeWidgetItem([tr(e.label_key, e.label)])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if saved:
                checked = e.command in saved
            elif self.DEFAULT_CHECKED_COMMANDS is None:
                checked = True
            else:
                checked = e.command in self.DEFAULT_CHECKED_COMMANDS
            it.setCheckState(0, Qt.CheckState.Checked if checked
                             else Qt.CheckState.Unchecked)
            it.setData(0, Qt.ItemDataRole.UserRole, e.command)
            tree.addTopLevelItem(it)

    def _on_select_all(self):
        tree = self._ctl.get("IDC_MENULIST")
        cb = self._ctl.get("IDC_SELECTALL")
        if tree is None or cb is None:
            return
        state = (Qt.CheckState.Checked if cb.isChecked()
                 else Qt.CheckState.Unchecked)
        for i in range(tree.topLevelItemCount()):
            tree.topLevelItem(i).setCheckState(0, state)

    def _on_restore(self):
        tree = self._ctl.get("IDC_MENULIST")
        if tree is None:
            return
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if self.DEFAULT_CHECKED_COMMANDS is None:
                checked = True
            else:
                checked = (it.data(0, Qt.ItemDataRole.UserRole)
                           in self.DEFAULT_CHECKED_COMMANDS)
            it.setCheckState(0, Qt.CheckState.Checked if checked
                             else Qt.CheckState.Unchecked)

    def save_to_settings(self):
        tree = self._ctl.get("IDC_MENULIST")
        if tree is None or not self.SETTINGS_KEY:
            return
        checked = []
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                checked.append(it.data(0, Qt.ItemDataRole.UserRole))
        s = general_settings()
        s.setValue(self.SETTINGS_KEY, checked)
        s.sync()


class _ContextMenuPage(_MenuListPage):
    """IDD_SETTINGSLOOKANDFEEL —— Context Menu。"""

    TEMPLATE = "IDD_SETTINGSLOOKANDFEEL"
    SETTINGS_KEY = "contextMenuEntries"
    # 原版 defaultTopMenuEntries = Sync | CreateRepo | Clone | Commit
    DEFAULT_CHECKED_COMMANDS = {"sync", "repocreate", "clone", "commit"}

    # 注意：RC 中首个 IDC_STATIC（第一个分组框）未被去重，勿重复添加
    _GROUPS = [
        (7, 161, 286, 56, "set_ctx_no_menu_group",
         "Do not show the context menu for the following paths:"),
    ]
    _LABELS = [
        (12, 18, 274, 18, "set_ctx_hint",
         "Unchecked items will appear in the TortoiseGit submenu, checked "
         "items directly in the main context menu."),
    ]
    _SETTINGS = [
        ("HideMenusForUnversionedItems", "IDC_HIDEMENUS", "bool", False),
        ("NoContextPaths", "IDC_NOCONTEXTPATHS", "text", ""),
        ("EnableDragContextMenu", "IDC_ENABLEDRAGCONTEXTMENU", "bool", True),
    ]


class _ContextMenu2Page(_MenuListPage):
    """IDD_SETTINGSEXTMENU —— Context Menu 2。"""

    TEMPLATE = "IDD_SETTINGSEXTMENU"
    SETTINGS_KEY = "contextMenuHideEntries"
    # 原版 defaultExtMenuEntries = SVNIgnore | StashApply | SubmoduleSync
    DEFAULT_CHECKED_COMMANDS = {"svnignore", "stashapply", "subsync"}

    # 注意：RC 中首个 IDC_STATIC（分组框）未被去重，勿重复添加
    _LABELS = [
        (12, 18, 274, 18, "set_ctx2_hint",
         "Checked items will be hidden in the context menu by default and "
         "will only be visible if the shift key is pressed while opening the "
         "context menu."),
    ]


class _DialogsPage(_SettingPage):
    """IDD_SETTINGSDIALOGS —— Dialogs 1（补回被去重的 IDC_STATIC 标签）。"""

    TEMPLATE = "IDD_SETTINGSDIALOGS"

    _LABELS = [
        (14, 20, 140, 8, "set_default_log_limit",
         "Default limitation of log messages:"),
        (14, 34, 92, 13, "set_font_log", "&Font for log messages:"),
        (19, 211, 84, 8, "set_describe_strategy", "Describe Strategy"),
        (19, 228, 84, 8, "set_describe_size", "Abbreviated size"),
    ]

    # 键名对齐 TortoiseGit 注册表（Software\TortoiseGit\...）
    _SETTINGS = [
        ("NumberOfLogs", "IDC_DEFAULT_NUMBER_OF", "text", "1"),
        ("NumberOfLogsScale", "IDC_DEFAULT_SCALE", "index", 0),
        ("LogFontName", "IDC_FONTNAMES", "text", "Consolas"),
        ("LogFontSize", "IDC_FONTSIZES", "text", "9"),
        ("LogDateFormat", "IDC_SHORTDATEFORMAT", "bool", True),
        ("RelativeTimes", "IDC_RELATIVETIMES", "bool", False),
        ("AsteriskLogPrefix", "IDC_ASTERISKLOGPREFIX", "bool", True),
        ("UseSystemLocaleForDates", "IDC_SYSTEMLOCALEFORDATES", "bool", True),
        ("DiffByDoubleClickInLog", "IDC_DIFFBYDOUBLECLICK", "bool", False),
        ("AbbreviateRenamings", "IDC_ABBREVIATERENAMINGS", "bool", False),
        ("SymbolizeRefNames", "IDC_SYMBOLIZEREFNAMES", "bool", False),
        ("EnableLogCache", "IDC_ENABLELOGCACHE", "bool", True),
        ("EnableGravatar", "IDC_ENABLEGRAVATAR", "bool", False),
        ("GravatarUrl", "IDC_GRAVATARURL", "text",
         "https://gravatar.com/avatar/%HASH%?d=identicon"),
        ("DrawTagsBranchesOnRightSide", "IDC_RIGHTSIDEBRANCHESTAGS",
         "bool", False),
        ("FullCommitMessageOnLogLine", "IDC_FULLCOMMITMESSAGEONLOGLINE",
         "bool", False),
        ("ShowBranchRevisionNumber", "IDC_SHOWREVCOUNTER", "bool", False),
        ("ShowDescribe", "IDC_SHOWDESCRIBE", "bool", False),
        ("DescribeStrategy", "IDC_DESCRIBESTRATEGY", "index", 0),
        ("DescribeAbbreviatedSize", "IDC_DESCRIBEABBREVIATEDSIZE",
         "text", "7"),
        ("DescribeAlwaysLong", "IDC_DESCRIBEALWAYSLONG", "bool", False),
        ("DescribeOnlyFollowFirstParent", "IDC_DESCRIBEONLYFIRSTPARENT",
         "bool", False),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        gb = QGroupBox(tr("set_describe", "Describe"), self)
        gb.setGeometry(self._fu.px(14, 183, 272, 76))
        gb.lower()
        for x, y, w, h, key, default in self._LABELS:
            lbl = QLabel(tr(key, default), self)
            lbl.setGeometry(self._fu.px(x, y, w, h))
        self._populate_combos()

    def _populate_combos(self):
        from PySide6.QtGui import QFontDatabase
        if c := self._ctl.get("IDC_DEFAULT_SCALE"):
            c.addItems([
                tr("set_scale_nolimit", "No limit"),
                tr("set_scale_lastdate", "Last selected date"),
                tr("set_scale_lastn_commits", "Last N commits"),
                tr("set_scale_lastn_years", "Last N years"),
                tr("set_scale_lastn_months", "Last N months"),
                tr("set_scale_lastn_weeks", "Last N weeks"),
            ])
        if c := self._ctl.get("IDC_FONTNAMES"):
            c.addItems(QFontDatabase.families())
        if c := self._ctl.get("IDC_FONTSIZES"):
            c.addItems([str(s) for s in range(6, 32, 2)])
        if c := self._ctl.get("IDC_GRAVATARURL"):
            c.setEditable(True)
            c.addItems([
                "https://gravatar.com/avatar/%HASH%",
                "https://gravatar.com/avatar/%HASH%?d=mm",
                "https://gravatar.com/avatar/%HASH%?d=identicon",
                "https://gravatar.com/avatar/%HASH%?d=monsterid",
                "https://gravatar.com/avatar/%HASH%?d=wavatar",
                "https://gravatar.com/avatar/%HASH%?d=retro",
                "https://gravatar.com/avatar/%HASH%?d=blank",
            ])
        if c := self._ctl.get("IDC_DESCRIBESTRATEGY"):
            c.addItems([
                tr("set_describe_annotated", "Annotated tags"),
                tr("set_describe_alltags", "All tags"),
                tr("set_describe_allrefs", "All refs"),
            ])


class _Dialogs2Page(_SettingPage):
    """IDD_SETTINGSDIALOGS2 —— Dialogs 2（补回被去重的 IDC_STATIC 标签）。"""

    TEMPLATE = "IDD_SETTINGSDIALOGS2"

    _LABELS = [
        (14, 16, 85, 16, "set_autoclose", "&Autoclose Git.exe dialog:"),
        (14, 257, 270, 9, "set_dialogs3_hint",
         "Further options for the commit dialog are on Dialogs 3 page."),
    ]

    _SETTINGS = [
        ("AutoCloseGitProgress", "IDC_AUTOCLOSECOMBO", "index", 0),
        ("RevertWithRecycleBin", "IDC_USERECYCLEBIN", "bool", True),
        ("ConfirmKillProcess", "IDC_CONFIRMKILLPROCESS", "bool", False),
        ("SyncDialogRandomPos", "IDC_SYNCDIALOGRANDOMPOS", "bool", False),
        ("RefCompareHideUnchanged", "IDC_REFCOMPAREHIDEUNCHANGED",
         "bool", False),
        ("ShowGitexeTimings", "IDC_PROGRESSDLG_SHOW_TIMES", "bool", True),
        ("SortTagsReversed", "IDC_SORTTAGSREVERSED", "bool", False),
        ("NoSounds", "IDC_NOSOUNDS", "bool", False),
        ("BranchesIncludeFetchHead", "IDC_BRANCHESINCLUDEFETCHHEAD",
         "bool", True),
        ("UseMailmap", "IDC_USEMAILMAP", "bool", True),
        ("Autocompletion", "IDC_AUTOCOMPLETION", "bool", True),
        ("AutocompleteParseTimeout", "IDC_AUTOCOMPLETIONTIMEOUT", "text", "5"),
        ("MaxHistoryItems", "IDC_MAXHISTORY", "text", "25"),
        ("SelectFilesForCommit", "IDC_SELECTFILESONCOMMIT", "bool", True),
        ("AutoselectMissingFiles", "IDC_NOAUTOSELECTMISSING", "bool", False),
        ("StripCommentedLines", "IDC_STRIPCOMMENTEDLINES", "bool", False),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        for x, y, w, h, key, default in self._LABELS:
            lbl = QLabel(tr(key, default), self)
            lbl.setGeometry(self._fu.px(x, y, w, h))
        if c := self._ctl.get("IDC_AUTOCLOSECOMBO"):
            c.addItems([
                tr("set_autoclose_manual", "Manual"),
                tr("set_autoclose_nooptions", "If no options"),
                tr("set_autoclose_noerror", "If no errors"),
            ])


def _add_static_labels(page):
    """按页面上的 _GROUPS / _LABELS 定义补回被去重的 IDC_STATIC 标签/分组框。"""
    for x, y, w, h, key, default in getattr(page, "_GROUPS", []):
        gb = QGroupBox(tr(key, default), page)
        gb.setGeometry(page._fu.px(x, y, w, h))
        gb.lower()
    for x, y, w, h, key, default in getattr(page, "_LABELS", []):
        text = tr(key, default) if key else default
        lbl = QLabel(text, page)
        lbl.setGeometry(page._fu.px(x, y, w, h))


class _Dialogs3Page(_SettingPage):
    """IDD_SETTINGSDIALOGS3 —— Dialogs 3（补回被去重的标签/分组框）。"""

    TEMPLATE = "IDD_SETTINGSDIALOGS3"

    _GROUPS = [
        (7, 7, 286, 26, "set_config_source", "Config source"),
        (7, 34, 286, 136, "set_commit_group", "Commit"),
        (7, 170, 286, 40, "set_dialogs_group", "Dialogs"),
    ]
    _LABELS = [
        (173, 18, 13, 11, None, "<<"),
        (233, 18, 13, 11, None, "<<"),
        (112, 18, 13, 11, None, "<<"),
        (14, 43, 269, 18, "set_lang_hint",
         "Select the language this project is using. This settings affects "
         "the spell checker used for commit messages."),
        (14, 63, 99, 8, "set_language_label", "Language:"),
        (14, 80, 99, 10, "set_keep_english", "keep the file lists in English"),
        (14, 99, 269, 8, "set_min_chars",
         "Minimum number of chars for a commit message:"),
        (14, 113, 99, 8, "set_limit_label", "&Limit:"),
        (14, 126, 269, 8, "set_border_pos",
         "Char position where to show a border line in commit text boxes:"),
        (14, 138, 99, 8, "set_border_label", "&Border:"),
        (14, 153, 179, 10, "set_warn_signoff",
         "&Warn on missing Signed-Off-By on commit"),
        (14, 183, 91, 8, "set_overlay_icon", "&Overlay Icon:"),
        (14, 212, 99, 11, "set_save_to", "Save to:"),
    ]

    _SETTINGS = [
        ("ProjectLanguage", "IDC_LANGCOMBO", "index", 0),
        ("LogFileListEnglish", "IDC_KEEPFILELISTSENGLISH", "index", 0),
        ("LogMinSize", "IDC_LOGMINSIZE", "text", ""),
        ("LogWidthMarker", "IDC_BORDER", "text", ""),
        ("WarnNoSignedOffBy", "IDC_WARN_NO_SIGNED_OFF_BY", "index", 0),
        ("IconFile", "IDC_ICONFILE", "text", ""),
    ]
    _RADIO_GROUPS = [
        ("Dialogs3ConfigSource",
         ["IDC_RADIO_SETTINGS_EFFECTIVE", "IDC_RADIO_SETTINGS_LOCAL",
          "IDC_RADIO_SETTINGS_PROJECT", "IDC_RADIO_SETTINGS_GLOBAL",
          "IDC_RADIO_SETTINGS_SYSTEM"], 0),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)
        if c := self._ctl.get("IDC_LANGCOMBO"):
            for text, _key in _LANGUAGES:
                c.addItem(text)
        for cid in ("IDC_WARN_NO_SIGNED_OFF_BY", "IDC_KEEPFILELISTSENGLISH"):
            if c := self._ctl.get(cid):
                c.addItems(["", "true", "false"])
        if c := self._ctl.get("IDC_COMBO_SETTINGS_SAFETO"):
            c.addItems([
                tr("set_save_local", "Local"),
                tr("set_save_project", "Project"),
                tr("set_save_global", "Global"),
                tr("set_save_system", "System"),
            ])
        if b := self._ctl.get("IDC_ICONFILE_BROWSE"):
            b.clicked.connect(self._browse_icon)

    def _browse_icon(self):
        from ..utils.pick import pick_file
        p = pick_file(self, tr("set_select_icon", "Select overlay icon"), "")
        if p:
            w = self._ctl.get("IDC_ICONFILE")
            if w is not None:
                w.setText(p)


class _Colors1Page(_ColorPage):
    """IDD_SETTINGSCOLORS_1 —— Colors 1（补回被去重的标签/分组框 + 颜色读写）。"""

    TEMPLATE = "IDD_SETTINGSCOLORS_1"

    _GROUPS = [(7, 130, 286, 62, "col_revgraph_group", "Revision graph")]
    _LABELS = [
        (14, 23, 137, 8, "col_conflict", "possible or real conflict/obstructed"),
        (14, 40, 135, 8, "col_added", "added files"),
        (14, 57, 137, 8, "col_missing", "missing/deleted/replaced"),
        (14, 74, 137, 8, "col_merged", "merged"),
        (14, 92, 137, 8, "col_modified", "modified/copied"),
        (14, 109, 137, 8, "col_renamed", "renamed"),
        (14, 142, 137, 8, "col_note_node", "Note node"),
        (14, 159, 137, 8, "col_unknown_refs", "Unknown ref-types"),
    ]

    _COLORS = [
        ("Colors/Conflict", "IDC_CONFLICTCOLOR", "#ff0000"),
        ("Colors/Added", "IDC_ADDEDCOLOR", "#640064"),
        ("Colors/Deleted", "IDC_DELETEDCOLOR", "#640000"),
        ("Colors/Merged", "IDC_MERGEDCOLOR", "#006400"),
        ("Colors/Modified", "IDC_MODIFIEDCOLOR", "#0032a0"),
        ("Colors/Renamed", "IDC_RENAMEDCOLOR", "#0000ff"),
        ("Colors/NoteNode", "IDC_NOTENODECOLOR", "#a0a000"),
        ("Colors/OtherRef", "IDC_OTHERREFSCOLOR", "#e0e0e0"),
    ]
    _SETTINGS = [
        ("RevGraphUseLocalForCur", "IDC_REVGRAPHUSELOCALFORCUR", "bool", False),
        ("UseDarkMode", "IDC_DARKTHEME", "bool", False),
    ]


class _Colors2Page(_ColorPage):
    """IDD_SETTINGSCOLORS_2 —— Colors 2（补回被去重的标签 + 颜色读写）。"""

    TEMPLATE = "IDD_SETTINGSCOLORS_2"

    _LABELS = [
        (14, 23, 137, 8, "col_current_branch", "Current Branch"),
        (14, 40, 135, 8, "col_local_branch", "Local Branch"),
        (14, 57, 137, 8, "col_remote_branch", "Remote Branch"),
        (14, 74, 137, 8, "col_tag", "Tag"),
        (14, 103, 137, 8, "col_filter_match", "Filter match"),
    ]

    _COLORS = [
        ("Colors/CurrentBranch", "IDC_CURRENT_BRANCH", "#c80000"),
        ("Colors/LocalBranch", "IDC_LOCAL_BRANCH", "#00c300"),
        ("Colors/RemoteBranch", "IDC_REMOTE_BRANCH", "#ffddaa"),
        ("Colors/Tag", "IDC_TAGS", "#ffff00"),
        ("Colors/FilterMatch", "IDC_FILTERMATCHCOLOR", "#c80000"),
    ]


class _Colors3Page(_ColorPage):
    """IDD_SETTINGSCOLORS_3 —— Colors 3（补回被去重的标签 + 颜色/线宽读写）。"""

    TEMPLATE = "IDD_SETTINGSCOLORS_3"

    _LABELS = [
        (14, 23, 137, 8, "col_line1", "LINE1"),
        (14, 40, 135, 8, "col_line2", "LINE2"),
        (14, 57, 137, 8, "col_line3", "LINE3"),
        (14, 74, 137, 8, "col_line4", "LINE4"),
        (14, 91, 137, 8, "col_line5", "LINE5"),
        (14, 108, 135, 8, "col_line6", "LINE6"),
        (14, 125, 137, 8, "col_line7", "LINE7"),
        (14, 142, 137, 8, "col_line8", "LINE8"),
        (14, 159, 33, 8, "col_line_width", "Line width"),
        (14, 176, 32, 8, "col_node_size", "Node size"),
    ]

    _COLORS = [
        ("Colors/BranchLine1", "IDC_COLOR_LINE1", "#000000"),
        ("Colors/BranchLine2", "IDC_COLOR_LINE2", "#ff0000"),
        ("Colors/BranchLine3", "IDC_COLOR_LINE3", "#00ff00"),
        ("Colors/BranchLine4", "IDC_COLOR_LINE4", "#0000ff"),
        ("Colors/BranchLine5", "IDC_COLOR_LINE5", "#808080"),
        ("Colors/BranchLine6", "IDC_COLOR_LINE6", "#808000"),
        ("Colors/BranchLine7", "IDC_COLOR_LINE7", "#008080"),
        ("Colors/BranchLine8", "IDC_COLOR_LINE8", "#800080"),
    ]
    _SETTINGS = [
        ("LogLineWidth", "IDC_LOGGRAPHLINEWIDTH", "text", "2"),
        ("LogNodeSize", "IDC_LOGGRAPHNODESIZE", "text", "10"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        if c := self._ctl.get("IDC_LOGGRAPHLINEWIDTH"):
            c.addItems([str(i) for i in range(1, 11)])
        if c := self._ctl.get("IDC_LOGGRAPHNODESIZE"):
            c.addItems([str(i) for i in range(1, 31)])


# ---------------------------------------------------------------------------
# 设置主对话框
# ---------------------------------------------------------------------------

class SettingsDlg(QDialog):
    def __init__(self, repo: Repository | None = None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.pages: List[Tuple[QTreeWidgetItem, _SettingPage]] = []
        self._build_ui()
        self._load_config()
        self._load_general()

    @property
    def _runner(self) -> GitRunner:
        if self.repo is not None:
            return self.repo.runner
        return GitRunner(cwd=os.path.expanduser("~"))

    # ---- UI ----
    def _build_ui(self):
        title = tr("settings_title", "Settings")
        if self.repo is not None:
            title = f"{title} - {self.repo.root}"
        self.setWindowTitle(title)
        self.resize(860, 560)
        root = QVBoxLayout(self)

        split = QSplitter(self)
        self.tree = QTreeWidget(split)
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(220)
        self.stack = QStackedWidget(split)
        split.addWidget(self.tree)
        split.addWidget(self.stack)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 620])
        root.addWidget(split, 1)

        btnbar = QHBoxLayout()
        btnbar.addStretch(1)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton(tr("apply"), self)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)
        for b in (self.btn_ok, self.btn_cancel, self.btn_apply, self.btn_help):
            btnbar.addWidget(b)
        root.addLayout(btnbar)

        self.tree.currentItemChanged.connect(self._on_tree_changed)
        self._build_pages()

    def _build_pages(self):
        """对齐 CSettings::AddPropPages 的树结构与顺序。"""
        self._items: dict[str, QTreeWidgetItem] = {}
        has_repo = self.repo is not None

        main = self._add_page("main", _GeneralPage(self), "IDI_GENERAL")
        self._add_page("look", _ContextMenuPage(self), "IDI_MISC", main)
        self._add_page("extmenu", _ContextMenu2Page(self), "IDI_MISC", main)
        if _is_win11():
            self._add_page(
                "win11menu",
                _Win11MenuPage(self),
                "IDI_MISC",
                main,
            )
        self._add_page("dialog", _DialogsPage(self), "IDI_DIALOGS", main)
        self._add_page("dialog2", _Dialogs2Page(self), "IDI_DIALOGS", main)
        self._add_page("dialog3", _Dialogs3Page(self), "IDI_DIALOGS", main)
        self._add_page("color1", _Colors1Page(self), "IDI_LOOKANDFEEL", main)
        self._add_page("color2", _Colors2Page(self), "IDI_LOOKANDFEEL", main)
        self._add_page("color3", _Colors3Page(self), "IDI_LOOKANDFEEL", main)
        self._add_page(
            "alternativeeditor",
            _AlternativeEditorPage(self),
            "IDI_NOTEPAD",
            main,
        )

        git = self._add_page("gitconfig", _GitPage(self), "IDI_GITCONFIG")
        if has_repo:
            self._add_page(
                "gitremote", _GitRemotePage(self),
                "IDI_GITREMOTE", git)
        self._add_page(
            "gitcredential",
            _CredentialPage(self),
            "IDI_GITCREDENTIAL", git)

        hooks = self._add_page("hooks", _RcPage("IDD_SETTINGSHOOKS", self), "IDI_HOOK")
        self._add_page("bugtraq", _RcPage("IDD_SETTINGSBUGTRAQ", self), "IDI_BUGTRAQ", hooks)
        if has_repo:
            self._add_page(
                "bugtraqconfig",
                _BugtraqConfigPage(self),
                "IDI_BUGTRAQ",
                hooks,
            )

        overlay = self._add_page("overlay", _OverlayPage(self), "IDI_SET_OVERLAYS")
        self._add_page("overlays", _OverlayIconsPage(self), "IDI_ICONSET", overlay)
        self._add_page(
            "overlayshandlers",
            _OverlayHandlersPage(self),
            "IDI_SET_OVERLAYS",
            overlay,
        )

        proxy = self._add_page("proxy", _NetworkPage(self), "IDI_PROXY")
        self._add_page("smtp", _SmtpPage(self), "IDI_MISC", proxy)

        diff = self._add_page("diff", _DiffPage(self), "IDI_SWITCHLEFTRIGHT")
        self._add_page("merge", _MergePage(self), "IDI_MERGEACTIVE", diff)

        self._add_page("save", _SavedDataPage(self), "IDI_SAVEDDATA")
        self._add_page("blame", _BlamePage(self), "IDI_TORTOISEBLAME")
        self._add_page("udiff", _UDiffPage(self), "IDI_TORTOISEUDIFF")
        self._add_page("advanced", _AdvancedPage(self), "IDI_GENERAL")

        self.tree.expandAll()
        default = "gitconfig" if has_repo else "main"
        item = self._items.get(default) or self._items.get("main")
        if item is not None:
            self.tree.setCurrentItem(item)

    def _add_page(self, key: str, page: _SettingPage, icon_name: str,
                  parent: QTreeWidgetItem | None = None) -> QTreeWidgetItem:
        idx = self.stack.count()
        self.stack.addWidget(page)
        item = QTreeWidgetItem(parent if parent is not None else self.tree)
        caption = getattr(page, "_spec", None)
        title = caption.caption if caption and caption.caption else key
        item.setText(0, tr_settings(title))
        item.setData(0, Qt.ItemDataRole.UserRole, idx)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, key)
        try:
            from ..res import icons as _icons
            ic = _icons.icon(icon_name)
            if ic is not None and not ic.isNull():
                item.setIcon(0, ic)
        except Exception:
            pass
        self._items[key] = item
        self.pages.append((item, page))
        return item

    def _on_tree_changed(self, item, _prev):
        if item is None:
            return
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None:
            self.stack.setCurrentIndex(idx)

    def _on_help(self):
        QMessageBox.information(self, tr("help"), tr("settings_title", "Settings"))

    # ---- 命名自定义逻辑（Git 页）----
    @property
    def name_edit(self):
        for _, page in self.pages:
            edit = getattr(page, "name_edit", None)
            if edit is not None:
                return edit
        return None

    @property
    def email_edit(self):
        for _, page in self.pages:
            edit = getattr(page, "email_edit", None)
            if edit is not None:
                return edit
        return None

    # ---- Git config ----
    def _load_config(self):
        values = {
            "user.name": "",
            "user.email": "",
            "http.proxy": "",
            "core.autocrlf": "false",
            "init.defaultBranch": "main",
        }
        for key, val in self._config_lines():
            if key in values:
                values[key] = val
        if self.name_edit is not None:
            self.name_edit.setText(values["user.name"])
        if self.email_edit is not None:
            self.email_edit.setText(values["user.email"])
        # network / proxy：git 只认单个 http.proxy（[proto://][user:pass@]host[:port]）
        for _, page in self.pages:
            if isinstance(page, _NetworkPage):
                proxy = values["http.proxy"]
                host, port, user, pwd = _parse_proxy(proxy)
                if page.enable is not None:
                    page.enable.setChecked(bool(proxy))
                if page.server_edit is not None:
                    page.server_edit.setText(host)
                if page.port_edit is not None:
                    page.port_edit.setText(port or "8080")
                if page.username_edit is not None:
                    page.username_edit.setText(user)
                if page.password_edit is not None:
                    page.password_edit.setText(pwd)
                if page.ssh_edit is not None:
                    page.ssh_edit.setText(
                        general_settings().value("sshClient", "") or "")
            elif isinstance(page, _SmtpPage):
                self._load_smtp(page)
            elif isinstance(page, _DiffPage):
                if page.diff_edit:
                    page.diff_edit.setText(self._get_ext("tortoisegit.externaldiff"))
                if page.viewer_edit:
                    page.viewer_edit.setText(self._get_ext("tortoisegit.diffviewer"))
            elif isinstance(page, _MergePage):
                if page.merge_edit:
                    page.merge_edit.setText(self._get_ext("tortoisegit.externalmerge"))
            elif isinstance(page, _AdvancedPage):
                self._load_advanced(page)
            elif isinstance(page, _GitPage):
                self._load_git(page)
            elif isinstance(page, _BugtraqConfigPage):
                self._load_bugtraq(page)
        for _, page in self.pages:
            page.load_settings()

    def _load_bugtraq(self, page: "_BugtraqConfigPage"):
        g = self._get_ext
        page._set("IDC_BUGTRAQ_URL", g("bugtraq.url"))
        page._set_combo("IDC_BUGTRAQ_WARNINGIFNOISSUE",
                        g("bugtraq.warnifnoissue"))
        page._set("IDC_BUGTRAQ_MESSAGE", g("bugtraq.message"))
        page._set_combo("IDC_BUGTRAQ_APPEND", g("bugtraq.append"))
        page._set("IDC_BUGTRAQ_LABEL", g("bugtraq.label"))
        page._set_combo("IDC_BUGTRAQ_NUMBER", g("bugtraq.number"))
        page._set("IDC_BUGTRAQ_LOGREGEX", g("bugtraq.logregex"))
        page._set("IDC_UUID32", g("bugtraq.provideruuid"))
        page._set("IDC_UUID64", g("bugtraq.provideruuid64"))
        page._set("IDC_PARAMS", g("bugtraq.providerparams"))

    def _load_git(self, page: "_GitPage"):
        if page.signingkey_edit is not None:
            page.signingkey_edit.setText(self._get_ext("user.signingkey"))
        for combo, key in ((page.autocrlf_combo, "core.autocrlf"),
                           (page.safecrlf_combo, "core.safecrlf")):
            if combo is not None:
                val = self._get_ext(key)
                i = combo.findText(val)
                combo.setCurrentIndex(i if i >= 0 else 0)
        if page.quotepath_check is not None:
            page.quotepath_check.setChecked(
                self._get_ext("core.quotepath").strip().lower()
                in ("true", "1", "yes"))
        if page.prune_check is not None:
            page.prune_check.setChecked(
                self._get_ext("fetch.prune").strip().lower()
                in ("true", "1", "yes"))

    def _load_smtp(self, page: "_SmtpPage"):
        g = self._get_ext
        if page.server_edit is not None:
            page.server_edit.setText(g("sendemail.smtpserver"))
        if page.port_edit is not None:
            page.port_edit.setText(g("sendemail.smtpserverport"))
        if page.from_edit is not None:
            page.from_edit.setText(g("sendemail.from"))
        if page.user_edit is not None:
            page.user_edit.setText(g("sendemail.smtpuser"))
        if page.encryption_combo is not None:
            enc = g("sendemail.smtpencryption")
            i = page.encryption_combo.findText(enc)
            page.encryption_combo.setCurrentIndex(i if i >= 0 else 0)
        if page.auth_check is not None:
            page.auth_check.setChecked(
                g("sendemail.smtpauth").strip().lower() in ("true", "1", "yes"))

    def _load_advanced(self, page: "_AdvancedPage"):
        tree = page.config_tree
        if tree is None:
            return
        tree.clear()
        out = self._runner.run("config", "--global", "--list").stdout or ""
        for line in out.splitlines():
            key, _, val = line.partition("=")
            key = key.strip()
            if not key:
                continue
            item = QTreeWidgetItem([key, val.strip()])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            tree.addTopLevelItem(item)

    def _config_lines(self) -> List[Tuple[str, str]]:
        keys = ["user.name", "user.email", "http.proxy",
                "core.autocrlf", "init.defaultBranch"]
        result = self._runner.run("config", "--global", "--get-regexp",
                                  "^(" + "|".join(k.replace(".", r"\.") for k in keys) + ")$")
        out = result.stdout or ""
        values: List[Tuple[str, str]] = []
        for line in out.splitlines():
            key, _, val = line.partition(" ")
            if key.strip():
                values.append((key.strip(), val.strip()))
        return values

    def _get_ext(self, key: str) -> str:
        r = self._runner.run("config", "--global", "--get", key)
        if r.returncode == 0 and r.stdout and r.stdout.strip():
            return r.stdout.strip()
        return ""

    def _load_general(self):
        for _, page in self.pages:
            if isinstance(page, _GeneralPage):
                page.setup()
                page.load_from_settings()
                break

    def _on_ok(self):
        self._apply()
        self.accept()

    def _apply(self):
        if self.name_edit is not None:
            self._set_global("user.name", self.name_edit.text().strip())
        if self.email_edit is not None:
            self._set_global("user.email", self.email_edit.text().strip())
        for _, page in self.pages:
            if isinstance(page, _GeneralPage):
                page.apply_to_settings()
        for _, page in self.pages:
            if isinstance(page, _NetworkPage):
                self._apply_proxy(page)
            elif isinstance(page, _SmtpPage):
                self._apply_smtp(page)
            elif isinstance(page, _DiffPage):
                val = page.diff_edit.text().strip() if page.diff_edit else ""
                self._set_global("tortoisegit.externaldiff", val or None)
                val2 = page.viewer_edit.text().strip() if page.viewer_edit else ""
                self._set_global("tortoisegit.diffviewer", val2 or None)
            elif isinstance(page, _MergePage):
                val = page.merge_edit.text().strip() if page.merge_edit else ""
                self._set_global("tortoisegit.externalmerge", val or None)
            elif isinstance(page, _AdvancedPage):
                self._apply_advanced(page)
            elif isinstance(page, _MenuListPage):
                page.save_to_settings()
            elif isinstance(page, _GitPage):
                self._apply_git(page)
            elif isinstance(page, _BugtraqConfigPage):
                self._apply_bugtraq(page)
        for _, page in self.pages:
            page.save_settings()

    def _apply_bugtraq(self, page: "_BugtraqConfigPage"):
        mapping = [
            ("bugtraq.url", "IDC_BUGTRAQ_URL", "text"),
            ("bugtraq.warnifnoissue", "IDC_BUGTRAQ_WARNINGIFNOISSUE", "combo"),
            ("bugtraq.message", "IDC_BUGTRAQ_MESSAGE", "text"),
            ("bugtraq.append", "IDC_BUGTRAQ_APPEND", "combo"),
            ("bugtraq.label", "IDC_BUGTRAQ_LABEL", "text"),
            ("bugtraq.number", "IDC_BUGTRAQ_NUMBER", "combo"),
            ("bugtraq.logregex", "IDC_BUGTRAQ_LOGREGEX", "text"),
            ("bugtraq.provideruuid", "IDC_UUID32", "text"),
            ("bugtraq.provideruuid64", "IDC_UUID64", "text"),
            ("bugtraq.providerparams", "IDC_PARAMS", "text"),
        ]
        for key, cid, kind in mapping:
            val = page._combo(cid) if kind == "combo" else page._text(cid)
            self._set_global(key, val or None)

    def _apply_git(self, page: "_GitPage"):
        if page.signingkey_edit is not None:
            self._set_global("user.signingkey",
                             page.signingkey_edit.text().strip() or None)
        if page.autocrlf_combo is not None:
            self._set_global("core.autocrlf",
                             page.autocrlf_combo.currentText().strip() or None)
        if page.safecrlf_combo is not None:
            self._set_global("core.safecrlf",
                             page.safecrlf_combo.currentText().strip() or None)
        if page.quotepath_check is not None:
            self._set_global("core.quotepath",
                             "true" if page.quotepath_check.isChecked()
                             else "false")
        if page.prune_check is not None:
            self._set_global("fetch.prune",
                             "true" if page.prune_check.isChecked() else "false")

    def _apply_proxy(self, page: "_NetworkPage"):
        enabled = page.enable.isChecked() if page.enable is not None else True
        host = page.server_edit.text().strip() if page.server_edit else ""
        port = page.port_edit.text().strip() if page.port_edit else ""
        user = page.username_edit.text().strip() if page.username_edit else ""
        pwd = page.password_edit.text().strip() if page.password_edit else ""
        if enabled and host:
            auth = f"{user}:{pwd}@" if user else ""
            value = f"http://{auth}{host}" + (f":{port}" if port else "")
            self._set_global("http.proxy", value)
        else:
            self._set_global("http.proxy", None)
        if page.ssh_edit is not None:
            s = general_settings()
            s.setValue("sshClient", page.ssh_edit.text().strip())
            s.sync()

    def _apply_smtp(self, page: "_SmtpPage"):
        for key, wgt in (("sendemail.smtpserver", page.server_edit),
                         ("sendemail.smtpserverport", page.port_edit),
                         ("sendemail.from", page.from_edit),
                         ("sendemail.smtpuser", page.user_edit)):
            val = wgt.text().strip() if wgt is not None else ""
            self._set_global(key, val or None)
        if page.encryption_combo is not None:
            enc = page.encryption_combo.currentText().strip()
            self._set_global("sendemail.smtpencryption", enc or None)
        if page.auth_check is not None:
            self._set_global("sendemail.smtpauth",
                             "true" if page.auth_check.isChecked() else None)

    def _apply_advanced(self, page: "_AdvancedPage"):
        tree = page.config_tree
        if tree is None:
            return
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            key = it.text(0).strip()
            if not key:
                continue
            self._set_global(key, it.text(1).strip() or None)

    def _set_global(self, key: str, val: str | None):
        if val:
            self._runner.run("config", "--global", key, val)
        else:
            self._runner.run("config", "--global", "--unset-all", key)