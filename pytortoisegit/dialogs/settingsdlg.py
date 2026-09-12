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


# ---------------------------------------------------------------------------
# General 页（IDD_SETTINGSMAIN）
# ---------------------------------------------------------------------------

_APP_NAME = "PyTortoiseGit"


def general_settings() -> QSettings:
    """General 页的应用级配置（跨平台，Windows 下写注册表）。"""
    return QSettings(_APP_NAME, _APP_NAME)


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

    @property
    def name_edit(self):
        return self._ctl.get("IDC_GIT_USERNAME")

    @property
    def email_edit(self):
        return self._ctl.get("IDC_GIT_USEREMAIL")


class _DiffPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSPROGSDIFF"

    def _build_ui(self):
        super()._build_ui()
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

    def _build_ui(self):
        super()._build_ui()
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

    def _build_ui(self):
        super()._build_ui()
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


class _BlamePage(_SettingPage):
    """IDD_SETTINGSTBLAME —— TortoiseGitBlame：字体/颜色/移动行检测。"""

    TEMPLATE = "IDD_SETTINGSTBLAME"

    _DEFAULT_COLORS = {
        "IDC_NEWLINESCOLOR": "#ffff88",
        "IDC_OLDLINESCOLOR": "#ffffff",
    }

    def _build_ui(self):
        super()._build_ui()
        self._fill_fonts()
        self._apply_colors()
        if c := self._ctl.get("IDC_DETECT_MOVED_OR_COPIED_LINES"):
            c.addItems(["", "0", "1", "2"])
        if b := self._ctl.get("IDC_RESTORE"):
            b.clicked.connect(self._apply_colors)

    def _fill_fonts(self):
        from PySide6.QtGui import QFontDatabase
        if c := self._ctl.get("IDC_FONTNAMES"):
            c.addItems(QFontDatabase.families())
        if c := self._ctl.get("IDC_FONTSIZES"):
            c.addItems([str(s) for s in range(6, 73)])

    def _apply_colors(self):
        for cid, color in self._DEFAULT_COLORS.items():
            w = self._ctl.get(cid)
            if w is not None:
                w.setText("")
                w.setStyleSheet(f"background-color: {color};")


class _UDiffPage(_SettingPage):
    """IDD_SETTINGSUDIFF —— TortoiseGitUDiff：字体/颜色。"""

    TEMPLATE = "IDD_SETTINGSUDIFF"

    # 对齐 DiffView.LIGHT 默认配色
    _DEFAULT_COLORS = {
        "IDC_FORECOMMANDCOLOR": "#0a2436",
        "IDC_BACKCOMMANDCOLOR": "#ffffff",
        "IDC_FOREPOSITIONCOLOR": "#ff0000",
        "IDC_BACKPOSITIONCOLOR": "#ffffff",
        "IDC_FOREHEADERCOLOR": "#800000",
        "IDC_BACKHEADERCOLOR": "#ffff80",
        "IDC_FORECOMMENTCOLOR": "#008000",
        "IDC_BACKCOMMENTCOLOR": "#ffffff",
        "IDC_FOREADDEDCOLOR": "#000000",
        "IDC_BACKADDEDCOLOR": "#ccffcc",
        "IDC_FOREREMOVEDCOLOR": "#000000",
        "IDC_BACKREMOVEDCOLOR": "#ffdddd",
    }

    def _build_ui(self):
        super()._build_ui()
        from PySide6.QtGui import QFontDatabase
        if c := self._ctl.get("IDC_FONTNAMES"):
            c.addItems(QFontDatabase.families())
        if c := self._ctl.get("IDC_FONTSIZES"):
            c.addItems([str(s) for s in range(6, 73)])
        self._apply_colors()
        if b := self._ctl.get("IDC_RESTORE"):
            b.clicked.connect(self._apply_colors)

    def _apply_colors(self):
        for cid, color in self._DEFAULT_COLORS.items():
            w = self._ctl.get(cid)
            if w is not None:
                w.setText("")
                w.setStyleSheet(f"background-color: {color};")


class _MenuListPage(_SettingPage):
    """Context Menu / Context Menu 2 通用：菜单项复选列表。"""

    SETTINGS_KEY = ""

    def _build_ui(self):
        super()._build_ui()
        tree = self._ctl.get("IDC_MENULIST")
        if tree is not None:
            tree.setColumnCount(1)
            tree.setHeaderHidden(True)
            tree.setRootIsDecorated(False)
            self._populate_menu_list(tree)
            # 减小与分组框标题的间距：上移并加高列表（补偿 QGroupBox 的 QSS margin）
            g = tree.geometry()
            dy = self._fu.px(0, 0, 0, 12).height()
            tree.setGeometry(g.x(), g.y() - dy, g.width(), g.height() + dy)
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
            checked = (not saved) or (e.command in saved)
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
            tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Checked)

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


