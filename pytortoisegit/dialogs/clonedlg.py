"""clonedlg.py —— CloneDlg：克隆仓库对话框（镜像 TortoiseGit IDD_CLONE）。

严格按 IDD_CLONE 模板排版（URL/目标目录/深度/递归/裸仓库/分支/Origin、
Putty 密钥、SVN 部分），尺寸变化时按 ResizableLib 锚点缩放。
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
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from ..git.repo import Repository
from ..res.strings import tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .progress import ProgressDialog
from .resize import AnchorLayout


class CloneDlg(QDialog):
    def __init__(self, url: str = "", parent=None, default_dir: str = ""):
        super().__init__(parent, Qt.WindowType.Window)
        self._url = url
        self._default_dir = default_dir or ""
        self._base_dir = self._default_dir
        self._dir_custom = False
        self._build_ui()
        if url:
            self._suggest_directory(url)
        elif default_dir and not self.dir_edit.text().strip():
            self.dir_edit.setText(default_dir)
        self._base_dir = self._default_dir or os.getcwd()

    # ---- UI（IDD_CLONE 模板）----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_CLONE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_horizontal_resize(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or tr("clone_title", "Clone repository"))
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._ctl: dict = {}

        def make(ctrl) -> object:
            wgt = _mint(ctrl, self)
            self._ctl[ctrl.ctrl_id] = wgt
            return wgt

        self._anchors = AnchorLayout(self.width(), self.height())

        # 组框
        grp_clone = QGroupBox(tr("clone_group", "Clone Existing Repository"), self)
        grp_svn = QGroupBox(tr("clone_svn_group", "From SVN Repository"), self)
        for wgt, cid in ((grp_clone, "IDC_GROUP_CLONE"),
                         (grp_svn, "IDC_CLONE_GROUP_SVN")):
            wgt.setObjectName(cid)
            self._ctl[cid] = wgt

        self.url_label = QLabel(tr("clone_url", "URL:"), self)
        self.url_combo = QComboBox(self)
        self.url_combo.setEditable(True)
        self.url_combo.activated.connect(self._on_url_selected)
        self.btn_browse_url = QPushButton(tr("clone_browse_url", "&Browse..."), self)
        self.btn_browse_url.clicked.connect(self._browse_url)
        self.dir_edit = QLineEdit(self)
        self.btn_browse_dir = QPushButton(tr("clone_browse_dir", "Bro&wse..."), self)
        self.btn_browse_dir.clicked.connect(self._browse_dir)
        self.chk_depth = QCheckBox(tr("clone_depth", "Depth"), self)
        self.depth_edit = QLineEdit(self)
        self.depth_edit.setText("1")
        self.chk_recursive = QCheckBox(tr("clone_recursive", "Recursive"), self)
        self.chk_bare = QCheckBox(tr("clone_bare", "Clone into Bare Repo"), self)
        self.chk_nocheckout = QCheckBox(tr("clone_nocheckout", "No Checkout"), self)
        self.chk_branch = QCheckBox(tr("clone_branch", "Branch"), self)
        self.branch_edit = QLineEdit(self)
        self.chk_origin = QCheckBox(tr("clone_origin", "Origin Name"), self)
        self.origin_edit = QLineEdit(self)
        self.origin_edit.setText("origin")
        self.chk_putty = QCheckBox(tr("clone_putty", "Load Putty &Key"), self)
        self.putty_edit = QLineEdit(self)
        self.btn_putty = QPushButton("...", self)
        self.btn_putty.clicked.connect(self._browse_putty)
        self.chk_svn = QCheckBox(tr("clone_svn", "From &SVN Repository"), self)
        self.chk_svn.toggled.connect(self.chk_svn_toggled)
        self.chk_svn_trunk = QCheckBox(tr("clone_svn_trunk", "&Trunk:"), self)
        self.svn_trunk_edit = QLineEdit(self)
        self.chk_svn_tag = QCheckBox(tr("clone_svn_tag", "Ta&gs:"), self)
        self.svn_tag_edit = QLineEdit(self)
        self.chk_svn_branch = QCheckBox(tr("clone_svn_branch", "Branc&h:"), self)
        self.svn_branch_edit = QLineEdit(self)
        self.chk_svn_from = QCheckBox(tr("clone_svn_from", "&From:"), self)
        self.svn_from_edit = QLineEdit(self)
        self.chk_username = QCheckBox(tr("clone_username", "User&name:"), self)
        self.username_edit = QLineEdit(self)

        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(lambda: QMessageBox.information(
            self, tr("help"), tr("clone_help", "Enter the repository URL to clone and the target directory, then start cloning.")))

        # 复选框 -> 编辑框 启用联动（对齐 TGit）
        for chk, edit in ((self.chk_depth, self.depth_edit),
                          (self.chk_branch, self.branch_edit),
                          (self.chk_origin, self.origin_edit),
                          (self.chk_svn_trunk, self.svn_trunk_edit),
                          (self.chk_svn_tag, self.svn_tag_edit),
                          (self.chk_svn_branch, self.svn_branch_edit),
                          (self.chk_svn_from, self.svn_from_edit),
                          (self.chk_username, self.username_edit)):
            chk.toggled.connect(lambda on, e=edit: e.setEnabled(on))
            edit.setEnabled(False)

        # URL 剪贴板自动填：检测剪贴板中的 `git clone <url>` 或直接 url
        if not self.url_combo.currentText().strip():
            clip_url = self._clipboard_clone_url()
            if clip_url:
                self.url_combo.setEditText(clip_url)
                self._suggest_directory(clip_url)

        # 摆放：全按模板坐标
        mapping = {
            "IDC_STATIC": self.url_label,
            "IDC_URLCOMBO": self.url_combo,
            "IDC_CLONE_BROWSE_URL": self.btn_browse_url,
            "IDC_CLONE_DIR": self.dir_edit,
            "IDC_CLONE_DIR_BROWSE": self.btn_browse_dir,
            "IDC_CHECK_DEPTH": self.chk_depth,
            "IDC_EDIT_DEPTH": self.depth_edit,
            "IDC_CHECK_RECURSIVE": self.chk_recursive,
            "IDC_CHECK_BARE": self.chk_bare,
            "IDC_CHECK_NOCHECKOUT": self.chk_nocheckout,
            "IDC_CHECK_BRANCH": self.chk_branch,
            "IDC_EDIT_BRANCH": self.branch_edit,
            "IDC_CHECK_ORIGIN": self.chk_origin,
            "IDC_EDIT_ORIGIN": self.origin_edit,
            "IDC_PUTTYKEY_AUTOLOAD": self.chk_putty,
            "IDC_PUTTYKEYFILE": self.putty_edit,
            "IDC_PUTTYKEYFILE_BROWSE": self.btn_putty,
            "IDC_CHECK_SVN": self.chk_svn,
            "IDC_CHECK_SVN_TRUNK": self.chk_svn_trunk,
            "IDC_EDIT_SVN_TRUNK": self.svn_trunk_edit,
            "IDC_CHECK_SVN_TAG": self.chk_svn_tag,
            "IDC_EDIT_SVN_TAG": self.svn_tag_edit,
            "IDC_CHECK_SVN_BRANCH": self.chk_svn_branch,
            "IDC_EDIT_SVN_BRANCH": self.svn_branch_edit,
            "IDC_CHECK_SVN_FROM": self.chk_svn_from,
            "IDC_EDIT_SVN_FROM": self.svn_from_edit,
            "IDC_CHECK_USERNAME": self.chk_username,
            "IDC_EDIT_USERNAME": self.username_edit,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
            "IDHELP": self.btn_help,
            "IDC_GROUP_CLONE": grp_clone,
            "IDC_CLONE_GROUP_SVN": grp_svn,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            _place(self, fu, ctrl, wgt)
            self._ctl[ctrl.ctrl_id] = wgt

        # 锚点（参考 CloneDlg.cpp）
        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _CLONE_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        self.url_combo.setEditText(self._url or "")
        self.url_combo.lineEdit().editingFinished.connect(self._on_url_edited)
        self.url_combo.lineEdit().returnPressed.connect(self._on_accept)
        self.chk_svn_toggled(False)

    def chk_svn_toggled(self, on: bool):
        for w, e in ((self.chk_svn_trunk, self.svn_trunk_edit),
                     (self.chk_svn_tag, self.svn_tag_edit),
                     (self.chk_svn_branch, self.svn_branch_edit),
                     (self.chk_svn_from, self.svn_from_edit),
                     (self.chk_username, self.username_edit)):
            w.setVisible(on)
            e.setVisible(on)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 交互 ----
    def _on_url_selected(self, *_a):
        """选中下拉 URL 后，自动补全目录 = 基准目录/仓库名。"""
        url = self.url_combo.currentText().strip()
        if url and not self._dir_custom:
            self._suggest_directory(url)

    def _clipboard_clone_url(self) -> str:
        """从剪贴板提取 clone URL（支持 'git clone <url>' 前缀）。"""
        try:
            from ..utils.clipboard import ClipboardHelper
            text = ClipboardHelper().get_text().strip()
        except Exception:
            return ""
        if not text:
            return ""
        for tok in text.split():
            if tok.startswith(("http://", "https://", "git@", "ssh://",
                               "git://", "file://")):
                return tok.strip()
        return ""

    def _browse_url(self):
        from ..git.git import GitRunner
        start = self.dir_edit.text() or os.getcwd()
        path = QFileDialog.getExistingDirectory(self, tr("clone_browse_url"), start)
        if path:
            res = GitRunner(cwd=path).run("remote", "get-url", "origin")
            url = (res.stdout or "").strip()
            if url:
                self.url_combo.setEditText(url)
                self._on_url_edited()

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, tr("clone_dir", "Directory"), self.dir_edit.text() or os.getcwd())
        if path:
            self.dir_edit.setText(path)
            self._dir_custom = True

    def _browse_putty(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("clone_putty", "Select PuTTY key"),
            self.putty_edit.text() or os.path.expanduser("~"),
            "Putty Key (*.ppk);;All Files (*.*)")
        if path:
            self.putty_edit.setText(path)

    def _url_repo_name(self, url: str) -> str:
        """从 URL 提取仓库名（去掉 .git 后缀），解析失败返回空串。"""
        m = re.search(r"[:/]([^/:]+?)(\.git)?$", url.strip())
        return m.group(1) if m and m.group(1) else ""

    def _suggest_directory(self, url: str):
        """在基准目录下自动追加 URL 仓库名：base/<仓库名>。"""
        name = self._url_repo_name(url)
        if name:
            self.dir_edit.setText(
                os.path.join(self._base_dir, name))

    def _on_url_edited(self):
        """URL 手动编辑完成后，自动补全目录 = 基准目录/仓库名。"""
        url = self.url_combo.currentText().strip()
        if url and not self._dir_custom:
            self._suggest_directory(url)

    def _on_url_selected(self, *_a):
        """选中下拉 URL 后，自动补全目录 = 基准目录/仓库名。"""
        url = self.url_combo.currentText().strip()
        if url and not self._dir_custom:
            self._suggest_directory(url)

    # ---- 执行 ----
    def _on_accept(self):
        url = self.url_combo.currentText().strip()
        target = self.dir_edit.text().strip()
        if not url or not target:
            return
        if os.path.exists(target) and os.path.isdir(target) and os.listdir(target):
            resp = QMessageBox.question(
                self, tr("confirm"),
                tr("clone_not_empty", "Target directory is not empty. Continue anyway?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return
        args = ["clone"]
        if self.chk_branch.isChecked() and self.branch_edit.text().strip():
            args += ["--branch", self.branch_edit.text().strip()]
        if self.chk_depth.isChecked() and self.depth_edit.text().strip():
            args += ["--depth", self.depth_edit.text().strip()]
        if self.chk_recursive.isChecked():
            args.append("--recursive")
        if self.chk_bare.isChecked():
            args.append("--bare")
        if self.chk_nocheckout.isChecked():
            args.append("--no-checkout")
        if self.chk_origin.isChecked() and self.origin_edit.text().strip():
            args += ["--origin", self.origin_edit.text().strip()]
        if self.chk_putty.isChecked() and self.putty_edit.text().strip():
            args += ["-c", f"core.sshCommand=ssh -i {self.putty_edit.text().strip()}"]
        args += [url, target]

        dlg = ProgressDialog(title=tr("clone_title", "Clone repository"), parent=self)
        dlg.set_label("git clone " + url)
        dlg.run(lambda: _clone_reporter(dlg, url, target, args))
        dlg.on_finish(lambda ok: self._after_clone(ok, target))
        dlg.exec()

    def _after_clone(self, ok: bool, target: str):
        # 克隆成功才关闭对话框；失败保留以便用户修改 URL/目录后重试。
        if ok:
            self.accept()


_CLONE_ANCHORS = {
    "IDC_URLCOMBO": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_CLONE_BROWSE_URL": ("TOP_RIGHT",),
    "IDC_CLONE_DIR": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_CLONE_DIR_BROWSE": ("TOP_RIGHT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDC_GROUP_CLONE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_PUTTYKEYFILE_BROWSE": ("TOP_RIGHT",),
    "IDC_PUTTYKEY_AUTOLOAD": ("TOP_LEFT",),
    "IDC_PUTTYKEYFILE": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_CLONE_GROUP_SVN": ("TOP_LEFT", "TOP_RIGHT"),
    "IDHELP": ("BOTTOM_RIGHT",),
}


def _place(dlg, fu, ctrl, wgt):
    rc_mod.place_widget(dlg, fu, ctrl, wgt)
    if isinstance(wgt, QComboBox) and wgt.height() > 30:
        wgt.setFixedHeight(23)
    if ctrl.hidden:
        wgt.hide()


def _mint(ctrl, parent):
    """辅助：未单独定制时按 make_widget 创建。"""
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton)
    kind, cls = ctrl.kind, ctrl.cls
    text = ctrl.text.replace("&", "")
    if kind == "PUSHBUTTON" or kind == "DEFPUSHBUTTON":
        b = QPushButton(text or "OK", parent)
        if kind == "DEFPUSHBUTTON":
            b.setDefault(True)
        return b
    if kind in ("LTEXT", "RTEXT", "CTEXT") or (cls == "Static" and "SS_BLACKFRAME" not in (ctrl.style or "")):
        return QLabel(text, parent)
    if ctrl.style and "BS_AUTOCHECKBOX" in ctrl.style:
        return QCheckBox(text, parent)
    if cls == "ComboBox":
        c = QComboBox(parent)
        c.setEditable(True)
        return c
    if cls == "Edit" or kind == "EDITTEXT":
        return QLineEdit(parent)
    return QLabel(text, parent)


def _clone_reporter(dlg, url: str, target: str, args) -> bool:
    from ..git.git import GitRunner
    runner = GitRunner(cwd=os.path.dirname(os.path.abspath(target)) or ".")
    result = runner.run_interactive(*args)
    if result.stdout:
        dlg.log(result.stdout)
    if result.stderr:
        dlg.log(result.stderr)
    if result.returncode != 0 and not result.stderr:
        dlg.log(tr("clone_failed", "Clone failed"))
    return result.returncode == 0