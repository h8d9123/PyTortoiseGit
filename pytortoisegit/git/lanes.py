# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""lanes.py —— 对齐 TortoiseGit Proc/lanes.h（qgit 风格分支图）。"""

from __future__ import annotations

from enum import IntEnum
from typing import List, Sequence


class LaneType(IntEnum):
    EMPTY = 0
    ACTIVE = 1
    NOT_ACTIVE = 2
    MERGE_FORK = 3
    MERGE_FORK_R = 4
    MERGE_FORK_L = 5
    MERGE_FORK_L_INITIAL = 6
    JOIN = 7
    JOIN_R = 8
    JOIN_L = 9
    HEAD = 10
    HEAD_R = 11
    HEAD_L = 12
    TAIL = 13
    TAIL_R = 14
    TAIL_L = 15
    CROSS = 16
    CROSS_EMPTY = 17
    INITIAL = 18
    BRANCH = 19
    UNAPPLIED = 20
    APPLIED = 21
    BOUNDARY = 22
    BOUNDARY_C = 23
    BOUNDARY_R = 24
    BOUNDARY_L = 25


COLORS_NUM = 8

_HEAD = {LaneType.HEAD, LaneType.HEAD_R, LaneType.HEAD_L}
_TAIL = {LaneType.TAIL, LaneType.TAIL_R, LaneType.TAIL_L}
_JOIN = {LaneType.JOIN, LaneType.JOIN_R, LaneType.JOIN_L}
_BOUNDARY = {LaneType.BOUNDARY, LaneType.BOUNDARY_C, LaneType.BOUNDARY_R,
             LaneType.BOUNDARY_L}
_MERGE = {LaneType.MERGE_FORK, LaneType.MERGE_FORK_R, LaneType.MERGE_FORK_L,
          LaneType.MERGE_FORK_L_INITIAL} | _BOUNDARY
_ACTIVE = {LaneType.ACTIVE, LaneType.INITIAL, LaneType.BRANCH} | _MERGE


def is_head(x: LaneType) -> bool:
    return x in _HEAD


def is_tail(x: LaneType) -> bool:
    return x in _TAIL


def is_join(x: LaneType) -> bool:
    return x in _JOIN


def is_boundary(x: LaneType) -> bool:
    return x in _BOUNDARY


def is_merge(x: LaneType) -> bool:
    return x in _MERGE


def is_active(x: LaneType) -> bool:
    return x in _ACTIVE


