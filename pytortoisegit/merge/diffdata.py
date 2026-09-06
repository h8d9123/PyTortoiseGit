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

"""diffdata.py —— TortoiseGitMerge 的 DiffData（行级 diff 数据）。

对齐 CDiffData::DoTwoWayDiff / DoThreeWayDiff：
  * 按 hunk 把删除/新增**配对到同一行**（svn_diff 的 original/modified 对齐）
  * 未改段用独立的 old_i / new_i 推进，避免 unified diff 行号分叉后错位
  * 三路合并落到同一套行网格（左=theirs，右=ours，底=合并结果）
"""

from __future__ import annotations

import os
from difflib import SequenceMatcher, unified_diff
from enum import Enum
from typing import List, Optional, Sequence, Tuple

from ..udiff import FilePatch, parse_diff, parse_file_patch
from .viewdata import DiffState, HideState, ViewData


class IgnoreWS(Enum):
    """对齐 CDiffData::IgnoreWS。"""
    None_ = 0
    AllWhiteSpaces = 1
    WhiteSpaces = 2


def _vd(text: str, state: DiffState, linenumber: int = -1) -> ViewData:
    hidden = HideState.Hidden if state == DiffState.Normal else HideState.Shown
    return ViewData(text, state, linenumber, hidestate=hidden)


def _pick_patch(patches: Sequence[FilePatch], path: str | None) -> Optional[FilePatch]:
    if not patches:
        return None
    if path:
        norm = path.replace("\\", "/").lstrip("./")
        for p in patches:
            for cand in (p.new_path, p.old_path):
                if cand and cand.replace("\\", "/").endswith(norm):
                    return p
    return patches[0]


def _synthetic_patch(old_lines: List[str], new_lines: List[str]) -> str:
    return "\n".join(unified_diff(old_lines, new_lines, lineterm="", n=0))


def align_lines(old_lines: List[str], new_lines: List[str],
                patch_text: str = "", path: str | None = None,
                match_old: List[str] | None = None,
                match_new: List[str] | None = None
                ) -> Tuple[List[ViewData], List[ViewData]]:
    """按 LCS（对齐 svn_diff）把删除/新增配对到同一行。

    patch_text 仅作无文件内容时的回退；有左右文本时以 SequenceMatcher 为准，
    避免 git diff -U0 把未改行吞进 + 侧导致错位。
    """
    if not old_lines and not new_lines and patch_text:
        return _align_from_patch(old_lines, new_lines, patch_text, path)

    left: List[ViewData] = []
    right: List[ViewData] = []
    a = match_old if match_old is not None else old_lines
    b = match_new if match_new is not None else new_lines
    sm = SequenceMatcher(a=a, b=b, autojunk=False)

    def add_pair(ltext: str, lstate: DiffState, lno: int,
                 rtext: str, rstate: DiffState, rno: int):
        left.append(_vd(ltext, lstate, lno))
        right.append(_vd(rtext, rstate, rno))

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                add_pair(old_lines[i1 + k], DiffState.Normal, i1 + k + 1,
                         new_lines[j1 + k], DiffState.Normal, j1 + k + 1)
        elif tag == "replace":
            n_old, n_new = i2 - i1, j2 - j1
            n = max(n_old, n_new)
            for k in range(n):
                if k < n_old and k < n_new:
                    add_pair(old_lines[i1 + k], DiffState.Removed, i1 + k + 1,
                             new_lines[j1 + k], DiffState.Added, j1 + k + 1)
                elif k < n_old:
                    add_pair(old_lines[i1 + k], DiffState.Removed, i1 + k + 1,
                             "", DiffState.Empty, -1)
                else:
                    add_pair("", DiffState.Empty, -1,
                             new_lines[j1 + k], DiffState.Added, j1 + k + 1)
        elif tag == "delete":
            for k in range(i1, i2):
                add_pair(old_lines[k], DiffState.Removed, k + 1,
                         "", DiffState.Empty, -1)
        elif tag == "insert":
            for k in range(j1, j2):
                add_pair("", DiffState.Empty, -1,
                         new_lines[k], DiffState.Added, k + 1)
    return left, right


