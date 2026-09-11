"""checkforupdatesdlg.py —— CheckForUpdatesDlg：检查更新（IDD_CHECKFORUPDATES 模板）。

500x320 "Check For Updates - TortoiseGit"：版本信息 + Changelog + 下载列表。
PyTortoiseGit 无远端更新源 → 显示已是最新。
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
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QLabel, QPlainTextEdit, QPushButton, QTreeWidget,
    QTreeWidgetItem,
)
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


def _version() -> str:
    try:
        import pytortoisegit
        v = getattr(pytortoisegit, "__version__", "0.1.0")
        return str(v)
    except Exception:
        return "0.1.0"


class CheckForUpdatesDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self._build_ui()
        self._fill()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_CHECKFORUPDATES")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Check For Updates - TortoiseGit")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.lbl_source = QLabel("", self)
        self.lbl_your = QLabel("", self)
        self.lbl_current = QLabel("", self)
        self.lbl_result = QLabel("", self)
        self.lnk_link = QLabel("", self)
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        mono = QFont("Consolas")
        mono.setPointSize(9)
        self.log_view.setFont(mono)
        self.download_list = QTreeWidget(self)
        self.download_list.setColumnCount(2)
        self.download_list.setHeaderLabels([tr("upd_file", "File"),
                                           tr("upd_size", "Size")])
        self.btn_download = QPushButton(tr("upd_download", "&Download"), self)
        self.btn_ok = QPushButton(tr("upd_close", "&Close"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)

        mapping = {
            "IDC_SOURCE": self.lbl_source,
            "IDC_YOURVERSION": self.lbl_your,
            "IDC_CURRENTVERSION": self.lbl_current,
            "IDC_CHECKRESULT": self.lbl_result,
            "IDC_LINK": self.lnk_link,
            "IDC_LOGMESSAGE": self.log_view,
            "IDC_LIST_DOWNLOADS": self.download_list,
            "IDC_BUTTON_UPDATE": self.btn_download,
            "IDOK": self.btn_ok,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)
                self._ctl[ctrl.ctrl_id] = wgt
        for ctrl in spec.controls:
            a = _ANCHORS.get(ctrl.ctrl_id)
            if a and ctrl.ctrl_id in self._ctl:
                self._anchors.add(self._ctl[ctrl.ctrl_id], a[0],
                                  a[1] if len(a) > 1 else None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _fill(self):
        ver = _version()
        self.lbl_source.setText(tr("upd_source", "Check source: PyTortoiseGit repository"))
        self.lbl_your.setText(tr("upd_your", "Your version is: {}").format(ver))
        self.lbl_current.setText(tr("upd_current", "Current version is: {}").format(
            tr("upd_latest", "Latest")))
        self.lbl_result.setText(tr("upd_result", "You are already using the latest version."))
        item = QTreeWidgetItem([tr("upd_no_downloads", "No downloads available"), ""])
        self.download_list.addTopLevelItem(item)
        self.log_view.setPlainText(tr("upd_changelog", "PyTortoiseGit has no remote update server.\nFollow the repository releases for feature updates."))


_ANCHORS = {
    "IDC_YOURVERSION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_CURRENTVERSION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_CHECKRESULT": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_LINK": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_GROUP_CHANGELOG": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_LOGMESSAGE": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_GROUP_DOWNLOADS": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_LIST_DOWNLOADS": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_PROGRESSBAR": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_BUTTON_UPDATE": ("BOTTOM_RIGHT",),
    "IDOK": ("BOTTOM_CENTER",),
}