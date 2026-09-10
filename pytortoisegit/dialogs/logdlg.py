"""logdlg.py —— LogDlg：提交历史/日志查看器（镜像 TortoiseGit IDD_LOGMESSAGE）。

严格按 IDD_LOGMESSAGE（422x265, "Log Messages"）模板排版：
顶行（分支/From-To 日期/Search/跳转）、IDC_LOGLIST 提交列表、
中部 IDC_MSGVIEW（提交信息）、下部 IDC_LOGMSG（文件列表）、
底行（Whole Project / All Branches / Filter + 按钮行）。
"""

# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import QFileInfo, Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFileIconProvider,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..git.repo import Repository
from ..git.rev import GitRev, GitRevLoglist
from ..res.strings import tr
from ..asyncfw import run_async
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .diffdlg import DiffDlg
from .loggraph import LogListDelegate, graph_width
from .loglists import (
    FILE_COL_ADD, FILE_COL_DEL, FILE_COL_EXT, FILE_COL_PATH, FILE_COL_SIZE,
    FILE_COL_STATUS, LOG_COL_ACTIONS, LOG_COL_AUTHOR, LOG_COL_DATE, LOG_COL_EMAIL,
    LOG_COL_GRAPH, LOG_COL_HASH, LOG_COL_MESSAGE, ChangedFile, file_column_labels,
    file_default_hidden, log_column_labels, log_default_hidden, parse_show_files,
    status_color, status_text,
)
from .resize import AnchorLayout


