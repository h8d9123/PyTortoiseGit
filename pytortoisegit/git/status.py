"""status.py —— 镜像 TortoiseGit 的 Git/GitStatus、Git/GitStatusListCtrl。

解析 `git status --porcelain=v1 -z` 输出。注意 `-z` 下字段以 NUL 分隔、实体转义。
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

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .repo import Repository

# porcelain v1 状态字母 → 含义
_STATUS_NAMES = {
    "?": "未跟踪",
    "M": "已修改",
    "A": "已暂存",
    "D": "已删除",
    "R": "已重命名",
    "C": "已复制",
    "U": "未合并",
    "T": "类型变化",
    "!": "被忽略",
}

STATUS_INDEX = "index"
STATUS_WORKTREE = "worktree"
STATUS_UNTRACKED = "untracked"
STATUS_CONFLICT = "conflict"


@dataclass
class GitStatusEntry:
    """一个文件的状态条目。"""

    index_status: str            # X 列：stage/索引
    worktree_status: str         # Y 列：工作区
    path: str
    orig_path: str = ""          # 重命名/复制时原路径
    using_default_format: bool = False

    @property
    def is_untracked(self) -> bool:
        return self.index_status == "?" or self.worktree_status == "?"

    @property
    def is_modified(self) -> bool:
        return (self.index_status == "M" or self.index_status in ("A", "D", "R", "C", "T")
                or self.worktree_status in ("M", "A", "D", "R", "C", "T"))

    @property
    def is_staged(self) -> bool:
        return self.index_status in ("M", "A", "D", "R", "C", "T")

    @property
    def is_conflicted(self) -> bool:
        return (self.index_status, self.worktree_status) in {
            ("U", "U"), ("U", "A"), ("U", "D"),
            ("A", "U"), ("D", "U"), ("A", "A"), ("D", "D"),
        }

    @property
    def status_text(self) -> str:
        if self.is_untracked:
            return "未跟踪"
        parts = []
        if self.is_staged:
            parts.append("index:" + _STATUS_NAMES.get(self.index_status, self.index_status))
        if self.worktree_status and self.worktree_status not in " ":
            parts.append("worktree:" + _STATUS_NAMES.get(self.worktree_status, self.worktree_status))
        return " ".join(parts) or "?"

    @property
    def display_path(self) -> str:
        if self.orig_path:
            return f"{self.orig_path} → {self.path}"
        return self.path


class GitStatus:
    """仓库当前状态解析。"""

    def __init__(self, repo: Repository, ignore_submodules: bool = False):
        self.repo = repo
        self.ignore_submodules = ignore_submodules
        self.entries: List[GitStatusEntry] = []

    def get_status(self) -> List[GitStatusEntry]:
        args = ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
        if self.ignore_submodules:
            args.append("--ignore-submodules=dirty")
        result = self.repo.runner.run(*args)
        if result.returncode != 0:
            return []
        self.entries = self._parse_z(result.stdout)
        return self.entries

    @staticmethod
    def _parse_z(out: str) -> List[GitStatusEntry]:
        """解析 `-z` 输出。条目间用 NUL 分隔；重命名是两段。"""
        # -z 模式下 git 会去除引号转义，直接以 NUL 分隔字段
        raw_fields: List[str] = out.split("\x00")
        entries: List[GitStatusEntry] = []
        fields_iter = iter(raw_fields)
        for field_val in fields_iter:
            if not field_val:
                continue
            if len(field_val) < 3:
                continue
            x, y, sep, path = field_val[0], field_val[1], field_val[2], field_val[3:]
            if sep != " ":
                # 重命名/复制：下一字段是原路径
                try:
                    orig = next(fields_iter)
                except StopIteration:
                    orig = ""
                entries.append(GitStatusEntry(x, y, path, orig_path=orig))
            else:
                entries.append(GitStatusEntry(x, y, path))
        return entries

    def counts(self) -> Dict[str, int]:
        if not self.entries:
            self.get_status()
        staged = sum(1 for e in self.entries if e.is_staged)
        modified = sum(1 for e in self.entries if e.is_modified and not e.is_staged)
        untracked = sum(1 for e in self.entries if e.is_untracked)
        conflicted = sum(1 for e in self.entries if e.is_conflicted)
        return {"staged": staged, "modified": modified,
                "untracked": untracked, "conflicted": conflicted}