"""dispatcher.py —— 命令分发器。

按 TortoiseGit 的参数协议把命令行映射到命令类。命令可以是：
- 打开对话框（返回 None / "ok" / "cancel"）
- 纯函数命令（不依赖 GUI）

命令命名为 TortoiseGit 的 Command 名：commit、log、diff、blame、clone、sync……
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

import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..cmdline import CommandLine


class UnknownCommandError(ValueError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(name)


@dataclass
class CommandContext:
    """传给命令的上下文：Qt app、解析后的命令行。"""
    qapp: Optional["QApplication"] = None  # noqa: F821
    cl: Optional[CommandLine] = None
    # 可选的额外输出回调（test 中捕获对话框数据用）
    hooks: Dict[str, Callable] = field(default_factory=dict)

    def hook(self, name: str, *args, **kwargs):
        fn = self.hooks.get(name)
        if fn:
            return fn(*args, **kwargs)


CommandFunc = Callable[[CommandContext], Optional[str]]

_REGISTRY: Dict[str, CommandFunc] = {}


def register(name: str):
    def deco(func: CommandFunc) -> CommandFunc:
        _REGISTRY[name] = func
        return func
    return deco


def available_commands() -> List[str]:
    return sorted(_REGISTRY)


def get_command(name: str) -> CommandFunc | None:
    return _REGISTRY.get(name.lower())


def run_command(ctx: CommandContext, name: str) -> Optional[str]:
    func = get_command(name)
    if func is None:
        raise UnknownCommandError(name)
    return func(ctx)


def _ensure_imports():
    """延迟导入各命令模块以注册。"""
    import importlib
    for mod in ("about", "commit", "log", "diff", "blame", "changed",
                "sync", "settings", "clone", "branch", "reflog", "shell",
                "stash", "merge", "rebase", "submodule",
                "push", "pull", "fetch", "reset", "revert", "clean",
                "add", "ignore",
                "export", "formatpatch", "importpatch", "repocreate",
                "updatecheck", "bisect",
                "worktreelist", "newworktree", "switch", "repobrowser",
                "revisiongraph",
                "requestpull", "sendmail", "lfslock", "lfslocks",
                "mergeabort", "addremote", "firststart", "menu",
                "stashsave", "stashpop", "stashapply", "stashlist",
                "subsync", "worktreecreate", "unignore", "lfsunlock",
                "cat", "cleanup", "rename", "resolve", "commitisonrefs",
                "autotexttest", "conflicteditor", "remove", "help",
                "daemon", "pgpfp", "showcompare",
                "crash", "rtfm", "rebuildiconcache",
                "registerwin11contextmenu", "inaccessible",
                "dropcopy", "pastecopy", "dropcopyadd", "dropmove",
                "pastemove", "dropworktreecreate",
                "svndcommit", "svnfetch", "svnrebase", "svnignore",
                "repostatus"):
        try:
            importlib.import_module(f".{mod}", __package__)
        except ImportError:
            pass


def dispatch(verb: str, ctx: CommandContext) -> Optional[str]:
    """分发主入口（自动导入插件）。"""
    _ensure_imports()
    return run_command(ctx, verb)