class _ContextMenu2Page(_MenuListPage):
    """IDD_SETTINGSEXTMENU —— Context Menu 2。"""

    TEMPLATE = "IDD_SETTINGSEXTMENU"
    SETTINGS_KEY = "contextMenuHideEntries"


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

    def __init__(self, parent=None):
        super().__init__(parent)
        gb = QGroupBox(tr("set_describe", "Describe"), self)
        gb.setGeometry(self._fu.px(14, 183, 272, 76))
        gb.lower()
        for x, y, w, h, key, default in self._LABELS:
            lbl = QLabel(tr(key, default), self)
            lbl.setGeometry(self._fu.px(x, y, w, h))


class _Dialogs2Page(_SettingPage):
    """IDD_SETTINGSDIALOGS2 —— Dialogs 2（补回被去重的 IDC_STATIC 标签）。"""

    TEMPLATE = "IDD_SETTINGSDIALOGS2"

    _LABELS = [
        (14, 16, 85, 16, "set_autoclose", "&Autoclose Git.exe dialog:"),
        (14, 257, 270, 9, "set_dialogs3_hint",
         "Further options for the commit dialog are on Dialogs 3 page."),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        for x, y, w, h, key, default in self._LABELS:
            lbl = QLabel(tr(key, default), self)
            lbl.setGeometry(self._fu.px(x, y, w, h))


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

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


class _Colors1Page(_SettingPage):
    """IDD_SETTINGSCOLORS_1 —— Colors 1（补回被去重的标签/分组框）。"""

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

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


class _Colors2Page(_SettingPage):
    """IDD_SETTINGSCOLORS_2 —— Colors 2（补回被去重的标签）。"""

    TEMPLATE = "IDD_SETTINGSCOLORS_2"

    _LABELS = [
        (14, 23, 137, 8, "col_current_branch", "Current Branch"),
        (14, 40, 135, 8, "col_local_branch", "Local Branch"),
        (14, 57, 137, 8, "col_remote_branch", "Remote Branch"),
        (14, 74, 137, 8, "col_tag", "Tag"),
        (14, 103, 137, 8, "col_filter_match", "Filter match"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


class _Colors3Page(_SettingPage):
    """IDD_SETTINGSCOLORS_3 —— Colors 3（补回被去重的标签）。"""

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

    def __init__(self, parent=None):
        super().__init__(parent)
        _add_static_labels(self)


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
                _RcPage("IDD_SETTINGSWIN11CONTEXTMENU", self),
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
            _RcPage("IDD_SETTINGSPROGSALTERNATIVEEDITOR", self),
            "IDI_NOTEPAD",
            main,
        )

        git = self._add_page("gitconfig", _GitPage(self), "IDI_GITCONFIG")
        if has_repo:
            self._add_page(
                "gitremote", _RcPage("IDD_SETTINREMOTE", self, readonly=True),
                "IDI_GITREMOTE", git)
        self._add_page(
            "gitcredential",
            _RcPage("IDD_SETTINGSCREDENTIAL", self, readonly=True),
            "IDI_GITCREDENTIAL", git)

        hooks = self._add_page("hooks", _RcPage("IDD_SETTINGSHOOKS", self), "IDI_HOOK")
        self._add_page("bugtraq", _RcPage("IDD_SETTINGSBUGTRAQ", self), "IDI_BUGTRAQ", hooks)
        if has_repo:
            self._add_page(
                "bugtraqconfig",
                _RcPage("IDD_SETTINGSBUGTRAQ_CONFIG", self),
                "IDI_BUGTRAQ",
                hooks,
            )

        overlay = self._add_page("overlay", _RcPage("IDD_SETTINGSOVERLAY", self), "IDI_SET_OVERLAYS")
        self._add_page("overlays", _RcPage("IDD_SETOVERLAYICONS", self), "IDI_ICONSET", overlay)
        self._add_page(
            "overlayshandlers",
            _RcPage("IDD_SETTINGSOVERLAYHANDLERS", self),
            "IDI_SET_OVERLAYS",
            overlay,
        )

        proxy = self._add_page("proxy", _NetworkPage(self), "IDI_PROXY")
        self._add_page("smtp", _SmtpPage(self), "IDI_MISC", proxy)

        diff = self._add_page("diff", _DiffPage(self), "IDI_SWITCHLEFTRIGHT")
        self._add_page("merge", _MergePage(self), "IDI_MERGEACTIVE", diff)

        self._add_page("save", _RcPage("IDD_SETTINGSSAVEDDATA", self), "IDI_SAVEDDATA")
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