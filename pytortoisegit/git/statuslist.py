"""git/statuslist.py —— 镜像 TortoiseGit 的 Git/GitStatusListCtrl。

在 GitStatus 的条目基础上补充每文件的：
  - action（状态名，供 Status 列显示与着色）
  - lines_added / lines_removed（`git diff --numstat`）
  - mtime（工作区文件修改时间）
  - ignored / assume-valid / skip-worktree 标记
  - index_only（仅暂存、工作区无改动）

统计与配色规则参考 GitStatusListCtrl.cpp 的 GetStatisticsString()/OnNMCustomdraw()。
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

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .repo import Repository
from .status import GitStatusEntry

# 与 Colors.cpp 默认值一致
COLOR_CONFLICT = "#ff0000"
COLOR_MODIFIED = "#0032a0"
COLOR_MERGED = "#006400"
COLOR_DELETED = "#640000"
COLOR_ADDED = "#640064"
COLOR_RENAMED = "#0000ff"


@dataclass
class StatusRow:
    """已充实显示数据的列表行。"""

    entry: GitStatusEntry
    action: str = "Unknown"
    state: str = ""                 # 归类用：modified/added/deleted/renamed/copied/conflicted/untracked/ignored
    lines_added: int = 0
    lines_removed: int = 0
    mtime: Optional[datetime] = None
    index_only: bool = False
    assume_valid: bool = False
    skip_worktree: bool = False

    @property
    def path(self) -> str:
        return self.entry.path

    @property
    def display_path(self) -> str:
        return self.entry.display_path

    @property
    def color(self) -> str:
        if self.entry.is_conflicted:
            return COLOR_CONFLICT
        if self.state == "added" or self.state == "copied":
            return COLOR_ADDED
        if self.state == "modified":
            return COLOR_MODIFIED
        if self.state == "deleted":
            return COLOR_DELETED
        if self.state == "renamed":
            return COLOR_RENAMED
        if self.state == "ignored" or self.assume_valid or self.skip_worktree:
            return "#808080"
        return "#000000"


class GitStatusList:
    """工作区更改列表（含 numstat 行数、mtime、各种显示开关对应的数据）。"""

    def __init__(self, repo: Repository):
        self.repo = repo
        self.rows: List[StatusRow] = []

    # ------------------------------------------------------------------
    # 抓取
    # ------------------------------------------------------------------
    def fetch(self, include_staged: bool = True,
              include_unversioned: bool = True,
              include_ignored: bool = False,
              include_local_changes_ignored: bool = False) -> List[StatusRow]:
        runner = self.repo.runner
        base = ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
        res = runner.run(*base)
        entries = _parse_porcelain_z(res.stdout or "")

        staged_num = self._parse_numstat(runner.run("diff", "--cached", "--numstat", "-M").stdout or "")
        work_num = self._parse_numstat(runner.run("diff", "--numstat", "-M").stdout or "")

        ignored_paths = set()
        if include_ignored:
            self._gather_ignored(ignored_paths)

        assume_valid: Dict[str, bool] = {}
        skip_worktree: Dict[str, bool] = {}
        if include_local_changes_ignored:
            self._gather_local_changes_ignored(assume_valid, skip_worktree)

        rows: List[StatusRow] = []
        for e in entries:
            if not include_staged and _is_index_only(e):
                continue
            index_only = _is_index_only(e)
            row = self._row_for_entry(e, staged_num, work_num, index_only)
            if e.is_untracked:
                if not include_unversioned:
                    continue
                row.action = "non-versioned"
                row.state = "untracked"
                if os.path.isfile(self._abs(e.path)):
                    lines = self._count_lines(self._abs(e.path))
                    row.lines_added = lines
            elif e.is_conflicted:
                row.action = "Conflict"
                row.state = "conflicted"
            elif e.index_status == "A":
                row.action = "Added"
                row.state = "added"
            elif e.index_status == "C" or (e.index_status, e.worktree_status) == (" ", "A"):
                row.action = "Copy"
                row.state = "copied"
            elif e.index_status == "R" or e.worktree_status == "R":
                row.action = "Rename"
                row.state = "renamed"
            elif e.index_status == "D" or e.worktree_status == "D":
                row.action = "Deleted"
                row.state = "deleted"
            else:
                row.action = "Modified"
                row.state = "modified"
            row.mtime = self._mtime(e.path)
            rows.append(row)

        for path in sorted(ignored_paths):
            rows.append(self._ignored_row(path))

        for path in sorted(set(assume_valid) | set(skip_worktree)):
            if any(r.path == path for r in rows):
                continue
            row = self._existing_state_row(
                path, assume_valid=path in assume_valid, skip_worktree=path in skip_worktree)
            rows.append(row)

        self.rows = rows
        return rows

    def _row_for_entry(self, e: GitStatusEntry, staged_num, work_num, index_only: bool) -> StatusRow:
        added, removed = 0, 0
        for table in (staged_num, work_num):
            a, rm = table.get(e.path, (0, 0))
            added += a
            removed += rm
        return StatusRow(entry=e, lines_added=added, lines_removed=removed, index_only=index_only)

    def _ignored_row(self, path: str) -> StatusRow:
        return StatusRow(
            entry=GitStatusEntry("!", "!", path),
            action="Ignored", state="ignored", mtime=self._mtime(path))

    def _existing_state_row(self, path: str, assume_valid: bool, skip_worktree: bool) -> StatusRow:
        return StatusRow(
            entry=GitStatusEntry(" ", ",", path),
            action="Assume valid/unchanged" if assume_valid else "Skip worktree",
            state="assumevalid" if assume_valid else "skipworktree",
            mtime=self._mtime(path),
            assume_valid=assume_valid, skip_worktree=skip_worktree)

    # ------------------------------------------------------------------
    # 底层解析
    # ------------------------------------------------------------------
    def _abs(self, path: str) -> str:
        return os.path.normpath(os.path.join(self.repo.root, path))

    def _mtime(self, path: str) -> Optional[datetime]:
        try:
            return datetime.fromtimestamp(os.path.getmtime(self._abs(path)))
        except OSError:
            return None

    @staticmethod
    def _count_lines(path: str) -> int:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return sum(1 for _ in fh)
        except OSError:
            return 0

    @staticmethod
    def _parse_numstat(out: str) -> Dict[str, Tuple[int, int]]:
        """解析 `git diff --numstat`（含 renames 的 {old => new} 形式）。"""
        result: Dict[str, Tuple[int, int]] = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            add, rem = parts[0], parts[1]
            if add == "-":
                add = "0"
            if rem == "-":
                rem = "0"
            path = parts[2]
            path = _unnest_rename(path)
            result[path] = (int(add), int(rem))
        return result

    def _gather_ignored(self, ignored_paths: Dict[str, None]):
        res = self.repo.runner.run(
            "status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=normal")
        out = res.stdout or ""
        for field in out.split("\x00"):
            if not field:
                continue
            if len(field) < 3:
                continue
            if field[:2] == "!!":
                ignored_paths[field[3:]] = None

    def _gather_local_changes_ignored(self, assume_valid: Dict[str, bool],
                                      skip_worktree: Dict[str, bool]):
        res = self.repo.runner.run("ls-files", "-v")
        out = res.stdout or ""
        for line in out.splitlines():
            if len(line) < 3:
                continue
            flag, path = line[0], line[2:]
            if flag == "h":
                assume_valid[path] = True
            elif flag == "S":
                skip_worktree[path] = True

    # ------------------------------------------------------------------
    # 统计（对应 GetStatisticsString）
    # ------------------------------------------------------------------
    def statistics(self) -> Dict[str, int]:
        counts = {"normal": 0, "non-versioned": 0, "modified": 0,
                  "added": 0, "deleted": 0, "conflicted": 0}
        for r in self.rows:
            if r.state == "untracked":
                counts["non-versioned"] += 1
            elif r.state == "conflicted":
                counts["conflicted"] += 1
            elif r.state == "added":
                counts["added"] += 1
            elif r.state == "deleted":
                counts["deleted"] += 1
            elif r.state in ("modified", "renamed", "copied"):
                counts["modified"] += 1
            elif r.state in ("ignored", "assumevalid", "skipworktree"):
                pass
            else:
                counts["normal"] += 1
        return counts

    def line_stats(self) -> Tuple[int, int]:
        added = sum(r.lines_added for r in self.rows)
        removed = sum(r.lines_removed for r in self.rows)
        return added, removed


def _parse_porcelain_z(out: str) -> List[GitStatusEntry]:
    from .status import GitStatus
    return GitStatus._parse_z(out)


def _is_index_only(e: GitStatusEntry) -> bool:
    return bool(e.index_status in ("M", "A", "D", "R", "C", "T") and
                (e.worktree_status in (" ", "")))


def _unnest_rename(path: str) -> str:
    """把 numstat 的 {old => new}（或 old => new）归一到新路径。"""
    if " => " in path:
        start = path.find("{")
        end = path.find("}")
        if start >= 0 and end > start:
            inside = path[start + 1:end]
            old, new = inside.split(" => ", 1)
            prefix, suffix = path[:start], path[end + 1:]
            return f"{prefix}{new}{suffix}"
        return path.split(" => ", 1)[1]
    return path