"""changedlg.py —— ChangedDlg：检查工作区修改（镜像 TortoiseGit IDD_CHANGEDFILES）。

复刻 TortoiseGit 的 Working Tree 对话框：按 .rc 模板 IDD_CHANGEDFILES 排版，
文件列表列 = GITSLC_COLEXT|COLSTATUS|COLADD|COLDEL|COLMODIFICATIONDATE，
行为参考 ChangedDlg.cpp（UpdateShowFlags 过滤、行统计、Stash 下拉、分支 SysLink）。
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

from typing import List, Optional

from PySide6.QtCore import QFileInfo, QSignalBlocker, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileIconProvider,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from ..asyncfw import run_async
from ..git.index import GitIndex
from ..git.repo import Repository
from ..git.stash import GitStash
from ..git.statuslist import GitStatusList, StatusRow
from ..res.strings import format_string, tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits


# ---------------------------------------------------------------------------
# 复刻工具：按 rc 模板排版的控件
# ---------------------------------------------------------------------------

class ChangedDlg(QDialog):
    """Working Tree 对话框。"""

    COLS = [tr("rc_col_path", "Path"), tr("rc_col_ext", "Extension"),
            tr("rc_col_status", "Status"), tr("rc_col_add", "Lines added"),
            tr("rc_col_del", "Lines removed"), tr("rc_col_moddate", "Last Modified")]

    def __init__(self, repo: Repository, paths: Optional[List[str]] = None,
                 parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.paths: List[str] = list(paths or []) or [""]
        self.index = GitIndex(repo)
        self.stash = GitStash(repo)
        self.listctrl = GitStatusList(repo)
        self.rows: List[StatusRow] = []
        self.m_bool_show: dict = {}
        self._build_ui()
        self.refresh()

    # ---- UI 构建（按 rc 模板与 ChangedDlg.cpp 的 AddAnchor 布局）----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_CHANGEDFILES")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        self._fu = fu
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        if spec.caption:
            self.setWindowTitle(spec.caption)
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._is_whole_default = (len(self.paths) == 1 and self.paths[0] == "")
        self._set_dlg_title()

        # 顶部：分支 SysLink（IDC_BRANCH）
        self.branch_link = QLabel(self)
        self.branch_link.setTextFormat(Qt.TextFormat.RichText)
        self.branch_link.setOpenExternalLinks(False)
        self.branch_link.linkActivated.connect(self._on_branch_clicked)

        # 中部：文件列表（IDC_CHANGEDLIST）
        self.status_tree = QTreeWidget(self)
        self.status_tree.setColumnCount(len(self.COLS))
        self.status_tree.setHeaderLabels(self.COLS)
        self.status_tree.setColumnWidth(0, 240)
        self.status_tree.setColumnWidth(1, 64)
        self.status_tree.setColumnWidth(2, 96)
        self.status_tree.setColumnWidth(3, 70)
        self.status_tree.setColumnWidth(4, 76)
        self.status_tree.setColumnWidth(5, 120)
        self.status_tree.setRootIsDecorated(True)
        self.status_tree.setIndentation(12)
        self.status_tree.setUniformRowHeights(True)
        self._file_icons = QFileIconProvider()
        self.status_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.status_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.status_tree.customContextMenuRequested.connect(self._on_menu)

        # 复选框（ddx 顺序与 ChangedDlg.h 一致）
        self.chk_unversioned = _checkbox(self, "Show un&versioned files", self._on_flag_toggled)
        self.chk_localchangesignored = _checkbox(
            self, "Show ignore local changes flagged files", self._on_flag_toggled)
        self.chk_ignored = _checkbox(self, "Show i&gnored files", self._on_flag_toggled)
        self.chk_staged = _checkbox(self, "Show all &staged files", self._on_flag_toggled)
        self.chk_whole_project = _checkbox(self, "Show &Whole Project", self._on_flag_toggled)

        # 底部信息区
        self.summary_text = QLabel(self)
        self.summary_text.setWordWrap(True)
        self.info_label = QPlainTextEdit(self)
        self.info_label.setReadOnly(True)
        self.info_label.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.info_label.setMaximumHeight(46)

        # 按钮
        self.btn_unifieddiff = QPushButton(tr("changes_save_unified", "Save unified diff"), self)
        self.btn_stash = QPushButton(tr("changes_stash", "Stash"), self)
        self.btn_commit = QPushButton(tr("commit_perform", "Commit"), self)
        self.btn_refresh = QPushButton(tr("refresh"), self)
        self.btn_ok = _defbutton(self, tr("ok"))

        # 若非整仓（单文件/选中路径），Whole Project 可用；空路径强制整仓
        with QSignalBlocker(self.chk_unversioned), QSignalBlocker(self.chk_staged), QSignalBlocker(self.chk_whole_project):
            self.chk_whole_project.setChecked(self._is_whole_default)
            self.chk_unversioned.setChecked(True)
            self.chk_staged.setChecked(True)

        # 按 rc 模板绝对定位（DLU -> px）
        for c in spec.controls:
            self._place_control(c, fu)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_commit.clicked.connect(self._open_commit)
        self.btn_unifieddiff.clicked.connect(self._open_unified_diff)
        self.btn_stash.clicked.connect(self._on_stash_menu)

        self._anchors = {
            "branch": self.branch_link,
            "list": self.status_tree,
            "summary": self.summary_text,
            "chk_unversioned": self.chk_unversioned,
            "chk_localchangesignored": self.chk_localchangesignored,
            "chk_ignored": self.chk_ignored,
            "chk_staged": self.chk_staged,
            "chk_whole": self.chk_whole_project,
            "info": self.info_label,
            "btn_unifieddiff": self.btn_unifieddiff,
            "btn_stash": self.btn_stash,
            "btn_commit": self.btn_commit,
            "btn_refresh": self.btn_refresh,
            "btn_ok": self.btn_ok,
        }

        self._setup_anchors(r.width(), r.height())

    def _set_dlg_title(self):
        # 镜像 SetDlgTitle()/CAppUtils::SetWindowTitle：整仓→根目录，否则→路径
        caption = self.windowTitle()
        if self._is_whole_default:
            base = self.repo.root
        elif len(self.paths) == 1:
            base = self.repo.full_path(self.paths[0])
        else:
            base = self.repo.root
        self.setWindowTitle(f"{base} - {caption}")

    def _place_control(self, ctrl, fu):
        target = {
            "IDC_BRANCH": self.branch_link,
            "IDC_CHANGEDLIST": self.status_tree,
            "IDC_SHOWUNVERSIONED": self.chk_unversioned,
            "IDC_SHOWLOCALCHANGESIGNORED": self.chk_localchangesignored,
            "IDC_SHOWIGNORED": self.chk_ignored,
            "IDC_SHOWSTAGED": self.chk_staged,
            "IDC_WHOLE_PROJECT": self.chk_whole_project,
            "IDC_SUMMARYTEXT": self.summary_text,
            "IDC_INFOLABEL": self.info_label,
            "IDC_BUTTON_UNIFIEDDIFF": self.btn_unifieddiff,
            "IDC_BUTTON_STASH": self.btn_stash,
            "IDC_COMMIT": self.btn_commit,
            "IDC_REFRESH": self.btn_refresh,
            "IDOK": self.btn_ok,
        }.get(ctrl.ctrl_id)
        if target is None:
            return
        rc_mod.place_widget(self, fu, ctrl, target)

    def _on_flag_toggled(self):
        state = self._show_flags()
        if state["unversioned"] and not (self.m_bool_show.get("fileloaded_unver")):
            self.refresh()
            return
        if state["ignored"] and not (self.m_bool_show.get("fileloaded_ignore")):
            self.refresh()
            return
        if state["localchangesignored"] and not (self.m_bool_show.get("fileloaded_localchangesignored")):
            self.refresh()
            return
        self._apply_show_flags()

    def _show_flags(self) -> dict:
        return {
            "unversioned": self.chk_unversioned.isChecked(),
            "localchangesignored": self.chk_localchangesignored.isChecked(),
            "ignored": self.chk_ignored.isChecked(),
            "staged": self.chk_staged.isChecked(),
            "whole": self.chk_whole_project.isChecked(),
            "unmodified": False,
        }

    def _apply_show_flags(self):
        flags = self._show_flags()
        self.m_bool_show.update(flags)
        self._populate()
        counts = self.listctrl.statistics()
        added, removed = self.listctrl.line_stats()
        text = format_string(
            tr("changes_stats",
               "line: {add}(+) {remove}(-) files: normal={normal}, non-versioned={unver}, "
               "modified={modified}, added={added}, deleted={deleted}, conflicted={conflicted}"),
            add=added, remove=removed,
            normal=counts["normal"], unver=counts["non-versioned"],
            modified=counts["modified"], added=counts["added"],
            deleted=counts["deleted"], conflicted=counts["conflicted"])
        self.info_label.setPlainText(text)

    # ---- 数据刷新（镜像 ChangedStatusThread）----
    def refresh(self):
        if self.m_bool_show.get("busy"):
            return
        self.m_bool_show["busy"] = True
        self.m_bool_show["canceled"] = False
        self._load_flags = self._show_flags()
        self.btn_ok.setText(tr("cancel"))
        for w in (self.btn_refresh, self.chk_unversioned, self.chk_ignored,
                  self.chk_localchangesignored, self.chk_staged, self.chk_whole_project):
            w.setEnabled(False)
        self.branch_link.setText("")
        self.status_tree.clear()
        run_async(self._load_bg, on_done=self._on_loaded,
                  on_error=lambda m, _tb: self._load_failed(m), parent=self)

    def _load_bg(self):
        flags = self._load_flags
        self.listctrl.fetch(
            include_staged=flags["staged"],
            include_unversioned=flags["unversioned"] or self._is_whole_default,
            include_ignored=flags["ignored"],
            include_local_changes_ignored=flags["localchangesignored"],
        )
        return self.listctrl.rows

    def _on_loaded(self, rows: List[StatusRow]):
        self.rows = rows
        self.m_bool_show["fileloaded_unver"] = True
        self.m_bool_show["fileloaded_ignore"] = True
        self.m_bool_show["fileloaded_localchangesignored"] = True
        self._apply_show_flags()

        branch = self.repo.current_branch()
        self.branch_link.setText(f'<a href="switch:{branch}">{branch}</a>')

        self.btn_ok.setText(tr("ok"))
        for w in (self.btn_refresh, self.chk_unversioned, self.chk_ignored,
                  self.chk_localchangesignored, self.chk_staged, self.chk_whole_project):
            w.setEnabled(True)
        if self._is_whole_default:
            self.chk_whole_project.setEnabled(False)
        self.m_bool_show["busy"] = False

    def _load_failed(self, message: str):
        self.info_label.setPlainText(message)
        self.btn_ok.setText(tr("ok"))
        for w in (self.btn_refresh, self.chk_unversioned, self.chk_ignored,
                  self.chk_localchangesignored, self.chk_staged, self.chk_whole_project):
            w.setEnabled(True)
        self.m_bool_show["busy"] = False

    # ---- 列表填充（对齐 CGitStatusListCtrl::PrepareGroups）----
    def _populate(self):
        self.status_tree.clear()
        buckets = {
            "modified": [],
            "unversioned": [],
            "ignored": [],
            "localignore": [],
        }
        for r in self.rows:
            if not self._row_visible(r):
                continue
            if r.state == "untracked":
                buckets["unversioned"].append(r)
            elif r.state == "ignored":
                buckets["ignored"].append(r)
            elif r.assume_valid or r.skip_worktree:
                buckets["localignore"].append(r)
            else:
                buckets["modified"].append(r)
        labels = (
            ("modified", tr("log_file_group", "Modified files")),
            ("unversioned", tr("status_group_unversioned", "Unversioned files")),
            ("ignored", tr("status_group_ignored", "Ignored files")),
            ("localignore", tr("status_group_localignore", "Files with local changes ignored")),
        )
        # 有未跟踪/忽略等才分组（与 PrepareGroups 的 bHasGroups 一致）
        has_groups = bool(buckets["unversioned"] or buckets["ignored"]
                          or buckets["localignore"])
        first_item = None
        for key, title in labels:
            rows = buckets[key]
            if not rows:
                continue
            parent = None
            if has_groups:
                parent = QTreeWidgetItem([title])
                parent.setFirstColumnSpanned(True)
                font = parent.font(0)
                font.setBold(True)
                parent.setFont(0, font)
                self.status_tree.addTopLevelItem(parent)
            for r in rows:
                item = self._make_file_item(r)
                if parent is None:
                    self.status_tree.addTopLevelItem(item)
                else:
                    parent.addChild(item)
                if first_item is None:
                    first_item = item
            if parent is not None:
                parent.setExpanded(True)
        if first_item is not None:
            self.status_tree.setCurrentItem(first_item)

    def _make_file_item(self, r: StatusRow) -> QTreeWidgetItem:
        ext = _extension_of(r.path)
        mod = r.mtime.strftime("%Y-%m-%d %H:%M") if r.mtime else ""
        item = QTreeWidgetItem([
            r.display_path, ext, r.action,
            str(r.lines_added) if r.lines_added else "",
            str(r.lines_removed) if r.lines_removed else "",
            mod,
        ])
        info = QFileInfo(self.repo.full_path(r.path))
        icon = self._file_icons.icon(info)
        if icon.isNull():
            kind = (QFileIconProvider.IconType.Folder if info.isDir()
                    else QFileIconProvider.IconType.File)
            icon = self._file_icons.icon(kind)
        item.setIcon(0, icon)
        brush = QBrush(QColor(r.color))
        for c in range(item.columnCount()):
            item.setForeground(c, brush)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, r)
        return item

    def _row_visible(self, r: StatusRow) -> bool:
        flags = self.m_bool_show
        if r.state == "ignored" and not flags.get("ignored"):
            return False
        if r.state == "untracked" and not flags.get("unversioned"):
            return False
        if (r.assume_valid or r.skip_worktree) and not flags.get("localchangesignored"):
            return False
        if not flags.get("staged") and r.index_only:
            return False
        return True

    # ---- 分支 SysLink / 菜单 ----
    def _on_branch_clicked(self, _url: str = ""):
        from .browserefs import BrowseRefsDlg
        dlg = BrowseRefsDlg(self.repo, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_stash_menu(self):
        menu = QMenu(self)
        act_save = menu.addAction(tr("changes_stash_save", "Stash changes"))
        has_stash = bool(self.stash.list())
        menu.addSeparator()
        act_list = menu.addAction(tr("changes_stash_list", "Stash List"))
        act_pop = menu.addAction(tr("changes_stash_pop", "Stash Pop"))
        act_apply = menu.addAction(tr("changes_stash_apply", "Stash Apply"))
        act_pop.setEnabled(has_stash)
        act_apply.setEnabled(has_stash)
        chosen = menu.exec(self.btn_stash.mapToGlobal(self.btn_stash.rect().bottomLeft()))
        if chosen is None:
            return
        if chosen is act_save:
            ok = self.stash.create(include_untracked=self.chk_unversioned.isChecked())
            if not ok:
                QMessageBox.warning(self, tr("error"), tr("changes_stash_failed", "Stash failed"))
        elif chosen is act_pop:
            latest = self.stash.latest()
            if latest:
                self.stash.pop(latest.gd)
        elif chosen is act_apply:
            latest = self.stash.latest()
            if latest:
                self.stash.apply(latest.gd)
        elif chosen is act_list:
            self._show_stash_list()
        self.refresh()

    def _show_stash_list(self):
        entries = self.stash.list()
        if not entries:
            QMessageBox.information(self, tr("information"), tr("stash_empty"))
            return
        lines = [e.display_text for e in entries]
        QMessageBox.information(self, tr("stash_list", "Stash List"), "\n".join(lines))

    def _on_menu(self, pos):
        item = self.status_tree.itemAt(pos)
        r = item.data(0, Qt.ItemDataRole.UserRole + 1) if item else None
        if not isinstance(r, StatusRow):
            return
        e = r.entry
        menu = QMenu(self)
        if e.is_staged:
            act_unstage = menu.addAction(tr("changes_unstage", "Unstage"))
        else:
            act_stage = menu.addAction(tr("changes_stage", "Stage"))
        act_diff_head = menu.addAction(tr("changes_diff_head", "Compare with HEAD"))
        act_revert = menu.addAction(tr("changes_revert", "Revert changes…"))
        menu.addSeparator()
        act_open = menu.addAction(tr("menu_open", "Open in editor"))
        act_copy = menu.addAction(tr("menu_copy_path", "Copy path"))
        act_blame = menu.addAction(tr("menu_blame", "Blame this file"))
        act_patch = menu.addAction(tr("changes_save_unified", "Show patch for this file"))
        chosen = menu.exec(self.status_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        import os
        from ..utils.clipboard import ClipboardHelper
        full = os.path.join(self.repo.root, str(e.path).replace("/", os.sep))
        if chosen is act_copy:
            ClipboardHelper().copy_text(e.path)
        elif chosen is act_open:
            if os.path.isfile(full):
                os.startfile(full)  # noqa: S606
        elif chosen is act_blame:
            from .blamedlg import BlameDlg
            BlameDlg(self.repo, str(e.path), parent=self).exec()
        elif chosen is act_patch:
            try:
                text = self.repo.runner.run_checked("diff", "HEAD", "--", str(e.path))
                from .patchviewdlg import PatchViewDlg
                PatchViewDlg(text, title=str(e.path), parent=self).exec()
            except Exception:
                pass
        elif (e.is_staged and chosen is act_unstage) or ((not e.is_staged) and (chosen is act_stage)):
            if e.is_staged:
                self.index.reset([e.path])
            else:
                self.index.add([e.path])
            self.refresh()
        elif chosen is act_diff_head:
            from ..merge.mergefrm import MergeFrm
            MergeFrm(self.repo, str(e.path), "HEAD", None, parent=self).show()
        elif chosen is act_revert:
            resp = QMessageBox.question(
                self, tr("confirm"),
                format_string(tr("changes_revert_q", "Revert changes to {path}?"), path=e.path),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.Yes:
                self.repo.runner.run("checkout", "--", e.path)
                self.refresh()

    def _on_file_double_clicked(self, item, _col):
        """双击文件行：对齐 CGitStatusListCtrl::StartDiff，打开 TortoiseGitMerge 并排比较。"""
        r = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(r, StatusRow):
            return
        from ..merge.mergefrm import MergeFrm
        MergeFrm(self.repo, r.path, "HEAD", None, parent=self).show()

    def _open_commit(self):
        from .commitdlg import CommitDlg
        dlg = CommitDlg(self.repo, parent=self)
        dlg.exec()
        self.refresh()

    def _open_unified_diff(self):
        from .diffdlg import DiffDlg
        paths = None if self._show_flags()["whole"] else list(self.paths)
        dlg = DiffDlg(self.repo, rev2="HEAD", paths=paths or None, parent=self)
        dlg.exec()

    # ---- 布局锚点（参考 AddAnchor：左列 BOTTOM_LEFT、中部拉伸、右列 BOTTOM_RIGHT）----
    def _setup_anchors(self, base_w: int, base_h: int):
        self._anchor_base = (base_w, base_h)
        self._anchor_rects = {}
        for key, w in self._anchors.items():
            self._anchor_rects[key] = (w.x(), w.y(), w.width(), w.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "_anchor_rects"):
            return
        dw = self.width() - self._anchor_base[0]
        dh = self.height() - self._anchor_base[1]
        stretch = {"branch", "list", "summary"}
        for key, (x, y, w, h) in self._anchor_rects.items():
            widget = self._anchors[key]
            if key in stretch:
                widget.setGeometry(x, y, w + dw, h + (dh if key == "list" else 0))
            else:
                widget.setGeometry(x + dw, y + dh, w, h)


def _checkbox(parent: QWidget, text: str, on_toggle) -> QCheckBox:
    cb = QCheckBox(parent)
    txt = text.replace("&", "")
    cb.setText(txt)
    cb.toggled.connect(on_toggle)
    return cb


def _defbutton(parent: QWidget, text: str) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setDefault(True)
    return btn


def _extension_of(path: str) -> str:
    if "." not in path or path.endswith("/") or path.rfind(".") < path.rfind("/"):
        return ""
    return path.rsplit(".", 1)[1]