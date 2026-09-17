"""browserefs.py —— BrowseRefsDlg：浏览/选择引用（IDD_BROWSE_REFS 模板）。

对齐 TortoiseGit 的 BrowseRefsDlg：

* 顶部 Filter（按引用名/提交信息/作者/SHA 过滤）+ 分支过滤下拉
  （All / Only merged / Only unmerged）；
* 左侧引用树（Branches / Remotes / Tags，可显示嵌套引用）；
* 右侧引用列表：Branch Name / Last Author Date / Last Commit / Last Author；
* 底部 Show nested refs、状态标签、Current Branch / OK / Cancel / Help。

选择模式（``select=True`` 或 :meth:`pick`）下，OK 返回所选引用的完整名，
供合并/切换/过滤等对话框回填。
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

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.rev import GitRevLoglist, RefInfo
from ..res.strings import format_string, tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout

_GROUP = (
    ("branch", "browse_branches", "Branches", "refs/heads/"),
    ("remote", "browse_remotes", "Remote branches", "refs/remotes/"),
    ("tag", "browse_tags", "Tags", "refs/tags/"),
)


class BrowseRefsDlg(QDialog):
    def __init__(self, repo: Repository, parent=None, select: bool = False,
                 initial_ref: str = "", pick_kind: str = "all"):
        super().__init__(parent)
        self.repo = repo
        self.select_mode = bool(select)
        self.selected_ref = ""
        self._pick_kind = pick_kind or "all"
        self._initial_ref = initial_ref or ""
        self.current_branch = repo.current_branch()
        self._refs: List[RefInfo] = []
        self._shown: List[RefInfo] = []
        self._merged_cache = None
        self._build_ui()
        self._load()

    # ---- 便捷入口 ----
    @staticmethod
    def pick(repo: Repository, parent=None, initial_ref: str = "",
             kind: str = "all") -> str:
        """打开选择模式，返回所选引用的完整名（取消返回空串）。"""
        dlg = BrowseRefsDlg(repo, parent=parent, select=True,
                            initial_ref=initial_ref, pick_kind=kind)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.selected_ref
        return ""

    # ---- UI（IDD_BROWSE_REFS）----
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_BROWSE_REFS")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(
            f"{self.repo.name} — {tr('browse_refs', 'Browse references')}")
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.filter_label = QLabel(tr("browse_filter", "Filter:"), self)
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText(
            tr("browse_filter_cue", "Filter by Refname, Subject, Authors, SHAs"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(lambda *_: self._apply_filter())

        self.branch_filter = QComboBox(self)
        self.branch_filter.addItems([
            tr("browse_bf_all", "All"),
            tr("browse_bf_merged", "Only merged (to HEAD)"),
            tr("browse_bf_unmerged", "Only unmerged (to HEAD)"),
        ])
        self.branch_filter.currentIndexChanged.connect(
            lambda *_: self._apply_filter())

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.currentItemChanged.connect(self._on_tree_changed)

        self.list = QTreeWidget(self)
        self.list.setColumnCount(4)
        self.list.setHeaderLabels([
            tr("browse_col_name", "Branch Name"),
            tr("browse_col_date", "Last Author Date"),
            tr("browse_col_commit", "Last Commit"),
            tr("browse_col_author", "Last Author"),
        ])
        self.list.setRootIsDecorated(False)
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setColumnWidth(0, 150)
        self.list.setColumnWidth(1, 110)
        self.list.setColumnWidth(2, 220)
        self.list.setColumnWidth(3, 100)
        self.list.itemSelectionChanged.connect(self._update_info)
        self.list.itemDoubleClicked.connect(self._on_double_clicked)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)

        self.chk_nested = QCheckBox(
            tr("browse_include_nested", "Show &nested refs"), self)
        self.chk_nested.setChecked(True)
        self.chk_nested.toggled.connect(lambda *_: self._build_tree())

        self.info_label = QLabel("", self)
        self.btn_current = QPushButton(
            tr("browse_btn_current", "Current Branch"), self)
        self.btn_current.clicked.connect(self._on_current_branch)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)

        mapping = {
            "IDC_BROWSEREFS_STATIC_FILTER": self.filter_label,
            "IDC_BROWSEREFS_EDIT_FILTER": self.filter_edit,
            "IDC_BROWSE_REFS_BRANCHFILTER": self.branch_filter,
            "IDC_TREE_REF": self.tree,
            "IDC_LIST_REF_LEAFS": self.list,
            "IDC_INCLUDENESTEDREFS": self.chk_nested,
            "IDC_INFOLABEL": self.info_label,
            "IDC_CURRENTBRANCH": self.btn_current,
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

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())

    # ---- 数据 ----
    def _load(self):
        run_async(self._load_bg, on_done=self._on_loaded, parent=self)

    def _load_bg(self) -> List[RefInfo]:
        log = GitRevLoglist(self.repo)
        log.load_refs()
        refs = list(log.refs.values())
        if self._pick_kind != "all":
            kinds = {"head": ("branch",), "tag": ("tag",),
                     "remote": ("remote",),
                     "notag": ("branch", "remote")}.get(self._pick_kind)
            if kinds:
                refs = [r for r in refs if r.ref_type in kinds]
        return refs

    def _on_loaded(self, refs: List[RefInfo]):
        self._refs = list(refs)
        self._build_tree()
        self._select_initial()

    def _select_initial(self):
        target = self._initial_ref or self.current_branch
        for i in range(self.list.topLevelItemCount()):
            it = self.list.topLevelItem(i)
            if it.text(0) == target or it.data(0, Qt.ItemDataRole.UserRole + 1) == target:
                self.list.setCurrentItem(it)
                break

    def _build_tree(self):
        self.tree.clear()
        nested = self.chk_nested.isChecked()
        roots = {}
        for rtype, key, default, prefix in _GROUP:
            group = [r for r in self._refs if r.ref_type == rtype]
            if not group:
                continue
            top = QTreeWidgetItem([tr(key, default)])
            top.setData(0, Qt.ItemDataRole.UserRole, None)
            top.setData(0, Qt.ItemDataRole.UserRole + 1, rtype)
            self.tree.addTopLevelItem(top)
            roots[rtype] = top
            if nested:
                self._add_nested(top, group, prefix)
            else:
                for r in sorted(group, key=lambda x: x.shortname):
                    self._add_leaf(top, r)
            top.setExpanded(True)
        # 默认列出全部引用
        self._fill_list(self._refs)

    def _add_nested(self, parent, group, prefix):
        node_by_path = {}
        for r in sorted(group, key=lambda x: x.shortname):
            rel = r.shortname
            segs = [s for s in rel.split("/") if s]
            node = parent
            path = ""
            for i, seg in enumerate(segs):
                path = f"{path}/{seg}" if path else seg
                if i == len(segs) - 1:
                    self._add_leaf(node, r)
                else:
                    child = node_by_path.get((id(parent), path))
                    if child is None:
                        child = QTreeWidgetItem([seg])
                        child.setData(0, Qt.ItemDataRole.UserRole, None)
                        child.setData(0, Qt.ItemDataRole.UserRole + 1, None)
                        node.addChild(child)
                        node_by_path[(id(parent), path)] = child
                    node = child

    def _add_leaf(self, parent, ref: RefInfo):
        item = QTreeWidgetItem([ref.shortname])
        item.setData(0, Qt.ItemDataRole.UserRole, ref.fullname)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, ref.ref_type)
        parent.addChild(item)

    def _on_tree_changed(self, item, _prev):
        if item is None:
            return
        fullname = item.data(0, Qt.ItemDataRole.UserRole)
        if fullname:
            self._fill_list([r for r in self._refs if r.fullname == fullname])
        else:
            rtype = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if rtype:
                self._fill_list([r for r in self._refs if r.ref_type == rtype])
            else:
                self._fill_list(self._collect_subtree(item))

    def _collect_subtree(self, item) -> List[RefInfo]:
        out = []
        for i in range(item.childCount()):
            child = item.child(i)
            fullname = child.data(0, Qt.ItemDataRole.UserRole)
            if fullname:
                out += [r for r in self._refs if r.fullname == fullname]
            else:
                out += self._collect_subtree(child)
        return out

    def _merged_sets(self):
        if self._merged_cache is None:
            def _run(*args):
                out = self.repo.runner.run(*args).stdout or ""
                return {x.strip() for x in out.splitlines() if x.strip()}
            self._merged_cache = (
                _run("branch", "-a", "--merged", "HEAD",
                     "--format=%(refname)"),
                _run("branch", "-a", "--no-merged", "HEAD",
                     "--format=%(refname)"),
            )
        return self._merged_cache

    def _fill_list(self, refs: List[RefInfo]):
        idx = self.branch_filter.currentIndex()
        if idx == 1:
            merged, _ = self._merged_sets()
            refs = [r for r in refs if r.ref_type != "tag"
                    and r.fullname in merged]
        elif idx == 2:
            _, unmerged = self._merged_sets()
            refs = [r for r in refs if r.ref_type != "tag"
                    and r.fullname in unmerged]
        self._shown = sorted(refs, key=lambda x: x.shortname)
        self.list.clear()
        for r in self._shown:
            it = QTreeWidgetItem([r.shortname, r.date, r.subject, r.author])
            it.setData(0, Qt.ItemDataRole.UserRole, r.fullname)
            it.setData(0, Qt.ItemDataRole.UserRole + 1, r.ref_type)
            it.setToolTip(0, r.fullname)
            self.list.addTopLevelItem(it)
        if self.list.topLevelItemCount():
            self.list.setCurrentItem(self.list.topLevelItem(0))
        self._apply_filter()

    def _apply_filter(self, *_a):
        text = self.filter_edit.text().strip().lower()
        shown = 0
        for i in range(self.list.topLevelItemCount()):
            it = self.list.topLevelItem(i)
            hay = " ".join(it.text(c) for c in range(self.list.columnCount())).lower()
            vis = (not text) or (text in hay)
            it.setHidden(not vis)
            if vis:
                shown += 1
        self._update_info(shown)

    def _update_info(self, shown: Optional[int] = None):
        if shown is None:
            shown = sum(1 for i in range(self.list.topLevelItemCount())
                        if not self.list.topLevelItem(i).isHidden())
        selected = len(self.list.selectedItems())
        self.info_label.setText(format_string(
            tr("browse_showing", "Showing {shown} ref(s), {selected} ref(s) selected"),
            shown=shown, selected=selected))

    # ---- 选择 ----
    def _selected(self) -> Tuple[Optional[str], Optional[str]]:
        items = self.list.selectedItems()
        item = items[-1] if items else self.list.currentItem()
        if item is not None:
            return (item.data(0, Qt.ItemDataRole.UserRole),
                    item.data(0, Qt.ItemDataRole.UserRole + 1))
        # 兼容：仅选中了引用树上的叶子节点
        tree_item = self.tree.currentItem()
        if tree_item is not None:
            fullname = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if fullname:
                return (fullname,
                        tree_item.data(0, Qt.ItemDataRole.UserRole + 1))
        return None, None

    def _on_current_branch(self):
        for i in range(self.list.topLevelItemCount()):
            it = self.list.topLevelItem(i)
            if it.data(0, Qt.ItemDataRole.UserRole + 1) == "branch" \
                    and it.text(0) == self.current_branch:
                self.list.setCurrentItem(it)
                self.list.scrollToItem(it)
                return

    def _on_double_clicked(self, _item, _col):
        if self.select_mode:
            self._on_ok()

    def _on_ok(self):
        fullname, _rtype = self._selected()
        if fullname:
            self.selected_ref = fullname
        self.accept()

    def _on_help(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, tr("help", "Help"),
                                tr("browse_refs", "Browse references"))

    # ---- 右键菜单 ----
    def _on_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        self.list.setCurrentItem(item)
        menu = QMenu(self)
        act_checkout = menu.addAction(tr("browse_checkout", "Checkout"))
        act_delete = menu.addAction(tr("browse_delete", "Delete…"))
        menu.addSeparator()
        act_copy = menu.addAction(tr("browse_copyref", "Copy ref name"))
        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
        if chosen is act_checkout:
            self._checkout_selected()
        elif chosen is act_delete:
            self._delete_selected()
        elif chosen is act_copy:
            from ..utils.clipboard import ClipboardHelper
            fullname, _ = self._selected()
            if fullname:
                ClipboardHelper().copy_text(fullname)

    def _checkout_selected(self):
        fullname, rtype = self._selected()
        if fullname is None:
            return
        if rtype == "remote":
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, tr("information"),
                format_string(tr("browse_checkout_remote",
                                 "Cannot directly check out remote branch {name}; "
                                 "use git checkout -b <local> {name}"),
                              name=fullname))
            return
        name = fullname.replace("refs/heads/", "").replace("refs/tags/", "")
        result = self.repo.runner.run("checkout", name)
        if result.returncode != 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("error"), result.stderr)
            return
        self.current_branch = self.repo.current_branch()
        self._load()

    def _delete_selected(self):
        fullname, rtype = self._selected()
        if fullname is None:
            return
        name = (fullname.replace("refs/heads/", "")
                .replace("refs/tags/", "").replace("refs/remotes/", ""))
        from PySide6.QtWidgets import QMessageBox
        resp = QMessageBox.question(
            self, tr("confirm"),
            format_string(tr("browse_delete_confirm", 'Delete "{name}"?'),
                          name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        if rtype == "branch":
            args = ["branch", "-d", name]
        elif rtype == "tag":
            args = ["tag", "-d", name]
        else:
            args = ["branch", "-dr", name]
        result = self.repo.runner.run(*args)
        if result.returncode != 0:
            QMessageBox.warning(self, tr("error"), result.stderr)
            return
        self._load()


_ANCHORS = {
    "IDC_BROWSEREFS_EDIT_FILTER": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_BROWSE_REFS_BRANCHFILTER": ("TOP_RIGHT",),
    "IDC_TREE_REF": ("TOP_LEFT", "BOTTOM_LEFT"),
    "IDC_LIST_REF_LEAFS": ("BOTTOM_RIGHT",),
    "IDC_INCLUDENESTEDREFS": ("BOTTOM_LEFT",),
    "IDC_INFOLABEL": ("BOTTOM_RIGHT",),
    "IDC_CURRENTBRANCH": ("BOTTOM_RIGHT",),
}
