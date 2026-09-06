"""settingsdlg.py —— SettingsDlg：设置对话框（属性页，镜像 TortoiseGit）。

用 QTreeWidget(左侧树) + QStackedWidget(右侧页) 复刻 TortoiseGit 的
CPropertySheet 属性页。页面按 IDD_SETTINGS* 模板排版。
当前复刻核心页：General / Context Menu / ExtMenu / Dialogs / Git /
Diff Viewer / Merge Tool / Network(Proxy) / Saved Data / Credential /
Advanced(Git config)。
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
from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
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
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from ..utils.pick import pick_file


# ---------------------------------------------------------------------------
# 页面基类：按 rc 模板排版
# ---------------------------------------------------------------------------

class _SettingPage(QWidget):
    """一个设置页：按 IDD_SETTINGS* 模板绝对定位控件。"""

    TEMPLATE: str = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctl: dict = {}
        self._build_ui()

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
        """按 rc 生成控件，子类可覆盖映射。"""
        return rc_mod.make_widget(ctrl, self)

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

class _GeneralPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSMAIN"

    def _build_ui(self):
        super()._build_ui()
        self.name_edit = None
        self.email_edit = None


# ---------------------------------------------------------------------------
# Git 页（IDD_SETTINGIT_CONFIG）
# ---------------------------------------------------------------------------

class _GitPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGIT_CONFIG"

    @property
    def name_edit(self):
        return self._ctl.get("IDC_GIT_USERNAME")

    @property
    def email_edit(self):
        return self._ctl.get("IDC_GIT_USEREMAIL")


# ---------------------------------------------------------------------------
# 外部程序页（Diff / Merge）
# ---------------------------------------------------------------------------

class _DiffPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSPROGSDIFF"

    @property
    def diff_edit(self):
        return self._ctl.get("IDC_EXTDIFF")

    @property
    def viewer_edit(self):
        return self._ctl.get("IDC_DIFFVIEWER")


class _MergePage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSPROGSMERGE"

    @property
    def merge_edit(self):
        return self._ctl.get("IDC_EXTMERGE")


# ---------------------------------------------------------------------------
# Network 页（IDD_SETTINGSPROXY）
# ---------------------------------------------------------------------------

class _NetworkPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSPROXY"

    @property
    def server_edit(self):
        return self._ctl.get("IDC_SERVERADDRESS")

    @property
    def port_edit(self):
        return self._ctl.get("IDC_SERVERPORT")


# ---------------------------------------------------------------------------
# 其他简单页面：直接按 rc 生成控件（无特殊逻辑）
# ---------------------------------------------------------------------------

class _LookAndFeelPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSLOOKANDFEEL"


class _ExtMenuPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSEXTMENU"


class _DialogsPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSDIALOGS"


class _Dialogs2Page(_SettingPage):
    TEMPLATE = "IDD_SETTINGSDIALOGS2"


class _ColorsPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSCOLORS_1"


class _SavedDataPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSSAVEDDATA"


class _OverlayPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSOVERLAY"


class _CredentialPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGSCREDENTIAL"


class _AdvancedPage(_SettingPage):
    TEMPLATE = "IDD_SETTINGS_CONFIG"


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
        self.setWindowTitle(tr("settings_title", "设置"))
        self.resize(760, 500)
        root = QVBoxLayout(self)

        split = QSplitter(self)
        self.tree = QTreeWidget(split)
        self.tree.setHeaderHidden(True)
        self.tree.setFixedWidth(200)
        self.stack = QStackedWidget(split)
        split.addWidget(self.tree)
        split.addWidget(self.stack)
        root.addWidget(split, 1)

        btnbar = QHBoxLayout()
        btnbar.addStretch(1)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._save_all)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton(tr("apply"), self)
        self.btn_apply.clicked.connect(self._save_all)
        for b in (self.btn_ok, self.btn_cancel, self.btn_apply):
            btnbar.addWidget(b)
        root.addLayout(btnbar)

        self.tree.currentItemChanged.connect(self._on_tree_changed)
        self._build_pages()

    def _build_pages(self):
        # (标题, 类别, 页面实例)
        pages = [
            (tr("settings_general", "General"), None, _GeneralPage(self)),
            (tr("settings_look", "Context Menu"), "general", _LookAndFeelPage(self)),
            (tr("settings_extmenu", "Context Menu 2"), "general", _ExtMenuPage(self)),
            (tr("settings_dialogs", "Dialogs"), "general", _DialogsPage(self)),
            (tr("settings_dialogs2", "Dialogs 2"), "general", _Dialogs2Page(self)),
            (tr("settings_colors", "Colors"), "general", _ColorsPage(self)),
            (tr("settings_git", "Git"), None, _GitPage(self)),
            (tr("settings_diff", "Diff Viewer"), "git", _DiffPage(self)),
            (tr("settings_merge", "Merge Tool"), "git", _MergePage(self)),
            (tr("settings_network", "Network"), None, _NetworkPage(self)),
            (tr("settings_saved", "Saved Data"), None, _SavedDataPage(self)),
            (tr("settings_overlay", "Overlay Icons"), None, _OverlayPage(self)),
            (tr("settings_credential", "Credential"), None, _CredentialPage(self)),
            (tr("settings_advanced", "Advanced"), None, _AdvancedPage(self)),
        ]
        parents: dict = {}
        try:
            from ..res import icons as _icons
        except Exception:
            _icons = None
        for label, category, page in pages:
            # 找已存在的单个同名项避免重复堆叠
            where = self.stack.count()
            self.stack.addWidget(page)
            dupe = QTreeWidgetItem(parents.get(category))
            dupe.setText(0, label)
            dupe.setData(0, Qt.ItemDataRole.UserRole, where)
            parents.setdefault(category, dupe)
            if _icons is not None:
                icon_name = self._icon_of(page)
                if icon_name:
                    ic = _icons.icon(icon_name)
                    if ic is not None and not ic.isNull():
                        dupe.setIcon(0, ic)
            self.pages.append((dupe, page))

    def _icon_of(self, page) -> str:
        """按页面类型选 TGit 图标（IDI_* 或别名）。"""
        name = type(page).__name__
        return {
            "_GeneralPage": "IDI_GENERAL",
            "_LookAndFeelPage": "IDI_LOOKANDFEEL",
            "_ExtMenuPage": "IDI_LOOKANDFEEL",
            "_DialogsPage": "IDI_DIALOGS",
            "_Dialogs2Page": "IDI_DIALOGS",
            "_ColorsPage": "IDI_ICONSET",
            "_GitPage": "IDI_GITCONFIG",
            "_DiffPage": "IDI_SWITCHLEFTRIGHT",
            "_MergePage": "IDI_MERGEACTIVE",
            "_NetworkPage": "IDI_PROXY",
            "_SavedDataPage": "IDI_SAVEDDATA",
            "_OverlayPage": "IDI_SET_OVERLAYS",
            "_CredentialPage": "IDI_GITCREDENTIAL",
            "_AdvancedPage": "IDI_GITCONFIG",
        }.get(name)

    def _on_tree_changed(self, item, _prev):
        if item is None:
            return
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None:
            self.stack.setCurrentIndex(idx)

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
            "http.proxyPort": "",
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
        # network
        for _, page in self.pages:
            if isinstance(page, _NetworkPage):
                if page.server_edit:
                    page.server_edit.setText(values["http.proxy"])
                if page.port_edit:
                    port = values["http.proxyPort"]
                    page.port_edit.setText(port if port else "8080")
        # diff/merge
        for _, page in self.pages:
            if isinstance(page, _DiffPage):
                if page.diff_edit:
                    page.diff_edit.setText(self._get_ext("tortoisegit.externaldiff"))
                if page.viewer_edit:
                    page.viewer_edit.setText(self._get_ext("tortoisegit.diffviewer"))
            elif isinstance(page, _MergePage):
                if page.merge_edit:
                    page.merge_edit.setText(self._get_ext("tortoisegit.externalmerge"))

    def _config_lines(self) -> List[Tuple[str, str]]:
        keys = ["user.name", "user.email", "http.proxy", "http.proxyPort",
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
        git = shutil.which("git")
        for _, page in self.pages:
            ver = page._ctl.get("IDC_MSYSGIT_VER") if hasattr(page, "_ctl") else None
            if ver is not None:
                if git:
                    try:
                        out = subprocess.run([git, "--version"], capture_output=True,
                                             text=True).stdout.strip()
                        ver.setText(out)
                    except Exception:
                        pass

    def _save_all(self):
        if self.name_edit is not None:
            self._set_global("user.name", self.name_edit.text().strip())
        if self.email_edit is not None:
            self._set_global("user.email", self.email_edit.text().strip())
        for _, page in self.pages:
            if isinstance(page, _NetworkPage):
                host = page.server_edit.text().strip() if page.server_edit else ""
                port = page.port_edit.text().strip() if page.port_edit else ""
                self._set_global("http.proxy", host or None)
                if host and port:
                    self._set_global("http.proxyPort", port)
            elif isinstance(page, _DiffPage):
                val = page.diff_edit.text().strip() if page.diff_edit else ""
                self._set_global("tortoisegit.externaldiff", val or None)
            elif isinstance(page, _MergePage):
                val = page.merge_edit.text().strip() if page.merge_edit else ""
                self._set_global("tortoisegit.externalmerge", val or None)
        self.accept()

    def _set_global(self, key: str, val: str | None):
        if val:
            self._runner.run("config", "--global", key, val)
        else:
            self._runner.run("config", "--global", "--unset-all", key)