class Lanes:
    """CLanes：按提交顺序推进，每行快照一组 LaneType。"""

    def __init__(self):
        self.active_lane = 0
        self.type_vec: List[LaneType] = []
        self.next_sha: List[str] = []
        self.boundary = False
        self.NODE = LaneType.EMPTY
        self.NODE_L = LaneType.EMPTY
        self.NODE_R = LaneType.EMPTY

    def is_empty(self) -> bool:
        return not self.type_vec

    def clear(self):
        self.type_vec.clear()
        self.next_sha.clear()

    def init(self, expected_sha: str):
        self.clear()
        self.active_lane = 0
        self.set_boundary(False, False)
        self.add(LaneType.BRANCH, expected_sha, self.active_lane)

    def set_boundary(self, b: bool, initial: bool):
        self.NODE = LaneType.BOUNDARY_C if b else LaneType.MERGE_FORK
        self.NODE_R = LaneType.BOUNDARY_R if b else LaneType.MERGE_FORK_R
        self.NODE_L = (LaneType.BOUNDARY_L if b
                       else (LaneType.MERGE_FORK_L_INITIAL if initial
                             else LaneType.MERGE_FORK_L))
        self.boundary = b
        if b and self.type_vec:
            self.type_vec[self.active_lane] = LaneType.BOUNDARY

    def _is_node(self, x: LaneType) -> bool:
        return x in (self.NODE, self.NODE_R, self.NODE_L)

    def find_next_sha(self, nxt: str, pos: int) -> int:
        for i in range(pos, len(self.next_sha)):
            if self.next_sha[i] == nxt:
                return i
        return -1

    def find_type(self, typ: LaneType, pos: int) -> int:
        for i in range(pos, len(self.type_vec)):
            if self.type_vec[i] == typ:
                return i
        return -1

    def add(self, typ: LaneType, nxt: str, pos: int) -> tuple:
        was_empty_cross = False
        if pos < len(self.type_vec):
            pos_empty = self.find_type(LaneType.EMPTY, pos)
            pos_cross = self.find_type(LaneType.CROSS_EMPTY, pos)
            if pos_empty != -1 and pos_cross != -1:
                pos = min(pos_empty, pos_cross)
            elif pos_empty != -1:
                pos = pos_empty
            elif pos_cross != -1:
                pos = pos_cross
            else:
                pos = -1
            if pos != -1:
                was_empty_cross = pos == pos_cross
                self.type_vec[pos] = typ
                self.next_sha[pos] = nxt
                return pos, was_empty_cross
        self.type_vec.append(typ)
        self.next_sha.append(nxt)
        return len(self.type_vec) - 1, was_empty_cross

    def is_fork(self, sha: str) -> tuple:
        pos = self.find_next_sha(sha, 0)
        is_disc = self.active_lane != pos
        if pos == -1:
            return False, is_disc
        return self.find_next_sha(sha, pos + 1) != -1, is_disc

    def set_fork(self, sha: str):
        idx = self.find_next_sha(sha, 0)
        range_start = range_end = idx
        while idx != -1:
            range_end = idx
            self.type_vec[idx] = LaneType.TAIL
            idx = self.find_next_sha(sha, idx + 1)
        self.type_vec[self.active_lane] = self.NODE
        start_t = self.type_vec[range_start]
        end_t = self.type_vec[range_end]
        if start_t == self.NODE:
            self.type_vec[range_start] = self.NODE_L
        if end_t == self.NODE:
            self.type_vec[range_end] = self.NODE_R
        if self.type_vec[range_start] == LaneType.TAIL:
            self.type_vec[range_start] = LaneType.TAIL_L
        if self.type_vec[range_end] == LaneType.TAIL:
            self.type_vec[range_end] = LaneType.TAIL_R
        for i in range(range_start + 1, range_end):
            t = self.type_vec[i]
            if t == LaneType.NOT_ACTIVE:
                self.type_vec[i] = LaneType.CROSS
            elif t == LaneType.EMPTY:
                self.type_vec[i] = LaneType.CROSS_EMPTY

    def set_merge(self, parents: Sequence[str], only_first: bool = False):
        if self.boundary:
            return
        t = self.type_vec[self.active_lane]
        was_fork = t == self.NODE
        was_fork_l = t == self.NODE_L
        was_fork_r = t == self.NODE_R
        start_join_cross = end_join_cross = False
        end_was_empty_cross = False
        self.type_vec[self.active_lane] = self.NODE
        range_start = range_end = self.active_lane
        if not only_first:
            for parent in list(parents)[1:]:
                idx = self.find_next_sha(parent, 0)
                if idx != -1:
                    if idx > range_end:
                        range_end = idx
                        end_join_cross = self.type_vec[idx] == LaneType.CROSS
                    if idx < range_start:
                        range_start = idx
                        start_join_cross = self.type_vec[idx] == LaneType.CROSS
                    self.type_vec[idx] = LaneType.JOIN
                else:
                    range_end, end_was_empty_cross = self.add(
                        LaneType.HEAD, parent, range_end + 1)
        if self.type_vec[range_start] == self.NODE and not was_fork and not was_fork_r:
            self.type_vec[range_start] = self.NODE_L
        if self.type_vec[range_end] == self.NODE and not was_fork and not was_fork_l:
            self.type_vec[range_end] = self.NODE_R
        if self.type_vec[range_start] == LaneType.JOIN and not start_join_cross:
            self.type_vec[range_start] = LaneType.JOIN_L
        if self.type_vec[range_end] == LaneType.JOIN and not end_join_cross:
            self.type_vec[range_end] = LaneType.JOIN_R
        if self.type_vec[range_start] == LaneType.HEAD:
            self.type_vec[range_start] = LaneType.HEAD_L
        if self.type_vec[range_end] == LaneType.HEAD and not end_was_empty_cross:
            self.type_vec[range_end] = LaneType.HEAD_R
        for i in range(range_start + 1, range_end):
            t2 = self.type_vec[i]
            if t2 == LaneType.NOT_ACTIVE:
                self.type_vec[i] = LaneType.CROSS
            elif t2 == LaneType.EMPTY:
                self.type_vec[i] = LaneType.CROSS_EMPTY
            elif t2 in (LaneType.TAIL_R, LaneType.TAIL_L):
                self.type_vec[i] = LaneType.TAIL

    def set_initial(self):
        t = self.type_vec[self.active_lane]
        if not self._is_node(t) and t != LaneType.APPLIED:
            self.type_vec[self.active_lane] = (
                LaneType.BOUNDARY if self.boundary else LaneType.INITIAL)

    def change_active_lane(self, sha: str):
        t = self.type_vec[self.active_lane]
        if t == LaneType.INITIAL or is_boundary(t):
            self.type_vec[self.active_lane] = LaneType.EMPTY
        else:
            self.type_vec[self.active_lane] = LaneType.NOT_ACTIVE
        idx = self.find_next_sha(sha, 0)
        if idx != -1:
            self.type_vec[idx] = LaneType.ACTIVE
        else:
            idx, _ = self.add(LaneType.BRANCH, sha, self.active_lane)
        self.active_lane = idx

    def after_merge(self):
        if self.boundary:
            return
        for i, t in enumerate(self.type_vec):
            if is_head(t) or is_join(t) or t == LaneType.CROSS:
                self.type_vec[i] = LaneType.NOT_ACTIVE
            elif t == LaneType.CROSS_EMPTY:
                self.type_vec[i] = LaneType.EMPTY
            elif self._is_node(t):
                self.type_vec[i] = LaneType.ACTIVE

    def after_fork(self):
        for i, t in enumerate(self.type_vec):
            if t == LaneType.CROSS:
                self.type_vec[i] = LaneType.NOT_ACTIVE
            elif is_tail(t) or t == LaneType.CROSS_EMPTY:
                self.type_vec[i] = LaneType.EMPTY
            if not self.boundary and self._is_node(self.type_vec[i]):
                self.type_vec[i] = LaneType.ACTIVE
        while self.type_vec and self.type_vec[-1] == LaneType.EMPTY:
            self.type_vec.pop()
            self.next_sha.pop()

    def is_branch(self) -> bool:
        if not self.type_vec or self.active_lane >= len(self.type_vec):
            return False
        return self.type_vec[self.active_lane] == LaneType.BRANCH

    def after_branch(self):
        self.type_vec[self.active_lane] = LaneType.ACTIVE

    def next_parent(self, sha: str):
        if self.boundary:
            self.next_sha[self.active_lane] = ""
        else:
            self.next_sha[self.active_lane] = sha

    def snapshot(self) -> List[LaneType]:
        return list(self.type_vec)


def assign_lanes(commits) -> None:
    """为 GitRev 列表写入 lanes（对齐 CLogDataVector::updateLanes）。"""
    if not commits:
        return
    lns = Lanes()
    for c in commits:
        if lns.is_empty():
            lns.init(c.hash)
        is_fork, is_disc = lns.is_fork(c.hash)
        is_merge = len(c.parents) > 1
        is_initial = not c.parents
        if is_disc:
            lns.change_active_lane(c.hash)
        lns.set_boundary(False, is_initial)
        if is_fork:
            lns.set_fork(c.hash)
        if is_merge:
            lns.set_merge(c.parents, False)
        if is_initial:
            lns.set_initial()
        c.lanes = lns.snapshot()
        c.lane = lns.active_lane
        next_sha = c.parents[0] if c.parents else ""
        lns.next_parent(next_sha)
        if is_merge:
            lns.after_merge()
        if is_fork:
            lns.after_fork()
            if is_initial:
                lns.set_initial()
        if lns.is_branch():
            lns.after_branch()
