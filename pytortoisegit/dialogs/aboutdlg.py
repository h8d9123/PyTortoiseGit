"""aboutdlg.py —— AboutDlg：关于对话框（IDD_ABOUT 模板）。

333x265 "About TortoiseGit"：贡献者/网站链接 + Version Information 组。
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
    QDialog,
    QGroupBox,
    QLabel,
    QPushButton,
)

from .. import __appname__, __version__
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


class AboutDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_ABOUT")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(tr("about_title", "关于 {}").format(__appname__))
        self._ctl: dict = {}

        self.contrib_label = QLabel(
            tr("about_contrib", "Significant contributions by (Git 仓库):"), self)
        self.contrib_text = QLabel(
            tr("about_authors",
               "PyTortoiseGit contributors\n"
               "基于 TortoiseGit (GPLv2, tortoisegit.org)\n"
               "图标经 TortoiseSVN (tortoisesvn.net) 授权使用"), self)
        self.contrib_text.setWordWrap(True)
        self.website_link = QLabel(
            '<a href="https://tortoisegit.org">Visit our website</a>', self)
        self.website_link.setOpenExternalLinks(True)
        self.support_link = QLabel(
            '<a href="https://tortoisesvn.net">and support the developers</a>', self)
        self.support_link.setOpenExternalLinks(True)
        self.version_box = QGroupBox(tr("about_versionbox", "Version Information"), self)
        self.version_label = QLabel("", self)
        self.btn_update = QPushButton(tr("about_check_updates", "Check For Updates..."), self)
        self.btn_update.clicked.connect(self._on_check_updates)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)

        mapping = {
            "IDC_STATIC": self.contrib_label,
            "IDC_STATIC_AUTHORS": self.contrib_text,
            "IDC_WEBLINK": self.website_link,
            "IDC_SUPPORTLINK": self.support_link,
            "IDC_VERSIONBOX": self.version_box,
            "IDC_VERSIONABOUT": self.version_label,
            "IDC_UPDATE": self.btn_update,
            "IDOK": self.btn_ok,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        if self.version_box:
            self.version_box.setFlat(False)

        self.version_label.setText(self._version_text())

    @staticmethod
    def _version_text() -> str:
        git = "?"
        try:
            from ..git.git import GitRunner, find_git_executable
            git = GitRunner(find_git_executable()).version()
        except Exception:
            pass
        return (f"{__appname__} {__version__}\n"
                f"Git: {git}\n"
                f"GPLv2 · 基于 TortoiseGit 复刻\n"
                f"图标源自 TortoiseSVN（tortoisesvn.net）")

    def _on_check_updates(self):
        from .checkforupdatesdlg import CheckForUpdatesDlg
        CheckForUpdatesDlg(parent=self).exec()