class LogDlg(QDialog):
    """日志查看主对话框。"""

    def __init__(self, repo: Repository, pathspec: str | None = None,
                 rev: str | None = None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.pathspec = pathspec
        self.rev = rev
        self.log = GitRevLoglist(repo)
        self.current_item: Optional[QTreeWidgetItem] = None
        self._ordering: str = "default"
        self._build_ui()
        self._populate()

    # ---- UI（IDD_LOGMESSAGE 模板）----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_LOGMESSAGE")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        self.setWindowTitle(spec.caption or tr("log_title", "Log"))
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.branch_label = QLabel(tr("log_branch_label", "Branch:"), self)
        self.branch_value = QLabel(self, text="")
        self.branch_value.setText(self.repo.current_branch())
        self.branch_value.setObjectName("IDC_STATIC_REF")
        self.from_label = QLabel(tr("log_from", "From:"), self)
        self.date_from = QDateEdit(self)
        self.to_label = QLabel(tr("log_to", "To:"), self)
        self.date_to = QDateEdit(self)
        for de in (self.date_from, self.date_to):
            de.setCalendarPopup(True)
            de.setDisplayFormat("yyyy-MM-dd")
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("author:xxx grep:yyy")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self._populate)
        self.jump_combo = QComboBox(self)
        self.jump_combo.setEditable(False)
        self.jump_up_btn = QPushButton("\u25b2", self)
        self.jump_down_btn = QPushButton("\u25bc", self)
        self.jump_up_btn.setFixedHeight(23)
        self.jump_down_btn.setFixedHeight(23)

        labels = log_column_labels()
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(len(labels))
        self.tree.setHeaderLabels(labels)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setIndentation(0)
        self.tree.setColumnWidth(LOG_COL_GRAPH, 90)
        self.tree.setColumnWidth(LOG_COL_ACTIONS, 2 + 16 * 5 + 6)
        self.tree.setColumnWidth(LOG_COL_MESSAGE, 280)
        self.tree.setItemDelegate(LogListDelegate(self._commit_from_index, self.tree))
        for col in log_default_hidden():
            self.tree.setColumnHidden(col, True)
        self.tree.itemClicked.connect(self._on_commit_selected)
        self.tree.itemDoubleClicked.connect(self._on_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_menu)
        self.tree.header().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.header().customContextMenuRequested.connect(self._on_log_header_menu)

        self.author_pic = QLabel("", self)
        self.author_pic.setObjectName("IDC_PIC_AUTHOR")

        self.file_list = QTreeWidget(self)
        self.file_list.setColumnCount(len(file_column_labels()))
        self.file_list.setHeaderLabels(file_column_labels())
        self.file_list.setRootIsDecorated(True)
        self.file_list.setIndentation(12)
        self.file_list.setUniformRowHeights(True)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.header().setSectionResizeMode(FILE_COL_PATH, QHeaderView.ResizeMode.Stretch)
        self.file_list.setColumnWidth(FILE_COL_EXT, 64)
        self.file_list.setColumnWidth(FILE_COL_STATUS, 72)
        self.file_list.setColumnWidth(FILE_COL_ADD, 48)
        self.file_list.setColumnWidth(FILE_COL_DEL, 48)
        for col in (FILE_COL_ADD, FILE_COL_DEL, FILE_COL_SIZE):
            self.file_list.headerItem().setTextAlignment(col, int(Qt.AlignmentFlag.AlignRight))
        for col in file_default_hidden():
            self.file_list.setColumnHidden(col, True)
        self._file_icons = QFileIconProvider()
        self.file_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_menu)
        self.file_list.header().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.header().customContextMenuRequested.connect(self._on_file_header_menu)

        # 原版：IDC_MSGVIEW = 提交信息，IDC_LOGMSG = 受影响文件列表
        self.msg_box = QPlainTextEdit(self)
        self.msg_box.setReadOnly(True)
        self.msg_box.setPlaceholderText(tr("log_msg_hint", "Commit message…"))
        self.middle_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.middle_splitter.addWidget(self.msg_box)
        self.middle_splitter.setObjectName("IDC_MSGVIEW")
        self.bottom_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.bottom_splitter.addWidget(self.file_list)
        self.bottom_splitter.setObjectName("IDC_LOGMSG")
        self.log_info = QLineEdit(self)
        self.log_info.setReadOnly(True)

        self.chk_whole = QCheckBox(tr("log_whole", "Show &Whole Project"), self)
        self.chk_whole.toggled.connect(self._on_scope_toggled)
        self.chk_allbranch = QCheckBox(tr("log_allbranch", "&All Branches"), self)
        self.chk_allbranch.toggled.connect(self._on_scope_toggled)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(tr("log_filter", "Filter…"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)
        self.btn_refresh = QPushButton(tr("refresh"), self)
        self.btn_refresh.clicked.connect(self._populate)
        self.btn_stats = QPushButton(tr("log_stats", "S&tatistics"), self)
        self.btn_stats.clicked.connect(self._on_stats)
        self.btn_walk = QPushButton(tr("log_walk", "Walk Be&havior"), self)
        self.btn_walk.clicked.connect(self._on_walk)
        self.btn_view = QPushButton(tr("log_view", "&View"), self)
        self.btn_view.clicked.connect(self._on_view_menu)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.reject)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.limit_spin = QSpinBox(self)
        self.limit_spin.setRange(10, 5000)
        self.limit_spin.setValue(500)
        self.limit_spin.hide()
        self._status = self.log_info
        self._details = self.log_info

        mapping = {
            "IDC_STATIC_REF": self.branch_label,
            "IDC_FROMLABEL": self.from_label,
            "IDC_DATEFROM": self.date_from,
            "IDC_TOLABEL": self.to_label,
            "IDC_DATETO": self.date_to,
            "IDC_SEARCHEDIT": self.search_edit,
            "IDC_LOG_JUMPTYPE": self.jump_combo,
            "IDC_LOG_JUMPUP": self.jump_up_btn,
            "IDC_LOG_JUMPDOWN": self.jump_down_btn,
            "IDC_LOGLIST": self.tree,
            "IDC_MSGVIEW": self.middle_splitter,
            "IDC_PIC_AUTHOR": self.author_pic,
            "IDC_LOGMSG": self.bottom_splitter,
            "IDC_LOGINFO": self.log_info,
            "IDC_WHOLE_PROJECT": self.chk_whole,
            "IDC_LOG_ALLBRANCH": self.chk_allbranch,
            "IDC_FILTER": self.filter_edit,
            "IDHELP": self.btn_help,
            "IDC_REFRESH": self.btn_refresh,
            "IDC_STATBUTTON": self.btn_stats,
            "IDC_WALKBEHAVIOUR": self.btn_walk,
            "IDC_VIEW": self.btn_view,
            "IDOK": self.btn_ok,
            "IDCANCEL": self.btn_cancel,
        }
        for ctrl in spec.controls:
            wgt = mapping.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            rc_mod.place_widget(self, fu, ctrl, wgt)
            self._ctl[ctrl.ctrl_id] = wgt
        self.branch_value.setParent(self)
        self.branch_value.setObjectName("IDC_BRANCHVAL")
        geom = self.branch_label.geometry()
        self.branch_value.setGeometry(geom.x() +
                                      fu.px(0, 0, 40, 8).width(), geom.y(),
                                      geom.width() - fu.px(0, 0, 40, 8).width(),
                                      geom.height())

        for ctrl in spec.controls:
            wgt = self._ctl.get(ctrl.ctrl_id)
            if wgt is None:
                continue
            a = _LOG_ANCHORS.get(ctrl.ctrl_id)
            if a:
                self._anchors.add(wgt, a[0], a[1] if len(a) > 1 else None)

        self._populate_jump()

    def _populate_jump(self):
        refs = []
        for ref in (self.repo.runner.run("for-each-ref",
                                         "--format=%(refname:short)").stdout or "").splitlines():
            if ref.strip():
                refs.append(ref.strip())
        self.jump_combo.addItems(refs[:60])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    def _header_menu(self, tree: QTreeWidget, pos):
        menu = QMenu(self)
        header = tree.header()
        for i in range(tree.columnCount()):
            act = menu.addAction(tree.headerItem().text(i))
            act.setCheckable(True)
            act.setChecked(not tree.isColumnHidden(i))
            act.setData(i)
        chosen = menu.exec(header.mapToGlobal(pos))
        if chosen is None:
            return
        col = int(chosen.data())
        tree.setColumnHidden(col, not tree.isColumnHidden(col))

    def _on_log_header_menu(self, pos):
        self._header_menu(self.tree, pos)

    def _on_file_header_menu(self, pos):
        self._header_menu(self.file_list, pos)

    # ---- 数据 ----
    def _populate(self):
        self.tree.clear()
        self.file_list.clear()
        self.msg_box.clear()
        self._status.setText(tr("loading"))
        run_async(self._load_bg, on_done=self._on_loaded,
                  on_error=self._on_error, parent=self)

    def _load_bg(self) -> list:
        search = self.search_edit.text() or None
        self.log.load(limit=self.limit_spin.value(),
                      search=search,
                      pathspec="" if self.chk_whole.isChecked() else self.pathspec,
                      ordering=self._ordering,
                      all_branches=self.chk_allbranch.isChecked())
        return []

    def _on_loaded(self, _payload):
        self.tree.clear()
        for commit in self.log:
            refs = f" [{commit.refs_str}]" if commit.refs_str else ""
            item = QTreeWidgetItem([
                "",
                "",
                commit.subject + refs,
                commit.author_name,
                commit.date_span(),
                commit.hash,
                commit.author_email,
                commit.committer_name,
                commit.committer_email,
                commit.date_span(),
            ])
            item.setToolTip(LOG_COL_ACTIONS, self._action_tip(commit.actions))
            item.setToolTip(LOG_COL_MESSAGE, commit.body or commit.subject)
            item.setData(0, Qt.ItemDataRole.UserRole, commit.hash)
            self.tree.addTopLevelItem(item)
        max_lanes = max((len(c.lanes) for c in self.log), default=1)
        row_h = self.tree.sizeHintForRow(0) or 20
        self.tree.setColumnWidth(LOG_COL_GRAPH, graph_width(max_lanes, row_h))
        self._status.setText(
            f" {self.log.count()} {tr('log_commits', 'commits')} · "
            f"{self.repo.current_branch()}")
        if self.log.count():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
            self._on_commit_selected(self.tree.topLevelItem(0), 0)
        self._apply_filter()

    def _on_error(self, message, _tb):
        self._status.setText(message)

    def _on_scope_toggled(self, *_a):
        self._populate()

    def _on_commit_selected(self, item, _col):
        if item is self.current_item:
            return
        self.current_item = item
        commit = self._commit_of(item)
        if commit is None:
            return
        self._show_commit(commit)

    def _commit_of(self, item) -> Optional[GitRev]:
        h = item.data(0, Qt.ItemDataRole.UserRole)
        return self.log.get(h) if isinstance(h, str) else None

    def _commit_from_index(self, index) -> Optional[GitRev]:
        item = self.tree.itemFromIndex(index)
        return self._commit_of(item) if item is not None else None

    def _action_tip(self, actions: str) -> str:
        names = {
            "M": tr("log_st_modified", "Modified"),
            "A": tr("log_st_added", "Added"),
            "D": tr("log_st_deleted", "Deleted"),
            "R": tr("log_st_renamed", "Renamed"),
            "C": tr("log_st_copied", "Copied"),
            "U": tr("log_st_unmerged", "Unmerged"),
        }
        lines = [names[c] for c in "MADRC" if c in (actions or "")]
        if not lines:
            return ""
        return tr("log_actions", "Action") + ":\n" + "\n".join(lines)

    def _selected_commits(self) -> List[GitRev]:
        out = []
        for item in self.tree.selectedItems():
            c = self._commit_of(item)
            if c is not None:
                out.append(c)
        return out

    def _show_commit(self, commit: GitRev):
        author = f"{commit.author_name} [{commit.author_email}]" if commit.author_email else commit.author_name
        self.msg_box.setPlainText(
            f"{commit.hash}\n{author}  {commit.date_span()}\n"
            f"{commit.subject}\n\n{commit.body}".strip() + "\n")
        self.log_info.setText(
            f"{commit.short_hash} · {author} · {commit.date_span()}")
        run_async(self._load_files_bg, args=(commit.hash,),
                  on_done=self._on_files_loaded, parent=self)

    def _load_files_bg(self, rev_hash: str) -> list:
        commit = self.log.get(rev_hash)
        if commit is not None and commit.is_merge and commit.parents:
            groups = []
            for i, parent in enumerate(commit.parents):
                out = self.repo.runner.run(
                    "diff", "--no-color", "--name-status", "--numstat",
                    parent, rev_hash, "--").stdout or ""
                files = parse_show_files(out)
                title = tr("log_diff_parent", "Diff with parent {}: {}").format(
                    i + 1, parent[:8])
                groups.append((title, files))
            return groups
        out = self.repo.runner.run(
            "show", "--no-color", "--format=", "--name-status", "--numstat",
            "-r", rev_hash, "--").stdout or ""
        # 非合并：原版不启用分组（PrepareGroups 仅 max>0 时分组）
        return [(None, parse_show_files(out))]

    def _file_icon(self, path: str):
        return self._file_icons.icon(QFileInfo(path))

    def _add_file_item(self, parent: Optional[QTreeWidgetItem], row: ChangedFile):
        it = QTreeWidgetItem([
            row.display_name(),
            row.filename,
            row.ext,
            status_text(row.status),
            row.added,
            row.deleted,
            "",
            "",
        ])
        it.setData(0, Qt.ItemDataRole.UserRole, row.path)
        it.setIcon(0, self._file_icon(row.path))
        align_r = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        it.setTextAlignment(FILE_COL_ADD, align_r)
        it.setTextAlignment(FILE_COL_DEL, align_r)
        it.setTextAlignment(FILE_COL_SIZE, align_r)
        rgb = status_color(row.status)
        if rgb:
            brush = QBrush(QColor(*rgb))
            for c in range(it.columnCount()):
                it.setForeground(c, brush)
        if parent is None:
            self.file_list.addTopLevelItem(it)
        else:
            parent.addChild(it)

    def _on_files_loaded(self, groups):
        self.file_list.clear()
        for title, rows in groups:
            parent = None
            if title:
                parent = QTreeWidgetItem([title])
                parent.setFirstColumnSpanned(True)
                font = parent.font(0)
                font.setBold(True)
                parent.setFont(0, font)
                self.file_list.addTopLevelItem(parent)
            for row in rows:
                self._add_file_item(parent, row)
            if parent is not None:
                parent.setExpanded(True)

    def _current_commit(self):
        tree_item = self.tree.currentItem()
        return self._commit_of(tree_item) if tree_item is not None else None

    def _file_path(self, item) -> str:
        return item.data(0, Qt.ItemDataRole.UserRole) or ""

    def _open_file_diff(self, path: str, commit: GitRev, with_wc: bool = False):
        from ..merge.mergefrm import MergeFrm
        if with_wc:
            dlg = MergeFrm(self.repo, path, commit.hash, None, parent=self)
        else:
            base = commit.hash + "^" if not commit.is_root else None
            dlg = MergeFrm(self.repo, path, base or None, commit.hash, parent=self)
        dlg.show()

    def _on_file_double_clicked(self, item, _col):
        path = self._file_path(item)
        commit = self._current_commit()
        if path and commit is not None:
            self._open_file_diff(path, commit)

    def _copy_text(self, text: str):
        from ..utils.clipboard import ClipboardHelper
        ClipboardHelper().copy_text(text)

    def _on_file_menu(self, pos):
        item = self.file_list.itemAt(pos)
        if item is None:
            return
        path = self._file_path(item)
        commit = self._current_commit()
        if not path or commit is None:
            return
        menu = QMenu(self)
        act_base = menu.addAction(tr("log_compare_base", "Compare with base version"))
        act_gnu = menu.addAction(tr("log_gnudiff", "Show unified diff"))
        act_wc = menu.addAction(tr("log_compare_wc", "Compare with working copy"))
        menu.addSeparator()
        act_log = menu.addAction(tr("log_show_log", "Show log"))
        act_blame = menu.addAction(tr("log_blame", "Blame"))
        act_revert = menu.addAction(tr("log_revert_to_rev", "Revert to this revision"))
        menu.addSeparator()
        act_save = menu.addAction(tr("log_save_as", "Save as…"))
        act_view = menu.addAction(tr("log_view_rev", "View revision"))
        act_open = menu.addAction(tr("log_open", "Open"))
        act_openwith = menu.addAction(tr("log_open_with", "Open with…"))
        act_explore = menu.addAction(tr("log_explore", "Open in Explorer"))
        clip = menu.addMenu(tr("log_copy_clip", "Copy to clipboard"))
        act_full = clip.addAction(tr("log_copy_full", "Full path"))
        act_rel = clip.addAction(tr("log_copy_rel", "Relative path"))
        act_name = clip.addAction(tr("log_copy_name", "File name"))
        chosen = menu.exec(self.file_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        full = self.repo.full_path(path)
        if chosen is act_base:
            self._open_file_diff(path, commit)
        elif chosen is act_gnu:
            base = commit.hash + "^" if not commit.is_root else None
            DiffDlg(self.repo, base or commit.hash, commit.hash,
                    paths=[path], parent=self).exec()
        elif chosen is act_wc:
            self._open_file_diff(path, commit, with_wc=True)
        elif chosen is act_log:
            LogDlg(self.repo, pathspec=path, rev=commit.hash, parent=self).exec()
        elif chosen is act_blame:
            from .blamedlg import BlameDlg
            BlameDlg(self.repo, path, rev=commit.hash, parent=self).exec()
        elif chosen is act_revert:
            self._do_simple(["checkout", commit.hash, "--", path])
        elif chosen is act_save:
            dest, _ = QFileDialog.getSaveFileName(self, tr("log_save_as", "Save as…"),
                                                  os.path.basename(path))
            if dest:
                data = self.repo.runner.run("show", f"{commit.hash}:{path}").stdout or ""
                with open(dest, "w", encoding="utf-8", newline="") as fh:
                    fh.write(data)
        elif chosen is act_view:
            DiffDlg(self.repo, commit.hash + "^" if not commit.is_root else commit.hash,
                    commit.hash, paths=[path], parent=self).exec()
        elif chosen is act_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(full))
        elif chosen is act_openwith:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(full)))
        elif chosen is act_explore:
            folder = full if os.path.isdir(full) else os.path.dirname(full)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        elif chosen is act_full:
            self._copy_text(full)
        elif chosen is act_rel:
            self._copy_text(path)
        elif chosen is act_name:
            self._copy_text(os.path.basename(path))

    def _on_double_clicked(self, item, _col):
        commit = self._commit_of(item)
        if commit is not None:
            self._compare_previous(commit)

    def _compare_wc(self, commit: GitRev):
        DiffDlg(self.repo, commit.hash, paths=self.pathspec or None, parent=self).exec()

    def _compare_previous(self, commit: GitRev):
        DiffDlg(self.repo,
                commit.hash + "^" if not commit.is_root else commit.hash,
                commit.hash, paths=self.pathspec or None, parent=self).exec()

    def _compare_two(self, a: GitRev, b: GitRev):
        DiffDlg(self.repo, a.hash, b.hash, paths=self.pathspec or None, parent=self).exec()

    def _apply_filter(self, *_a):
        text = self.filter_edit.text().strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            hay = " ".join(it.text(c) for c in (
                LOG_COL_MESSAGE, LOG_COL_AUTHOR, LOG_COL_DATE, LOG_COL_HASH,
                LOG_COL_EMAIL)).lower()
            it.setHidden(bool(text) and text not in hay)

    def _on_stats(self):
        from .statgraphdlg import StatGraphDlg
        StatGraphDlg(self.repo, parent=self).exec()

    def _on_walk(self):
        from .logorderingdlg import LogOrderingDlg
        dlg = LogOrderingDlg(parent=self)
        if dlg.exec():
            self._ordering = dlg.selected
            self._populate()

    def _on_view_menu(self):
        menu = QMenu(self)
        self._fill_log_menu(menu, self._selected_commits())
        menu.exec(self.btn_view.mapToGlobal(self.btn_view.rect().bottomLeft()))

    def _on_help(self):
        QMessageBox.information(
            self, tr("help"),
            tr("log_help", "Search syntax: author:xxx / grep:yyy, Enter to refresh.\n"
               "Double-click a commit to compare with the previous version."))

    def _on_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        if item not in self.tree.selectedItems():
            self.tree.setCurrentItem(item)
        menu = QMenu(self)
        self._fill_log_menu(menu, self._selected_commits())
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _fill_log_menu(self, menu: QMenu, commits: List[GitRev]):
        if not commits:
            return
        one = len(commits) == 1
        first = commits[0]
        if one:
            act_wc = menu.addAction(tr("log_compare_wc", "Compare with working copy"))
            act_wc.triggered.connect(lambda: self._compare_wc(first))
            act_prev = menu.addAction(tr("log_compare_prev", "Compare with previous version"))
            act_prev.triggered.connect(lambda: self._compare_previous(first))
            act_gnu = menu.addAction(tr("log_gnudiff", "Show unified diff"))
            act_gnu.triggered.connect(lambda: self._compare_previous(first))
            menu.addSeparator()
            act_browse = menu.addAction(tr("log_browse", "Browse repository"))
            act_browse.triggered.connect(lambda: self._browse(first))
            act_merge = menu.addAction(
                tr("log_merge_to", "Merge to \"{}\"").format(self.repo.current_branch()))
            act_merge.triggered.connect(lambda: self._merge(first))
            act_reset = menu.addAction(tr("log_reset", "Reset \"{}\" to this…").format(
                self.repo.current_branch()))
            act_reset.triggered.connect(lambda: self._reset(first))
            act_switch = menu.addAction(tr("log_switch", "Switch/Checkout…"))
            act_switch.triggered.connect(lambda: self._switch(first))
            act_branch = menu.addAction(tr("log_newbranch", "Create branch here…"))
            act_branch.triggered.connect(lambda: self._ask_branch(first.hash))
            act_tag = menu.addAction(tr("log_newtag", "Create tag here…"))
            act_tag.triggered.connect(lambda: self._ask_tag(first.hash))
            act_export = menu.addAction(tr("log_export", "Export…"))
            act_export.triggered.connect(lambda: self._export(first))
            act_revert = menu.addAction(tr("log_revert", "Revert changes introduced by this commit"))
            act_revert.triggered.connect(
                lambda: self._do_simple(["revert", "--no-edit", first.hash]))
            act_pick = menu.addAction(tr("log_cherry_pick", "Cherry Pick…"))
            act_pick.triggered.connect(
                lambda: self._do_simple(["cherry-pick", first.hash]))
            act_patch = menu.addAction(tr("log_create_patch", "Create patch…"))
            act_patch.triggered.connect(lambda: self._format_patch(first))
        elif len(commits) == 2:
            act_two = menu.addAction(tr("log_compare_two", "Compare two revisions"))
            act_two.triggered.connect(lambda: self._compare_two(commits[0], commits[1]))
            act_chg = menu.addAction(tr("log_compare_changes", "Compare changes of two commits"))
            act_chg.triggered.connect(lambda: self._compare_two(commits[0], commits[1]))
            menu.addSeparator()
            act_pick = menu.addAction(tr("log_cherry_pick", "Cherry Pick…"))
            act_pick.triggered.connect(lambda: self._do_simple(
                ["cherry-pick", commits[-1].hash, "^" + commits[0].hash]))
        else:
            act_pick = menu.addAction(tr("log_cherry_pick", "Cherry Pick…"))
            act_pick.triggered.connect(lambda: self._do_simple(
                ["cherry-pick"] + [c.hash for c in reversed(commits)]))
        menu.addSeparator()
        clip = menu.addMenu(tr("log_copy_clip", "Copy to clipboard"))
        clip.addAction(tr("log_copyhash", "Full hash"),
                       lambda: self._copy_text("\n".join(c.hash for c in commits)))
        clip.addAction(tr("log_copyshort", "Short hash"),
                       lambda: self._copy_text("\n".join(c.short_hash for c in commits)))
        clip.addAction(tr("log_copy_authors", "Authors"),
                       lambda: self._copy_text("\n".join(c.author_name for c in commits)))
        clip.addAction(tr("log_copy_emails", "E-mails"),
                       lambda: self._copy_text("\n".join(c.author_email for c in commits)))
        clip.addAction(tr("log_copy_subjects", "Subjects"),
                       lambda: self._copy_text("\n".join(c.subject for c in commits)))
        clip.addAction(tr("log_copy_messages", "Full messages"),
                       lambda: self._copy_text("\n\n".join(
                           (c.subject + "\n" + c.body).strip() for c in commits)))
        if one:
            clip.addAction(tr("log_copy_refs", "Branches/tags"),
                           lambda: self._copy_text(first.refs_str))
            menu.addAction(tr("log_show_branches", "Show refs containing this commit"),
                           lambda: self._show_refs(first))
        menu.addAction(tr("log_find", "Find…"), self.filter_edit.setFocus)

    def _browse(self, commit: GitRev):
        from .repobrowserdlg import RepositoryBrowserDlg
        RepositoryBrowserDlg(self.repo, rev=commit.hash, parent=self).exec()

    def _merge(self, commit: GitRev):
        from .mergedlg import MergeDlg
        MergeDlg(self.repo, branch=commit.hash, parent=self).exec()
        self._populate()

    def _reset(self, commit: GitRev):
        from .resetdlg import ResetDlg
        ResetDlg(self.repo, parent=self, commit=commit.hash).exec()
        self._populate()

    def _switch(self, commit: GitRev):
        from .gitswitchdlg import GitSwitchDlg
        GitSwitchDlg(self.repo, parent=self, commit=commit.hash).exec()
        self._populate()

    def _export(self, commit: GitRev):
        from .exportdlg import ExportDlg
        ExportDlg(self.repo, parent=self, commit=commit.hash).exec()

    def _format_patch(self, commit: GitRev):
        from .formatpatchdlg import FormatPatchDlg
        FormatPatchDlg(self.repo, parent=self).exec()
        _ = commit

    def _show_refs(self, commit: GitRev):
        from .commitisonrefsdlg import CommitIsOnRefsDlg
        CommitIsOnRefsDlg(self.repo, commit=commit.hash, parent=self).exec()

    def _do_simple(self, args: list):
        from .progress import ProgressDialog
        dlg = ProgressDialog(title=tr("progress"), parent=self)
        dlg.set_label("git " + " ".join(args))

        def _bg():
            result = self.repo.runner.run(*args)
            if result.stdout:
                dlg.log(result.stdout)
            if result.stderr:
                dlg.log(result.stderr)
            return result.returncode == 0

        def _finish(ok):
            if ok:
                self._populate()
        dlg.on_finish(_finish)
        dlg.run(_bg)
        dlg.exec()

    def _ask_branch(self, commit_hash: str):
        from .createbranchdlg import CreateBranchDlg
        dlg = CreateBranchDlg(self.repo, start=commit_hash, parent=self)
        if dlg.exec():
            self._populate()

    def _ask_tag(self, commit_hash: str):
        from .createbranchdlg import CreateTagDlg
        dlg = CreateTagDlg(self.repo, start=commit_hash, parent=self)
        if dlg.exec():
            self._populate()

    def button_open_diff(self):
        item = self.tree.currentItem()
        if item is None:
            return
        commit = self._commit_of(item)
        if commit is not None:
            self._compare_wc(commit)


