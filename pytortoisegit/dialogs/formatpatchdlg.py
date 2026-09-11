"""formatpatchdlg.py —— FormatPatchDlg：生成补丁包（IDD_FORMAT_PATCH 模板）。

321x193 "Format Patch"：输出目录 + 版本（Since/Number Commits/Range）
+ SendMail / NoPrefix / Save unified diff。
OK 执行 git format-patch。
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
    QCheckBox, QComboBox, QDialog, QLabel, QLineEdit, QPushButton,
    QRadioButton, QSpinBox,
)
from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from ..utils.pick import pick_dir
from .resize import AnchorLayout
from .progress import ProgressDialog


class FormatPatchDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self._build_ui()

    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_FORMAT_PATCH")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or "Format Patch")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.grp_dir = QGroupBox(tr("fmt_patch_group_dir", "Output Directory"), self)
        self.grp_version = QGroupBox(tr("fmt_patch_group_version", "Version"), self)

        self.dir_label = QLabel(tr("fmt_patch_dir", "Directory:"), self)
        self.dir_combo = QComboBox(self)
        self.dir_combo.setEditable(True)
        self.dir_combo.addItem(os.path.join(self.repo.root, "patches"))
        self.btn_dir = QPushButton("...", self)
        self.btn_dir.clicked.connect(self._pick_dir)

        self.rd_since = QRadioButton(tr("fmt_patch_since", "Since"), self)
        self.since_combo = QComboBox(self)
        self.since_combo.setEditable(True)
        self.btn_ref = QPushButton("...", self)
        self.rd_num = QRadioButton(tr("fmt_patch_num", "Number Commits"), self)
        self.num_edit = QSpinBox(self)
        self.num_edit.setRange(1, 10000)
        self.num_edit.setValue(1)
        self.rd_range = QRadioButton(tr("fmt_patch_range", "Range"), self)
        self.from_combo = QComboBox(self)
        self.from_combo.setEditable(True)
        self.btn_from = QPushButton("...", self)
        self.to_combo = QComboBox(self)
        self.to_combo.setEditable(True)
        self.btn_to = QPushButton("...", self)
        self.chk_sendmail = QCheckBox(tr("fmt_patch_mail", "Send Mail after create"), self)
        self.chk_noprefix = QCheckBox(tr("fmt_patch_noprefix", "No a/ and b/ prefixes"), self)
        self.btn_unified = QPushButton(
            tr("fmt_patch_unified", "Save unified diff since HEAD"), self)
        self.btn_unified.clicked.connect(self._save_unified)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_format)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)

        mapping = {
            "IDC_GROUP_DIR": self.grp_dir,
            "IDC_GROUP_VERSION": self.grp_version,
            "IDC_STATIC": self.dir_label,
            "IDC_COMBOBOXEX_DIR": self.dir_combo,
            "IDC_BUTTON_DIR": self.btn_dir,
            "IDC_RADIO_SINCE": self.rd_since,
            "IDC_COMBOBOXEX_SINCE": self.since_combo,
            "IDC_BUTTON_REF": self.btn_ref,
            "IDC_RADIO_NUM": self.rd_num,
            "IDC_EDIT_NUM": self.num_edit,
            "IDC_RADIO_RANGE": self.rd_range,
            "IDC_COMBOBOXEX_FROM": self.from_combo,
            "IDC_BUTTON_FROM": self.btn_from,
            "IDC_COMBOBOXEX_TO": self.to_combo,
            "IDC_BUTTON_TO": self.btn_to,
            "IDC_CHECK_SENDMAIL": self.chk_sendmail,
            "IDC_CHECK_NOPREFIX": self.chk_noprefix,
            "IDC_BUTTON_UNIFIEDDIFF": self.btn_unified,
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
        refs = [x.strip() for x in out.splitlines() if x.strip()] or ["HEAD"]
        self.since_combo.addItems(refs)
        self.from_combo.addItems(refs)
        self.to_combo.addItems(refs + ["HEAD"])
        self.rd_since.setChecked(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _pick_dir(self):
        d = pick_dir(self, tr("fmt_patch_dir", "Output directory"), self.repo.root)
        if d:
            self.dir_combo.setEditText(d)

    def _args(self) -> list:
        outdir = self.dir_combo.currentText().strip() or str(self.repo.root)
        args = ["format-patch", f"--output-directory={outdir}"]
        if self.chk_noprefix.isChecked():
            args.append("--no-prefix")
        if self.rd_num.isChecked():
            args.append(f"-{self.num_edit.value()}")
        elif self.rd_range.isChecked():
            f = self.from_combo.currentText().strip()
            t = self.to_combo.currentText().strip()
            args.append(f"{f}..{t}" if f and t else (f or "HEAD"))
        else:
            args.append(self.since_combo.currentText().strip() or "HEAD")
        return args

    def _on_format(self):
        dlg = ProgressDialog(title=tr("progress", "Progress"), parent=self)
        dlg.set_label("git " + " ".join(self._args()))

        def _bg():
            r = self.repo.runner.run(*self._args())
            if r.stdout: dlg.log(r.stdout)
            if r.stderr: dlg.log(r.stderr)
            return r.returncode == 0

        dlg.run(_bg)
        dlg.exec()
        self.accept()

    def _save_unified(self):
        from ..utils.pick import pick_file
        path = pick_file(self, tr("fmt_patch_unified", "Save unified diff"), "*.diff")
        if not path:
            return
        out = self.repo.runner.run("diff", "HEAD").stdout or ""
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
        self.accept()


_ANCHORS = {
    "IDC_GROUP_DIR": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_GROUP_VERSION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_DIR": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_DIR": ("TOP_RIGHT",),
    "IDC_COMBOBOXEX_SINCE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_EDIT_NUM": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_SPIN_NUM": ("TOP_RIGHT",),
    "IDC_COMBOBOXEX_FROM": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_TO": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_FROM": ("TOP_RIGHT",),
    "IDC_BUTTON_TO": ("TOP_RIGHT",),
    "IDC_BUTTON_REF": ("TOP_RIGHT",),
    "IDC_CHECK_SENDMAIL": ("BOTTOM_LEFT",),
    "IDC_CHECK_NOPREFIX": ("BOTTOM_LEFT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}