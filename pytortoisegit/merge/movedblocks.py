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

"""movedblocks.py —— TortoiseMerge 的 MovedBlocks（移动块检测）。

逐行翻译 MovedBlocks.cpp：扫描左右两栏匹配的连续行段（被移动的代码块），
将左栏标记为 MovedFrom、右栏标记为 MovedTo。用于识别"同一段代码被移动了位置"。

简化实现（对齐 MovedBlocksDetect 语义）：
  * 找左右子序列中相同的连续行块（长度 >= MIN_BLOCK）
  * 把该块在左栏标 MovedFrom、右栏标 MovedTo（忽略空/删除行）
"""

from __future__ import annotations

from typing import List, Tuple

from .viewdata import DiffState


def _strip(line: str) -> str:
    return line.strip()


def detect_moved_blocks(left_data: list, right_data: list,
                        min_block: int = 3) -> List[Tuple[int, int, int]]:
    """返回 [(left_index, right_index, count)]：匹配的移动块。

    对齐原版 MovedBlocksDetect：**只考虑差异行**（左=删除行、右=新增行），
    不会把两侧相同的普通行误判为“移动”。普通行本就是对齐的，不应高亮。
    """
    # 仅取删除行（左）/新增行（右）作为候选，普通行不参与移动检测
    left = [(i, left_data[i].line) for i in range(len(left_data))
            if left_data[i].is_removed and left_data[i].line]
    right = [(j, right_data[j].line) for j in range(len(right_data))
             if right_data[j].is_added and right_data[j].line]

    matches: List[Tuple[int, int, int]] = []
    used_l: set = set()
    used_r: set = set()

    # 贪心：找长度 >= min_block 的相同连续块（在原文件中下标也须连续）
    for li in range(len(left)):
        if left[li][0] in used_l:
            continue
        for rj in range(len(right)):
            if right[rj][0] in used_r:
                continue
            if right[rj][1] == left[li][1]:
                k = 0
                while (li + k < len(left) and rj + k < len(right)
                       and left[li + k][1] == right[rj + k][1]
                       and left[li + k][0] == left[li][0] + k
                       and right[rj + k][0] == right[rj][0] + k
                       and left[li + k][0] not in used_l
                       and right[rj + k][0] not in used_r):
                    k += 1
                if k >= min_block:
                    matches.append((left[li][0], right[rj][0], k))
                    for x in range(k):
                        used_l.add(left[li + x][0])
                        used_r.add(right[rj + x][0])
                break
    return matches


def mark_moved(left_data: list, right_data: list, min_block: int = 3):
    """在 ViewData 列表上把移动块标为 MovedFrom(左)/MovedTo(右)。

    仅对差异行生效；普通行保持 Normal（不显示颜色）。
    """
    moved = detect_moved_blocks(left_data, right_data, min_block)
    for (l_start, r_start, count) in moved:
        for x in range(count):
            li = l_start + x
            ri = r_start + x
            if li < len(left_data):
                left_data[li].state = DiffState.MovedFrom
            if ri < len(right_data):
                right_data[ri].state = DiffState.MovedTo
    return moved