def _align_from_patch(old_lines: List[str], new_lines: List[str],
                      patch_text: str, path: str | None
                      ) -> Tuple[List[ViewData], List[ViewData]]:
    """仅有 unified diff、没有完整左右文本时的回退对齐。"""
    patches = parse_diff(patch_text) if patch_text else []
    target = _pick_patch(patches, path)
    if target is None or not target.hunks:
        parsed = parse_file_patch(patch_text) if patch_text else None
        target = parsed if parsed is not None and parsed.hunks else None
    if target is None or not target.hunks:
        return [], []
    left: List[ViewData] = []
    right: List[ViewData] = []
    old_i = new_i = 0

    def add_pair(ltext, lstate, lno, rtext, rstate, rno):
        left.append(_vd(ltext, lstate, lno))
        right.append(_vd(rtext, rstate, rno))

    def pair_group(minus: List[str], plus: List[str]):
        nonlocal old_i, new_i
        n = max(len(minus), len(plus))
        for k in range(n):
            if k < len(minus) and k < len(plus):
                add_pair(minus[k], DiffState.Removed, old_i + 1,
                         plus[k], DiffState.Added, new_i + 1)
                old_i += 1
                new_i += 1
            elif k < len(minus):
                add_pair(minus[k], DiffState.Removed, old_i + 1,
                         "", DiffState.Empty, -1)
                old_i += 1
            else:
                add_pair("", DiffState.Empty, -1,
                         plus[k], DiffState.Added, new_i + 1)
                new_i += 1

    for h in target.hunks:
        while old_i < max(0, h.old_start - 1) and new_i < max(0, h.new_start - 1):
            lo = old_lines[old_i] if old_i < len(old_lines) else ""
            no = new_lines[new_i] if new_i < len(new_lines) else ""
            add_pair(lo, DiffState.Normal, old_i + 1, no, DiffState.Normal, new_i + 1)
            old_i += 1
            new_i += 1
        idx = 0
        while idx < len(h.lines):
            kind = h.lines[idx].kind
            if kind == " ":
                add_pair(h.lines[idx].text, DiffState.Normal, old_i + 1,
                         h.lines[idx].text, DiffState.Normal, new_i + 1)
                old_i += 1
                new_i += 1
                idx += 1
                continue
            if kind == "\\":
                idx += 1
                continue
            minus: List[str] = []
            plus: List[str] = []
            while idx < len(h.lines) and h.lines[idx].kind == "-":
                minus.append(h.lines[idx].text)
                idx += 1
            while idx < len(h.lines) and h.lines[idx].kind == "+":
                plus.append(h.lines[idx].text)
                idx += 1
            if minus or plus:
                pair_group(minus, plus)
            else:
                idx += 1
    return left, right


