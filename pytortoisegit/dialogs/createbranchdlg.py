"""createbranchdlg.py —— 创建分支/标签对话框（IDD_NEW_BRANCH_TAG 模板）。

镜像 TortoiseGit 的 CCreateBranchTagDlg：Name / Base On（HEAD/Branch/Tag/
Commit）/ Options（Track/Force/Switch/Sign/Push）/ Message，分支与标签共用
同一模板，按模式切换标签与可见控件。
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
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
)

from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout


class _BranchTagDlg(QDialog):
    """分支/标签共用对话框（对齐 IDD_NEW_BRANCH_TAG）。"""

    def __init__(self, repo: Repository, is_tag: bool, start: str = "HEAD",
                 parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.is_tag = is_tag
        self.start = (start or "HEAD").strip()
        self.name: str = ""
        self.version_name: str = "HEAD"
        self._build_ui()
        self._load_refs()

    # ---- 构建 ----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_NEW_BRANCH_TAG")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        title = tr("tag_new", "New tag") if self.is_tag else tr("branch_new", "New branch")
        self.setWindowTitle(f"{self.repo.root} - {title} - TortoiseGit")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        # 分组框先建，保证位于子控件下层
        self.grp_name = QGroupBox(tr("grp_name", "&Name"), self)
        self.grp_baseon = QGroupBox(tr("grp_baseon", "Base On"), self)
        self.grp_option = QGroupBox(tr("merge_option", "Options"), self)
        self.grp_message = QGroupBox(tr("merge_message", "&Message"), self)

        self.label_branch = QLabel(self)
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("feature/xxx")

        self.rd_head = QRadioButton(tr("choose_head", "&HEAD"), self)
        self.rd_branch = QRadioButton(tr("switch_branch", "&Branch"), self)
        self.branch_combo = QComboBox(self)
        self.btn_browse_ref = QPushButton("...", self)
        self.rd_tags = QRadioButton(tr("switch_tag", "&Tag"), self)
        self.tags_combo = QComboBox(self)
        self.rd_version = QRadioButton(tr("switch_commit", "&Commit"), self)
        self.version_combo = QComboBox(self)
        self.version_combo.setEditable(True)
        self.btn_show = QPushButton("...", self)

        self.track_box = QCheckBox(tr("branch_track", "Trac&k"), self)
        self.force_box = QCheckBox(tr("force", "&Force"), self)
        self.switch_box = QCheckBox(tr("branch_switch", "&Switch to new branch"), self)
        self.switch_box.setChecked(not self.is_tag)
        self.sign_box = QCheckBox(tr("tag_annotated", "Si&gn"), self)
        self.annotated_box = self.sign_box
        self.push_box = QCheckBox(tr("push", "&Push"), self)

        self.msg_edit = QPlainTextEdit(self)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)

        # 模式差异
        self.rd_head.setText(f"{self.rd_head.text()} ({self.repo.current_branch()})")
        self.track_box.setEnabled(False)
        self.sign_box.hide()
        self.push_box.hide()
        if self.is_tag:
            self.label_branch.setText(tr("tag_label", "Tag:"))
            self.track_box.hide()
            self.switch_box.hide()
            self.sign_box.setText(tr("tag_annotated", "Create annotated tag"))
            self.sign_box.show()
        else:
            self.grp_message.setTitle(tr("description", "Description"))

        mapping = {
            "IDC_GROUP_BRANCH": self.grp_name,
            "IDC_LABEL_BRANCH": self.label_branch,
            "IDC_BRANCH_TAG": self.name_edit,
            "IDC_GROUP_BASEON": self.grp_baseon,
            "IDC_RADIO_HEAD": self.rd_head,
            "IDC_RADIO_BRANCH": self.rd_branch,
            "IDC_COMBOBOXEX_BRANCH": self.branch_combo,
            "IDC_BUTTON_BROWSE_REF": self.btn_browse_ref,
            "IDC_RADIO_TAGS": self.rd_tags,
            "IDC_COMBOBOXEX_TAGS": self.tags_combo,
            "IDC_RADIO_VERSION": self.rd_version,
            "IDC_COMBOBOXEX_VERSION": self.version_combo,
            "IDC_BUTTON_SHOW": self.btn_show,
            "IDC_GROUP_OPTION": self.grp_option,
            "IDC_CHECK_TRACK": self.track_box,
            "IDC_CHECK_FORCE": self.force_box,
            "IDC_CHECK_SWITCH": self.switch_box,
            "IDC_CHECK_SIGN": self.sign_box,
            "IDC_CHECK_PUSH": self.push_box,
            "IDC_GROUP_MESSAGE": self.grp_message,
            "IDC_EDIT_MESSAGE": self.msg_edit,
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
            a = _BRANCHTAG_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        if self.is_tag:
            # “附注标签”比模板 “Sign” 文本更宽，放到 Force 右侧
            g = self.force_box.geometry()
            self.sign_box.move(g.right() + 12, self.sign_box.y())
            self.sign_box.adjustSize()

        for rd in (self.rd_head, self.rd_branch, self.rd_tags, self.rd_version):
            rd.toggled.connect(self._update_radios)
        self.rd_head.setChecked(True)
        self._update_radios()
        self.branch_combo.currentTextChanged.connect(self._on_branch_changed)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 数据 ----
    def _load_refs(self):
        out = self.repo.runner.run(
            "for-each-ref", "--format=%(refname)").stdout or ""
        full = [x.strip() for x in out.splitlines() if x.strip()]
        branches, tags = [], []
        for name in full:
            if name.startswith("refs/heads/"):
                branches.append(name[len("refs/heads/"):])
            elif name.startswith("refs/remotes/"):
                branches.append("remotes/" + name[len("refs/remotes/"):])
            elif name.startswith("refs/tags/"):
                tags.append(name[len("refs/tags/"):])
        self.branch_combo.clear()
        self.branch_combo.addItems(branches)
        self.tags_combo.clear()
        self.tags_combo.addItems(tags)
        self.version_combo.clear()
        self.version_combo.addItems(branches + tags + ["HEAD"])
        self._select_start(branches, tags)

    def _select_start(self, branches, tags):
        start = self.start
        if not start or start == "HEAD":
            self.rd_head.setChecked(True)
            return
        if start in branches:
            self.branch_combo.setCurrentText(start)
            self.rd_branch.setChecked(True)
        elif start in tags:
            self.tags_combo.setCurrentText(start)
            self.rd_tags.setChecked(True)
        else:
            self.version_combo.setCurrentText(start)
            self.rd_version.setChecked(True)

    def _update_radios(self, *_a):
        self.branch_combo.setEnabled(self.rd_branch.isChecked())
        self.btn_browse_ref.setEnabled(self.rd_branch.isChecked())
        self.tags_combo.setEnabled(self.rd_tags.isChecked())
        self.version_combo.setEnabled(self.rd_version.isChecked())
        self.btn_show.setEnabled(self.rd_version.isChecked())
        if not self.rd_branch.isChecked() or self.is_tag:
            self.track_box.setEnabled(False)

    def _on_branch_changed(self, text: str):
        if self.is_tag:
            return
        self.track_box.setEnabled(self.rd_branch.isChecked()
                                  and text.startswith("remotes/"))
        if not self.track_box.isEnabled():
            self.track_box.setChecked(False)

    def _target(self) -> str:
        if self.rd_branch.isChecked():
            return self.branch_combo.currentText().strip()
        if self.rd_tags.isChecked():
            return self.tags_combo.currentText().strip()
        if self.rd_version.isChecked():
            return self.version_combo.currentText().strip()
        return "HEAD"

    # ---- 动作 ----
    def _on_help(self):
        QMessageBox.information(
            self, tr("help"),
            tr("branch_new") if not self.is_tag else tr("tag_new"))

    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setFocus()
            return
        base = self._target()
        if not base:
            return
        args = self._command_args(name, base)
        result = self.repo.runner.run(*args)
        if result.returncode != 0:
            QMessageBox.warning(self, tr("error"),
                                result.stderr or result.stdout)
            return
        self.name = name
        self.version_name = base
        self.accept()

    def _command_args(self, name: str, base: str) -> list:
        if self.is_tag:
            args = ["tag"]
            if self.annotated_box.isChecked():
                args.append("-a")
            msg = self.msg_edit.toPlainText().strip()
            if self.annotated_box.isChecked():
                args += ["-m", msg or name]
            args += [name, base]
            return args
        force = self.force_box.isChecked()
        if self.switch_box.isChecked():
            args = ["checkout", "-B" if force else "-b", name, base]
        else:
            args = ["branch"]
            if force:
                args.append("-f")
            args += [name, base]
        if self.track_box.isChecked() and base.startswith("remotes/"):
            args.append("--track")
        return args


class CreateBranchDlg(_BranchTagDlg):
    def __init__(self, repo: Repository, start: str = "HEAD", parent=None):
        super().__init__(repo, is_tag=False, start=start, parent=parent)


class CreateTagDlg(_BranchTagDlg):
    def __init__(self, repo: Repository, start: str = "HEAD", parent=None):
        super().__init__(repo, is_tag=True, start=start, parent=parent)


# 锚点：可拉伸控件（右缘/底部随窗口）
_BRANCHTAG_ANCHORS = {
    "IDC_GROUP_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BRANCH_TAG": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_GROUP_BASEON": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_BRANCH": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_TAGS": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_COMBOBOXEX_VERSION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BUTTON_BROWSE_REF": ("TOP_RIGHT",),
    "IDC_BUTTON_SHOW": ("TOP_RIGHT",),
    "IDC_GROUP_OPTION": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_GROUP_MESSAGE": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_EDIT_MESSAGE": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}
