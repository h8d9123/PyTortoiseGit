"""logdlg.py —— LogDlg：提交历史/日志查看器（镜像 TortoiseGit IDD_LOGMESSAGE）。

严格按 IDD_LOGMESSAGE（422x265, "Log Messages"）模板排版：
顶行（分支/From-To 日期/Search/跳转）、IDC_LOGLIST 提交列表、
中部 IDC_MSGVIEW（diff）、下部 IDC_LOGMSG（提交信息）、
底行（Whole Project / All Branches / Filter + 按钮行）。
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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
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
from .resize import AnchorLayout
from .widgets import DiffView


class LogDlg(QDialog):
    """日志查看主对话框。"""

    COLS = [tr("log_graph", "图"), tr("log_message", "提交信息"),
            tr("log_author", "作者"), tr("log_date", "日期"),
            tr("log_revision", "修订")]

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
        self.setWindowTitle(spec.caption or tr("log_title", "日志"))
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        # 顶行
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

        # 中部：提交列表 / diff / 提交信息
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(len(self.COLS))
        self.tree.setHeaderLabels(self.COLS)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setIndentation(0)
        self.tree.setColumnWidth(0, 90)   # 图列
        self.tree.setColumnWidth(1, 220)  # 提交信息
        self.tree.itemClicked.connect(self._on_commit_selected)
        self.tree.itemDoubleClicked.connect(self._on_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_menu)
        self.author_pic = QLabel("", self)
        self.author_pic.setObjectName("IDC_PIC_AUTHOR")
        # 受影响的文件列表（镜像 m_ChangedFileListCtrl）：双击打开 diff，右键菜单
        self.file_list = QTreeWidget(self)
        self.file_list.setColumnCount(3)
        self.file_list.setHeaderLabels([tr("log_file_path", "Path"),
                                        tr("log_file_status", "状态"),
                                        tr("log_file_changes", "增/删")])
        self.file_list.setRootIsDecorated(False)
        self.file_list.setIndentation(0)
        self.file_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_list.itemClicked.connect(self._on_file_clicked_preview)
        self.file_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_menu)
        # 中部 MSGVIEW 区：文件列表 + 内嵌 diff 预览（点文件行即在下方显示 diff）
        self.preview = DiffView(self)
        self.preview.setObjectName("IDC_MSGVIEW_PREVIEW")
        self.middle_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.middle_splitter.addWidget(self.file_list)
        self.middle_splitter.addWidget(self.preview)
        self.middle_splitter.setStretchFactor(0, 0)
        self.middle_splitter.setStretchFactor(1, 1)
        self.middle_splitter.setObjectName("IDC_MSGVIEW")
        # 底部 LOGMSG 区：提交信息
        self.msg_box = QPlainTextEdit(self)
        self.msg_box.setReadOnly(True)
        self.msg_box.setPlaceholderText(tr("log_msg_hint", "提交信息…"))
        self.bottom_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.bottom_splitter.addWidget(self.msg_box)
        self.bottom_splitter.setObjectName("IDC_LOGMSG")
        self.log_info = QLineEdit(self)
        self.log_info.setReadOnly(True)

        # 底行
        self.chk_whole = QCheckBox(tr("log_whole", "Show &Whole Project"), self)
        self.chk_whole.toggled.connect(self._on_scope_toggled)
        self.chk_allbranch = QCheckBox(tr("log_allbranch", "&All Branches"), self)
        self.chk_allbranch.toggled.connect(self._on_scope_toggled)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(tr("log_filter", "过滤…"))
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
        # 兼容内部：条数限制
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
        # 分支文字放网页到 Branch 标签右侧
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
                      pathspec=self.pathspec,
                      ordering=self._ordering)
        return []

    def _on_loaded(self, _payload):
        self.tree.clear()
        for commit in self.log:
            item = QTreeWidgetItem([
                commit.row_symbol if commit.row_symbol else "o",
                commit.subject,
                f"{commit.author_name} <{commit.author_email}>",
                commit.date_span(),
                commit.short_hash,
            ])
            item.setToolTip(0, commit.row_text)
            item.setToolTip(1, commit.body or commit.subject)
            item.setData(0, Qt.ItemDataRole.UserRole, commit.hash)
            self.tree.addTopLevelItem(item)
        self._status.setText(
            f" {self.log.count()} {tr('log_commits', '个提交')} · "
            f"{self.repo.current_branch()}")
        if self.log.count():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
            self._on_commit_selected(self.tree.topLevelItem(0), 0)
        self._apply_filter()

    def _on_error(self, message, _tb):
        self._status.setText(message)

    # ---- 交互 ----
    def _on_scope_toggled(self, *_a):
        self.pathspec = "" if self.chk_whole.isChecked() else self.pathspec
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
        """取该提交的受影响文件列表（name-status）。"""
        out = self.repo.runner.run(
            "show", "--no-color", "--format=", "--name-status", "-r",
            rev_hash, "--").stdout or ""
        rows = []
        for line in out.splitlines():
            if not line.strip():
                continue
            if "\t" in line:
                st, _, path = line.partition("\t")
                rows.append((path.strip(), st.strip()))
        return rows

    def _on_files_loaded(self, rows):
        self.file_list.clear()
        for path, st in rows:
            it = QTreeWidgetItem([path, st, ""])
            it.setData(0, Qt.ItemDataRole.UserRole, path)
            self.file_list.addTopLevelItem(it)

    def _current_commit(self):
        tree_item = self.tree.currentItem()
        return self._commit_of(tree_item) if tree_item is not None else None

    def _load_file_patch_bg(self, commit, path: str) -> str:
        """取某提交里指定文件的完整 diff（含 header 供 diff 预览/弹窗）。"""
        base = commit.hash + "^" if not commit.is_root else None
        try:
            if base:
                return self.repo.runner.run_checked(
                    "diff", base, commit.hash, "--", path)
            return self.repo.runner.run_checked(
                "show", "--no-color", "--format=", commit.hash, "--", path)
        except Exception:
            return ""

    def _on_file_clicked_preview(self, item, _col):
        """单击文件行：内嵌显示该文件 diff（对齐 TGit MSGVIEW 内嵌）。"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        commit = self._current_commit()
        if not path or commit is None:
            return
        run_async(self._load_file_patch_bg, args=(commit, path),
                  on_done=self._on_preview_loaded, parent=self)

    def _on_preview_loaded(self, patch: str):
        self.preview.display_patch(patch)

    def _on_file_double_clicked(self, item, _col):
        """双击文件打开 diff 窗口。"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        commit = self._current_commit()
        if not path or commit is None:
            return
        diff_parent = commit.hash + "^" if not commit.is_root else None
        DiffDlg(self.repo, diff_parent or commit.hash, commit.hash,
                paths=[path], parent=self).exec()

    def _on_file_menu(self, pos):
        item = self.file_list.itemAt(pos)
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        commit = self._current_commit()
        if not path or commit is None:
            return
        menu = QMenu(self)
        act_diff = menu.addAction(tr("log_diff", "与此提交比较…"))
        act_copy = menu.addAction(tr("menu_copy_path", "复制路径"))
        menu.addSeparator()
        act_blame = menu.addAction(tr("log_blame", "在该文件上运行 Blame"))
        chosen = menu.exec(self.file_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        from ..utils.clipboard import ClipboardHelper
        if chosen is act_diff:
            diff_parent = commit.hash + "^" if not commit.is_root else None
            DiffDlg(self.repo, diff_parent or commit.hash, commit.hash,
                    paths=[path], parent=self).exec()
        elif chosen is act_copy:
            ClipboardHelper().copy_text(path)
        elif chosen is act_blame:
            from .blamedlg import BlameDlg
            BlameDlg(self.repo, path, rev=commit.hash, parent=self).exec()

    def _on_double_clicked(self, item, _col):
        commit = self._commit_of(item)
        if commit is not None:
            DiffDlg(self.repo,
                    commit.hash + "^" if not commit.is_root else commit.hash,
                    commit.hash, paths=self.pathspec or None,
                    parent=self).exec()

    def _apply_filter(self, *_a):
        text = self.filter_edit.text().strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            it.setHidden(bool(text) and text not in it.text(1).lower()
                         and text not in it.text(2).lower()
                         and text not in it.text(3).lower())

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
        item = self.tree.currentItem()
        commit = self._commit_of(item) if item else None
        menu = QMenu(self)
        act_diff = menu.addAction(tr("log_diff", "与此提交比较…"))
        act_copy = menu.addAction(tr("log_copyhash", "复制完整哈希"))
        act_copy_short = menu.addAction(tr("log_copyshort", "复制短哈希"))
        chosen = menu.exec(self.btn_view.mapToGlobal(
            self.btn_view.rect().bottomLeft()))
        if chosen is None:
            return
        if commit is None:
            return
        if chosen is act_diff:
            DiffDlg(self.repo, commit.hash,
                    paths=self.pathspec or None, parent=self).exec()
        elif chosen is act_copy:
            from ..utils.clipboard import ClipboardHelper
            ClipboardHelper().copy_text(commit.hash)
        elif chosen is act_copy_short:
            from ..utils.clipboard import ClipboardHelper
            ClipboardHelper().copy_text(commit.short_hash)

    def _on_help(self):
        QMessageBox.information(
            self, tr("help"),
            tr("log_help",
               "搜索语法：author:xxx / grep:yyy，回车刷新。\n"
               "双击提交可打开 diff 窗口。"))

    # ---- 右键菜单 ----
    def _on_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        commit = self._commit_of(item)
        if commit is None:
            return
        menu = QMenu(self)
        act_checkout = menu.addAction(tr("log_checkout", "签出此提交…"))
        act_branch = menu.addAction(tr("log_newbranch", "在此创建分支…"))
        act_revert = menu.addAction(tr("log_revert", "还原此提交…"))
        act_pick = menu.addAction(tr("log_cherry_pick", "遴选 (cherry-pick)…"))
        act_diff = menu.addAction(tr("log_diff", "与此提交比较…"))
        menu.addSeparator()
        act_copy = menu.addAction(tr("log_copyhash", "复制完整哈希"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_checkout:
            self._do_simple(["checkout", commit.hash])
        elif chosen is act_revert:
            self._do_simple(["revert", "--no-edit", commit.hash])
        elif chosen is act_pick:
            self._do_simple(["cherry-pick", commit.hash])
        elif chosen is act_branch:
            self._ask_branch(commit.hash)
        elif chosen is act_copy:
            from ..utils.clipboard import ClipboardHelper
            ClipboardHelper().copy_text(commit.hash)
        elif chosen is act_diff:
            DiffDlg(self.repo, commit.hash, parent=self).exec()

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
        dlg.exec()

    def button_open_diff(self):
        item = self.tree.currentItem()
        if item is None:
            return
        commit = self._commit_of(item)
        if commit is not None:
            DiffDlg(self.repo, commit.hash, parent=self).exec()


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