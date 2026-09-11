"""diffdlg.py —— DiffDlg：CFileDiffDlg / IDD_DIFFFILES 的 Qt 复刻。

严格按原版 IDD_DIFFFILES（301x280 "Changed Files"）排版：
  顶行（Difference between / Diff Options / Show log / 左右交换）、
  Version 1 (Base) 与 Version 2 分组框（修订输入 + HEAD 按钮 + URL/subject）、
  IDC_FILTER 文件过滤、IDC_FILELIST 变更文件列表、
  右下 IDC_VIEW_PATCH "View Patch>>"（打开独立的 IDD_PATCH_VIEW 补丁窗口）。

支持：
  - 比较两个修订 rev1、rev2
  - 只比较工作区（rev1=None, rev2=None → git diff HEAD）
  - 可限定文件路径
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
from typing import List, Optional, Sequence

from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog,
    QFileIconProvider,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..git.repo import Repository
from ..res.strings import tr
from ..asyncfw import run_async
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .loglists import ChangedFile, filediff_action_color, status_text
from .resize import AnchorLayout
from .widgets import DiffView

# CFileDiffDlg：File / Extension / Action / Lines added / Lines removed
DIFF_COL_FILE = 0
DIFF_COL_EXT = 1
DIFF_COL_ACTION = 2
DIFF_COL_ADD = 3
DIFF_COL_DEL = 4


class _PatchViewDlg(QDialog):
    """IDD_PATCH_VIEW：独立的补丁查看窗口（IDC_PATCH 铺满）。"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        spec = rc_mod.load_spec("IDD_PATCH_VIEW")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.setWindowTitle(spec.caption or tr("filediff_patch_title", "View Patch"))
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.view = DiffView(self)
        self.view.setObjectName("IDC_PATCH")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.setGeometry(0, 0, self.width(), self.height())


