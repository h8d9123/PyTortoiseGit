"""admin.py —— 镜像 TortoiseGit 的 Git/GitAdminDir。

负责向上/向下查找 .git 目录，判定某路径是否位于 git 仓库内。
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
from pathlib import Path
from typing import Iterable, List, Optional

from .git import GitRunner

_WORKTREE_FILE = "commondir"


class GitAdminDir:
    """查找仓库的 .git 管理目录。"""

    def __init__(self, path: str | os.PathLike | None = None):
        self._path = os.path.abspath(os.fspath(path or os.getcwd()))
        self._git_dir: Optional[str] = None

    @property
    def git_dir(self) -> Optional[str]:
        """向上遍历查找 .git 目录；不存在返回 None。"""
        if self._git_dir is not None:
            return self._git_dir
        start = self._path
        cur = start if os.path.isdir(start) else os.path.dirname(start)
        while True:
            cand = os.path.join(cur, ".git")
            if os.path.isdir(cand) or os.path.isfile(cand):
                self._git_dir = cand
                return cand
            parent = os.path.dirname(cur)
            if parent == cur:
                return None
            cur = parent

    @property
    def is_inside_worktree(self) -> bool:
        return self.git_dir is not None

    def get_worktree_root(self) -> Optional[str]:
        """解析出工作树根目录。处理 gitfile、submodule、裸仓库。"""
        git_dir = self.git_dir
        if git_dir is None:
            return None
        if os.path.isdir(git_dir):
            return os.path.dirname(git_dir)
        # gitfile 形式：.git 文件里写 gitdir: <path>
        try:
            with open(git_dir, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
        except OSError:
            return os.path.dirname(git_dir)
        if content.startswith("gitdir:"):
            target = content[7:].strip()
            if not os.path.isabs(target):
                target = os.path.join(os.path.dirname(git_dir), target)
            return os.path.dirname(target)
        return os.path.dirname(git_dir)

    def is_versioned(self, path: str | os.PathLike | None = None,
                     submodules: bool = True) -> bool:
        """路径是否在版本控制之下（submodule 递归可选）。"""
        target = os.path.abspath(os.fspath(path or self._path))
        root = self.get_worktree_root()
        if root is None:
            return False
        if _inside_parent(root, target):
            return True
        if submodules and not _inside_parent(root, target):
            # 子模块路径：.git/modules/<name>
            modules_dir = os.path.join(self.git_dir or "", "../modules")
            return os.path.isdir(os.path.join(modules_dir, target))
        return False


def _inside_parent(parent: str, child: str) -> bool:
    parent = os.path.normcase(parent)
    child = os.path.normcase(child)
    if child == parent:
        return True
    return child.startswith(parent + os.sep)


def find_repo_root(path: str | os.PathLike) -> Optional[str]:
    """从给定路径（文件或目录）向上查找工作树根，未找到返回 None。"""
    return GitAdminDir(path).get_worktree_root()


def is_git_repo(path: str | os.PathLike) -> bool:
    return GitAdminDir(path).git_dir is not None


def git_dir_of(path: str | os.PathLike) -> Optional[str]:
    return GitAdminDir(path).git_dir