_LOG_ANCHORS = {
    "IDC_STATIC_REF": ("TOP_LEFT",),
    "IDC_FROMLABEL": ("TOP_LEFT",),
    "IDC_DATEFROM": ("TOP_LEFT",),
    "IDC_TOLABEL": ("TOP_LEFT",),
    "IDC_DATETO": ("TOP_LEFT",),
    "IDC_SEARCHEDIT": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_LOG_JUMPTYPE": ("TOP_RIGHT",),
    "IDC_LOG_JUMPUP": ("TOP_RIGHT",),
    "IDC_LOG_JUMPDOWN": ("TOP_RIGHT",),
    "IDC_LOGLIST": ("TOP_LEFT", "MIDDLE_RIGHT"),
    "IDC_MSGVIEW": ("MIDDLE_LEFT", "MIDDLE_RIGHT"),
    "IDC_PIC_AUTHOR": ("MIDDLE_RIGHT",),
    "IDC_LOGMSG": ("MIDDLE_LEFT", "BOTTOM_RIGHT"),
    "IDC_LOGINFO": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_WALKBEHAVIOUR": ("BOTTOM_LEFT",),
    "IDC_VIEW": ("BOTTOM_LEFT",),
    "IDC_LOG_ALLBRANCH": ("BOTTOM_LEFT",),
    "IDC_FILTER": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDC_WHOLE_PROJECT": ("BOTTOM_LEFT",),
    "IDC_REFRESH": ("BOTTOM_LEFT",),
    "IDC_STATBUTTON": ("BOTTOM_LEFT",),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
}
