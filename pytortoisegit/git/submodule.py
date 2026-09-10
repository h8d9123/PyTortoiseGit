"""git/submodule.py —— 镜像 TortoiseGit 的 Git/GitSubmodule。

解析 `git submodule status` 并封装 add/update/deinit/sync。
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
from typing import List

from .repo import Repository
from ..res.strings import tr

# 状态字符含义 → (i18n key, 英文默认)
_STATUS_NAMES = {
    " ": ("submodule_ok", "Up to date"),
    "-": ("submodule_notinit", "Not initialized"),
    "+": ("submodule_mismatch", "Commit mismatch"),
    "U": ("submodule_conflict", "Conflict"),
}


@dataclass
class SubmoduleEntry:
    """一个子模块：路径 + 状态 + sha1 + 描述/url。"""

    path: str
    status_char: str = " "
    sha1: str = ""
    description: str = ""

    @property
    def module_path(self) -> str:
        return self.path

    @property
    def status_text(self) -> str:
        key, default = _STATUS_NAMES.get(self.status_char, (self.status_char, self.status_char))
        return tr(key, default)


def _parse_submodule_status(out: str) -> List[SubmoduleEntry]:
    """解析 `git submodule status [--recursive]` 输出。

    行格式：`{statuschar}{sha} {path} ({describe})`，尾部的 `(describe)`
    仅在可描述时出现，如 `(heads/main)`、`(untracked)`。
    """
    entries: List[SubmoduleEntry] = []
    for line in out.splitlines():
        if len(line) < 42:
            continue
        status = line[0]
        sha1 = line[1:41].strip()
        path = line[41:].strip()
        describe = ""
        if path.endswith(")") and " (" in path:
            path, _, describe = path.rpartition(" (")
            path = path.strip()
            describe = describe.rstrip(")")
        entries.append(SubmoduleEntry(path, status, sha1, describe))
    return entries


def submodule_urls(repo: Repository) -> dict:
    """读取 .gitmodules 中每个子模块的 url。"""
    out = repo.runner.run("config", "-f", ".gitmodules", "--list").stdout or ""
    urls: dict = {}
    for line in out.splitlines():
        key, _, val = line.partition("=")
        if key.startswith("submodule.") and key.endswith(".url"):
            urls[key[len("submodule."):-len(".url")]] = val
    return urls


class GitSubmodule:
    """子模块操作。"""

    def __init__(self, repo: Repository):
        self.repo = repo

    def list(self, recursive: bool = False) -> List[SubmoduleEntry]:
        args = ["submodule", "status"]
        if recursive:
            args.append("--recursive")
        out = self.repo.runner.run(*args).stdout or ""
        entries = _parse_submodule_status(out)
        urls = submodule_urls(self.repo)
        for e in entries:
            # 优先显示 .gitmodules 的远程 url，其次用 status 的 describe 后缀
            if urls.get(e.path):
                e.description = urls[e.path]
        return entries

    def add(self, path: str, url: str, force: bool = False) -> bool:
        args = ["submodule", "add"]
        if force:
            args.append("--force")
        args.append(url)
        args.append(path)
        return self.repo.runner.run(*args).returncode == 0

    def update(self, init: bool = False, recursive: bool = False,
               force: bool = False) -> bool:
        args = ["submodule", "update"]
        if init:
            args.append("--init")
        if recursive:
            args.append("--recursive")
        if force:
            args.append("--force")
        return self.repo.runner.run(*args).returncode == 0

    def deinit(self, path: str, force: bool = False) -> bool:
        args = ["submodule", "deinit"]
        if force:
            args.append("--force")
        args.append("--")
        args.append(path)
        return self.repo.runner.run(*args).returncode == 0

    def sync(self, recursive: bool = False) -> bool:
        args = ["submodule", "sync"]
        if recursive:
            args.append("--recursive")
        return self.repo.runner.run(*args).returncode == 0

    def foreach_status(self) -> str:
        return self.repo.runner.run(
            "submodule", "foreach", "--quiet",
            "git describe --always --dirty").stdout or ""

    def inited(self, path: str) -> bool:
        """判断子模块是否已初始化。

        git 2.46 下子模块的 `.git` 是文件（gitdir 指针）而非目录，
        因此用 exists 而非 isdir。
        """
        return os.path.exists(os.path.join(self.repo.root, path, ".git"))