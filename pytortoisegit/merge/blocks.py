# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""blocks.py —— 对齐 TortoiseGitMerge 的块操作（RightView / BottomView）。

纯 ViewData 列表操作，不依赖 Qt，便于单测。
"""

from __future__ import annotations

from typing import List, Sequence

from .viewdata import DiffState, ViewData

_SKIP_SAVE = {
    DiffState.Empty,
    DiffState.ConflictEmpty,
    DiffState.IdenticalRemoved,
    DiffState.Removed,
    DiffState.TheirsRemoved,
    DiffState.YoursRemoved,
    DiffState.ConflictResolvedEmpty,
}

_CONFLICT_SAVE = (DiffState.Conflict, DiffState.ConflictIgnored)

_USE_BLOCK_NORMALIZE = {
    DiffState.Added,
    DiffState.ConflictAdded,
    DiffState.Conflict,
    DiffState.ConflictIgnored,
    DiffState.IdenticalAdded,
    DiffState.TheirsAdded,
    DiffState.YoursAdded,
    DiffState.IdenticalRemoved,
    DiffState.Removed,
    DiffState.TheirsRemoved,
    DiffState.YoursRemoved,
}


def resolve_state(state: DiffState) -> DiffState:
    """CBaseView::ResolveState：冲突行改为已解决。"""
    if state == DiffState.ConflictEmpty:
        return DiffState.ConflictResolvedEmpty
    if state in (DiffState.Conflict, DiffState.ConflictIgnored, DiffState.ConflictAdded):
        return DiffState.ConflictsResolved
    return state


def empty_line() -> ViewData:
    return ViewData("", DiffState.Empty, -1)


def insert_view_data(dest: List[ViewData], index: int, line: ViewData) -> None:
    dest.insert(max(0, min(index, len(dest))), line.clone())


def insert_empty_lines(dest: List[ViewData], index: int, count: int) -> None:
    if count <= 0:
        return
    at = max(0, min(index, len(dest)))
    dest[at:at] = [empty_line() for _ in range(count)]


def _copy_for_use(src: ViewData) -> ViewData:
    line = src.clone()
    if line.state in (DiffState.ConflictEmpty, DiffState.Unknown):
        line.state = DiffState.Empty
    if line.state in _USE_BLOCK_NORMALIZE:
        line.state = DiffState.Normal
    return line


def use_view_block(dest: List[ViewData], src: Sequence[ViewData],
                   first: int, last: int) -> None:
    """CBaseView::UseViewBlock：把 src[first..last] 覆盖到 dest（双向右栏）。"""
    for i in range(first, last + 1):
        if i >= len(dest) or i >= len(src):
            continue
        dest[i] = _copy_for_use(src[i])


def use_resolved_block(dest: List[ViewData], src: Sequence[ViewData],
                       first: int, last: int) -> None:
    """CBottomView::UseBlock：覆盖到底栏并 ResolveState。"""
    for i in range(first, last + 1):
        if i >= len(dest) or i >= len(src):
            continue
        line = src[i].clone()
        line.state = resolve_state(line.state)
        dest[i] = line


def use_both_left_first(right: List[ViewData], left: List[ViewData],
                        first: int, last: int,
                        others: Sequence[List[ViewData]] | None = None) -> None:
    """CRightView::UseBothLeftFirst：左侧块插到右侧原块之前。"""
    if last < first:
        return
    for i in range(first, last + 1):
        if i < len(right) and not right[i].is_empty:
            right[i].state = DiffState.YoursAdded
    for i in range(first, last + 1):
        src = left[i].clone() if i < len(left) else empty_line()
        if src.is_empty:
            src.state = DiffState.Empty
        else:
            src.state = DiffState.TheirsAdded
        insert_view_data(right, i, src)
    ncount = last - first + 1
    insert_empty_lines(left, last + 1, ncount)
    for other in others or ():
        insert_empty_lines(other, last + 1, ncount)


def use_both_right_first(right: List[ViewData], left: List[ViewData],
                         first: int, last: int,
                         others: Sequence[List[ViewData]] | None = None) -> None:
    """CRightView::UseBothRightFirst：右侧块在前，再插入左侧块。"""
    if last < first:
        return
    for i in range(first, last + 1):
        if i < len(right) and not right[i].is_empty:
            right[i].state = DiffState.Added
    nnext = last + 1
    for i in range(first, last + 1):
        src = left[i].clone() if i < len(left) else empty_line()
        if src.is_empty:
            src.state = DiffState.Empty
        else:
            src.state = DiffState.TheirsAdded
        insert_view_data(right, nnext, src)
        nnext += 1
    ncount = last - first + 1
    insert_empty_lines(left, first, ncount)
    for other in others or ():
        insert_empty_lines(other, first, ncount)


def use_both_blocks(bottom: List[ViewData], first_view: Sequence[ViewData],
                    last_view: Sequence[ViewData], first: int, last: int,
                    pad_first: List[ViewData], pad_last: List[ViewData]) -> None:
    """CBottomView::UseBothBlocks：先覆盖 first，再插入 last。"""
    if last < first:
        return
    for i in range(first, last + 1):
        if i >= len(bottom) or i >= len(first_view):
            continue
        line = first_view[i].clone()
        line.state = resolve_state(line.state)
        bottom[i] = line
        if i < len(pad_first) and not pad_first[i].is_empty:
            pad_first[i].state = DiffState.YoursAdded
    nnext = last + 1
    for i in range(first, last + 1):
        src = last_view[i].clone() if i < len(last_view) else empty_line()
        src.state = resolve_state(src.state)
        insert_view_data(bottom, nnext, src)
        if i < len(pad_last) and not pad_last[i].is_empty:
            pad_last[i].state = DiffState.TheirsAdded
        nnext += 1
    ncount = last - first + 1
    insert_empty_lines(pad_last, first, ncount)
    insert_empty_lines(pad_first, last + 1, ncount)


def serialize_view(dest: Sequence[ViewData],
                   left: Sequence[ViewData],
                   right: Sequence[ViewData]) -> List[str]:
    """对齐 CMainFrame::SaveFile：跳过空/删行，未解决冲突写标记。"""
    out: List[str] = []
    i = 0
    n = len(dest)
    while i < n:
        state = dest[i].state
        if state in _CONFLICT_SAVE:
            last = i
            while last + 1 < n and dest[last + 1].state in _CONFLICT_SAVE:
                last += 1
            out.append("<<<<<<< .mine")
            for j in range(i, last + 1):
                if j < len(right) and not right[j].is_empty:
                    out.append(right[j].line)
            out.append("=======")
            for j in range(i, last + 1):
                if j < len(left) and not left[j].is_empty:
                    out.append(left[j].line)
            out.append(">>>>>>> .theirs")
            i = last + 1
            continue
        if state in _SKIP_SAVE:
            i += 1
            continue
        out.append(dest[i].line)
        i += 1
    return out


def first_conflict_index(data: Sequence[ViewData]) -> int:
    for i, vd in enumerate(data):
        if vd.is_conflict:
            return i
    return -1


def mark_block(dest: List[ViewData], marked: bool, first: int, last: int) -> None:
    """对齐 CBaseView::MarkBlock。"""
    for i in range(first, last + 1):
        if 0 <= i < len(dest):
            dest[i].marked = marked


def use_view_block_skip(dest: List[ViewData], src: Sequence[ViewData],
                        first: int, last: int, skip_fn) -> None:
    """对齐 CBaseView::UseViewBlock(..., fnSkip)：skip_fn 为真的行跳过并清除标记。"""
    for i in range(first, last + 1):
        if skip_fn(i):
            if 0 <= i < len(dest):
                dest[i].marked = False
            continue
        if i >= len(dest) or i >= len(src):
            continue
        dest[i] = _copy_for_use(src[i])


def leave_only_marked_blocks(dest: List[ViewData], src: Sequence[ViewData]) -> None:
    """对齐 LeaveOnlyMarkedBlocks：只保留标记块（其余用 src 覆盖）。"""
    use_view_block_skip(
        dest, src, 0, len(dest) - 1,
        lambda i: dest[i].marked or dest[i].state == DiffState.Edited)


def use_view_file_of_marked(dest: List[ViewData], src: Sequence[ViewData]) -> None:
    """对齐 UseViewFileOfMarked：仅用 src 覆盖标记块。"""
    use_view_block_skip(
        dest, src, 0, len(dest) - 1,
        lambda i: (not dest[i].marked) or dest[i].state == DiffState.Edited)


def use_view_file_except_edited(dest: List[ViewData], src: Sequence[ViewData]) -> None:
    """对齐 UseViewFileExceptEdited：除手动编辑行外都用 src 覆盖。"""
    use_view_block_skip(
        dest, src, 0, len(dest) - 1,
        lambda i: dest[i].state == DiffState.Edited)
