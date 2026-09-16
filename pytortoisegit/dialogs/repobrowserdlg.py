"""repobrowserdlg.py —— RepositoryBrowserDlg：仓库浏览器（IDD_REPOSITORY_BROWSER）。

忠实复刻 TortoiseGit 的 CRepositoryBrowser（src/TortoiseProc/RepositoryBrowser.cpp）：

  * 左侧目录树（IDC_REPOTREE）按需展开：展开时才读取该子树的条目
    （ReadTree/TreeExpanding）
  * 右侧文件列表（IDC_REPOLIST）三列：文件名 / 扩展名 / 大小，
    点列头排序，文件夹恒排在文件之前（CRepoListCompareFunc）
  * 目录 / 子模块 / 可执行 / 符号链接分别叠加覆盖图标
    （OVERLAY_EXTERNAL / OVERLAY_EXECUTABLE / OVERLAY_SYMLINK）
  * 树与列表之间的分隔条可拖动（HandleDividerMove）
  * 文件夹与文件用不同的右键菜单（ShowContextMenu + eSelectionType）
  * 底部信息标签显示当前目录统计或选中项（UpdateInfoLabel）
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

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QDialog, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QSizePolicy, QTreeWidget, QTreeWidgetItem,
)

from ..git.repo import Repository
from ..res.strings import format_string, tr
from ..ui import rc as rc_mod
from ..ui.rc import DialogUnits
from .resize import AnchorLayout

# 覆盖图标槽位（对齐 RepositoryBrowser.cpp 顶部的 OVERLAY_* 定义）
OVERLAY_EXTERNAL = 1
OVERLAY_EXECUTABLE = 2
OVERLAY_SYMLINK = 3

# eCol_*
COL_NAME = 0
COL_EXTENSION = 1
COL_FILESIZE = 2

# 分隔条两侧控件的最小宽度（REPOBROWSER_CTRL_MIN_WIDTH）
CTRL_MIN_WIDTH = 20
# 拖动热点宽度（原版取 3 像素，此处按 DPI 缩放后的逻辑像素）
DIVIDER_GRAB = 4

# git 文件模式（与 libgit2 GIT_FILEMODE_* / S_IFDIR 对齐）
_FILEMODE_DIR = 0o040000
_FILEMODE_EXECUTABLE = 0o100755
_FILEMODE_LINK = 0o120000
_FILEMODE_COMMIT = 0o160000


@dataclass
class ShadowFilesTree:
    """镜像 CShadowFilesTree：目录树中的一个条目（文件夹或文件）。"""

    name: str = ""
    oid: str = ""
    size: int = 0
    is_folder: bool = False
    loaded: bool = True          # 文件夹的子树是否已读取
    is_submodule: bool = False
    is_executable: bool = False
    is_symlink: bool = False
    parent: Optional["ShadowFilesTree"] = None
    children: Dict[str, "ShadowFilesTree"] = field(default_factory=dict)
    tree_item: Optional[QTreeWidgetItem] = None

    @property
    def full_name(self) -> str:
        """仓库内相对路径（根为空）。"""
        if self.parent is None:
            return self.name
        parent_path = self.parent.full_name
        if not parent_path:
            return self.name
        return parent_path + "/" + self.name


def _sort_key_logical(name: str):
    """StrCmpLogicalW 风格的键：数字段按数值比较。"""
    parts = re.split(r"(\d+)", name.lower())
    return [(1, int(p)) if p.isdigit() else (0, p) for p in parts if p != ""]


def _file_extension(name: str) -> str:
    """CPathUtils::GetFileExtFromPath —— 取最后一个点号起的内容。

    对齐原版：`dotPos > slashPos` 即算扩展名，故 ".gitignore" -> ".gitignore"。
    """
    dot = name.rfind(".")
    slash = max(name.rfind("/"), name.rfind("\\"))
    if dot > slash:
        return name[dot:]
    return ""


def _format_byte_size(size: int) -> str:
    """StrFormatByteSize64 —— Windows 风格的字节数格式化。"""
    if size < 1024:
        return format_string(tr("size_bytes", "{n} bytes"), n=size)
    units = ("KB", "MB", "GB", "TB", "PB")
    value = float(size)
    for unit in units:
        value /= 1024.0
        if value < 1024.0 or unit == units[-1]:
            # Windows 对 1024 以下保留一位小数，否则取整
            if value < 10:
                return f"{value:.2f} {unit}"
            if value < 100:
                return f"{value:.1f} {unit}"
            return f"{value:.0f} {unit}"
    return f"{size} B"


class RepositoryBrowserDlg(QDialog):
    """仓库浏览器。"""

    def __init__(self, repo: Repository, rev: str = "HEAD", parent=None,
                 path: str = ""):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.rev = rev
        self.start_path = (path or "").strip("/")
        self.tree_root = ShadowFilesTree(is_folder=True)
        self._current_node: Optional[ShadowFilesTree] = None
        self._curr_sort_col = COL_NAME
        self._curr_sort_desc = False
        self._divider_x = 0
        self._drag_mode = False
        self._mark_for_diff_name = ""
        self._mark_for_diff_rev = ""
        self._has_wc = not self._is_bare()
        self._head_error = ""
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # 构建（IDD_REPOSITORY_BROWSER）
    # ------------------------------------------------------------------
    def _build_ui(self):
        spec = rc_mod.load_spec("IDD_REPOSITORY_BROWSER")
        fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
        r = fu.px(0, 0, spec.width, spec.height)
        self.resize(r.width(), r.height())
        rc_mod.apply_min_size(self, r.width(), r.height())
        self.setWindowTitle(spec.caption or "Repository Browser")
        font = self.font()
        font.setPointSize(spec.font_size or 9)
        self.setFont(font)
        self._anchors = AnchorLayout(self.width(), self.height())
        self._ctl: dict = {}

        self.path_label = QLabel(tr("repobrowser_path", "Path:"), self)
        self.url_edit = QLineEdit(self)
        self.url_edit.setReadOnly(True)
        self.ref_label = QLabel(tr("repobrowser_rev", "Revision:"), self)
        self.btn_revision = QPushButton(self.rev, self)
        self.btn_revision.clicked.connect(self._on_revision)

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.itemExpanded.connect(self._on_tree_expanded)
        self.tree.currentItemChanged.connect(self._on_tree_sel_changed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_menu)

        self.list = QTreeWidget(self)
        self.list.setColumnCount(3)
        self.list.setHeaderLabels([
            tr("repobrowser_name", "Filename"),
            tr("repobrowser_ext", "Extension"),
            tr("repobrowser_size", "Size")])
        self.list.setRootIsDecorated(False)
        self.list.setUniformRowHeights(True)
        self.list.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_list_menu)
        self.list.itemDoubleClicked.connect(self._on_list_double_clicked)
        self.list.itemSelectionChanged.connect(self._update_info_label)
        header = self.list.header()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_column_clicked)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            COL_EXTENSION, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(
            COL_FILESIZE, QHeaderView.ResizeMode.Interactive)
        # 对齐原版列宽：150 / 100 / 100 像素（按 DLU 换算）
        unit = fu.px(0, 0, 4, 0).width() or 1
        header.resizeSection(COL_NAME, unit * 150 // 4)
        header.resizeSection(COL_EXTENSION, unit * 100 // 4)
        header.resizeSection(COL_FILESIZE, unit * 100 // 4)
        # 大小列右对齐（m_ColumnManager.SetRightAlign(eCol_FileSize)）
        self.list.headerItem().setTextAlignment(
            COL_FILESIZE,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.info_label = QLabel("", self)
        # IDC_INFOLABEL 是单行静态文本（SS_NOPREFIX WS_EX_RIGHT），内容过长时
        # 按控件宽度裁切，不应把对话框撑大——否则长统计文本会抬高最小宽度。
        self.info_label.setWordWrap(False)
        self.info_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction)
        self.info_label.setMinimumWidth(0)
        self.info_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.btn_ok = QPushButton(tr("ok"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton(tr("cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton(tr("help"), self)
        self.btn_help.clicked.connect(self._on_help)

        mapping = {
            "IDC_STATIC_REPOURL": self.path_label,
            "IDC_REPOBROWSER_URL": self.url_edit,
            "IDC_STATIC_REF": self.ref_label,
            "IDC_BUTTON_REVISION": self.btn_revision,
            "IDC_REPOTREE": self.tree,
            "IDC_REPOLIST": self.list,
            "IDC_INFOLABEL": self.info_label,
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
        # 分隔条初始位置取树的宽度（原版读注册表 RepobrowserDivider）
        self._divider_x = self.tree.geometry().right()
        self.tree.setMouseTracking(True)
        self.tree.installEventFilter(self)
        self._install_divider_filter()

    def _install_divider_filter(self):
        """在对话框上跟踪鼠标，以便在分隔条区域显示左右拖动光标。"""
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_anchors"):
            self._anchors.apply(self.width(), self.height())
            if self._divider_x:
                # 拖动过分隔条后，宽度由用户设定，缩放时保持树宽不变
                tree_geo = self.tree.geometry()
                self._divider_x = tree_geo.right()

    # ------------------------------------------------------------------
    # 读取仓库（ReadTree / ReadTreeRecursive）
    # ------------------------------------------------------------------
    def _is_bare(self) -> bool:
        try:
            return self.repo.is_bare()
        except Exception:  # noqa: BLE001
            return False

    def _resolve_tree_oid(self) -> str:
        """解析 m_sRevision 为 tree 对象（对齐 ReadTree 的 rev^{} 处理）。"""
        rev = self.rev or "HEAD"
        if rev == "HEAD":
            res = self.repo.runner.run("rev-parse", "--verify", "HEAD")
            if res.returncode != 0:
                self._head_error = tr(
                    "repobrowser_head_error", "Could not check HEAD.")
                return ""
        # 加 ^{} 以解开附注标签
        res = self.repo.runner.run("rev-parse", "--verify", f"{rev}^{{}}")
        if res.returncode != 0:
            self._head_error = format_string(
                tr("repobrowser_hash_error",
                   'Could not get hash of "{rev}".'), rev=rev)
            return ""
        oid = res.stdout.strip()
        type_res = self.repo.runner.run("cat-file", "-t", oid)
        obj_type = (type_res.stdout or "").strip()
        if obj_type == "commit":
            tree_res = self.repo.runner.run("rev-parse", f"{oid}^{{tree}}")
            if tree_res.returncode != 0:
                self._head_error = tr(
                    "repobrowser_object_error", "Could not lookup object.")
                return ""
            return tree_res.stdout.strip()
        if obj_type == "tree":
            return oid
        self._head_error = tr(
            "repobrowser_unknown_type", "Found unknown object type.")
        return ""

    def _ls_tree(self, treeish: str) -> List[ShadowFilesTree]:
        """读取一个 tree 的直接条目（对齐 ReadTreeRecursive 的一层）。"""
        res = self.repo.runner.run("ls-tree", "-l", treeish)
        if res.returncode != 0:
            return []
        out: List[ShadowFilesTree] = []
        for line in (res.stdout or "").splitlines():
            if not line.strip():
                continue
            meta, _, name = line.partition("\t")
            if not name:
                continue
            parts = meta.split()
            if len(parts) < 3:
                continue
            mode_str, obj_type, oid = parts[0], parts[1], parts[2]
            try:
                mode = int(mode_str, 8)
            except ValueError:
                mode = 0
            entry = ShadowFilesTree(name=name, oid=oid)
            if mode == _FILEMODE_COMMIT or obj_type == "commit":
                entry.is_submodule = True
                entry.size = 0
            elif mode == _FILEMODE_DIR or obj_type == "tree":
                entry.is_folder = True
                entry.loaded = False
            else:
                if mode == _FILEMODE_EXECUTABLE:
                    entry.is_executable = True
                if mode == _FILEMODE_LINK:
                    entry.is_symlink = True
                # ls-tree -l 的第 4 列是 blob 大小（"-" 表示未知）
                if len(parts) >= 4 and parts[3].isdigit():
                    entry.size = int(parts[3])
                else:
                    size_res = self.repo.runner.run("cat-file", "-s", oid)
                    if size_res.returncode == 0:
                        try:
                            entry.size = int(size_res.stdout.strip())
                        except ValueError:
                            entry.size = 0
            out.append(entry)
        return out

    def _read_tree(self, node: ShadowFilesTree, recursive: bool = False):
        """读取 node 的子条目并填充其 ShadowFilesTree（ReadTree）。"""
        treeish = node.oid or "HEAD^{tree}"
        node.loaded = True
        for child in self._ls_tree(treeish):
            child.parent = node
            node.children[child.name] = child
        if recursive:
            for child in node.children.values():
                if child.is_folder:
                    self._read_tree(child, recursive=True)

    def _entry_to_tree_item(self, node: ShadowFilesTree) -> QTreeWidgetItem:
        icon_name = "IDI_GITFOLDER" if node.is_folder else "IDI_FILE"
        item = QTreeWidgetItem([node.name])
        item.setData(0, Qt.ItemDataRole.UserRole, node)
        item.setIcon(0, _icon(icon_name))
        node.tree_item = item
        # 有子目录才显示展开箭头（cChildren）
        item.setChildIndicatorPolicy(
            QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            if (node.is_folder and node.oid) else
            QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
        return item

    def _populate_tree(self, parent_item: Optional[QTreeWidgetItem],
                       node: ShadowFilesTree):
        """把 node 的文件夹子项加入树的对应层级（ReadTreeRecursive）。"""
        folders = [c for c in node.children.values() if c.is_folder]
        folders.sort(key=lambda c: _sort_key_logical(c.name))
        for child in folders:
            item = self._entry_to_tree_item(child)
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            # 递归读取以填满 ShadowTree，但树控件按需展开
            if not child.loaded:
                self._read_tree(child, recursive=False)

    # ------------------------------------------------------------------
    # 列表填充（FillListCtrlForShadowTree）
    # ------------------------------------------------------------------
    def _fill_list_for_node(self, node: ShadowFilesTree):
        self.list.clear()
        if not node.loaded:
            self._read_tree(node)
        entries = list(node.children.values())
        entries.sort(key=self._sort_key_for_list)
        if self._curr_sort_desc:
            entries.reverse()
        # 文件夹恒在前（CRepoListCompareFunc 末尾的 m_bFolder 兜底）
        folders = [e for e in entries if e.is_folder]
        files = [e for e in entries if not e.is_folder]
        for entry in folders + files:
            self._add_list_row(entry)
        self._update_sort_indicator()
        self._update_info_label()

    def _add_list_row(self, entry: ShadowFilesTree):
        item = QTreeWidgetItem()
        item.setText(COL_NAME, entry.name)
        item.setData(0, Qt.ItemDataRole.UserRole, entry)
        if entry.is_submodule:
            item.setIcon(COL_NAME, _icon("IDI_EXTERNALOVL"))
            item.setText(COL_EXTENSION, "")
            item.setText(COL_FILESIZE, "")
        elif entry.is_folder:
            item.setIcon(COL_NAME, _icon("IDI_GITFOLDER"))
            item.setText(COL_EXTENSION, "")
            item.setText(COL_FILESIZE, "")
        else:
            icon_name = "IDI_FILE"
            if entry.is_symlink:
                icon_name = "IDI_SYMLINKOVL"
            elif entry.is_executable:
                icon_name = "IDI_EXECUTABLEOVL"
            item.setIcon(COL_NAME, _icon(icon_name))
            item.setText(COL_EXTENSION, _file_extension(entry.name))
            item.setText(COL_FILESIZE, _format_byte_size(entry.size))
        item.setTextAlignment(
            COL_FILESIZE, Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter)
        self.list.addTopLevelItem(item)

    def _sort_key_for_list(self, entry: ShadowFilesTree):
        if self._curr_sort_col == COL_EXTENSION:
            return _sort_key_logical(_file_extension(entry.name))
        if self._curr_sort_col == COL_FILESIZE:
            return (entry.size, _sort_key_logical(entry.name))
        return _sort_key_logical(entry.name)

    def _update_sort_indicator(self):
        header = self.list.header()
        header.setSortIndicatorShown(True)
        order = (Qt.SortOrder.DescendingOrder if self._curr_sort_desc
                 else Qt.SortOrder.AscendingOrder)
        header.setSortIndicator(self._curr_sort_col, order)

    def _on_column_clicked(self, column: int):
        if self._curr_sort_col == column:
            self._curr_sort_desc = not self._curr_sort_desc
        else:
            self._curr_sort_col = column
            self._curr_sort_desc = False
        node = self._current_tree_node()
        if node is not None:
            self._fill_list_for_node(node)

    # ------------------------------------------------------------------
    # 树交互
    # ------------------------------------------------------------------
    def _current_tree_node(self) -> Optional[ShadowFilesTree]:
        item = self.tree.currentItem()
        node = _node_of(item)
        if node is not None:
            return node
        return self._current_node

    def _on_tree_sel_changed(self, current: QTreeWidgetItem, _previous):
        if current is None:
            return
        node = _node_of(current)
        if node is None:
            return
        self._current_node = node
        self.url_edit.setText("/" + node.full_name)
        if not node.loaded:
            self._read_tree(node)
            self._populate_tree(current, node)
        self._fill_list_for_node(node)

    def _on_tree_expanded(self, item: QTreeWidgetItem):
        """TVN_ITEMEXPANDING：首次展开时才读取子树。"""
        node = _node_of(item)
        if node is None or not node.is_folder:
            return
        if not node.loaded:
            self._read_tree(node)
        if item.childCount() == 0 and node.children:
            self._populate_tree(item, node)

    def _on_tree_clicked(self, item: QTreeWidgetItem, _column: int = 0):
        self._on_tree_sel_changed(item, None)

    # ------------------------------------------------------------------
    # 列表交互
    # ------------------------------------------------------------------
    def _selected_entries(self) -> List[ShadowFilesTree]:
        out = []
        for item in self.list.selectedItems():
            node = _node_of(item)
            if node is not None:
                out.append(node)
        return out

    def _on_list_double_clicked(self, item: QTreeWidgetItem, _column: int):
        node = _node_of(item)
        if node is None:
            return
        if node.is_folder:
            self._enter_folder(node)
        else:
            self._open_file(node, mode="open")

    def _enter_folder(self, node: ShadowFilesTree):
        """OnOK / 双击文件夹：在树中选中该目录并把列表切过去。"""
        item = self._find_tree_item(node)
        if item is not None:
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)
            self._current_node = node
        else:
            if not node.loaded:
                self._read_tree(node)
            self._current_node = node
            self.url_edit.setText("/" + node.full_name)
            self._fill_list_for_node(node)

    def _find_tree_item(self, node: ShadowFilesTree) -> Optional[QTreeWidgetItem]:
        """在树里按路径查找条目，必要时逐级展开。"""
        parts = [p for p in node.full_name.split("/") if p]
        parent_item = None
        current_node = self.tree_root
        for part in parts:
            child = current_node.children.get(part)
            if child is None:
                return None
            if parent_item is None:
                found = self._top_level_item(part)
            else:
                found = self._child_item(parent_item, part)
            if found is None:
                # 展开上一级以生成子项
                if parent_item is not None:
                    self.tree.expandItem(parent_item)
                    found = self._child_item(parent_item, part)
                if found is None:
                    return None
            parent_item = found
            current_node = child
        return parent_item

    def _top_level_item(self, name: str) -> Optional[QTreeWidgetItem]:
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.text(0) == name:
                return it
        return None

    def _child_item(self, parent: QTreeWidgetItem,
                    name: str) -> Optional[QTreeWidgetItem]:
        for i in range(parent.childCount()):
            it = parent.child(i)
            if it.text(0) == name:
                return it
        return None

    # ------------------------------------------------------------------
    # 信息标签（UpdateInfoLabel）
    # ------------------------------------------------------------------
    def _update_info_label(self):
        selected = self._selected_entries()
        if selected:
            if len(selected) > 1:
                text = format_string(
                    tr("repobrowser_info_multi", "{count} items selected"),
                    count=len(selected))
            else:
                entry = selected[0]
                if entry.is_submodule:
                    text = format_string(
                        tr("repobrowser_info_ext",
                           'Submodule "{name}"\nRevision {rev}'),
                        name=entry.name, rev=entry.oid)
                elif entry.is_folder:
                    text = entry.name
                else:
                    text = format_string(
                        tr("repobrowser_info_file", "{name}\nSize {size}"),
                        name=entry.name, size=_format_byte_size(entry.size))
            self.info_label.setText(text)
            return
        node = self._current_tree_node()
        if node is None:
            self.info_label.setText("")
            return
        files = sum(
            1 for c in node.children.values()
            if not c.is_folder and not c.is_submodule)
        submodules = sum(1 for c in node.children.values() if c.is_submodule)
        total = len(node.children)
        folders = total - files - submodules
        # 根节点的 m_sName 为空：原版 FormatMessage 会保留空的第一行，
        # 从而统计信息显示在单独一行（见 doc/images/en/RepoBrowser.png）。
        name = node.name or "/"
        self.info_label.setText(format_string(
            tr("repobrowser_info",
               "{name}\nShowing {files} files, {submodules} submodules "
               "and {folders} folders, {total} items in total"),
            name=name, files=files, submodules=submodules,
            folders=folders, total=total))

    # ------------------------------------------------------------------
    # 右键菜单（ShowContextMenu）
    # ------------------------------------------------------------------
    def _on_tree_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        node = _node_of(item)
        if node is None or not node.is_folder:
            return
        self._show_context_menu(
            self.tree.viewport().mapToGlobal(pos), [node], only_folders=True)

    def _on_list_menu(self, pos: QPoint):
        item = self.list.itemAt(pos)
        selected = self._selected_entries()
        if item is not None:
            node = _node_of(item)
            if node is not None and node not in selected:
                selected = [node]
        if not selected:
            return
        folder_selected = any(e.is_folder for e in selected)
        files_selected = any(not e.is_folder for e in selected)
        submodules_selected = any(e.is_submodule for e in selected)
        if folder_selected and files_selected:
            sel_type = "mixed"
        elif folder_selected:
            sel_type = "folders"
        elif submodules_selected:
            sel_type = "files_submodules"
        else:
            sel_type = "files"
        self._show_context_menu(
            self.list.viewport().mapToGlobal(pos), selected, sel_type)

    def _show_context_menu(self, global_pos: QPoint,
                           selected: List[ShadowFilesTree], sel_type: str):
        only_folders = sel_type == "folders"
        only_files = sel_type in ("files", "files_submodules")
        single = len(selected) == 1
        menu = QMenu(self)

        act_open = act_open_with = act_alt = None
        act_compare = act_log = act_log_sub = None
        act_blame = act_saveas = act_revert = None
        act_prepare = act_diff_now = None

        if single:
            act_open = menu.addAction(
                _icon("IDI_OPEN"), tr("repobrowser_open", "&Open"))
            menu.setDefaultAction(act_open)
            if only_files:
                act_open_with = menu.addAction(
                    _icon("IDI_OPEN"),
                    tr("repobrowser_open_with", "Open With…"))
                act_alt = menu.addAction(
                    _icon("IDI_NOTEPAD"),
                    tr("repobrowser_view_rev",
                       "View revision in default editor"))
            menu.addSeparator()
            if self._has_wc and only_files:
                act_compare = menu.addAction(
                    _icon("IDI_DIFF"),
                    tr("repobrowser_compare_wc", "Compare with working tree"))
                menu.addSeparator()
            act_log = menu.addAction(
                _icon("IDI_LOG"), tr("repobrowser_show_log", "Show log"))
            if selected[0].is_submodule:
                act_log_sub = menu.addAction(
                    _icon("IDI_LOG"),
                    tr("repobrowser_show_log_submodule",
                       "Show log of submodule"))
            if sel_type == "files":
                if self._has_wc:
                    act_blame = menu.addAction(
                        _icon("IDI_BLAME"), tr("repobrowser_blame", "Blame…"))
                menu.addSeparator()
                act_saveas = menu.addAction(
                    _icon("IDI_SAVEAS"), tr("repobrowser_saveas", "Save &as…"))
            menu.addSeparator()

        if selected and sel_type == "files" and self._has_wc:
            act_revert = menu.addAction(
                _icon("IDI_REVERT"),
                tr("repobrowser_revert", "Revert to this revision"))
            menu.addSeparator()

        if single and sel_type == "files":
            act_prepare = menu.addAction(
                _icon("IDI_DIFF"),
                tr("repobrowser_prepare_diff", "Mark for comparison"))
            self._update_diff_with_file_from_reg()
            if self._mark_for_diff_name:
                target = selected[0].full_name
                if target == self._mark_for_diff_name:
                    diff_with = self._mark_for_diff_rev
                else:
                    diff_with = self._mark_for_diff_name
                    if self._mark_for_diff_rev:
                        diff_with += ":" + self._mark_for_diff_rev[:7]
                act_diff_now = menu.addAction(
                    _icon("IDI_DIFF"),
                    format_string(
                        tr("repobrowser_diff_now", "Compare with {name}"),
                        name=diff_with))
            menu.addSeparator()

        act_copy_path = act_copy_hash = None
        if selected:
            act_copy_path = menu.addAction(
                _icon("IDI_COPYCLIP"),
                tr("repobrowser_copy_path", "Copy paths to clipboard"))
            act_copy_hash = menu.addAction(
                _icon("IDI_COPYCLIP"),
                tr("repobrowser_copy_hash", "Copy commit hash"))

        _ = only_folders
        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen is act_open:
            if selected[0].is_folder:
                self._enter_folder(selected[0])
            else:
                self._open_file(selected[0], mode="open")
        elif chosen is act_open_with:
            self._open_file(selected[0], mode="open_with")
        elif chosen is act_alt:
            self._open_file(selected[0], mode="alternative")
        elif chosen is act_compare:
            self._compare_with_wc(selected[0])
        elif chosen is act_log:
            self._show_log(selected[0], submodule=False)
        elif chosen is act_log_sub:
            self._show_log(selected[0], submodule=True)
        elif chosen is act_blame:
            self._blame(selected[0])
        elif chosen is act_saveas:
            self._save_as(selected[0])
        elif chosen is act_revert:
            self._revert_to_revision(selected)
        elif chosen is act_prepare:
            self._mark_for_diff(selected[0])
        elif chosen is act_diff_now:
            self._diff_now(selected[0])
        elif chosen is act_copy_path:
            self._copy_paths(selected)
        elif chosen is act_copy_hash:
            self._copy_hashes(selected)

    # ------------------------------------------------------------------
    # 菜单命令实现
    # ------------------------------------------------------------------
    def _work_tree_relative(self, node: ShadowFilesTree) -> str:
        return node.full_name

    def _work_tree_path(self, node: ShadowFilesTree) -> str:
        return os.path.join(self.repo.root, *node.full_name.split("/"))

    def _open_file(self, node: ShadowFilesTree, mode: str = "open"):
        """OpenFile —— 把该修订的文件导出到临时目录后交给系统/编辑器打开。"""
        if node.is_submodule:
            self._open_submodule(node, mode)
            return
        tmp_path = self._export_to_temp(node)
        if tmp_path is None:
            return
        try:
            if mode == "alternative":
                self._launch_alternative_editor(tmp_path)
            elif mode == "open_with":
                self._launch_open_with(tmp_path)
            else:
                self._shell_open(tmp_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, tr("repobrowser_error_title", "TortoiseGit"), str(exc))

    def _export_to_temp(self, node: ShadowFilesTree) -> Optional[str]:
        """把 node 在该修订下的内容写入临时文件，返回路径。"""
        import tempfile

        res = self.repo.runner.run(
            "show", f"{self.rev}:{self._work_tree_relative(node)}")
        if res.returncode != 0:
            QMessageBox.warning(
                self, tr("repobrowser_error_title", "TortoiseGit"),
                format_string(
                    tr("repobrowser_checkout_failed",
                       "Could not checkout file {path}\n"
                       "Revision {rev} to {file}."),
                    path=node.full_name, rev=self.rev, file=node.name))
            return None
        base = os.path.basename(node.name) or "file"
        fd, tmp_path = tempfile.mkstemp(prefix="ptg-", suffix="-" + base)
        os.close(fd)
        data = res.stdout or ""
        with open(tmp_path, "w", encoding="utf-8", errors="replace",
                  newline="") as fh:
            fh.write(data)
        return tmp_path

    def _open_submodule(self, node: ShadowFilesTree, mode: str):
        """子模块：打开其仓库；工作区里不存在该修订时提示更新。"""
        if mode == "open" and self._has_wc:
            sub_path = self._work_tree_path(node)
            if os.path.isdir(os.path.join(sub_path, ".git")) or \
                    os.path.isfile(os.path.join(sub_path, ".git")):
                self._run_command("/command:repobrowser", [
                    f"/path:{sub_path}", f"/rev:{node.oid}"])
                return
            answer = QMessageBox.question(
                self, tr("repobrowser_error_title", "TortoiseGit"),
                format_string(
                    tr("repobrowser_submodule_update",
                       "Revision {rev} does not exist in submodule {path}.\n"
                       "Update the submodule?"),
                    rev=node.oid, path=node.full_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.Yes:
                self._run_command("/command:subupdate", [
                    f"/bkpath:{self.repo.root}",
                    f"/selectedpath:{self._work_tree_relative(node)}"])
            return
        # 非工作区打开：写出 "Subproject commit <hash>" 文本
        import tempfile

        fd, tmp_path = tempfile.mkstemp(prefix="ptg-", suffix=".txt")
        os.close(fd)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write("Subproject commit " + node.oid)
        self._shell_open(tmp_path)

    @staticmethod
    def _shell_open(path: str):
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
            return
        import subprocess

        from ..utils.proc import no_window_kwargs
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, path], **no_window_kwargs())

    def _launch_alternative_editor(self, path: str):
        self._shell_open(path)

    def _launch_open_with(self, path: str):
        if sys.platform == "win32":
            import subprocess

            from ..utils.proc import no_window_kwargs
            subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL",
                              path], **no_window_kwargs())
            return
        self._shell_open(path)

    def _run_command(self, command: str, args: List[str]):
        """等价于 CAppUtils::RunTortoiseGitProc —— 交给命令分发器执行。"""
        from ..cmdline import parse as parse_cmdline
        from ..commands.dispatcher import (
            CommandContext, dispatch, UnknownCommandError)
        verb = command.split(":", 1)[-1]
        try:
            cl = parse_cmdline([f"/command:{verb}"] + list(args))
        except Exception:  # noqa: BLE001
            return
        try:
            dispatch(verb, CommandContext(qapp=None, cl=cl))
        except UnknownCommandError:
            return
        except Exception:  # noqa: BLE001
            from ..utils.logging_utils import get_logger
            get_logger().exception("repobrowser command failed: %s", verb)

    def _compare_with_wc(self, node: ShadowFilesTree):
        from .diffdlg import DiffDlg
        paths = [self._work_tree_relative(node)]
        DiffDlg(self.repo, rev1=self.rev, rev2=None, paths=paths,
                parent=self).exec()

    def _show_log(self, node: ShadowFilesTree, submodule: bool = False):
        from .logdlg import LogDlg
        pathspec = self._work_tree_relative(node)
        rev = node.oid if submodule else self.rev
        dlg = LogDlg(self.repo, pathspec=pathspec, rev=rev, parent=None)
        dlg.show()
        dlg.raise_()

    def _blame(self, node: ShadowFilesTree):
        from ..blame import blame_file
        from .blamedlg import BlameDlg
        path = self._work_tree_path(node)
        if not os.path.isfile(path):
            QMessageBox.information(
                self, tr("repobrowser_error_title", "TortoiseGit"),
                tr("repobrowser_lookup_error", "Could not lookup path."))
            return
        dlg = BlameDlg(self.repo, path, rev=self.rev, parent=self)
        _ = blame_file
        dlg.exec()

    def _save_as(self, node: ShadowFilesTree):
        from ..utils.pick import pick_file
        rev_short = self._short_rev()
        base, ext = os.path.splitext(os.path.basename(node.name))
        suggested = f"{base}-{rev_short}{ext}"
        start = os.path.join(
            os.path.dirname(self._work_tree_path(node)), suggested)
        target = pick_file(
            self, tr("repobrowser_saveas", "Save &as…"), start)
        if not target:
            return
        res = self.repo.runner.run(
            "show", f"{self.rev}:{self._work_tree_relative(node)}")
        if res.returncode != 0:
            QMessageBox.warning(
                self, tr("repobrowser_error_title", "TortoiseGit"),
                format_string(
                    tr("repobrowser_checkout_failed",
                       "Could not checkout file {path}\n"
                       "Revision {rev} to {file}."),
                    path=node.full_name, rev=self.rev, file=target))
            return
        with open(target, "w", encoding="utf-8", errors="replace",
                  newline="") as fh:
            fh.write(res.stdout or "")

    def _short_rev(self) -> str:
        res = self.repo.runner.run("rev-parse", "--short", self.rev)
        return res.stdout.strip() if res.returncode == 0 else self.rev[:7]

    def _revert_to_revision(self, selected: List[ShadowFilesTree]):
        """RevertItemToVersion —— git checkout <rev> -- <path>。"""
        count = 0
        for node in selected:
            if node.is_folder or node.is_submodule:
                continue
            res = self.repo.runner.run(
                "checkout", self.rev, "--", self._work_tree_relative(node))
            if res.returncode != 0:
                answer = QMessageBox.warning(
                    self, tr("repobrowser_error_title", "TortoiseGit"),
                    res.stderr or res.stdout,
                    QMessageBox.StandardButton.Ok
                    | QMessageBox.StandardButton.Cancel)
                if answer == QMessageBox.StandardButton.Cancel:
                    break
                continue
            count += 1
        QMessageBox.information(
            self, tr("repobrowser_error_title", "TortoiseGit"),
            format_string(
                tr("repobrowser_files_reverted",
                   "{count} files reverted to {rev}."),
                count=count, rev=self.rev))

    def _mark_for_diff(self, node: ShadowFilesTree):
        self._mark_for_diff_name = node.full_name
        self._mark_for_diff_rev = self.rev

    def _diff_now(self, node: ShadowFilesTree):
        if not self._mark_for_diff_name:
            return
        from .diffdlg import DiffDlg
        DiffDlg(self.repo, rev1=self._mark_for_diff_rev, rev2=self.rev,
                paths=[node.full_name, self._mark_for_diff_name],
                parent=self).exec()
        self._mark_for_diff_name = ""
        self._mark_for_diff_rev = ""

    def _update_diff_with_file_from_reg(self):
        """读取“标记为比较对象”的设置（对齐 UpdateDiffWithFileFromReg）。"""
        try:
            from PySide6.QtCore import QSettings
            value = str(QSettings("PyTortoiseGit", "PyTortoiseGit")
                        .value("DiffLater", "") or "")
        except Exception:  # noqa: BLE001
            value = ""
        if value and value != self._mark_for_diff_name:
            self._mark_for_diff_name = value
            self._mark_for_diff_rev = ""

    def _copy_paths(self, selected: List[ShadowFilesTree]):
        from ..utils.clipboard import ClipboardHelper
        ClipboardHelper().copy_text(
            "\n".join(e.name for e in selected))

    def _copy_hashes(self, selected: List[ShadowFilesTree]):
        from ..utils.clipboard import ClipboardHelper
        ClipboardHelper().copy_text("\n".join(e.oid for e in selected))

    # ------------------------------------------------------------------
    # 修订按钮（OnBnClickedButtonRevision）
    # ------------------------------------------------------------------
    def _on_revision(self):
        from .logdlg import LogDlg
        dlg = LogDlg(self.repo, parent=self, select=True)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_hash:
            self.rev = dlg.selected_hash
            self.btn_revision.setText(self.rev)
            self.refresh()

    def _pick_rev(self):
        """兼容旧调用名。"""
        self._on_revision()

    def _on_help(self):
        QMessageBox.information(
            self, tr("help"),
            tr("repobrowser_help",
               "Browse the repository at the selected revision.\n"
               "Double-click a folder to enter it; F5 refreshes.\n"
               "Click a column header to sort the file list."))

    # ------------------------------------------------------------------
    # 刷新（Refresh）
    # ------------------------------------------------------------------
    def refresh(self):
        self._head_error = ""
        self.tree.clear()
        self.list.clear()
        self.tree_root = ShadowFilesTree(is_folder=True)
        tree_oid = self._resolve_tree_oid()
        if self._head_error:
            self.info_label.setText(self._head_error)
            return
        self.tree_root.oid = tree_oid
        self._read_tree(self.tree_root, recursive=False)
        self._populate_tree(None, self.tree_root)
        self.url_edit.setText("/")
        # 原版 Refresh() 在末尾 SelectItem(m_TreeRoot)：根目录是当前节点
        self._current_node = self.tree_root
        self.tree.setCurrentItem(None)
        self._fill_list_for_node(self.tree_root)
        self._update_info_label()
        # 命令行给了 /path 时进入该子目录
        if self.start_path:
            node = self._node_by_path(self.start_path)
            if node is not None:
                self._enter_folder(node)

    def _node_by_path(self, path: str) -> Optional[ShadowFilesTree]:
        parts = [p for p in path.split("/") if p]
        node = self.tree_root
        for part in parts:
            child = node.children.get(part)
            if child is None:
                return None
            node = child
            if node.is_folder and not node.loaded:
                self._read_tree(node)
        return node if parts else None

    # ------------------------------------------------------------------
    # 键盘与分隔条
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_F5:
            self.refresh()
            return
        if (key == Qt.Key.Key_A
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and self.list.hasFocus()):
            self.list.selectAll()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # OnOK：列表有焦点时“进入”所选项，否则接受对话框
            if self.list.hasFocus():
                selected = self._selected_entries()
                if len(selected) == 1:
                    if selected[0].is_folder:
                        self._enter_folder(selected[0])
                    else:
                        self._open_file(selected[0], mode="open")
                return
        super().keyPressEvent(event)

    def _divider_rect(self):
        """分隔条的命中区域（在对话框坐标系里）。"""
        tree_geo = self.tree.geometry()
        list_geo = self.list.geometry()
        left = tree_geo.right()
        right = list_geo.left()
        if right <= left:
            right = left + DIVIDER_GRAB
        return left, min(tree_geo.top(), list_geo.top()), \
            right, max(tree_geo.bottom(), list_geo.bottom())

    def mouseMoveEvent(self, event):
        if self._drag_mode:
            self._move_divider(event.position().x())
            return
        x = event.position().x()
        left, top, right, bottom = self._divider_rect()
        y = event.position().y()
        if left - DIVIDER_GRAB <= x <= right + DIVIDER_GRAB and top <= y <= bottom:
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            left, top, right, bottom = self._divider_rect()
            x, y = event.position().x(), event.position().y()
            if (left - DIVIDER_GRAB <= x <= right + DIVIDER_GRAB
                    and top <= y <= bottom):
                self._drag_mode = True
                self.setCursor(Qt.CursorShape.SplitHCursor)
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_mode:
            self._drag_mode = False
            self.unsetCursor()
            return
        super().mouseReleaseEvent(event)

    def _move_divider(self, x: float):
        """HandleDividerMove —— 按拖动位置重排树与列表。"""
        tree_geo = self.tree.geometry()
        list_geo = self.list.geometry()
        left = tree_geo.left()
        right = list_geo.right()
        min_w = CTRL_MIN_WIDTH
        new_x = int(x)
        new_x = max(left + min_w, min(right - min_w, new_x))
        if new_x == self._divider_x:
            return
        self._divider_x = new_x
        gap = 4
        tree_w = max(min_w, new_x - gap // 2 - left)
        list_left = new_x + gap // 2
        list_w = max(min_w, right - list_left)
        self.tree.setGeometry(left, tree_geo.top(), tree_w, tree_geo.height())
        self.list.setGeometry(
            list_left, list_geo.top(), list_w, list_geo.height())


def _node_of(item: Optional[QTreeWidgetItem]) -> Optional[ShadowFilesTree]:
    if item is None:
        return None
    data = item.data(0, Qt.ItemDataRole.UserRole)
    return data if isinstance(data, ShadowFilesTree) else None


def _icon(name: str):
    try:
        from ..res import icons
        return icons.icon(name)
    except Exception:  # noqa: BLE001
        from PySide6.QtGui import QIcon
        return QIcon()


_ANCHORS = {
    "IDC_REPOTREE": ("TOP_LEFT", "BOTTOM_LEFT"),
    "IDC_REPOLIST": ("TOP_LEFT", "BOTTOM_RIGHT"),
    "IDC_INFOLABEL": ("BOTTOM_LEFT", "BOTTOM_RIGHT"),
    "IDOK": ("BOTTOM_RIGHT",),
    "IDCANCEL": ("BOTTOM_RIGHT",),
    "IDHELP": ("BOTTOM_RIGHT",),
    "IDC_STATIC_REPOURL": ("TOP_LEFT",),
    "IDC_REPOBROWSER_URL": ("TOP_LEFT", "TOP_RIGHT"),
    "IDC_STATIC_REF": ("TOP_RIGHT",),
    "IDC_BUTTON_REVISION": ("TOP_RIGHT",),
}
