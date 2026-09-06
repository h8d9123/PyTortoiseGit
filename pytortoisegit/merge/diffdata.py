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

逐行翻译 DiffData.cpp 的核心：把两个修订的文件 diff 成左右对齐的行列表，
每行标注 DiffState（删除/添加/修改/正常），供 BaseView 渲染并排视图。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..git.repo import Repository
from ..udiff import parse_diff
from .viewdata import DiffState, EOL, ViewData


class DiffData:
    """为一个文件构建左右对齐的行 ViewData 列表。"""

    def __init__(self, repo: Repository):
        self.repo = repo

    def load(self, path: str, rev1: str | None, rev2: str | None):
        """读两版本内容并 diff 出对齐行。返回 (left_rows, right_rows)。"""
        old_lines = self._read(path, rev1)
        new_lines = self._read(path, rev2)
        patch_text = self._diff(path, rev1, rev2)
        return self._align(old_lines, new_lines, patch_text)

    def _read(self, path: str, rev: str | None) -> List[str]:
        if rev:
            out = self.repo.runner.run("show", f"{rev}:{path}").stdout
        else:
            out = self.repo.runner.run("cat-file", "-p", f"HEAD:{path}").stdout
        return out.splitlines() if out else []

    def _diff(self, path: str, rev1, rev2) -> str:
        args = ["diff", "--no-color", "-U0"]
        if rev1 and rev2:
            args += [rev1, rev2]
        elif rev2:
            args += [rev2]
        elif rev1:
            args += [rev1]
        args += ["--", path]
        return self.repo.runner.run(*args).stdout or ""

    def _align(self, old_lines: List[str], new_lines: List[str],
               patch_text: str) -> Tuple[List[ViewData], List[ViewData]]:
        """按 hunk 逐行对齐，生成左右 ViewData 行列表。"""
        left: List[ViewData] = []
        right: List[ViewData] = []

        def add_left(text, state):
            left.append(ViewData(text, state, len(left) + 1))

        def add_right(text, state):
            right.append(ViewData(text, state, len(right) + 1))

        patches = parse_diff(patch_text)
        target = next((p for p in patches if True), None)
        if target is None or not target.hunks:
            # 无差异：逐行对齐
            n = max(len(old_lines), len(new_lines))
            for i in range(n):
                lo = old_lines[i] if i < len(old_lines) else ""
                no = new_lines[i] if i < len(new_lines) else ""
                st = DiffState.Edited if lo != no else DiffState.Normal
                add_left(lo, st)
                add_right(no, st)
            return left, right

        old_i = 0
        new_i = 0
        for h in target.hunks:
            # hunk 前未改段
            while old_i < max(0, h.old_start - 1) or new_i < max(0, h.new_start - 1):
                lo = old_lines[old_i] if old_i < len(old_lines) else ""
                no = new_lines[new_i] if new_i < len(new_lines) else ""
                add_left(lo, DiffState.Normal)
                add_right(no, DiffState.Normal)
                old_i += 1
                new_i += 1
            # hunk 内
            for ln in h.lines:
                if ln.kind == " ":
                    add_left(ln.text, DiffState.Normal)
                    add_right(ln.text, DiffState.Normal)
                    old_i += 1
                    new_i += 1
                elif ln.kind == "-":
                    add_left(ln.text, DiffState.Removed)
                    add_right("", DiffState.Empty)
                    old_i += 1
                elif ln.kind == "+":
                    add_left("", DiffState.Empty)
                    add_right(ln.text, DiffState.Added)
                    new_i += 1
        # 尾部
        while old_i < len(old_lines) or new_i < len(new_lines):
            lo = old_lines[old_i] if old_i < len(old_lines) else ""
            no = new_lines[new_i] if new_i < len(new_lines) else ""
            diff = bool(lo or no) and lo != no
            add_left(lo, DiffState.Edited if diff else DiffState.Normal)
            add_right(no, DiffState.Edited if diff else DiffState.Normal)
            old_i += 1
            new_i += 1

        return left, right