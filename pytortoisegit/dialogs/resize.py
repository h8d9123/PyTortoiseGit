"""dialogs/resize.py —— ResizableLib 风格的通用锚点缩放引擎。

忠实复刻 TortoiseGit 所用 ResizableLib（CResizableLayout）的算法：
每个控件记录两个锚点（左上角、右下角），锚点位置为父窗口尺寸的
百分比带（0 / 50 / 100），同时记录控件四边到锚点所在位置的固定边距。
窗口缩放时：

    newLeft   = marginLeft  + W * anchorTL_x / 100
    newTop    = marginTop   + H * anchorTL_y / 100
    newRight  = marginRight + W * anchorBR_x / 100
    newBottom = marginBottom + H * anchorBR_y / 100

AddAnchor(ctrl, X) 表示两角都用 X（控件保持原尺寸，仅随锚点移动）；
AddAnchor(ctrl, X, Y) 表示左上角锚 X、右下角锚 Y（随窗口拉伸）。
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

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_BAND = {"LEFT": 0.0, "CENTER": 50.0, "RIGHT": 100.0,
         "TOP": 0.0, "MIDDLE": 50.0, "BOTTOM": 100.0}

# 便于书写："TOP_LEFT" → (0, 0)
_CORNERS: Dict[str, Tuple[float, float]] = {
    "TOP_LEFT": (0, 0), "TOP_CENTER": (50, 0), "TOP_RIGHT": (100, 0),
    "MIDDLE_LEFT": (0, 50), "MIDDLE_CENTER": (50, 50),
    "MIDDLE_RIGHT": (100, 50),
    "BOTTOM_LEFT": (0, 100), "BOTTOM_CENTER": (50, 100),
    "BOTTOM_RIGHT": (100, 100),
}


@dataclass
class _Item:
    widget: object
    ax1: float
    ay1: float
    ax2: float
    ay2: float
    ml: float
    mt: float
    mr: float
    mb: float


def _parse(corner: str) -> Tuple[float, float]:
    c = _CORNERS.get(corner.strip().upper())
    if c is None:
        return (0.0, 0.0)
    return c


class AnchorLayout:
    """管理一组控件的缩放锚点。"""

    def __init__(self, base_w: float, base_h: float):
        self.base_w = float(base_w)
        self.base_h = float(base_h)
        self._items: List[_Item] = []

    def add(self, widget, anchor: str,
            right_bottom: Optional[str] = None) -> None:
        """anchor 必填；right_bottom 省略时两角同为 anchor。"""
        ax1, ay1 = _parse(anchor)
        if right_bottom:
            ax2, ay2 = _parse(right_bottom)
        else:
            ax2, ay2 = ax1, ay1
        x, y = widget.x(), widget.y()
        w, h = widget.width(), widget.height()
        item = _Item(
            widget, ax1, ay1, ax2, ay2,
            ml=x - self.base_w * ax1 / 100.0,
            mt=y - self.base_h * ay1 / 100.0,
            mr=(x + w) - self.base_w * ax2 / 100.0,
            mb=(y + h) - self.base_h * ay2 / 100.0,
        )
        self._items.append(item)

    def apply(self, w: int, h: int) -> None:
        W, H = float(w), float(h)
        for it in self._items:
            nx = it.ml + W * it.ax1 / 100.0
            ny = it.mt + H * it.ay1 / 100.0
            nx2 = it.mr + W * it.ax2 / 100.0
            ny2 = it.mb + H * it.ay2 / 100.0
            if nx2 - nx < 8:
                nx2 = nx + 8
            if ny2 - ny < 8:
                ny2 = ny + 8
            it.widget.setGeometry(int(nx), int(ny),
                                  int(nx2 - nx), int(ny2 - ny))

    def __len__(self) -> int:
        return len(self._items)


def predict(anchor: str, right_bottom: Optional[str], base_w: float,
            base_h: float, x: float, y: float, w: float, h: float,
            new_w: float, new_h: float) -> Tuple[int, int, int, int]:
    """纯函数：预演一个控件的缩放结果（供测试/几何校验）。"""
    ax1, ay1 = _parse(anchor)
    ax2, ay2 = _parse(right_bottom) if right_bottom else (ax1, ay1)
    ml, mt = x - base_w * ax1 / 100.0, y - base_h * ay1 / 100.0
    mr = x + w - base_w * ax2 / 100.0
    mb = y + h - base_h * ay2 / 100.0
    nx = ml + new_w * ax1 / 100.0
    ny = mt + new_h * ay1 / 100.0
    nx2 = mr + new_w * ax2 / 100.0
    ny2 = mb + new_h * ay2 / 100.0
    return int(nx), int(ny), int(nx2 - nx), int(ny2 - ny)