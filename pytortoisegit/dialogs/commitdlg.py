"""commitdlg.py — CommitDlg：提交对话框（镜像 TortoiseGit IDD_COMMITDLG）。

严格按 rc 模板 IDD_COMMITDLG 排版全部控件，行为参考 CommitDlg.cpp：
  - 顶行：Commit to / new branch / Bug-ID / BugTraq
  - 消息区（Scintilla → QPlainTextEdit）：amend、设置日期/时间、作者、
    Signed-off-by、字词统计（IDC_TEXT_INFO）
  - Check 链接行（All/None/Unversioned/Versioned/Added/Deleted/Modified/
    Files/Submodules）来回切换勾选
  - 文件清单（带复选框，Columns = Check/Path/Extension/Status/Add/Del）、
    统计（IDC_STATISTICS, "%d files selected, %d files total"）
  - 底行：Staging support / Show Unversioned / View Patch / Partial Staging/
    Unstaging / Whole Project / Message only / Commit / Cancel / Help
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
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..asyncfw import run_async
from ..git.index import GitIndex
from ..git.repo import Repository
from ..git.status import GitStatus
from ..git.statuslist import GitStatusList, StatusRow
from ..res.strings import format_string, tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits

# 锚点：参考 CommitDlg.cpp AddAnchor()
#   stretch_w  := 宽度随对话框横向拉伸（x,y,h 固定，w += dw）
#   stretch_b  := 横向 + 纵向拉伸（w += dw, h += dh）
#   br         := 钉在右下角（x += dw, y += dh）
#   bl         := 钉在左下角（y += dh）
#   tr         := 钉在右上角（x += dw）
#   其余默认     := 左上固定
_ANCHORS = {
    "IDC_MESSAGEGROUP": "stretch_w",
    "IDC_LOGMESSAGE": "stretch_w",
    "IDC_TEXT_INFO": "stretch_w",
    "IDC_SIGNOFF": "stretch_w",
    "IDC_LISTGROUP": "stretch_b",
    "IDC_FILELIST": "stretch_b",
    "IDC_VIEW_PATCH": "br",
    "IDC_PARTIAL_STAGING": "br",
    "IDC_PARTIAL_UNSTAGING": "br",
    "IDOK": "br",
    "IDCANCEL": "br",
    "IDHELP": "br",
    "IDC_SHOWUNVERSIONED": "bl",
    "IDC_STATISTICS": "bl",
    "IDC_WHOLE_PROJECT": "bl",
    "IDC_NOAUTOSELECTSUBMODULES": "bl",
    "IDC_STAGINGSUPPORT": "bl",
    "IDC_COMMIT_MESSAGEONLY": "bl",
    "IDC_NEWBRANCH": "tr",
    "IDC_BUGID": "tr",
}


class CommitDlg(QDialog):
    """提交对话框。"""

    COLS = [tr("rc_col_path", "Path"), tr("rc_col_ext", "Extension"),
            tr("rc_col_status", "Status"), tr("rc_col_add", "Lines added"),
            tr("rc_col_del", "Lines removed")]

    def __init__(self, repo: Repository, paths: Optional[List[str]] = None,
                 parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.paths: List[str] = list(paths or []) or [""]
        self.status = GitStatus(repo)
        self.index = GitIndex(repo)
        self.listctrl = GitStatusList(repo)
        self.rows: List[StatusRow] = []
        self._is_whole = (len(self.paths) == 1 and self.paths[0] == "")
        self._checked: Dict[str, bool] = {}
        self._build_ui()
        self.refresh()
        self._prefill_message()

    # ---- UI（IDD_COMMITDLG 模板）----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_COMMITDLG")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "")
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._ctl: Dict[str, object] = {}

        def add(widget, ctrl_id: str):
            widget.setObjectName(ctrl_id)
            self._ctl[ctrl_id] = widget
            return widget

        # 分组框
        add(QGroupBox(tr("commit_msg_group", "&Message:"), self),
            "IDC_MESSAGEGROUP")
        add(QGroupBox(tr("commit_list_group",
                         "Changes made (F5: refresh, double-click on file for "
                         "diff):"), self), "IDC_LISTGROUP")

        # 顶行：Commit to / new branch / Bug-ID
        add(QLabel(tr("commit_to_label", "Commit to:"), self), "IDC_COMMITLABEL")
        self.commit_to_edit = add(QLineEdit(self), "IDC_COMMIT_TO")
        self.commit_to_edit.setText(self.repo.current_branch())
        self.newbranch_edit = add(QLineEdit(self), "IDC_NEWBRANCH")
        self.chk_new_branch = add(QCheckBox(self), "IDC_CHECK_NEWBRANCH")
        self.chk_new_branch.setText(tr("commit_newbranch", "new branch"))
        self.chk_new_branch.toggled.connect(
            lambda on: self.newbranch_edit.setVisible(on))
        add(QLabel(tr("commit_bugid_label", "Bug-ID/Issue-Nr:"), self),
            "IDC_BUGIDLABEL")
        self.bugid_edit = add(QLineEdit(self), "IDC_BUGID")
        self.bugtraq_btn = add(QPushButton(tr("browse", "Browse..."), self),
                               "IDC_BUGTRAQBUTTON")

        # 消息区（Scintilla → QPlainTextEdit）
        self.message_edit = add(QPlainTextEdit(self), "IDC_LOGMESSAGE")
        self.message_edit.setPlaceholderText(
            tr("commit_hint", "First line is the subject, blank line then the body"))
        self.message_edit.textChanged.connect(self._update_stats)
        self.amend_box = add(QCheckBox(self), "IDC_COMMIT_AMEND")
        self.amend_box.setText(tr("commit_amend", "Amend last commit"))
        self.amend_box.toggled.connect(self._on_amend_toggled)
        self.amend_diff_btn = add(
            QPushButton(tr("commit_amend_diff", "Show changes to last commit"), self),
            "IDC_COMMIT_AMENDDIFF")
        self.amend_diff_btn.clicked.connect(self._on_amend_diff)
        self.chk_set_date = add(QCheckBox(self), "IDC_COMMIT_SETDATETIME")
        self.chk_set_date.setText(tr("commit_set_date", "Set author date"))
        self.chk_set_date.toggled.connect(self._on_set_date_toggled)
        self.date_picker = add(QDateTimeEdit(self), "IDC_COMMIT_DATEPICKER")
        self.time_picker = add(QDateTimeEdit(self), "IDC_COMMIT_TIMEPICKER")
        self.reset_date_btn = add(
            QPushButton(tr("commit_reset_date", "Reset"), self),
            "IDC_COMMIT_AS_COMMIT_DATE")
        self.reset_date_btn.clicked.connect(self._on_reset_date)
        self.chk_set_author = add(QCheckBox(self), "IDC_COMMIT_SETAUTHOR")
        self.chk_set_author.setText(tr("commit_set_author", "Set author"))
        self.chk_set_author.toggled.connect(self._on_set_author_toggled)
        self.author_edit = add(QLineEdit(self), "IDC_COMMIT_AUTHORDATA")
        self.signoff_btn = add(
            QPushButton(tr("commit_signoff", "Add Signed-off-by"), self),
            "IDC_SIGNOFF")
        self.signoff_btn.clicked.connect(self._on_signoff)
        self.text_info = add(QLabel("", self), "IDC_TEXT_INFO")

        # 分割线 + Check 链接行
        splitter = QFrame(self)
        splitter.setFrameShape(QFrame.Shape.HLine)
        add(splitter, "IDC_SPLITTER")
        add(QLabel(tr("commit_check_label", "Check:"), self), "IDC_SELECTLABEL")
        self.check_links: Dict[str, QLabel] = {}
        for key, ctrl_id, caption in (
                ("All", "IDC_CHECKALL", "&All"),
                ("None", "IDC_CHECKNONE", "&None"),
                ("Unversioned", "IDC_CHECKUNVERSIONED", "Unversioned"),
                ("Versioned", "IDC_CHECKVERSIONED", "Versioned"),
                ("Added", "IDC_CHECKADDED", "Added"),
                ("Deleted", "IDC_CHECKDELETED", "Deleted"),
                ("Modified", "IDC_CHECKMODIFIED", "Modified"),
                ("Files", "IDC_CHECKFILES", "Files"),
                ("Submodules", "IDC_CHECKSUBMODULES", "Submodules")):
            lbl = QLabel(caption.replace("&", ""), self)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.mousePressEvent = self._make_check_link(key)
            add(lbl, ctrl_id)
            self.check_links[key] = lbl

        # 文件清单（SysListView32 → QTreeWidget，带复选框）
        self.status_tree = add(QTreeWidget(self), "IDC_FILELIST")
        self.status_tree.setColumnCount(len(self.COLS))
        self.status_tree.setHeaderLabels(self.COLS)
        self.status_tree.setColumnWidth(0, 200)
        self.status_tree.setColumnWidth(1, 52)
        self.status_tree.setColumnWidth(2, 72)
        self.status_tree.setColumnWidth(3, 62)
        self.status_tree.setIndentation(0)
        self.status_tree.itemChanged.connect(self._on_item_changed)
        self.status_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        import PySide6.QtCore as _qcore
        self.status_tree.setContextMenuPolicy(_qcore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.status_tree.customContextMenuRequested.connect(self._on_status_menu)

        # 底行控件
        self.chk_staging = add(QCheckBox(self), "IDC_STAGINGSUPPORT")
        self.chk_staging.setText(tr("commit_staging",
                                    "Staging support (EXPERIMENTAL)"))
        self.chk_staging.toggled.connect(self._on_staging_toggled)
        self.chk_show_unversioned = add(QCheckBox(self), "IDC_SHOWUNVERSIONED")
        self.chk_show_unversioned.setText(tr("commit_show_unversioned",
                                             "Show &Unversioned Files"))
        self.chk_show_unversioned.setChecked(True)
        self.chk_show_unversioned.toggled.connect(self._on_show_unversioned)
        self.stats_label = add(QLabel("", self), "IDC_STATISTICS")
        self.partial_staging_link = add(
            QLabel(tr("commit_partial_staging", "Partial Staging>>"), self),
            "IDC_PARTIAL_STAGING")
        self.partial_unstaging_link = add(
            QLabel(tr("commit_partial_unstaging", "Partial Unstaging>>"), self),
            "IDC_PARTIAL_UNSTAGING")
        self.chk_no_autoselect = add(QCheckBox(self),
                                     "IDC_NOAUTOSELECTSUBMODULES")
        self.chk_no_autoselect.setText(
            tr("commit_no_autoselect", "Do not autoselect submodules"))
        self.view_patch_link = add(
            QLabel(tr("commit_view_patch", "View Patch>>"), self),
            "IDC_VIEW_PATCH")
        self.view_patch_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_patch_link.mousePressEvent = self._on_view_patch
        self.chk_whole_project = add(QCheckBox(self), "IDC_WHOLE_PROJECT")
        self.chk_whole_project.setText(tr("commit_whole_project",
                                          "Show &Whole Project"))
        self.chk_whole_project.setChecked(self._is_whole)
        self.chk_whole_project.setEnabled(not self._is_whole)
        self.chk_message_only = add(QCheckBox(self), "IDC_COMMIT_MESSAGEONLY")
        self.chk_message_only.setText(tr("commit_message_only", "Message onl&y"))

        self.btn_commit = add(QToolButton(self), "IDOK")
        self.btn_commit.setText(tr("commit", "C&ommit"))
        self.btn_commit.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_commit.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        menu = QMenu(self.btn_commit)
        self._act_commit = menu.addAction(tr("commit", "C&ommit"))
        self._act_commit_push = menu.addAction(tr("commit_push", "Commit and &Push"))
        self.btn_commit.setMenu(menu)
        self.btn_commit.setDefaultAction(self._act_commit)
        self._act_commit.triggered.connect(lambda *_: self._accept_commit(False))
        self._act_commit_push.triggered.connect(lambda *_: self._accept_commit(True))
        self.btn_cancel = add(QPushButton(tr("cancel"), self), "IDCANCEL")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = add(QPushButton(tr("help"), self), "IDHELP")
        self.btn_help.clicked.connect(self._on_help)

        # 按模板摆放全部控件
        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is not None:
                rc_mod.place_widget(self, fu, ctrl, wgt)

        self._setup_anchors()
        self._on_set_author_toggled(False)

    # ---- 锚点（参考 CResizableDialog）----
    def _setup_anchors(self):
        self._anchor_base = (self.width(), self.height())
        self._anchor_rects: Dict[str, tuple] = {}
        for ctrl_id, wgt in self._ctl.items():
            self._anchor_rects[ctrl_id] = (
                wgt.x(), wgt.y(), wgt.width(), wgt.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "_anchor_base"):
            return
        dw = self.width() - self._anchor_base[0]
        dh = self.height() - self._anchor_base[1]
        for ctrl_id, (x, y, w, h) in self._anchor_rects.items():
            kind = _ANCHORS.get(ctrl_id, "")
            wgt = self._ctl.get(ctrl_id)
            if wgt is None:
                continue
            if kind == "stretch_w":
                wgt.setGeometry(x, y, w + dw, h)
            elif kind == "stretch_b":
                wgt.setGeometry(x, y, w + dw, h + dh)
            elif kind == "br":
                wgt.setGeometry(x + dw, y + dh, w, h)
            elif kind == "bl":
                wgt.setGeometry(x, y + dh, w, h)
            elif kind == "tr":
                wgt.setGeometry(x + dw, y, w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
            event.accept()
            return
        super().keyPressEvent(event)

    # ---- 事件 ----
    def _on_amend_toggled(self, on: bool):
        self.amend_diff_btn.setVisible(on)
        if on and not self.message_edit.toPlainText().strip():
            head = self.repo.runner.run("log", "-1", "--format=%B").stdout.rstrip("\n")
            if head:
                self.message_edit.setPlainText(head)

    def _prefill_message(self):
        """打开时若消息为空，按 commit.template / MERGE_MSG / SQUASH_MSG 预填。"""
        if self.message_edit.toPlainText().strip():
            return
        template = ""
        try:
            cfg = self.repo.runner.run("config", "--get", "commit.template").stdout
            template = (cfg or "").strip()
        except Exception:
            pass
        if not template:
            for fname in ("MERGE_MSG", "SQUASH_MSG"):
                p = os.path.join(self.repo.git_dir, fname)
                if os.path.isfile(p):
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        template = fh.read()
                    break
        if not template:
            return
        has_comment = any(l.strip().startswith(("##", "#")) for l in template.splitlines())
        cleaned = template
        if has_comment:
            cleaned = "\n".join(
                l for l in template.splitlines()
                if not l.strip().startswith("#"))
        self.message_edit.setPlainText(cleaned.strip())

    def _on_set_date_toggled(self, on: bool):
        self.date_picker.setVisible(on)
        self.time_picker.setVisible(on)
        self.reset_date_btn.setVisible(on)

    def _on_reset_date(self):
        self.chk_set_date.setChecked(False)

    def _on_set_author_toggled(self, on: bool):
        self.author_edit.setEnabled(on)
        self.author_edit.setVisible(on)
        if not on:
            self.author_edit.clear()

    def _on_signoff(self):
        name = self.repo.config("user.name")
        email = self.repo.config("user.email")
        line = f"Signed-off-by: {name} <{email}>"
        text = self.message_edit.toPlainText()
        if line in text:
            return
        self.message_edit.setPlainText(text.rstrip() + "\n\n" + line + "\n")

    def _on_staging_toggled(self, on: bool):
        self.partial_staging_link.setVisible(on)
        self.partial_unstaging_link.setVisible(on)

    def _on_show_unversioned(self, _on: bool):
        self._apply_show_flags()

    def _on_view_patch(self, _event=None):
        from .diffdlg import DiffDlg
        sel = self._checked_paths()
        paths = sel or None
        dlg = DiffDlg(self.repo, rev2="HEAD", paths=paths, parent=self)
        dlg.exec()

    def _on_help(self):
        QMessageBox.information(
            self, tr("help"),
            tr("commit_help", "The first line is the subject, followed by a blank line then the body. Use the checkboxes on the left to choose which files to commit."))

    # ---- Check 链接 ----

    def closeEvent(self, event):
        # 取消确认：有未提交内容时询问（对齐 TGit）
        if self.message_edit.toPlainText().strip() or self._checked_paths():
            resp = QMessageBox.question(
                self, tr("confirm", "Confirm"),
                tr("commit_cancel_confirm", "Really cancel? Uncommitted changes will be lost."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)

    def _make_check_link(self, key: str):
        def _clicked(_event):
            self._toggle_check_group(key)
        return _clicked

    def _toggle_check_group(self, key: str):
        items = [self.status_tree.topLevelItem(i)
                 for i in range(self.status_tree.topLevelItemCount())]
        if key == "All":
            for item in items:
                item.setCheckState(0, Qt.CheckState.Checked)
        elif key == "None":
            for item in items:
                item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            wanted = {
                "Unversioned": {"untracked"},
                "Versioned": {"modified", "added", "deleted", "renamed",
                              "copied", "conflicted"},
                "Added": {"added", "copied"},
                "Deleted": {"deleted"},
                "Modified": {"modified", "renamed", "conflicted"},
            }.get(key, None)
            if key == "Files":
                wanted = {"untracked", "modified", "added", "deleted",
                          "renamed", "copied", "conflicted"}
            for item in items:
                row = item.data(0, Qt.ItemDataRole.UserRole + 1)
                if not isinstance(row, StatusRow):
                    continue
                if wanted is not None and row.state not in wanted:
                    continue  # Submodules：无匹配，跳过
                cur = item.checkState(0)
                item.setCheckState(0, Qt.CheckState.Unchecked if cur == Qt.CheckState.Checked
                                   else Qt.CheckState.Checked)

    # ---- 加载 ----
    def refresh(self):
        run_async(self._load_bg, on_done=self._on_loaded,
                  on_error=lambda m, _tb: self.stats_label.setText(m), parent=self)

    def _load_bg(self) -> List[StatusRow]:
        self.listctrl.fetch(
            include_staged=True,
            include_unversioned=True,
            include_ignored=False,
            include_local_changes_ignored=False,
        )
        return self.listctrl.rows

    def _on_loaded(self, rows: List[StatusRow]):
        self.rows = rows
        for r in rows:
            key = r.path
            if r.entry.is_staged or r.index_only:
                self._checked[key] = True
        self._apply_show_flags()

    def _apply_show_flags(self):
        self.status_tree.blockSignals(True)
        self.status_tree.clear()
        show_unver = self.chk_show_unversioned.isChecked()
        for r in self.rows:
            if r.state == "untracked" and not show_unver:
                continue
            ext = r.entry.path.rsplit(".", 1)[1] if "." in r.entry.path.split("/")[-1] else ""
            item = QTreeWidgetItem([
                r.display_path, ext, r.action,
                str(r.lines_added) if r.lines_added else "",
                str(r.lines_removed) if r.lines_removed else "",
            ])
            color = QColor(r.color)
            item.setForeground(0, color)
            item.setForeground(2, color)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if self._checked.get(r.path)
                               else Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, r)
            self.status_tree.addTopLevelItem(item)
        self.status_tree.blockSignals(False)
        self._update_stats()
        if self.status_tree.topLevelItemCount():
            self.status_tree.setCurrentItem(self.status_tree.topLevelItem(0))

    def _on_item_changed(self, item, _col):
        if _col != 0:
            return
        row = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if isinstance(row, StatusRow):
            self._checked[row.path] = (item.checkState(0) == Qt.CheckState.Checked)
        self._update_stats()

    def _on_item_double_clicked(self, item, _col):
        row = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if isinstance(row, StatusRow):
            self._show_diff(row.path)

    def _on_status_menu(self, pos):
        item = self.status_tree.itemAt(pos)
        if item is None:
            return
        row = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(row, StatusRow):
            return
        path = row.path
        menu = QMenu(self)
        act_open = menu.addAction(tr("menu_open", "Open in editor"))
        act_copy = menu.addAction(tr("menu_copy_path", "Copy path"))
        menu.addSeparator()
        act_diff = menu.addAction(tr("menu_diff_file", "View diff"))
        act_viewpatch = menu.addAction(tr("commit_view_patch", "View patch"))
        act_blame = menu.addAction(tr("menu_blame", "Blame this file"))
        chosen = menu.exec(self.status_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        full = self._full_path(path)
        if chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_open:
            import os
            if full and os.path.isfile(full):
                os.startfile(full)  # noqa: S606
        elif chosen is act_diff:
            self._show_diff(path)
        elif chosen is act_viewpatch:
            self._show_patch(path)
        elif chosen is act_blame:
            from .blamedlg import BlameDlg
            BlameDlg(self.repo, path, parent=self).exec()

    def _full_path(self, path: str) -> str:
        import os
        return os.path.join(self.repo.root, str(path).replace("/", os.sep))

    def _show_diff(self, path: str):
        from .diffdlg import DiffDlg
        DiffDlg(self.repo, rev1="HEAD", rev2=None, paths=[path],
                parent=self).show()

    def _show_patch(self, path: str):
        try:
            text = self.repo.runner.run_checked(
                "diff", "HEAD", "--", path)
            from .patchviewdlg import PatchViewDlg
            PatchViewDlg(text, title=path, parent=self).exec()
        except Exception:
            pass

    def _on_amend_diff(self):
        """amend 模式下显示到上次提交的改动。"""
        from .diffdlg import DiffDlg
        DiffDlg(self.repo, rev1="HEAD~1", rev2="HEAD", parent=self).exec()

    def _update_stats(self):
        # 字数统计（对齐 TGit IDC_TEXT_INFO 实时统计）
        msg = self.message_edit.toPlainText()
        if hasattr(self, "text_info"):
            words = len(msg.split()) if msg.strip() else 0
            self.text_info.setText(format_string(
                tr("commit_text_info", "{chars} chars / {lines} lines"),
                chars=len(msg), lines=len(msg.splitlines())))
        total = self.status_tree.topLevelItemCount()
        if not total:
            self.stats_label.setText(tr("commit_nothing", "No changes to commit"))
            return
        n = sum(1 for i in range(total)
                if self.status_tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)
        self.stats_label.setText(format_string(
            tr("commit_stats", "{sel} files selected, {total} files total"),
            sel=n, total=total))

    def _checked_paths(self) -> List[str]:
        return [p for p, ck in self._checked.items() if ck]

    # ---- 提交 ----
    def _accept_commit(self, push: bool = False):
        msg = self.message_edit.toPlainText().strip()
        paths = self._checked_paths()
        if not paths and not self.amend_box.isChecked() and not self.chk_message_only.isChecked():
            QMessageBox.warning(self, tr("warning"), tr("commit_nothing", "No files selected to commit"))
            return
        if not msg and not self.chk_message_only.isChecked():
            QMessageBox.warning(self, tr("warning"), tr("commit_empty_msg", "Please enter a commit message"))
            return

        brand_new = self.chk_new_branch.isChecked()
        if brand_new:
            branch = self.newbranch_edit.text().strip()
            if not branch:
                QMessageBox.warning(self, tr("warning"), tr("commit_newname", "Please enter a new branch name"))
                return
            if self.repo.runner.run("branch", "--list", branch).stdout.strip():
                QMessageBox.warning(self, tr("warning"),
                                    format_string(tr("commit_branch_exists", "Branch {name} already exists"),
                                                  name=branch))
                return
            self.repo.runner.run("checkout", "-b", branch)

        if paths:
            self.index.add(paths)

        author = None
        if self.chk_set_author.isChecked():
            author = self.author_edit.text().strip() or None
        result = self.index.commit(
            message=msg or None,
            amend=self.amend_box.isChecked(),
            author=author,
            sign_off="Signed-off-by:" in self.message_edit.toPlainText(),
            allow_empty=self.chk_message_only.isChecked(),
        )
        if result.returncode != 0:
            QMessageBox.warning(self, tr("commit_failed", "Commit failed"), result.stderr)
            return
        if push:
            from .pushdlg import do_push_after_commit
            do_push_after_commit(
                self.repo, parent=self, amend=self.amend_box.isChecked())
        self.accept()