def merge_three_views(
        base_theirs_left: List[ViewData], theirs_right: List[ViewData],
        base_ours_left: List[ViewData], ours_right: List[ViewData]
        ) -> Tuple[List[ViewData], List[ViewData], List[ViewData]]:
    """把两次「base↔side」对齐合并成同一行网格（左=theirs，右=ours，底=结果）。"""
    left: List[ViewData] = []
    right: List[ViewData] = []
    bottom: List[ViewData] = []
    i = j = 0

    def _gap(rows: List[ViewData], idx: int) -> bool:
        if idx >= len(rows):
            return True
        return rows[idx].state == DiffState.Empty

    def _base_ln(rows: List[ViewData], idx: int) -> int:
        if idx >= len(rows):
            return 10 ** 9
        ln = rows[idx].linenumber
        return ln if ln >= 0 else 10 ** 9

    while i < len(base_theirs_left) or j < len(base_ours_left):
        if i >= len(base_theirs_left) and j >= len(base_ours_left):
            break
        if i >= len(base_theirs_left):
            orow = ours_right[j] if j < len(ours_right) else _vd("", DiffState.Empty)
            left.append(_vd("", DiffState.Empty))
            right.append(ViewData(orow.line, DiffState.YoursAdded, orow.linenumber))
            bottom.append(ViewData(orow.line, DiffState.YoursAdded, orow.linenumber))
            j += 1
            continue
        if j >= len(base_ours_left):
            tr = theirs_right[i] if i < len(theirs_right) else _vd("", DiffState.Empty)
            left.append(ViewData(tr.line, DiffState.TheirsAdded, tr.linenumber))
            right.append(_vd("", DiffState.Empty))
            bottom.append(ViewData(tr.line, DiffState.TheirsAdded, tr.linenumber))
            i += 1
            continue
        a_gap = _gap(base_theirs_left, i)
        b_gap = _gap(base_ours_left, j)
        if i < len(base_theirs_left) and j < len(base_ours_left) and not a_gap and not b_gap:
            if _base_ln(base_theirs_left, i) < _base_ln(base_ours_left, j):
                b_gap = True
            elif _base_ln(base_ours_left, j) < _base_ln(base_theirs_left, i):
                a_gap = True

        if a_gap and not b_gap:
            tr = theirs_right[i] if i < len(theirs_right) else _vd("", DiffState.Empty)
            left.append(ViewData(tr.line, DiffState.TheirsAdded, tr.linenumber))
            right.append(_vd("", DiffState.Empty))
            bottom.append(ViewData(tr.line, DiffState.TheirsAdded, tr.linenumber))
            i += 1
            continue
        if b_gap and not a_gap:
            orow = ours_right[j] if j < len(ours_right) else _vd("", DiffState.Empty)
            left.append(_vd("", DiffState.Empty))
            right.append(ViewData(orow.line, DiffState.YoursAdded, orow.linenumber))
            bottom.append(ViewData(orow.line, DiffState.YoursAdded, orow.linenumber))
            j += 1
            continue
        if a_gap and b_gap:
            tr = theirs_right[i] if i < len(theirs_right) else _vd("", DiffState.Empty)
            orow = ours_right[j] if j < len(ours_right) else _vd("", DiffState.Empty)
            if tr.line == orow.line:
                st = DiffState.IdenticalAdded
                left.append(ViewData(tr.line, st, tr.linenumber))
                right.append(ViewData(orow.line, st, orow.linenumber))
                bottom.append(ViewData(orow.line, st, orow.linenumber))
            else:
                left.append(ViewData(tr.line, DiffState.ConflictAdded, tr.linenumber))
                right.append(ViewData(orow.line, DiffState.ConflictAdded, orow.linenumber))
                bottom.append(ViewData(orow.line or tr.line, DiffState.Conflict, -1))
            i += 1
            j += 1
            continue

        t_base = base_theirs_left[i]
        o_base = base_ours_left[j]
        t_side = theirs_right[i] if i < len(theirs_right) else _vd("", DiffState.Empty)
        o_side = ours_right[j] if j < len(ours_right) else _vd("", DiffState.Empty)
        theirs_changed = t_base.state != DiffState.Normal or t_side.state != DiffState.Normal
        ours_changed = o_base.state != DiffState.Normal or o_side.state != DiffState.Normal
        theirs_text = "" if t_side.state == DiffState.Empty else t_side.line
        ours_text = "" if o_side.state == DiffState.Empty else o_side.line
        base_text = t_base.line

        if not theirs_changed and not ours_changed:
            left.append(ViewData(theirs_text or base_text, DiffState.Normal, t_side.linenumber))
            right.append(ViewData(ours_text or base_text, DiffState.Normal, o_side.linenumber))
            bottom.append(ViewData(ours_text or base_text, DiffState.Normal, o_side.linenumber))
        elif theirs_changed and not ours_changed:
            lst = DiffState.TheirsRemoved if t_side.state == DiffState.Empty else DiffState.TheirsAdded
            if t_base.state == DiffState.Removed and t_side.state != DiffState.Empty:
                lst = DiffState.TheirsAdded
            left.append(ViewData(theirs_text if t_side.state != DiffState.Empty else t_base.line, lst,
                                 t_side.linenumber if t_side.state != DiffState.Empty else t_base.linenumber))
            right.append(ViewData(ours_text or base_text, DiffState.Normal, o_side.linenumber))
            if t_side.state == DiffState.Empty:
                bottom.append(_vd("", DiffState.Empty))
            else:
                bottom.append(ViewData(theirs_text, DiffState.TheirsAdded, t_side.linenumber))
        elif ours_changed and not theirs_changed:
            rst = DiffState.YoursRemoved if o_side.state == DiffState.Empty else DiffState.YoursAdded
            if o_base.state == DiffState.Removed and o_side.state != DiffState.Empty:
                rst = DiffState.YoursAdded
            left.append(ViewData(theirs_text or base_text, DiffState.Normal, t_side.linenumber))
            right.append(ViewData(ours_text if o_side.state != DiffState.Empty else o_base.line, rst,
                                  o_side.linenumber if o_side.state != DiffState.Empty else o_base.linenumber))
            if o_side.state == DiffState.Empty:
                bottom.append(_vd("", DiffState.Empty))
            else:
                bottom.append(ViewData(ours_text, DiffState.YoursAdded, o_side.linenumber))
        else:
            if theirs_text == ours_text:
                st = DiffState.IdenticalRemoved if not theirs_text else DiffState.IdenticalAdded
                left.append(ViewData(t_base.line if t_side.state == DiffState.Empty else theirs_text,
                                     st, t_base.linenumber))
                right.append(ViewData(o_base.line if o_side.state == DiffState.Empty else ours_text,
                                      st, o_base.linenumber))
                bottom.append(ViewData(ours_text, st, o_side.linenumber))
            else:
                left.append(ViewData(
                    theirs_text if t_side.state != DiffState.Empty else t_base.line,
                    DiffState.ConflictAdded if t_side.state != DiffState.Empty else DiffState.ConflictEmpty,
                    t_base.linenumber))
                right.append(ViewData(
                    ours_text if o_side.state != DiffState.Empty else o_base.line,
                    DiffState.ConflictAdded if o_side.state != DiffState.Empty else DiffState.ConflictEmpty,
                    o_base.linenumber))
                bottom.append(ViewData(ours_text or theirs_text, DiffState.Conflict, -1))
        i += 1
        j += 1

    return left, right, bottom


