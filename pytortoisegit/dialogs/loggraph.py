# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""loggraph.py —— 对齐 CGitLogListBase::paintGraphLane / LOGLIST_ACTION 图标。"""

from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

from ..git.lanes import COLORS_NUM, LaneType, is_merge
from .loglists import LOG_COL_ACTIONS, LOG_COL_GRAPH

# Colors.cpp BranchLine1..8 默认值
_LANE_COLORS = (
    QColor(0, 0, 0),
    QColor(0xFF, 0, 0),
    QColor(0, 0xFF, 0),
    QColor(0, 0, 0xFF),
    QColor(128, 128, 128),
    QColor(128, 128, 0),
    QColor(0, 128, 128),
    QColor(128, 0, 128),
)

_LINE_WIDTH = 2
_NODE_SIZE = 10

_ACTION_ICONS = (
    ("M", "IDI_ACTIONMODIFIED"),
    ("A", "IDI_ACTIONADDED"),
    ("D", "IDI_ACTIONDELETED"),
    ("R", "IDI_ACTIONREPLACED"),
    ("C", "IDI_ACTIONREPLACED"),
    ("U", "IDI_ACTIONCONFLICTED"),
)


def lane_color(index: int) -> QColor:
    return _LANE_COLORS[index % COLORS_NUM]