class DiffDlg(QDialog):
    def __init__(self, repo: Repository, rev1: str | None = None,
                 rev2: str | None = None, paths: Sequence[str] | None = None,
                 parent=None, title: str = ""):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.rev1 = rev1
        self.rev2 = rev2
        self.paths = list(paths or [])
        self.patches: list = []
        self._ignore: List[str] = []
        self._patch_dlg: Optional[_PatchViewDlg] = None
        self._build_ui()
        self._load()

    # ---- UI（IDD_DIFFFILES 模板）----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_DIFFFILES")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        # 对齐原版 CResizableStandAloneDialog（WS_THICKFRAME）：可缩放，不小于模板
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(tr("filediff_title", "Changed Files"))
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        # 顶行
        self.lbl_between = QLabel(tr("filediff_between", "Difference between"), self)
        self.btn_diffoption = QPushButton(tr("filediff_diffoption", "Diff Options"), self)
        self.btn_diffoption.setCheckable(True)
        self.btn_diffoption.clicked.connect(self._on_diff_options)
        self.btn_log = QPushButton(tr("log_show_log", "Show log"), self)
        self.btn_log.clicked.connect(self._on_show_log)
        self.btn_switch = QPushButton(self)
        try:
            from ..res import icons
            self.btn_switch.setIcon(icons.icon("IDI_SWITCHLEFTRIGHT"))
        except Exception:  # noqa: BLE001
            pass
        self.btn_switch.setToolTip(tr("filediff_switch", "Switch left/right"))
        self.btn_switch.clicked.connect(self._on_switch)

        # Version 1 / Version 2 分组框（子控件与其同级，按 .rc 坐标覆盖其上）
        self.grp_rev1 = QGroupBox(tr("filediff_rev1", "Version 1 (Base)"), self)
        self.rev1_edit = QLineEdit(self)
        self.rev1_edit.returnPressed.connect(self._reload)
        self.rev1_btn = QPushButton("HEAD", self)
        self.rev1_btn.clicked.connect(lambda: self._browse_rev(1, self.rev1_btn))
        self.first_url = QLabel(self)
        self.first_url.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        self.grp_rev2 = QGroupBox(tr("filediff_rev2", "Version 2"), self)
        self.rev2_edit = QLineEdit(self)
        self.rev2_edit.returnPressed.connect(self._reload)
        self.rev2_btn = QPushButton("HEAD", self)
        self.rev2_btn.clicked.connect(lambda: self._browse_rev(2, self.rev2_btn))
        self.second_url = QLabel(self)
        self.second_url.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        # 文件过滤 + 变更文件列表
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(tr("filediff_filter", "Filter changed files…"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)

        self.file_tree = QTreeWidget(self)
        self.file_tree.setColumnCount(5)
        self.file_tree.setHeaderLabels([
            tr("filediff_file", "File"),
            tr("filediff_ext", "Extension"),
            tr("filediff_action", "Action"),
            tr("filediff_add", "Added"),
            tr("filediff_del", "Deleted"),
        ])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setIndentation(0)
        self.file_tree.setUniformRowHeights(True)
        self.file_tree.header().setSectionResizeMode(
            DIFF_COL_FILE, QHeaderView.ResizeMode.Stretch)
        self.file_tree.setColumnWidth(DIFF_COL_EXT, 64)
        self.file_tree.setColumnWidth(DIFF_COL_ACTION, 72)
        self.file_tree.setColumnWidth(DIFF_COL_ADD, 48)
        self.file_tree.setColumnWidth(DIFF_COL_DEL, 48)
        align_r = int(Qt.AlignmentFlag.AlignRight)
        self.file_tree.headerItem().setTextAlignment(DIFF_COL_ADD, align_r)
        self.file_tree.headerItem().setTextAlignment(DIFF_COL_DEL, align_r)
        self._file_icons = QFileIconProvider()
        self.file_tree.itemClicked.connect(self._on_file_clicked)
        self.file_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._on_menu)

        self.btn_view_patch = QPushButton(tr("filediff_viewpatch", "View Patch>>"), self)
        self.btn_view_patch.setFlat(True)
        self.btn_view_patch.clicked.connect(self._toggle_patch)

        mapping = {
            "IDC_DIFFSTATIC1": self.lbl_between,
            "IDC_DIFFOPTION": self.btn_diffoption,
            "IDC_LOG": self.btn_log,
            "IDC_SWITCHLEFTRIGHT": self.btn_switch,
            "IDC_REV1GROUP": self.grp_rev1,
            "IDC_REV1EDIT": self.rev1_edit,
            "IDC_REV1BTN": self.rev1_btn,
            "IDC_FIRSTURL": self.first_url,
            "IDC_REV2GROUP": self.grp_rev2,
            "IDC_REV2EDIT": self.rev2_edit,
            "IDC_REV2BTN": self.rev2_btn,
            "IDC_SECONDURL": self.second_url,
            "IDC_FILTER": self.filter_edit,
            "IDC_FILELIST": self.file_tree,
            "IDC_VIEW_PATCH": self.btn_view_patch,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            rc_mod.place_widget(self, fu, ctrl, wgt)
            self._ctl[ctrl.ctrl_id] = wgt

        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _DIFF_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        self.rev1_edit.setText(self.rev1 or "")
        self.rev2_edit.setText(self.rev2 or "")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 数据 ----
    def _reload(self, *_a):
        self.rev1 = self.rev1_edit.text().strip() or None
        self.rev2 = self.rev2_edit.text().strip() or None
        self._load()

    def _load(self):
        self.setWindowTitle(f"{self.repo.name} — {tr('loading')}")
        run_async(self._build_patch, on_done=self._on_loaded,
                  on_error=self._on_error, parent=self)

    def _build_patch(self) -> tuple:
        from ..udiff import parse_diff
        from ..merge.diffdata import normalize_revs
        old_rev, new_rev = normalize_revs(self.rev1, self.rev2)
        args: List[str] = ["diff", "--no-color", "-U3", *self._ignore]
        if old_rev and new_rev:
            args += [old_rev, new_rev]
        elif old_rev:
            args += [old_rev]
        if self.paths:
            args += ["--", *self.paths]
        else:
            args.append("--")
        out = self.repo.runner.run_checked(*args)
        patches = parse_diff(out)
        total = sum(p.added + p.removed for p in patches)
        return patches, total, self._rev_label(self.rev1), self._rev_label(self.rev2)

    def _rev_label(self, rev: str | None) -> str:
        if not rev:
            return ""
        try:
            subj = (self.repo.runner.run("log", "-1", "--format=%s", rev).stdout or "").strip()
        except Exception:  # noqa: BLE001
            subj = ""
        return f"{rev}: {subj}" if subj else rev

    def _on_loaded(self, payload):
        patches, _total, label1, label2 = payload
        self.patches = patches
        wt = tr("filediff_working_tree", "(working tree)")
        self.first_url.setText(label1 or wt)
        self.second_url.setText(label2 or wt)
        self.file_tree.clear()
        align_r = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for p in patches:
            row = ChangedFile(
                p.git_path, p.status_code,
                added="-" if p.is_binary else str(p.added),
                deleted="-" if p.is_binary else str(p.removed),
                old_path=p.old_path if p.is_rename else "",
            )
            item = QTreeWidgetItem([
                row.display_name(),
                p.ext,
                status_text(p.status_code),
                row.added,
                row.deleted,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, p)
            item.setIcon(0, self._file_icons.icon(QFileInfo(p.git_path)))
            item.setTextAlignment(DIFF_COL_ADD, align_r)
            item.setTextAlignment(DIFF_COL_DEL, align_r)
            rgb = filediff_action_color(p.status_code)
            brush = QBrush(QColor(*rgb))
            for c in range(item.columnCount()):
                item.setForeground(c, brush)
            self.file_tree.addTopLevelItem(item)
        self.setWindowTitle(tr("filediff_title", "Changed Files"))
        self._apply_filter()
        if patches:
            self.file_tree.setCurrentItem(self.file_tree.topLevelItem(0))

    def _on_error(self, message: str, _tb: str):
        self.setWindowTitle(tr("filediff_title", "Changed Files"))
        self.first_url.setText("")
        self.second_url.setText("")
        self.file_tree.clear()
        self.file_tree.addTopLevelItem(QTreeWidgetItem([str(message)]))

    # ---- 文件列表交互 ----
    def _apply_filter(self, *_a):
        text = self.filter_edit.text().strip().lower()
        for i in range(self.file_tree.topLevelItemCount()):
            it = self.file_tree.topLevelItem(i)
            p = it.data(0, Qt.ItemDataRole.UserRole)
            path = (getattr(p, "git_path", "") or "").lower() if p is not None else ""
            it.setHidden(bool(text) and text not in path)

    def _on_file_clicked(self, item, _col):
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is not None and self._patch_dlg is not None and self._patch_dlg.isVisible():
            self._show_patch(p)

    def _show_patch(self, patch):
        dlg = self._ensure_patch_dlg()
        dlg.view.display_patch(patch.raw, title=f"═══ {patch.filename_display} ═══")
        dlg.show()
        dlg.raise_()

    def _toggle_patch(self):
        dlg = self._ensure_patch_dlg()
        if dlg.isVisible():
            dlg.hide()
            self.btn_view_patch.setText(tr("filediff_viewpatch", "View Patch>>"))
            return
        item = self.file_tree.currentItem()
        if item is None and self.file_tree.topLevelItemCount():
            item = self.file_tree.topLevelItem(0)
        p = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if p is not None:
            self._show_patch(p)
        else:
            dlg.show()
        self.btn_view_patch.setText(tr("filediff_hidepatch", "Hide Patch"))

    def _ensure_patch_dlg(self) -> _PatchViewDlg:
        if self._patch_dlg is None:
            self._patch_dlg = _PatchViewDlg(self)
        return self._patch_dlg

    def _on_file_double_clicked(self, item, _col):
        """双击：对齐 CFileDiffDlg::DoDiff，打开并排比较。"""
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is not None:
            self._open_compare(p)

    def _open_compare(self, p):
        from ..merge.mergefrm import MergeFrm
        frm = MergeFrm(self.repo, p.git_path, self.rev1, self.rev2, parent=self)
        frm.show()

    # ---- 顶行按钮 ----
    def _on_switch(self):
        """IDC_SWITCHLEFTRIGHT：交换 Version 1 / Version 2。"""
        self.rev1, self.rev2 = self.rev2, self.rev1
        self.rev1_edit.setText(self.rev1 or "")
        self.rev2_edit.setText(self.rev2 or "")
        self._load()

    def _browse_rev(self, which: int, btn: QPushButton):
        refs: List[str] = []
        out = self.repo.runner.run(
            "for-each-ref", "--format=%(refname:short)").stdout or ""
        refs = [x.strip() for x in out.splitlines() if x.strip()]
        menu = QMenu(self)
        for name in refs[:100]:
            menu.addAction(name)
        menu.addSeparator()
        menu.addAction("HEAD")
        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen is None:
            return
        edit = self.rev1_edit if which == 1 else self.rev2_edit
        edit.setText(chosen.text())
        self._reload()

    def _on_show_log(self):
        from .logdlg import LogDlg
        pathspec = self.paths[0] if len(self.paths) == 1 else None
        LogDlg(self.repo, pathspec=pathspec,
               rev=self.rev2 or self.rev1, parent=self).exec()

    def _on_diff_options(self):
        """IDC_DIFFOPTION：diff 忽略选项下拉（对齐原版弹出菜单）。"""
        options = [
            ("--ignore-space-at-eol",
             tr("filediff_opt_eol", "Ignore changes in whitespace at EOL")),
            ("--ignore-space-change",
             tr("filediff_opt_space", "Ignore changes in amount of whitespace")),
            ("--ignore-all-space",
             tr("filediff_opt_allspace", "Ignore all whitespace")),
            ("--ignore-blank-lines",
             tr("filediff_opt_blank", "Ignore blank lines")),
        ]
        menu = QMenu(self)
        acts = {}
        for opt, label in options:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(opt in self._ignore)
            acts[act] = opt
        chosen = menu.exec(
            self.btn_diffoption.mapToGlobal(self.btn_diffoption.rect().bottomLeft()))
        self.btn_diffoption.setChecked(False)
        if chosen is None:
            return
        opt = acts[chosen]
        if opt in self._ignore:
            self._ignore.remove(opt)
        else:
            self._ignore.append(opt)
        self._load()

    # ---- 右键菜单（对齐 CFileDiffDlg::OnContextMenu）----
    def _on_menu(self, pos):
        item = self.file_tree.itemAt(pos)
        if item is None:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p is None:
            return
        path = p.git_path
        menu = QMenu(self)
        act_cmp = menu.addAction(tr("log_compare_two", "Compare two revisions"))
        act_gnu = menu.addAction(tr("log_gnudiff", "Show unified diff"))
        menu.addSeparator()
        act_log = menu.addAction(tr("log_show_log", "Show log"))
        act_blame = menu.addAction(tr("log_blame", "Blame"))
        menu.addSeparator()
        act_copy = menu.addAction(tr("log_copy_rel", "Relative path"))
        chosen = menu.exec(self.file_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_cmp:
            self._open_compare(p)
        elif chosen is act_gnu:
            self._show_patch(p)
        elif chosen is act_log:
            from .logdlg import LogDlg
            LogDlg(self.repo, pathspec=path, rev=self.rev2, parent=self).exec()
        elif chosen is act_blame:
            from .blamedlg import BlameDlg
            BlameDlg(self.repo, path, rev=self.rev2 or self.rev1, parent=self).exec()

    def _full_path(self, path: str) -> str:
        root = self.repo.root
        return os.path.join(root, path.replace("/", os.sep))

    def _open_external(self, path: str):
        """用外部工具打开文件 diff（配置了 tortoisegit.externaldiff 时）。"""
        import subprocess
        full = self._full_path(path)
        cmd = ""
        try:
            r = self.repo.runner.run("config", "--get", "diff.external")
            cmd = (r.stdout or "").strip()
        except Exception:  # noqa: BLE001
            pass
        if cmd:
            subprocess.Popen(cmd.replace("{path}", full), shell=False)
        elif os.path.isfile(full):
            os.startfile(full)  # noqa: S606


def diff_dialog(repo: Repository, rev1=None, rev2=None, paths=None,
                parent=None) -> DiffDlg:
    return DiffDlg(repo, rev1, rev2, paths, parent)


# AddAnchor 定义对齐 FileDiffDlg.cpp:189-204
_DIFF_ANCHORS = {
    "IDC_DIFFSTATIC1": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_SWITCHLEFTRIGHT": ("TOP_RIGHT",),
    "IDC_FIRSTURL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REV1BTN": ("TOP_RIGHT",),
    "IDC_SECONDURL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REV2BTN": ("TOP_RIGHT",),
    "IDC_FILTER": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_FILELIST": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_REV1GROUP": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REV2GROUP": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_REV1EDIT": ("TOP_LEFT",),
    "IDC_REV2EDIT": ("TOP_LEFT",),
    "IDC_DIFFOPTION": ("TOP_RIGHT",),
    "IDC_LOG": ("TOP_RIGHT",),
    "IDC_VIEW_PATCH": ("BOTTOM_RIGHT",),
}
