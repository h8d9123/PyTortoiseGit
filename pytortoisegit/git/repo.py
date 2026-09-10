"""repo.py —— 基于 GitAdminDir 与 GitRunner 的仓库视图。

对外暴露 Repository 对象：知道根目录、git 目录，能执行命令、读取配置。
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

from ..res.strings import tr

import os
from pathlib import Path
from typing import List, Optional

from .admin import GitAdminDir, find_repo_root
from .git import GitError, GitRunner, RunResult

# 仓库打开失败错误
from .admin import is_git_repo  # re-export 便于旧代码兼容


class NotARepositoryError(Exception):
    def __init__(self, path: str):
        self.path = path
        super().__init__(tr("not_a_repository", "Not a git repository: {path}").format(path=path))


class Repository:
    """一个已打开的 git 仓库。"""

    def __init__(self, root: str, git_dir: str | None = None):
        self.root = os.path.abspath(root)
        self.git_dir = git_dir or os.path.join(self.root, ".git")
        self._runner: Optional[GitRunner] = None

    # ---- 构造 ----
    @classmethod
    def open(cls, path: str) -> "Repository":
        """从任意路径向上查找并打开仓库。"""
        root = find_repo_root(path)
        if root is None:
            raise NotARepositoryError(path)
        return cls(root)

    @classmethod
    def init(cls, path: str, bare: bool = False,
             initial_branch: str | None = None,
             create_dir: bool = False) -> "Repository":
        target = os.path.abspath(path)
        if create_dir:
            os.makedirs(target, exist_ok=True)
        runner = GitRunner(cwd=target)
        result = runner.init(target, bare=bare, initial_branch=initial_branch)
        if result.returncode != 0:
            raise GitError(result.cmd_line, result.returncode, result.stdout, result.stderr)
        if bare:
            return cls(target, git_dir=target)
        return cls.open(target)

    # ---- 命令访问 ----
    @property
    def runner(self) -> GitRunner:
        if self._runner is None:
            self._runner = GitRunner(cwd=self.root)
        return self._runner

    def run(self, *args: str, check: bool = False, **kwargs) -> RunResult:
        return self.runner.run(*args, check=check, **kwargs)

    # ---- 基本属性 ----
    @property
    def name(self) -> str:
        return os.path.basename(self.root) or self.root

    def config(self, key: str, default: str = "") -> str:
        result = self.run("config", "--get", key)
        return result.stdout.strip() if result.returncode == 0 else default

    def config_bool(self, key: str, default: bool = False) -> bool:
        value = self.config(key)
        if value.lower() in ("true", "yes", "on", "1"):
            return True
        if value.lower() in ("false", "no", "off", "0", ""):
            return default if not value else False
        return default

    def set_config(self, key: str, value: str, local: bool = True) -> RunResult:
        args = ["config"]
        if local:
            args.append("--local")
        args.extend([key, value])
        return self.run(*args)

    # ---- 仓库信息 ----
    def is_bare(self) -> bool:
        return self.config_bool("core.bare", default=False)

    def current_branch(self) -> str:
        result = self.run("symbolic-ref", "--short", "-q", "HEAD")
        if result.returncode == 0:
            return result.stdout.strip()
        result = self.run("rev-parse", "--short", "HEAD")
        return result.stdout.strip() or tr("no_commits", "(no commits)")

    def get_remotes(self) -> List[str]:
        result = self.run("remote")
        return result.stdout.splitlines()

    def remote_url(self, name: str) -> str:
        return self.config(f"remote.{name}.url")

    def head_commit(self) -> str:
        result = self.run("rev-parse", "HEAD")
        return result.stdout.strip() if result.returncode == 0 else ""

    # ---- 钩子/文件 ----
    def path_relative(self, path: str) -> str:
        return os.path.relpath(os.path.abspath(path), self.root)

    def full_path(self, relative: str) -> str:
        return os.path.join(self.root, relative)

    def status(self, porcelain: bool = True) -> RunResult:
        return self.runner.status(porcelain=porcelain)

    def __repr__(self) -> str:
        return f"<Repository {self.root!r}>"