def _normalize(text: str, ignore_ws: IgnoreWS, ignore_eol: bool,
               ignore_case: bool, ignore_comments: bool) -> str:
    s = text
    if ignore_case:
        s = s.lower()
    if ignore_eol:
        s = s.replace("\r", "")
    if ignore_ws == IgnoreWS.AllWhiteSpaces:
        s = "".join(s.split())
    elif ignore_ws == IgnoreWS.WhiteSpaces:
        s = s.strip()
    if ignore_comments:
        stripped = s.lstrip()
        if stripped.startswith(("#", "//", ";")):
            s = ""
    return s


def apply_ignore_filters(left: List[ViewData], right: List[ViewData],
                         ignore_ws: IgnoreWS = IgnoreWS.None_,
                         ignore_eol: bool = False,
                         ignore_case: bool = False,
                         ignore_comments: bool = False):
    """把仅空白/大小写/注释造成的差异标成 Filtered / Whitespace。"""
    def _norm(text: str) -> str:
        return _normalize(text, ignore_ws, ignore_eol, ignore_case, ignore_comments)

    for lv, rv in zip(left, right):
        if lv.state == DiffState.Normal and rv.state == DiffState.Normal:
            if lv.line != rv.line:
                lv.state = rv.state = DiffState.Whitespace
            continue
        if lv.state not in (DiffState.Removed, DiffState.Empty):
            continue
        if rv.state not in (DiffState.Added, DiffState.Empty):
            continue
        if _norm(lv.line) == _norm(rv.line) and (lv.line or rv.line):
            if ignore_ws != IgnoreWS.None_ or ignore_case or ignore_comments:
                lv.state = rv.state = DiffState.FilteredDiff
                lv.hidestate = rv.hidestate = HideState.Hidden


