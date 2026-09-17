"""revisiongraphdlg.py —— RevisionGraphDlg：绘制的分支节点图。

对齐 TortoiseGit 原版 Revision Graph：

* 提交按 Sugiyama 分层布局（见 ``git/revgraph.py``），新提交在上、父提交在下。
* 节点为圆角矩形，每个引用一行，按引用类型着色（当前分支红、本地分支绿、
  远程分支米黄、标签黄、无引用浅粉并显示短 hash）。
* 父子连线沿折点绘制，两端裁剪到节点边界并带箭头。

默认使用 ``--simplify-by-decoration`` 只保留被引用标注的提交与分叉/合并点，
与原版 ``LOG_INFO_SIMPILFY_BY_DECORATION`` 一致。

外壳对齐 RevisionGraphDlg.cpp：
  * 菜单栏 File / View / Git / Help（对齐 IDR_REVISIONGRAPH），Git 菜单随选中数启用；
  * 工具栏直接使用原版 ``res/revgraph/revgraphbar.bmp``（20px/格）：放大/缩小/
    100%/适合高度/适合宽度/适合全部 + 缩放下拉框 + 过滤/概览/查找；
  * 缩放 1%–200%、步进 0.9，Ctrl+滚轮可缩放；
  * 「重置过滤」与过滤对话框改条件后都会**重新拉取**（原版走 StartWorkerThread）；
  * 加载中显示 "Loading…"，无数据时显示 "No graph available"。
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

import math
import re

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMenuBar,
    QPushButton,
    QScrollArea,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..asyncfw import run_async
from ..git.repo import Repository
from ..git.rev import GitRevLoglist
from ..git.revgraph import GraphLayout, build_layout
from ..res.strings import format_string, tr
from .statgraphdlg import StatGraphDlg

# C++：默认缩放字体 9；左上/右下内边距 20 / 5
_FONT_SIZE = 9
_MARGIN_X = 20.0
_MARGIN_Y = 5.0
_CORNER = 12.0
_ARROW_SIZE = 8.0
_ARROW_COS = math.cos(math.pi / 8)
_ARROW_SIN = math.sin(math.pi / 8)

# 缩放常量（对齐 RevisionGraphWnd.h: MIN_ZOOM/MAX_ZOOM/DEFAULT_ZOOM/ZOOM_STEP）
_MIN_ZOOM = 0.01
_MAX_ZOOM = 2.0
_DEFAULT_ZOOM = 1.0
_ZOOM_STEP = 0.9
_ZOOM_PRESETS = ("5%", "10%", "20%", "40%", "50%", "75%", "100%", "200%")

# 颜色默认值（#RRGGBB，与设置页 Colors2 默认一致）；渲染时从 QSettings 读取，
# 未设置回退这些默认值。stash / commit 无对应设置键，保持硬编码。
_DEFAULT_COLORS = {
    "current_branch": "#c80000",
    "branch": "#00c300",
    "remote": "#ffddaa",
    "tag": "#ffff00",
    "stash": "#808080",
    "commit": "#ffe5e5",
}

_COLORS = {k: QColor(v) for k, v in _DEFAULT_COLORS.items()}

# 工具栏位图：原版 revgraphbar.bmp（20px/格）。索引对应 IDR_REVGRAPHBAR：
# 0 放大 1 缩小 2 100% 3 适合高度 4 适合宽度 5 适合全部
# 6 缩放框占位 7 过滤 8 概览 9 查找
_BAR_ICON = 20
_toolbar_icons_cache: list | None = None


def _toolbar_icons() -> list:
    """把原版 revgraphbar.bmp 切成 20×20 图标（浅灰底转为透明）。"""
    global _toolbar_icons_cache
    if _toolbar_icons_cache is not None:
        return _toolbar_icons_cache
    from pathlib import Path
    icons: list = []
    path = (Path(__file__).resolve().parent.parent
            / "res" / "revgraph" / "revgraphbar.bmp")
    if path.is_file():
        img = QImage(str(path))
        if not img.isNull():
            mask = img.pixelColor(0, 0)
            for i in range(img.width() // _BAR_ICON):
                tile = img.copy(i * _BAR_ICON, 0, _BAR_ICON, _BAR_ICON)
                tile = tile.convertToFormat(QImage.Format.Format_ARGB32)
                for y in range(tile.height()):
                    for x in range(tile.width()):
                        if tile.pixelColor(x, y) == mask:
                            tile.setPixelColor(x, y, QColor(0, 0, 0, 0))
                icons.append(QIcon(QPixmap.fromImage(tile)))
    while len(icons) < 10:
        icons.append(QIcon())
    _toolbar_icons_cache = icons
    return icons


def invalidate() -> None:
    """设置页保存颜色后清空本模块使用的颜色缓存。"""
    from .settings_colors import invalidate as _invalidate
    _invalidate()


def _best_text_color(bg: QColor) -> QColor:
    """按亮度选择黑/白文字（对齐 GetBestContrastColor）。"""
    r = bg.redF()
    g = bg.greenF()
    b = bg.blueF()

    def chan(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    lum = 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)
    return QColor(0, 0, 0) if lum > 0.5 else QColor(255, 255, 255)


def _line_path(rect: QRectF, r: float, top: bool, bottom: bool) -> QPainterPath:
    """一行字形的路径：仅首行圆上角、末行圆下角，其余为直角。"""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = max(0.0, min(r, w / 2, h / 2))
    p = QPainterPath()
    if top:
        p.moveTo(x + r, y)
        p.arcTo(QRectF(x, y, 2 * r, 2 * r), 90, 90)
    else:
        p.moveTo(x, y)
    p.lineTo(x, y + h - (r if bottom else 0))
    if bottom:
        p.arcTo(QRectF(x, y + h - 2 * r, 2 * r, 2 * r), 180, 90)
    else:
        p.lineTo(x, y + h)
    p.lineTo(x + w - (r if bottom else 0), y + h)
    if bottom:
        p.arcTo(QRectF(x + w - 2 * r, y + h - 2 * r, 2 * r, 2 * r), 270, 90)
    else:
        p.lineTo(x + w, y + h)
    p.lineTo(x + w, y + (r if top else 0))
    if top:
        p.arcTo(QRectF(x + w - 2 * r, y, 2 * r, 2 * r), 0, 90)
    else:
        p.lineTo(x + w, y)
    p.closeSubpath()
    return p


def _cut_point(cx: float, cy: float, w: float, h: float, lw: float,
               ps: QPointF, pt: QPointF) -> QPointF:
    """把线段 ps->pt 裁剪到以 (cx,cy) 为中心、尺寸 w×h 的节点边界。"""
    xmin = cx - w / 2 - lw / 2
    xmax = cx + w / 2 + lw / 2
    ymin = cy - h / 2 - lw / 2
    ymax = cy + h / 2 + lw / 2
    dx = pt.x() - ps.x()
    dy = pt.y() - ps.y()
    if dy != 0:
        if pt.y() > ymax:
            x = ps.x() + (ymax - ps.y()) / dy * dx
            if xmin <= x <= xmax:
                return QPointF(x, ymax)
        elif pt.y() < ymin:
            x = ps.x() + (ymin - ps.y()) / dy * dx
            if xmin <= x <= xmax:
                return QPointF(x, ymin)
    if dx != 0:
        if pt.x() > xmax:
            y = ps.y() + (xmax - ps.x()) / dx * dy
            if ymin <= y <= ymax:
                return QPointF(xmax, y)
        elif pt.x() < xmin:
            y = ps.y() + (xmin - ps.x()) / dx * dy
            if ymin <= y <= ymax:
                return QPointF(xmin, y)
    return pt


def _split_revs(text: str) -> list:
    return [t for t in re.split(r"\s+", (text or "").strip()) if t]


def build_load_args(filter_state: dict, sparse: bool = False) -> dict:
    """把过滤条件翻译成 ``GitRevLoglist.load`` 的关键字参数。

    对齐 RevisionGraphDlgFunc.cpp:193-235：
      * 仅当前分支   -> range 加 "HEAD"（不加 --all/--branches）
      * 仅本地分支   -> --branches
      * 都未勾选     -> --all
      * From 非空    -> 每个 token 变成排除项 "^token"（任何模式下都生效）
      * To 非空      -> 仅在两个勾选框都未勾选时作为包含项加入
      * sparse       -> 附加 --sparse（原版「显示分支与合并」勾选时置
                        LOG_INFO_SPARSE）
    """
    state = filter_state or {}
    from_rev = _split_revs(state.get("from_rev", ""))
    to_rev = _split_revs(state.get("to_rev", ""))
    current = bool(state.get("current_branch"))
    local = bool(state.get("local_branches"))

    revisions = ["^" + t for t in from_rev]
    if current:
        revisions.append("HEAD")
    elif local:
        pass
    else:
        revisions.extend(to_rev)

    return {
        "limit": 0,
        "all_branches": not (current or local),
        "local_branches": local and not current,
        "simplify": True,
        "sparse": bool(sparse),
        "revisions": revisions,
    }


def drop_tag_only_commits(commits: list) -> list:
    """「显示所有标签」关闭时，丢掉只被标签标注的提交（对齐原版重写）。

    原版逻辑（RevisionGraphDlgFunc.cpp:260-282）：ShowAllTags 打开时任意标注都
    保留；关闭时只有非标签标注才算数，仅剩标签标注的提交被移除。
    """
    out = []
    for commit in commits:
        infos = list(getattr(commit, "ref_infos", []) or [])
        if infos and all(i.ref_type == "tag" for i in infos):
            continue
        out.append(commit)
    return out


def collapse_linear_chains(commits: list) -> list:
    """折叠没有标注的线性链（对齐原版「显示分支与合并」的重写）。

    仅当某提交满足：无引用标注、恰好 1 个父、恰好 1 个子，且该子也恰好
    1 个父时，才移除它并把子的父直接接到祖父（原版
    RevisionGraphDlgFunc.cpp:284-305 的 splice），从而保证链不断。
    """
    by_hash = {c.hash: c for c in commits}
    labelled = {c.hash for c in commits if getattr(c, "ref_infos", None)}

    children: dict = {}
    for commit in commits:
        for parent in commit.parents or []:
            children.setdefault(parent, []).append(commit.hash)

    drop = set()
    for commit in commits:
        if commit.hash in labelled:
            continue
        parents = list(commit.parents or [])
        kids = children.get(commit.hash, [])
        if len(parents) != 1 or len(kids) != 1:
            continue
        child = by_hash.get(kids[0])
        if child is None or len(list(child.parents or [])) != 1:
            continue
        drop.add(commit.hash)
        child.parents = [parents[0]]      # 子的父接到祖父，链不断

    if not drop:
        return commits
    return [c for c in commits if c.hash not in drop]


class _GraphCanvas(QWidget):
    """绘制提交节点图（x=lane/层坐标，y=层）。"""

    zoomRequested = Signal(float)
    selectionChanged = Signal()
    contextMenuRequested = Signal(QPointF)

    def __init__(self, layout: GraphLayout | None = None,
                 current_branch: str | None = None, parent=None):
        super().__init__(parent)
        self._layout = layout
        self._current_branch = current_branch or ""
        self._zoom = _DEFAULT_ZOOM
        # 选择：与原版一致，最多两个（m_SelectedEntry1 / m_SelectedEntry2）
        self._sel1: str | None = None
        self._sel2: str | None = None
        self._panning = False
        self._pan_origin = None
        self._pan_scroll = (0, 0)
        self._scroll = None            # QScrollArea，由对话框注入
        self._tooltip_provider = None  # callable(hash) -> str
        self._show_overview = False
        self._overview_drag = False
        self._arrow_to_merges = False
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.contextMenuRequested.emit(QPointF(pos)))
        if layout is not None:
            self._apply_min_size()

    def node_count(self) -> int:
        return len(self._layout.order) if self._layout is not None else 0

    def layout(self) -> GraphLayout | None:
        """当前布局（未加载时为 None）。"""
        return self._layout

    # ---- 选择 ----
    def selected(self) -> list:
        return [h for h in (self._sel1, self._sel2) if h]

    def node_at(self, pos) -> str | None:
        """按当前缩放命中节点（返回 hash）。"""
        if self._layout is None:
            return None
        x, y = pos.x(), pos.y()
        for key in reversed(self._layout.order):   # 后画的在上层
            node = self._layout.nodes.get(key)
            if node is None:
                continue
            if (abs(x - node.x * self._zoom) <= node.width * self._zoom / 2
                    and abs(y - node.y * self._zoom)
                    <= node.height * self._zoom / 2):
                return key
        return None

    def select(self, key: str | None, additive: bool = False) -> None:
        """选择逻辑对齐 OnLButtonDown：最多两个，Ctrl 多选。"""
        if key is None:
            self._sel1 = self._sel2 = None
        elif not additive:
            if self._sel1 == key:
                self._sel1 = self._sel2 = None       # 再点一次取消选择
            else:
                self._sel1, self._sel2 = key, None
        elif self._sel1 == key:
            if self._sel2 is not None:
                self._sel1, self._sel2 = self._sel2, None
            else:
                self._sel1 = None
        elif self._sel2 == key:
            self._sel2 = None
        elif self._sel1 is None:
            self._sel1 = key
        elif self._sel2 is None:
            self._sel2 = key
        else:
            self._sel1, self._sel2 = self._sel2, key
        self.update()
        self.selectionChanged.emit()

    def scroll_to(self, key: str) -> None:
        """把节点滚动到视口中央（对齐 ScrollTo）。"""
        if self._layout is None or self._scroll is None:
            return
        node = self._layout.nodes.get(key)
        if node is None:
            return
        vp = self._scroll.viewport()
        self._scroll.horizontalScrollBar().setValue(
            int(node.x * self._zoom - vp.width() / 2))
        self._scroll.verticalScrollBar().setValue(
            int(node.y * self._zoom - vp.height() / 2))

    # ---- 鼠标 / 提示 ----
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        # 概览图内点击/拖动 => 按比例跳转滚动
        if self._show_overview:
            target = self._overview_hit(pos)
            if target is not None and self._scroll is not None:
                self._overview_drag = True
                self._scroll.horizontalScrollBar().setValue(int(target[0]))
                self._scroll.verticalScrollBar().setValue(int(target[1]))
                return
        key = self.node_at(pos)
        if key is not None:
            additive = bool(event.modifiers()
                            & Qt.KeyboardModifier.ControlModifier)
            self.select(key, additive)
            return
        # 空白处：清空选择并开始平移
        self.select(None)
        if self._scroll is not None:
            self._panning = True
            self._pan_origin = pos
            self._pan_scroll = (self._scroll.horizontalScrollBar().value(),
                                self._scroll.verticalScrollBar().value())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):  # noqa: N802
        pos = event.position().toPoint()
        if self._overview_drag and self._show_overview:
            target = self._overview_hit(pos)
            if target is not None and self._scroll is not None:
                self._scroll.horizontalScrollBar().setValue(int(target[0]))
                self._scroll.verticalScrollBar().setValue(int(target[1]))
            return
        if not self._panning or self._scroll is None:
            return
        dx = pos.x() - self._pan_origin.x()
        dy = pos.y() - self._pan_origin.y()
        self._scroll.horizontalScrollBar().setValue(self._pan_scroll[0] - dx)
        self._scroll.verticalScrollBar().setValue(self._pan_scroll[1] - dy)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self._overview_drag:
            self._overview_drag = False
            return
        if self._panning:
            self._panning = False
            self.unsetCursor()

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            # 用 setToolTip 让 Qt 自己显示，避免手工 QToolTip.showText：
            # 后者在某些平台（含 offscreen）会尝试 grab 键盘/raise 窗口并阻塞。
            if self._tooltip_provider:
                key = self.node_at(event.pos())
                self.setToolTip(self._tooltip_provider(key) if key else "")
            return super().event(event)
        return super().event(event)

    def set_layout(self, layout: GraphLayout, current_branch: str | None,
                   font: QFont):
        self._layout = layout
        self._current_branch = current_branch or ""
        self.setFont(font)
        self._apply_min_size()
        self.update()

    def clear_layout(self) -> None:
        """清空图形（加载失败或无可显示内容时）。"""
        self._layout = None
        self.setMinimumSize(0, 0)
        self.update()

    # ---- 缩放 ----
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, float(zoom)))
        if abs(zoom - self._zoom) < 1e-9:
            return
        self._zoom = zoom
        self._apply_min_size()
        self.update()

    def _apply_min_size(self):
        if self._layout is None:
            return
        self.setMinimumSize(
            max(1, int(self._layout.width * self._zoom) + 2),
            max(1, int(self._layout.height * self._zoom) + 2))

    def wheelEvent(self, event):  # noqa: N802
        """Ctrl+滚轮缩放；其余交给滚动区域滚动（对齐 OnMouseWheel）。"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            dy = event.angleDelta().y()
            if dy == 0:
                return
            factor = (1.0 / _ZOOM_STEP) if dy > 0 else _ZOOM_STEP
            self.zoomRequested.emit(self._zoom * factor)
            event.accept()
            return
        event.ignore()

    # ---- 颜色 ----
    def _ref_color(self, text: str, ref_type: str) -> QColor:
        from .settings_colors import bool_value, color
        if ref_type == "branch":
            # RevGraphUseLocalForCur：勾选后用本地分支色画当前分支（不再区分）
            if text == self._current_branch \
                    and not bool_value("RevGraphUseLocalForCur", False):
                return color("Colors/CurrentBranch",
                             _DEFAULT_COLORS["current_branch"])
            return color("Colors/LocalBranch", _DEFAULT_COLORS["branch"])
        if ref_type == "remote":
            return color("Colors/RemoteBranch", _DEFAULT_COLORS["remote"])
        if ref_type == "tag":
            return color("Colors/Tag", _DEFAULT_COLORS["tag"])
        return _COLORS.get(ref_type, _COLORS["commit"])

    # ---- 绘制 ----
    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # 画布底色跟随主题（原版用 COLOR_WINDOW），不再硬编码白色
        p.fillRect(self.rect(), self.palette().base().color())
        if self._layout is None:
            return
        self.render(p, self._zoom)
        if self._show_overview:
            self._draw_overview(p)

    def render(self, p: QPainter, zoom: float) -> None:
        """在给定画笔上按 zoom 绘制整张图（供屏幕绘制与导出复用）。"""
        if self._layout is None:
            return
        p.save()
        p.scale(zoom, zoom)
        self._draw_edges(p)
        self._draw_nodes(p)
        p.restore()

    # ---- 概览缩略图（对齐原版 BuildPreview / 右下角预览 + 视口矩形）----
    def _preview_rect(self):
        """缩略图矩形与当前视口矩形（均为画布坐标）。"""
        if self._scroll is None or self._layout is None:
            return None, None
        vp = self._scroll.viewport()
        hx = self._scroll.horizontalScrollBar().value()
        hy = self._scroll.verticalScrollBar().value()
        view = QRectF(hx, hy, vp.width(), vp.height())
        size = max(120.0, min(vp.width(), vp.height()) / 4.0)
        pad = 10.0
        box = QRectF(hx + vp.width() - size - pad,
                     hy + vp.height() - size - pad, size, size)
        return box, view

    def _draw_overview(self, p: QPainter):
        box, view = self._preview_rect()
        if box is None:
            return
        layout = self._layout
        gw = max(1.0, layout.width)
        gh = max(1.0, layout.height)
        scale = min(box.width() / gw, box.height() / gh)
        off_x = box.x() + (box.width() - gw * scale) / 2.0
        off_y = box.y() + (box.height() - gh * scale) / 2.0

        p.save()
        p.setPen(QPen(QColor(0, 0, 0, 160)))
        p.setBrush(QBrush(QColor(255, 255, 255, 200)))
        p.drawRect(box)
        # 缩略图：只画节点小方块，够看清拓扑即可
        p.setPen(Qt.PenStyle.NoPen)
        for key in layout.order:
            node = layout.nodes.get(key)
            if node is None:
                continue
            p.setBrush(QBrush(self._ref_color(node.lines[0][0], node.lines[0][1])
                              if node.lines else _COLORS["commit"]))
            p.drawRect(QRectF(off_x + (node.x - node.width / 2) * scale,
                              off_y + (node.y - node.height / 2) * scale,
                              max(1.0, node.width * scale),
                              max(1.0, node.height * scale)))
        # 视口矩形
        p.setBrush(QBrush(QColor(0, 0, 0, 64)))
        p.setPen(QPen(QColor(0, 0, 0, 200)))
        p.drawRect(QRectF(off_x + view.x() * scale, off_y + view.y() * scale,
                          view.width() * scale, view.height() * scale))
        p.restore()

    def _overview_hit(self, pos):
        """点击是否落在缩略图内；是则返回目标滚动位置。"""
        box, _view = self._preview_rect()
        if box is None or not box.contains(QPointF(pos)):
            return None
        layout = self._layout
        gw = max(1.0, layout.width)
        gh = max(1.0, layout.height)
        scale = min(box.width() / gw, box.height() / gh)
        off_x = box.x() + (box.width() - gw * scale) / 2.0
        off_y = box.y() + (box.height() - gh * scale) / 2.0
        gx = (pos.x() - off_x) / scale
        gy = (pos.y() - off_y) / scale
        vp = self._scroll.viewport()
        return (gx - vp.width() / 2.0, gy - vp.height() / 2.0)

    def set_show_overview(self, on: bool) -> None:
        self._show_overview = bool(on)
        self.update()

    def show_overview(self) -> bool:
        return self._show_overview

    def _draw_edges(self, p: QPainter):
        assert self._layout is not None
        pen = QPen(QColor(0, 0, 0), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for e in self._layout.edges:
            pts = [QPointF(x, y) for x, y in e.points]
            if len(pts) < 2:
                continue
            src = self._layout.node(e.source)
            dst = self._layout.node(e.target)
            if src is not None:
                pts[0] = _cut_point(src.x, src.y, src.width, src.height, 1,
                                    pts[0], pts[1])
            if dst is not None:
                pts[-1] = _cut_point(dst.x, dst.y, dst.width, dst.height, 1,
                                     pts[-1], pts[-2])
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            p.drawPath(path)
            # 箭头默认指向父提交（末段）；ArrowPointToMerges 时改指首段
            if self._arrow_to_merges:
                self._draw_arrow(p, pts[0], pts[1])
            else:
                self._draw_arrow(p, pts[-1], pts[-2])

    def _draw_arrow(self, p: QPainter, tip: QPointF, prev: QPointF):
        dx = (prev.x() - tip.x()) * -1
        dy = (prev.y() - tip.y()) * -1
        length = math.hypot(dx, dy)
        if length == 0:
            return
        dx = _ARROW_SIZE * dx / length
        dy = _ARROW_SIZE * dy / length
        p1x = dx * _ARROW_COS - dy * _ARROW_SIN
        p1y = dx * _ARROW_SIN + dy * _ARROW_COS
        p2x = dx * _ARROW_COS + dy * _ARROW_SIN
        p2y = -dx * _ARROW_SIN + dy * _ARROW_COS
        d = -1.0
        a0 = QPointF(tip.x() + d * dx * 3 / 5, tip.y() + d * dy * 3 / 5)
        a1 = QPointF(tip.x() + d * p1x, tip.y() + d * p1y)
        a2 = tip
        a3 = QPointF(tip.x() + d * p2x, tip.y() + d * p2y)
        arrow = QPainterPath(a0)
        arrow.lineTo(a1)
        arrow.lineTo(a2)
        arrow.lineTo(a3)
        arrow.lineTo(a0)
        p.drawPath(arrow)

    def _draw_nodes(self, p: QPainter):
        assert self._layout is not None
        for key in self._layout.order:
            node = self._layout.nodes.get(key)
            if node is None:
                continue
            lines = node.lines or [(key[:8], "commit")]
            n = len(lines)
            lh = node.height / n
            left = node.x - node.width / 2
            top = node.y - node.height / 2
            for i, (text, ref_type) in enumerate(lines):
                rect = QRectF(left, top + i * lh, node.width, lh)
                fill = self._ref_color(text, ref_type)
                path = _line_path(rect, _CORNER, i == 0, i == n - 1)
                p.setPen(QPen(QColor(0, 0, 0, 0), 0))
                p.setBrush(QBrush(fill))
                p.drawPath(path)
                p.setPen(QPen(_best_text_color(fill)))
                p.setFont(self.font())
                p.drawText(QRectF(rect.x() + _MARGIN_X, rect.y() + _MARGIN_Y,
                                  rect.width() - 2 * _MARGIN_X,
                                  rect.height() - 2 * _MARGIN_Y),
                           int(Qt.AlignmentFlag.AlignLeft
                               | Qt.AlignmentFlag.AlignVCenter),
                           text)
            # 选中标记：I / II（对齐 DrawSelectedEntry 的 I、II 罗马数字）
            marker = ("I" if key == self._sel1
                      else "II" if key == self._sel2 else "")
            if marker:
                box = QRectF(left, top, node.width, node.height)
                pen = QPen(QColor(0, 0, 0), 2)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(box.adjusted(-3, -3, 3, 3), _CORNER, _CORNER)
                p.setPen(QPen(QColor(0, 0, 0)))
                p.setFont(self.font())
                p.drawText(
                    QRectF(box.x() - 16, box.y(), 14, box.height()),
                    int(Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter),
                    marker)


class RevisionGraphDlg(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.setWindowTitle(
            f"{repo.name} — {tr('revgraph_title', 'Revision Graph')}")
        self.resize(900, 640)

        self._filter: dict = {}
        self._filter_active = False
        self._loading = False
        self._error = ""
        self._node_count = 0
        self._commits: dict = {}
        self._find_dlg = None
        # 三个显示开关（默认值对齐原版 InitialSetMenu）
        self._show_all_tags = True
        self._show_branchings_merges = False
        self._arrow_to_merges = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_menubar())
        lay.addWidget(self._build_toolbar())

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.canvas = _GraphCanvas(None, None, self.scroll)
        self.canvas.zoomRequested.connect(self._on_zoom_requested)
        self.canvas.selectionChanged.connect(self._on_selection_changed)
        self.canvas.contextMenuRequested.connect(self._on_canvas_menu)
        self.canvas._scroll = self.scroll
        self.canvas._tooltip_provider = self._tooltip_for
        self.scroll.setWidget(self.canvas)
        lay.addWidget(self.scroll, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 2, 4, 2)
        self.status_label = QLabel("", self)
        bottom.addWidget(self.status_label, 1)
        self.btn_stats = QPushButton(tr("revgraph_stats", "Statistics"), self)
        self.btn_stats.clicked.connect(self._open_stats)
        bottom.addWidget(self.btn_stats)
        lay.addLayout(bottom)

        self._sync_zoom_box()
        self._load()

    # ---- 菜单栏（对齐 IDR_REVISIONGRAPH：File / View / Git / Help）----
    def _build_menubar(self) -> QMenuBar:
        bar = QMenuBar(self)
        self.menu_file = bar.addMenu(tr("revgraph_menu_file", "&File"))
        self.act_save = self.menu_file.addAction(
            tr("revgraph_save_graphas", "&Save graph as..."))
        self.act_save.triggered.connect(self._save_graph)
        self.menu_file.addSeparator()
        act_exit = self.menu_file.addAction(tr("revgraph_menu_exit", "E&xit"))
        act_exit.triggered.connect(self.close)

        self.menu_view = bar.addMenu(tr("revgraph_menu_view", "&View"))
        self.act_zoom_in = self.menu_view.addAction(
            tr("revgraph_menu_zoomin", "Zoom &in"))
        self.act_zoom_out = self.menu_view.addAction(
            tr("revgraph_menu_zoomout", "Zoom &out"))
        self.act_zoom_100 = self.menu_view.addAction(
            tr("revgraph_menu_zoom100", "Zoom to &100%"))
        self.act_fit_height = self.menu_view.addAction(
            tr("revgraph_menu_fitheight", "Fit height"))
        self.act_fit_width = self.menu_view.addAction(
            tr("revgraph_menu_fitwidth", "Fit width"))
        self.act_fit_all = self.menu_view.addAction(
            tr("revgraph_menu_fitall", "Fit graph"))
        self.act_zoom_in.triggered.connect(
            lambda: self._zoom_by(1.0 / _ZOOM_STEP))
        self.act_zoom_out.triggered.connect(lambda: self._zoom_by(_ZOOM_STEP))
        self.act_zoom_100.triggered.connect(
            lambda: self._set_zoom(_DEFAULT_ZOOM))
        self.act_fit_height.triggered.connect(lambda: self._zoom_fit("height"))
        self.act_fit_width.triggered.connect(lambda: self._zoom_fit("width"))
        self.act_fit_all.triggered.connect(lambda: self._zoom_fit("all"))
        self.act_zoom_in.setShortcut(QKeySequence("Ctrl++"))
        self.act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.menu_view.addSeparator()
        self.act_filter = self.menu_view.addAction(
            tr("revgraph_filter", "Filter"))
        self.act_filter.setCheckable(True)
        self.act_filter.triggered.connect(self._open_filter)
        self.menu_view.addSeparator()
        self.act_overview = self.menu_view.addAction(
            tr("revgraph_overview", "Overview"))
        self.act_overview.setCheckable(True)
        self.act_overview.toggled.connect(self._on_overview_toggled)
        self.act_branchings = self.menu_view.addAction(
            tr("revgraph_show_branchings", "Show branchings and merges"))
        self.act_branchings.setCheckable(True)
        self.act_branchings.setChecked(self._show_branchings_merges)
        self.act_branchings.toggled.connect(self._on_show_branchings)
        self.act_all_tags = self.menu_view.addAction(
            tr("revgraph_show_all_tags", "Show all tags"))
        self.act_all_tags.setCheckable(True)
        self.act_all_tags.setChecked(self._show_all_tags)
        self.act_all_tags.toggled.connect(self._on_show_all_tags)
        self.act_arrow = self.menu_view.addAction(
            tr("revgraph_arrow_to_merges", "Arrows point towards merges"))
        self.act_arrow.setCheckable(True)
        self.act_arrow.setChecked(self._arrow_to_merges)
        self.act_arrow.toggled.connect(self._on_arrow_to_merges)

        self.menu_git = bar.addMenu(tr("revgraph_menu_git", "&Git"))
        self.act_cmp = self.menu_git.addAction(
            tr("revgraph_popup_comparerevs", "Compare revisions"))
        self.act_cmp_heads = self.menu_git.addAction(
            tr("revgraph_popup_compareheads", "Compare HEAD revisions"))
        self.act_udiff = self.menu_git.addAction(
            tr("revgraph_popup_unidiffrevs", "Unified diff"))
        self.act_udiff_heads = self.menu_git.addAction(
            tr("revgraph_popup_unidiffheads", "Unified diff of HEAD revisions"))
        self.act_cmp.triggered.connect(lambda: self._menu_compare(False))
        self.act_udiff.triggered.connect(lambda: self._menu_compare(True))

        self.menu_help = bar.addMenu(tr("revgraph_menu_help", "&Help"))
        self.act_help = self.menu_help.addAction(tr("help", "Help"))
        self.act_help.triggered.connect(self._on_help)
        return bar

    # ---- 工具栏（对齐 IDR_REVGRAPHBAR 的按钮顺序与原版位图）----
    def _build_toolbar(self) -> QToolBar:
        icons = _toolbar_icons()
        bar = QToolBar(self)
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setIconSize(QSize(_BAR_ICON, _BAR_ICON))
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        def add(act: QAction, icon: int, tip_key: str, tip_default: str):
            act.setIcon(icons[icon])
            act.setToolTip(tr(tip_key, tip_default))
            bar.addAction(act)
            return act

        # 菜单动作与工具栏共用同一批 QAction（勾选状态自然同步）
        add(self.act_zoom_in, 0, "revgraph_zoom_in_tip", "Zoom in")
        add(self.act_zoom_out, 1, "revgraph_zoom_out_tip", "Zoom out")
        add(self.act_zoom_100, 2, "revgraph_zoom_100_tip", "Zoom 100%")
        add(self.act_fit_height, 3, "revgraph_zoom_height_tip", "Fit height")
        add(self.act_fit_width, 4, "revgraph_zoom_width_tip", "Fit width")
        add(self.act_fit_all, 5, "revgraph_zoom_all_tip", "Fit whole graph")
        bar.addSeparator()

        self.zoom_box = QComboBox(bar)
        self.zoom_box.setEditable(True)
        self.zoom_box.addItems(_ZOOM_PRESETS)
        self.zoom_box.setFixedWidth(80)
        self.zoom_box.setToolTip(tr("revgraph_zoom_tip", "Zoom factor"))
        self.zoom_box.activated.connect(self._on_zoom_box)
        self.zoom_box.lineEdit().editingFinished.connect(
            lambda: self._on_zoom_box(None))
        bar.addWidget(self.zoom_box)
        bar.addSeparator()

        add(self.act_filter, 7, "revgraph_filter_tip",
            "Filter the revision graph")
        bar.addSeparator()
        add(self.act_overview, 8, "revgraph_overview_tip",
            "Show the overview map")
        bar.addSeparator()

        self.act_find = QAction(self)
        self.act_find.setShortcut(QKeySequence("Ctrl+F"))
        self.act_find.triggered.connect(self._open_find)
        add(self.act_find, 9, "revgraph_find_tip", "Find in graph (Ctrl+F)")

        # 兼容旧属性名（测试/外部引用）
        self.btn_filter = self.act_filter
        self.btn_find = self.act_find
        self.btn_overview = self.act_overview
        return bar

    def _menu_compare(self, unified: bool):
        selected = self.canvas.selected()
        if len(selected) == 2:
            r1 = self._friend_ref_name(selected[0])
            r2 = self._friend_ref_name(selected[1])
        elif len(selected) == 1:
            r1 = self._friend_ref_name(selected[0])
            r2 = "HEAD"
        else:
            return
        if unified:
            self._do_unified(r1, r2)
        else:
            self._do_compare(r1, r2)

    def _on_help(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, tr("help", "Help"),
                                tr("revgraph_help", "Revision graph"))

    # ---- 显示开关（对齐 InitialSetMenu / UpdateFullHistory）----
    def _on_show_all_tags(self, on: bool):
        if bool(on) == self._show_all_tags:
            return
        self._show_all_tags = bool(on)
        self.refresh()                      # 原版：切换后重新拉取

    def _on_show_branchings(self, on: bool):
        if bool(on) == self._show_branchings_merges:
            return
        self._show_branchings_merges = bool(on)
        self.refresh()

    def _on_arrow_to_merges(self, on: bool):
        self._arrow_to_merges = bool(on)
        canvas = getattr(self, "canvas", None)
        if canvas is not None:
            canvas._arrow_to_merges = bool(on)
            canvas.update()

    def _on_overview_toggled(self, on: bool):
        canvas = getattr(self, "canvas", None)
        if canvas is not None:
            canvas.set_show_overview(bool(on))

    # ---- 概览 ----
    def _toggle_overview(self):
        """把概览对齐到当前勾选状态（act_overview 与工具栏共用同一 QAction）。"""
        self._on_overview_toggled(self.act_overview.isChecked())

    # ---- 另存为（对齐 OnFileSavegraphas / SaveGraphAs）----
    @staticmethod
    def save_formats() -> list:
        """可用的位图扩展名：以 Qt 实际支持写入的格式为准。

        原版过滤器是固定的 svg/wmf/jpg/png/bmp/gif；这里按运行时能力裁剪，
        避免用户选完路径才报"不支持"（例如某些 Qt 构建没有 GIF 写入插件）。
        """
        from PySide6.QtGui import QImageWriter
        supported = {bytes(f).decode().lower()
                     for f in QImageWriter.supportedImageFormats()}
        return [e for e in (".png", ".jpg", ".jpeg", ".bmp", ".gif")
                if e.lstrip(".") in supported]

    def _save_filter(self) -> str:
        patterns = " ".join(["*.svg"] + [f"*{e}" for e in self.save_formats()])
        return ";;".join([
            format_string(tr("revgraph_save_filter_pictures", "Pictures ({patterns})"),
                          patterns=patterns),
            tr("revgraph_save_filter_graphviz", "Graphs (*.gv)"),
            tr("revgraph_save_filter_all", "All Files (*)"),
        ])

    def _save_graph(self):
        import os
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        if self.canvas.layout() is None:
            QMessageBox.information(
                self, tr("revgraph_save", "Save graph as…"),
                tr("revgraph_nograph", "No graph available"))
            return
        filters = self._save_filter()
        start = os.path.join(self.repo.root, f"{self.repo.name}-revgraph.png")
        path, chosen = QFileDialog.getSaveFileName(
            self, tr("revgraph_save", "Save graph as…"), start, filters)
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if not ext:
            # 原版按过滤器索引补默认扩展名：Pictures -> .svg，Graphs -> .gv
            ext = ".gv" if "gv" in (chosen or "") else ".svg"
            path += ext
        try:
            self._write_graph(path, ext)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, tr("error"),
                format_string(tr("revgraph_save_failed", "Could not save: {message}"),
                              message=str(exc)))
            return
        self.status_label.setText(
            format_string(tr("revgraph_saved", "Saved to {path}"), path=path))

    def _write_graph(self, path: str, ext: str) -> None:
        """把当前图形写入 path（按扩展名分派）。不支持时抛异常由调用方提示。"""
        from PySide6.QtGui import QImage, QPainter

        layout = self.canvas.layout()
        if layout is None:
            raise RuntimeError(tr("revgraph_nograph", "No graph available"))
        zoom = self.canvas.zoom()
        width = max(1, int(layout.width * zoom) + 2)
        height = max(1, int(layout.height * zoom) + 2)

        if ext == ".gv":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._graphviz_text())
            return

        if ext == ".svg":
            from PySide6.QtSvg import QSvgGenerator
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(QSize(width, height))
            gen.setViewBox(QRect(0, 0, width, height))
            gen.setTitle(tr("revgraph_title", "Revision Graph"))
            painter = QPainter(gen)
            painter.fillRect(0, 0, width, height,
                             self.canvas.palette().base().color())
            self.canvas.render(painter, zoom)
            painter.end()
            return

        if ext in (".wmf", ".emf"):
            raise RuntimeError(tr(
                "revgraph_save_nowmf",
                "Windows metafile export is not supported; "
                "use SVG, PNG or .gv instead."))

        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(self.canvas.palette().base().color())
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.canvas.render(painter, zoom)
        painter.end()
        fmt = {".jpg": "JPG", ".jpeg": "JPG", ".bmp": "BMP",
               ".gif": "GIF"}.get(ext, "PNG")
        if not image.save(path, fmt):
            raise RuntimeError(
                f"{ext} is not supported by this Qt build; "
                f"available: {', '.join(self.save_formats())}")

    def _graphviz_text(self) -> str:
        """导出 GraphViz DOT（对齐原版的 .gv 输出）。"""
        layout = self.canvas.layout()
        assert layout is not None
        lines = ["digraph revisiongraph {", "  rankdir=TB;"]
        for key in layout.order:
            node = layout.nodes.get(key)
            if node is None:
                continue
            label = "\\n".join(text for text, _t in (node.lines or [])) or key[:8]
            lines.append(f'  "{key}" [label="{label}"];')
        for edge in layout.edges:
            lines.append(f'  "{edge.source}" -> "{edge.target}";')
        lines.append("}")
        return "\n".join(lines) + "\n"

    # ---- 缩放 ----
    def _sync_zoom_box(self):
        from PySide6.QtCore import QSignalBlocker
        with QSignalBlocker(self.zoom_box):
            self.zoom_box.setEditText(f"{self.canvas.zoom() * 100:.0f}%")

    def _set_zoom(self, zoom: float):
        self.canvas.set_zoom(zoom)
        self._sync_zoom_box()

    def _zoom_by(self, factor: float):
        self._set_zoom(self.canvas.zoom() * factor)

    def _on_zoom_requested(self, zoom: float):
        self._set_zoom(zoom)

    def _on_zoom_box(self, _index):
        text = self.zoom_box.currentText().strip().rstrip("%").strip()
        try:
            value = float(text)
        except ValueError:
            self._sync_zoom_box()
            return
        if value <= 0:
            self._sync_zoom_box()
            return
        self._set_zoom(value / 100.0)

    def _zoom_fit(self, mode: str):
        """适合高度/宽度/全部（对齐 OnViewZoomheight/Width/All）。"""
        layout = self.canvas.layout()
        if layout is None or layout.width <= 0 or layout.height <= 0:
            return
        vp = self.scroll.viewport().size()
        fx = (vp.width() - 4) / (layout.width + 4)
        fy = (vp.height() - 4) / (layout.height + 4)
        if mode == "height":
            zoom = fy
        elif mode == "width":
            zoom = fx
        else:
            zoom = min(fx, fy)
        self._set_zoom(zoom)

    # ---- 过滤（对齐 OnViewFilter：改条件后重新拉取）----
    def _open_filter(self):
        from .revgraphfilterdlg import RevGraphFilterDlg
        dlg = RevGraphFilterDlg(self.repo, parent=self, state=self._filter)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.btn_filter.setChecked(self._filter_active)
            return
        self._filter = dlg.state()
        self._filter_active = any((
            self._filter.get("from_rev"), self._filter.get("to_rev"),
            self._filter.get("current_branch"),
            self._filter.get("local_branches")))
        self.btn_filter.setChecked(self._filter_active)
        self.refresh()

    # ---- 加载 ----
    def refresh(self):
        """重新拉取并重排（原版 StartWorkerThread）。"""
        self._loading = True
        self._error = ""
        self._update_status()
        self._load()

    def _load(self):
        run_async(self._load_bg, on_done=self._on_loaded,
                  on_error=self._on_load_error, parent=self)

    def _load_bg(self) -> list:
        log = GitRevLoglist(self.repo)
        log.load(**build_load_args(self._filter,
                                  sparse=self._show_branchings_merges))
        commits = list(log)
        # 对齐原版：!ShowAllTags || ShowBranchingsMerges 时做后置重写
        if not self._show_all_tags:
            commits = drop_tag_only_commits(commits)
        if self._show_branchings_merges:
            commits = collapse_linear_chains(commits)
        return commits

    def _on_loaded(self, commits):
        self._loading = False
        self._error = ""
        font = QFont()
        font.setPointSize(_FONT_SIZE)
        fm = QFontMetricsF(font)

        def measure(text: str):
            return float(fm.horizontalAdvance(text)), float(fm.height())

        layout = build_layout(commits, measure)
        self._node_count = len(layout.order)
        self._commits = {c.hash: c for c in commits}
        self.canvas.set_layout(layout, self.repo.current_branch(), font)
        self._sync_zoom_box()
        self._update_status()

    def _on_load_error(self, message: str, _traceback: str = ""):
        self._loading = False
        self._error = str(message or "")
        self._node_count = 0
        self.canvas.clear_layout()
        self._update_status()

    def _update_status(self):
        """状态栏（原版状态栏内容被注释掉，这里给出节点数与过滤状态）。"""
        if self._loading:
            self.status_label.setText(tr("revgraph_loading", "Loading…"))
            return
        if self._error:
            self.status_label.setText(
                format_string(tr("revgraph_status_error", "Error: {message}"),
                              message=self._error))
            return
        if self._node_count == 0:
            self.status_label.setText(
                tr("revgraph_nograph", "No graph available"))
            return
        text = format_string(tr("revgraph_status_nodes", "{count} nodes"),
                             count=self._node_count)
        if self._filter_active:
            text += " · " + tr("revgraph_status_filtered", "filtered")
        self.status_label.setText(text)

    def _open_stats(self):
        from .modeless import show_modeless
        show_modeless(StatGraphDlg(self.repo, parent=self))

    # ------------------------------------------------------------------
    # P1：选择 / 提示 / 键盘 / 查找 / 右键菜单
    # ------------------------------------------------------------------
    def _commit(self, key: str):
        return self._commits.get(key) if key else None

    def _refs_of(self, key: str) -> list:
        """该提交上的完整引用名（refs/heads/xxx 形式）。"""
        commit = self._commit(key)
        if commit is None:
            return []
        out = []
        for info in getattr(commit, "ref_infos", []) or []:
            if info.fullname:
                out.append(info.fullname)
        return out

    def _friend_ref_name(self, key: str) -> str:
        """对齐 GetFriendRefName：优先第一个引用名，无引用时退回完整 hash。"""
        refs = self._refs_of(key)
        return refs[0] if refs else key

    def _local_branches_of(self, key: str) -> list:
        commit = self._commit(key)
        if commit is None:
            return []
        cur = self.repo.current_branch()
        out = []
        for info in getattr(commit, "ref_infos", []) or []:
            if getattr(info, "ref_type", "") != "branch":
                continue
            name = info.shortname
            if name and name != cur:
                out.append(name)
        return out

    def _deleteable_refs(self, key: str) -> list:
        """除当前分支外的全部引用（对齐 GetFriendRefNames(..., &currentBranch)）。"""
        cur = "refs/heads/" + self.repo.current_branch()
        return [r for r in self._refs_of(key) if r != cur]

    def _on_selection_changed(self):
        self._update_status()
        self._update_menu_state()

    def _update_menu_state(self):
        """Git 菜单项按选中数启用（对齐原版 GRAYED 条件）。"""
        n = len(self.canvas.selected())
        one = n == 1
        two = n == 2
        self.act_cmp.setEnabled(two)
        self.act_udiff.setEnabled(two)
        self.act_cmp_heads.setEnabled(one)
        self.act_udiff_heads.setEnabled(one)

    def _tooltip_for(self, key: str) -> str:
        """节点悬停提示（对齐 TooltipText：hash/作者/日期/标题/正文）。"""
        commit = self._commit(key)
        if commit is None:
            return ""
        lines = [commit.hash]
        author = (f"{commit.author_name} <{commit.author_email}>"
                  if getattr(commit, "author_email", "") else commit.author_name)
        date = ""
        dt = getattr(commit, "author_date_dt", None)
        if dt is not None:
            date = dt.strftime("%Y-%m-%d %H:%M")
        elif getattr(commit, "author_date", ""):
            date = str(commit.author_date)[:16]
        lines.append(f"{author}  {date}".rstrip())
        lines.append("")
        lines.append(getattr(commit, "subject", "") or "")
        body = getattr(commit, "body", "") or ""
        if body:
            lines.append(body)
        text = "\n".join(lines).strip()
        return text[:8000] + ("..." if len(text) > 8000 else "")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_F5:
            self.refresh()
            return
        if (key == Qt.Key.Key_F
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._open_find()
            return
        super().keyPressEvent(event)

    def _find_items(self):
        out = []
        for key in (self.canvas.layout().order
                    if self.canvas.layout() is not None else []):
            commit = self._commit(key)
            refs = " ".join(r.split("/")[-1] for r in self._refs_of(key))
            subject = getattr(commit, "subject", "") if commit else ""
            out.append((key, refs, subject or ""))
        return out

    def _open_find(self):
        from .revgraphfinddlg import RevGraphFindDlg
        if getattr(self, "_find_dlg", None) is None:
            self._find_dlg = RevGraphFindDlg(self._find_items(), parent=self)
            self._find_dlg.activated.connect(self._goto_node)
            self._find_dlg.finished.connect(
                lambda *_: setattr(self, "_find_dlg", None))
            self._find_dlg.show()
        else:
            self._find_dlg.set_items(self._find_items())
            self._find_dlg.raise_()
            self._find_dlg.activateWindow()

    def _goto_node(self, key: str):
        self.canvas.select(key)
        self.canvas.scroll_to(key)

    # ---- 右键菜单（对齐 OnContextMenu / ShowContextMenu）----
    def _on_canvas_menu(self, pos: QPointF):
        key = self.canvas.node_at(pos.toPoint())
        if key is None:
            # 原版在空白处不弹菜单
            return
        selected = self.canvas.selected()
        if key not in selected:
            self.canvas.select(key)
            selected = [key]
        self._show_node_menu(pos.toPoint(), selected)

    def _show_node_menu(self, pos, selected):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        actions = self._build_node_menu(menu, selected)
        chosen = menu.exec(self.canvas.mapToGlobal(pos))
        if chosen is None:
            return
        self._dispatch_node_menu(chosen, actions, selected)

    def _build_node_menu(self, menu, selected) -> dict:
        """按选择数构建菜单（对齐 ShowContextMenu 的条件分支）。

        返回 {动作名: QAction 或子菜单}，供 _dispatch_node_menu 分派；
        单独拆出来是为了不依赖 menu.exec 就能测试菜单内容。
        """
        one = len(selected) == 1
        two = len(selected) == 2
        key1 = selected[0]
        actions: dict = {}

        actions["showlog"] = menu.addAction(
            _icon("IDI_LOG"), tr("revgraph_popup_showlog", "Show &log"))
        if one:
            actions["browserepo"] = menu.addAction(
                _icon("IDI_REPOBROWSE"),
                tr("revgraph_popup_browserepo", "&Browse repository"))
            menu.addSeparator()
            branches = self._local_branches_of(key1)
            if len(branches) == 1:
                act = menu.addAction(format_string(
                    tr("revgraph_popup_switch_one",
                       '&Switch/Checkout to "{name}"'), name=branches[0]))
                act.setData([branches[0]])
                actions["switch"] = act
            elif len(branches) > 1:
                sub = menu.addMenu(tr("revgraph_popup_switch",
                                      "&Switch/Checkout to"))
                for name in branches:
                    sub.addAction(name).setData([name])
                actions["switch"] = sub
            elif self._refs_of(key1):
                actions["switch_rev"] = menu.addAction(
                    tr("revgraph_popup_switch_this", "Sw&itch/Checkout to this…"))
            menu.addSeparator()
            actions["copyrefs"] = menu.addAction(
                _icon("IDI_COPYCLIP"),
                tr("revgraph_popup_copyrefs", "Copy ref names"))
            refs = self._deleteable_refs(key1)
            if len(refs) == 1:
                act = menu.addAction(_icon("IDI_DELETE"), format_string(
                    tr("revgraph_popup_delete_one", "&Delete {name}"),
                    name=refs[0]))
                act.setData(refs)
                actions["delete"] = act
            elif len(refs) > 1:
                sub = menu.addMenu(tr("revgraph_popup_delete",
                                      "&Delete branch/tag"))
                for name in refs:
                    sub.addAction(name).setData([name])
                sub.addAction(tr("revgraph_popup_delete_all", "All")).setData(
                    list(refs))
                actions["delete"] = sub
            menu.addSeparator()
            actions["cmp_heads"] = menu.addAction(
                _icon("IDI_DIFF"),
                tr("revgraph_popup_compareheads", "Compare &HEAD revisions"))
            actions["udiff_heads"] = menu.addAction(
                _icon("IDI_DIFF"),
                tr("revgraph_popup_unidiffheads",
                   "Unified &diff of HEAD revisions"))
            actions["cmp_wt"] = menu.addAction(
                _icon("IDI_DIFF"),
                tr("revgraph_popup_comparewt", "Compare with &working tree"))
        if two:
            actions["cmp"] = menu.addAction(
                _icon("IDI_DIFF"),
                tr("revgraph_popup_comparerevs", "&Compare revisions"))
            actions["udiff"] = menu.addAction(
                _icon("IDI_DIFF"),
                tr("revgraph_popup_unidiffrevs", "&Unified diff"))
        return actions

    def _dispatch_node_menu(self, chosen, actions, selected):
        key1 = selected[0]
        matched = False
        for name, act in actions.items():
            if chosen is act:
                matched = name
                break
            # 子菜单项：QAction.parent() 指向所在子菜单
            sub = act
            if hasattr(sub, "menu") or sub.__class__.__name__ == "QMenu":
                if chosen.parent() is sub:
                    data = chosen.data()
                    if data:
                        if name == "switch":
                            self._do_switch(str(data[0]))
                        elif name == "delete":
                            self._do_delete_refs(list(data))
                    return
        if not matched:
            return
        if matched == "showlog":
            self._do_show_log(selected)
        elif matched == "browserepo":
            self._do_browse_repo(key1)
        elif matched == "switch_rev":
            self._do_switch_dialog(self._friend_ref_name(key1))
        elif matched == "copyrefs":
            self._do_copy_refs(key1)
        elif matched == "cmp_heads":
            self._do_compare(self._friend_ref_name(key1), "HEAD")
        elif matched == "udiff_heads":
            self._do_unified(self._friend_ref_name(key1), "HEAD")
        elif matched == "cmp_wt":
            self._do_compare(self._friend_ref_name(key1), None)
        elif matched == "cmp":
            self._do_compare(self._friend_ref_name(selected[0]),
                             self._friend_ref_name(selected[1]))
        elif matched == "udiff":
            self._do_unified(self._friend_ref_name(selected[0]),
                             self._friend_ref_name(selected[1]))

    # ---- 菜单动作实现 ----
    def _do_show_log(self, selected):
        from .logdlg import LogDlg
        from .modeless import show_modeless
        dlg = LogDlg(self.repo, rev=selected[0], parent=self)
        show_modeless(dlg)

    def _do_browse_repo(self, key):
        from .repobrowserdlg import RepositoryBrowserDlg
        from .modeless import show_modeless
        show_modeless(RepositoryBrowserDlg(
            self.repo, rev=self._friend_ref_name(key), parent=self))

    def _do_switch(self, ref):
        result = self.repo.runner.run("checkout", ref)
        if result.returncode != 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("error"), result.stderr or result.stdout)
        self.refresh()

    def _do_switch_dialog(self, ref):
        from .gitswitchdlg import GitSwitchDlg
        dlg = GitSwitchDlg(self.repo, parent=self, commit=ref)
        if dlg.exec():
            self.refresh()

    def _do_copy_refs(self, key):
        from ..utils.clipboard import ClipboardHelper
        refs = self._refs_of(key)
        ClipboardHelper().copy_text("\n".join(refs) if refs else key)

    def _do_delete_refs(self, refs):
        from PySide6.QtWidgets import QMessageBox
        names = ", ".join(r.split("/")[-1] for r in refs)
        resp = QMessageBox.question(
            self, tr("confirm"),
            format_string(tr("revgraph_delete_confirm", 'Delete "{names}"?'),
                          names=names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        for ref in refs:
            if ref.startswith("refs/heads/"):
                args = ["branch", "-D", ref[len("refs/heads/"):]]
            elif ref.startswith("refs/tags/"):
                args = ["tag", "-d", ref[len("refs/tags/"):]]
            elif ref.startswith("refs/remotes/"):
                args = ["branch", "-dr", ref[len("refs/remotes/"):]]
            else:
                args = ["update-ref", "-d", ref]
            result = self.repo.runner.run(*args)
            if result.returncode != 0:
                QMessageBox.warning(
                    self, tr("error"), result.stderr or result.stdout)
                break
        self.refresh()

    def _do_compare(self, rev1: str, rev2: str | None):
        from .diffdlg import DiffDlg
        from .modeless import show_modeless
        show_modeless(DiffDlg(self.repo, rev1=rev1, rev2=rev2, parent=self))

    def _do_unified(self, rev1: str, rev2: str | None):
        from .modeless import show_modeless
        from .patchviewdlg import PatchViewDlg
        args = ["diff", rev1]
        if rev2:
            args.append(rev2)
        result = self.repo.runner.run(*args)
        show_modeless(PatchViewDlg(
            result.stdout or result.stderr or "",
            title=f"{rev1[:8]}..{(rev2 or 'worktree')[:8]}", parent=self))


def _icon(name: str):
    try:
        from ..res import icons
        return icons.icon(name)
    except Exception:  # noqa: BLE001
        from PySide6.QtGui import QIcon
        return QIcon()
