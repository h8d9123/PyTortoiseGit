"""git/stash.py —— 镜像 TortoiseGit 的 Git/GitStash：stash 操作封装。

解析 `git stash list` 并封装 push/apply/pop/drop/clear/show。
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
from typing import List, Optional

from .repo import Repository


@dataclass
class StashEntry:
    """一条 stash(引用名 + 说明 + 提交时间 + 完整哈希)。"""

    gd: str            # stash@{0}
    subject: str = ""
    date: str = ""     # %ci ISO 8601
    hash: str = ""

    @property
    def display_text(self) -> str:
        if self.subject:
            return f"{self.gd}  {self.subject}"
        return self.gd


class GitStash:
    """仓库 stash 操作（`git stash …` 封装）。"""

    def __init__(self, repo: Repository):
        self.repo = repo

    def list(self) -> List[StashEntry]:
        """列出所有 stash。字段间以 NUL 分隔，记录间换行。"""
        out = self.repo.runner.run(
            "stash", "list", "--format=%gd%x00%s%x00%ci%x00%H").stdout or ""
        entries: List[StashEntry] = []
        for line in out.splitlines():
            fields = line.split("\x00")
            if len(fields) >= 4:
                entries.append(StashEntry(fields[0], fields[1], fields[2], fields[3]))
            elif fields[0]:
                entries.append(StashEntry(fields[0]))
        return entries

    def create(self, message: str = "",
               include_untracked: bool = False,
               keep_index: bool = False) -> bool:
        """暂存当前工作区（stash push）。返回是否成功。"""
        args = ["stash", "push"]
        if include_untracked:
            args.append("--include-untracked")
        if keep_index:
            args.append("--keep-index")
        if message:
            args += ["-m", message]
        return self.repo.runner.run(*args).returncode == 0

    def apply(self, gd: str, restore_index: bool = False) -> bool:
        args = ["stash", "apply"]
        if restore_index:
            args.append("--index")
        args.append(gd)
        return self.repo.runner.run(*args).returncode == 0

    def pop(self, gd: str) -> bool:
        return self.repo.runner.run("stash", "pop", gd).returncode == 0

    def drop(self, gd: str) -> bool:
        return self.repo.runner.run("stash", "drop", gd).returncode == 0

    def clear(self) -> bool:
        return self.repo.runner.run("stash", "clear").returncode == 0

    def show(self, gd: str) -> str:
        """stash diff 文本（stash show -p）。"""
        return self.repo.runner.run("stash", "show", "-p", gd).stdout or ""

    def latest(self) -> Optional[StashEntry]:
        entries = self.list()
        return entries[0] if entries else None