class DiffData:
    """为一个文件构建左右对齐的行 ViewData 列表。"""

    def __init__(self, repo=None):
        self.repo = repo
        self.ignore_ws = IgnoreWS.None_
        self.ignore_eol = False
        self.ignore_case = False
        self.ignore_comments = False

    def _match_copies(self, lines: List[str]) -> List[str] | None:
        if (self.ignore_ws == IgnoreWS.None_ and not self.ignore_eol
                and not self.ignore_case and not self.ignore_comments):
            return None
        return [_normalize(s, self.ignore_ws, self.ignore_eol,
                           self.ignore_case, self.ignore_comments)
                for s in lines]

    def load(self, path: str, rev1: str | None, rev2: str | None):
        """读两版本内容并 diff 出对齐行。返回 (left_rows, right_rows)。"""
        old_lines = self._read(path, rev1)
        new_lines = self._read(path, rev2)
        left, right = align_lines(
            old_lines, new_lines, "", path,
            match_old=self._match_copies(old_lines),
            match_new=self._match_copies(new_lines))
        apply_ignore_filters(left, right, self.ignore_ws, self.ignore_eol,
                             self.ignore_case, self.ignore_comments)
        return left, right

    def load_local(self, left_path: str, right_path: str):
        old_lines = self._read_local(left_path)
        new_lines = self._read_local(right_path)
        left, right = align_lines(
            old_lines, new_lines, "",
            match_old=self._match_copies(old_lines),
            match_new=self._match_copies(new_lines))
        apply_ignore_filters(left, right, self.ignore_ws, self.ignore_eol,
                             self.ignore_case, self.ignore_comments)
        return left, right

    def three_way(self, path: str, our_rev: str, their_rev: str):
        """三栏合并：左=theirs、右=ours、底=同一网格上的合并结果。"""
        base = ""
        if self.repo is not None:
            base = self.repo.runner.run(
                "merge-base", our_rev, their_rev).stdout.strip()
        base = base or our_rev
        base_lines = self._read(path, base)
        their_lines = self._read(path, their_rev)
        our_lines = self._read(path, our_rev)
        bt_l, th_r = align_lines(
            base_lines, their_lines, "", path,
            match_old=self._match_copies(base_lines),
            match_new=self._match_copies(their_lines))
        bo_l, ou_r = align_lines(
            base_lines, our_lines, "", path,
            match_old=self._match_copies(base_lines),
            match_new=self._match_copies(our_lines))
        return merge_three_views(bt_l, th_r, bo_l, ou_r)

    def _read(self, path: str, rev: str | None) -> List[str]:
        if rev:
            if self.repo is None:
                return []
            out = self.repo.runner.run("show", f"{rev}:{path}").stdout
            return out.splitlines() if out else []
        return self._read_local(self.repo.full_path(path) if self.repo else path)

    @staticmethod
    def _read_local(full: str) -> List[str]:
        if not full or not os.path.isfile(full):
            return []
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()

    def _diff_flags(self) -> List[str]:
        flags = ["diff", "--no-color", "-U0"]
        if self.ignore_ws == IgnoreWS.AllWhiteSpaces:
            flags.append("-w")
        elif self.ignore_ws == IgnoreWS.WhiteSpaces:
            flags.append("-b")
        if self.ignore_eol:
            flags.append("--ignore-cr-at-eol")
        return flags

    def _diff(self, path: str, rev1, rev2) -> str:
        if self.repo is None:
            return ""
        args = self._diff_flags()
        if rev1 and rev2:
            args += [rev1, rev2]
        elif rev2:
            args += [rev2]
        elif rev1:
            args += [rev1]
        args += ["--", path]
        return self.repo.runner.run(*args).stdout or ""

    def _diff_no_index(self, left_path: str, right_path: str) -> str:
        try:
            from ..git.git import GitRunner
            runner = self.repo.runner if self.repo is not None else GitRunner()
            args = self._diff_flags() + ["--no-index", "--", left_path, right_path]
            return runner.run(*args).stdout or ""
        except Exception:
            return _synthetic_patch(self._read_local(left_path),
                                    self._read_local(right_path))
