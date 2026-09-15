"""autostash.py —— 操作前自动暂存本地改动（stash → 操作 → stash pop）。

用于 pull/rebase 等要求工作区干净的操作：本地有未提交改动时，先 stash，
操作完成后再 pop 恢复，避免 "cannot pull with rebase: You have unstaged
changes" 之类直接失败。
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

from contextlib import contextmanager
from typing import Callable, Optional

STASH_MESSAGE = "PyTortoiseGit: auto-stash before operation"


def has_tracked_changes(repo) -> bool:
    """是否有已跟踪文件的未提交改动。

    未跟踪文件通常不阻塞 pull/rebase，忽略（--untracked-files=no）。
    """
    try:
        out = repo.runner.run(
            "status", "--porcelain", "--untracked-files=no").stdout or ""
    except Exception:  # noqa: BLE001
        return False
    return any(line.strip() for line in out.splitlines())


@contextmanager
def auto_stash(repo, log: Optional[Callable[[str], None]] = None):
    """with 块内先 stash，退出时 pop 恢复（无论操作成败）。

    yield 出是否已成功暂存；调用方应在进入前先与用户确认。
    """
    def _emit(text: str) -> None:
        if log and text:
            log(text)

    pushed = repo.runner.run("stash", "push", "-m", STASH_MESSAGE)
    _emit(pushed.stdout)
    _emit(pushed.stderr)
    if pushed.returncode != 0:
        yield False
        return
    try:
        yield True
    finally:
        popped = repo.runner.run("stash", "pop")
        _emit(popped.stdout)
        _emit(popped.stderr)
