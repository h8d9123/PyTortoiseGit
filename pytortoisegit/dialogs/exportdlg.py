"""exportdlg.py —— ExportDlg：导出 zip（IDD_EXPORT 模板）。

300x183 "Export"：Zip 文件路径 + Revision（HEAD/Branch/Tag/Commit）。
OK 执行 git archive。
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
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QRadioButton,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from ..utils.pick import pick_file
from .resize import AnchorLayout
from .progress import ProgressDialog


class ExportDlg(QDialog):
    def __init__(self, repo: Repository, parent=None, commit: str | None = None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()
        if commit:
            self.rd_version.setChecked(True)
            self.version_combo.setEditable(True)
            self.version_combo.setCurrentText(commit)

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_EXPORT")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Export")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.grp_revision = QGroupBox(tr("export_group_revision", "Revision"), self)

        self.file_label = QLabel(tr("export_file", "Zip File"), self)
        self.file_edit = QLineEdit(self)
        self.btn_browse = QPushButton("...", self)
        self.btn_browse.clicked.connect(self._pick_file)
        self.rd_head = QRadioButton(tr("export_head", "&HEAD"), self)
        self.rd_branch = QRadioButton(tr("export_branch", "&Branch"), self)
        self.branch_combo = QComboBox(self)
        self.btn_browse_ref = QPushButton("...", self)
        self.rd_tags = QRadioButton(tr("export_tag", "&Tag"), self)
        self.tags_combo = QComboBox(self)
        self.rd_version = QRadioButton(tr("export_commit", "&Commit"), self)
        self.version_combo = QComboBox(self)
        self.btn_show = QPushButton("...", self)
        self.chk_whole = QPushButton(tr("export_whole", "&Whole Project"), self)
        self.chk_whole.setCheckable(True)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_export)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_GROUP_BASEON": self.grp_revision,
            "IDC_EXPORTFILE_LABEL": self.file_label,
            "IDC_EXPORTFILE": self.file_edit,
            "IDC_EXPORTFILE_BROWSE": self.btn_browse,
            "IDC_RADIO_HEAD": self.rd_head,
            "IDC_RADIO_BRANCH": self.rd_branch,
            "IDC_COMBOBOXEX_BRANCH": self.branch_combo,
            "IDC_BUTTON_BROWSE_REF": self.btn_browse_ref,
            "IDC_RADIO_TAGS": self.rd_tags,
            "IDC_COMBOBOXEX_TAGS": self.tags_combo,
            "IDC_RADIO_VERSION": self.rd_version,
            "IDC_COMBOBOXEX_VERSION": self.version_combo,
            "IDC_BUTTON_SHOW": self.btn_show,
            "IDC_WHOLE_PROJECT": self.chk_whole,
            "IDOK": self.btn_ok,
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

        out = self.repo.runner.run("for-each-ref",
                                   "--format=%(refname:short)").stdout or ""
        refs = [x.strip() for x in out.splitlines() if x.strip()]
        self.branch_combo.addItems([r for r in refs if not r.startswith("tags/")])
        self.tags_combo.addItems([r[5:] for r in refs if r.startswith("tags/")])
        self.version_combo.addItems(refs + ["HEAD"])
        self.rd_head.setChecked(True)
        self.file_edit.setText(os.path.join(
            self.repo.root, os.path.basename(self.repo.root) + ".zip"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _pick_file(self):
        path = pick_file(self, tr("export_file", "Zip file"), "*.zip")
        if path:
            self.file_edit.setText(path)

    def _target(self) -> str:
        if self.rd_branch.isChecked():
            return self.branch_combo.currentText()
        if self.rd_tags.isChecked():
            return self.tags_combo.currentText()
        if self.rd_version.isChecked():
            return self.version_combo.currentText()
        return "HEAD"

    def _on_export(self):
        outfile = self.file_edit.text().strip()
        if not outfile:
            self.file_edit.setFocus()
            return
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label("git archive …")

        def _bg():
            r = self.repo.runner.run(
                "archive", "--format=zip", "-o", outfile, self._target())
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0

        dlg.run(_bg)
        dlg.exec()
        self.accept()


_ANCHORS = {
    "IDC_GROUP_BASEON": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REPOGROUP": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_EXPORTFILE_LABEL": ("TOP_LEFT",),
    "IDC_EXPORTFILE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_EXPORTFILE_BROWSE": ("TOP_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}