def paint_graph_lane(p: QPainter, lane_h: int, typ: LaneType,
                     x1: int, x2: int, col: QColor, active: QColor, top: int):
    """对齐 CGitLogListBase::paintGraphLane。"""
    h = lane_h // 2
    m = (x1 + x2) // 2
    r = max(2, (x2 - x1) * _NODE_SIZE // 30)
    d = 2 * r
    cy = h + top

    def line(pen_col: QColor, ax, ay, bx, by):
        p.setPen(QPen(pen_col, _LINE_WIDTH, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(ax, ay, bx, by)

    # 竖线
    if typ in (LaneType.ACTIVE, LaneType.MERGE_FORK, LaneType.MERGE_FORK_R,
               LaneType.MERGE_FORK_L, LaneType.NOT_ACTIVE, LaneType.JOIN,
               LaneType.JOIN_R, LaneType.JOIN_L, LaneType.CROSS):
        line(col, m, top, m, top + lane_h)
    elif typ in (LaneType.BRANCH, LaneType.HEAD_L):
        line(col, m, cy, m, top + lane_h)
    elif typ in (LaneType.INITIAL, LaneType.MERGE_FORK_L_INITIAL,
                 LaneType.BOUNDARY, LaneType.BOUNDARY_C, LaneType.BOUNDARY_R,
                 LaneType.BOUNDARY_L, LaneType.TAIL_L):
        line(col, m, top, m, cy)

    # 横线
    if typ in (LaneType.MERGE_FORK, LaneType.BOUNDARY_C, LaneType.JOIN,
               LaneType.HEAD, LaneType.TAIL, LaneType.CROSS, LaneType.CROSS_EMPTY):
        line(active, x1, cy, x2, cy)
    elif typ in (LaneType.MERGE_FORK_R, LaneType.BOUNDARY_R):
        line(active, x1, cy, m, cy)
    elif typ in (LaneType.MERGE_FORK_L, LaneType.MERGE_FORK_L_INITIAL,
                 LaneType.BOUNDARY_L, LaneType.HEAD_L, LaneType.TAIL_L):
        line(active, m, cy, x2, cy)

    # 弧（join/head/tail）
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if typ in (LaneType.JOIN, LaneType.JOIN_R, LaneType.HEAD, LaneType.HEAD_R):
        pen = QPen(active, _LINE_WIDTH)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(x1 - (x2 - x1) // 2 - 1, top + h - 1, x2 - x1, lane_h, 270 * 16, 90 * 16)
    elif typ == LaneType.JOIN_L:
        p.setPen(QPen(col, _LINE_WIDTH))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(x1 + (x2 - x1) // 2, top + h - 1, x2 - x1, lane_h, 180 * 16, 90 * 16)
    elif typ in (LaneType.TAIL, LaneType.TAIL_R):
        p.setPen(QPen(active, _LINE_WIDTH))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(x1 - (x2 - x1) // 2 - 1, top - h - 1, x2 - x1, lane_h, 0, 90 * 16)

    # 节点
    node = QRectF(m - r, cy - r, d, d)
    p.setPen(QPen(col, 1))
    p.setBrush(QBrush(col))
    if typ in (LaneType.ACTIVE, LaneType.INITIAL, LaneType.BRANCH):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.drawEllipse(node)
    elif typ in (LaneType.MERGE_FORK, LaneType.MERGE_FORK_R, LaneType.MERGE_FORK_L,
                 LaneType.MERGE_FORK_L_INITIAL, LaneType.BOUNDARY_C,
                 LaneType.BOUNDARY_R, LaneType.BOUNDARY_L):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.drawRect(node.toRect())
    elif typ == LaneType.BOUNDARY:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(node)


def paint_graph(p: QPainter, rect: QRect, lanes: Sequence[LaneType]):
    if not lanes:
        return
    active = 0
    for i, ln in enumerate(lanes):
        if is_merge(ln):
            active = i
            break
    lw = max(10, 3 * rect.height() // 4)
    x2 = 0
    active_col = lane_color(active)
    p.save()
    p.setClipRect(rect)
    for i, ln in enumerate(lanes):
        x1 = x2
        x2 += lw
        if x1 >= rect.width():
            break
        if ln == LaneType.EMPTY:
            continue
        col = active_col if i == active else lane_color(i)
        paint_graph_lane(p, rect.height(), ln, rect.left() + x1, rect.left() + x2,
                         col, active_col, rect.top())
    p.restore()


def graph_width(lane_count: int, row_h: int) -> int:
    lw = max(10, 3 * row_h // 4)
    return max(72, lane_count * lw + 8)


def paint_actions(p: QPainter, rect: QRect, actions: str):
    """对齐 LOGLIST_ACTION：固定槽位画 IDI_ACTION* 图标。"""
    from ..res import icons
    letters = set(actions or "")
    if "C" in letters:
        letters.add("R")
    icon_w = 16
    border = 2
    y = rect.top() + max(0, (rect.height() - icon_w) // 2)
    slots = ("M", "A", "D", "R", "U")
    names = {
        "M": "IDI_ACTIONMODIFIED",
        "A": "IDI_ACTIONADDED",
        "D": "IDI_ACTIONDELETED",
        "R": "IDI_ACTIONREPLACED",
        "U": "IDI_ACTIONCONFLICTED",
    }
    for n, key in enumerate(slots):
        if key not in letters:
            continue
        ic = icons.icon(names[key], size=icon_w)
        if ic is None or ic.isNull():
            continue
        x = rect.left() + border + n * icon_w
        p.drawPixmap(x, y, ic.pixmap(icon_w, icon_w))


class LogListDelegate(QStyledItemDelegate):
    """Graph / Actions 列自绘，其它列走默认。"""

    def __init__(self, commit_of, parent=None):
        super().__init__(parent)
        self._commit_of = commit_of

    def paint(self, painter, option, index):
        col = index.column()
        if col not in (LOG_COL_GRAPH, LOG_COL_ACTIONS):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else None
        if style is not None:
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, opt.widget)
        else:
            painter.fillRect(opt.rect, opt.backgroundBrush)
        item = index.model()
        # QTreeWidget 的 index.internalPointer 不稳，走 callback
        commit = self._commit_of(index)
        if commit is None:
            return
        if col == LOG_COL_GRAPH:
            paint_graph(painter, opt.rect.adjusted(2, 0, 0, 0), commit.lanes or [])
        else:
            paint_actions(painter, opt.rect, commit.actions)
        _ = item
