"""cmdline.py —— 镜像 TortoiseGit 的 Utils/CmdLineParser。

TortoiseProc.exe 使用如下命令行格式：

    /command:commit /path:"D:\repo" /msg:"commit message" /closeonend:1

- 选项统一带前缀 `/` 或 `-`
- `/option:value` 语义，`/option` 为纯开关
- 值可用 `"` 或 `'` 包围（通常因含空格）
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

import shlex
from dataclasses import dataclass, field
from typing import Dict, List


class CmdLineParsingError(ValueError):
    pass


@dataclass
class CommandLine:
    verb: str = ""
    options: Dict[str, List[str]] = field(default_factory=dict)
    switches: set = field(default_factory=set)
    positional: List[str] = field(default_factory=list)

    def has(self, name: str) -> bool:
        return name in self.options or name in self.switches

    def value(self, name: str, default: str | None = None) -> str | None:
        values = self.options.get(name)
        if values:
            return values[0]
        if name in self.switches:
            return ""
        return default

    def all_values(self, name: str) -> List[str]:
        return list(reversed(self.options.get(name, [])))

    @property
    def path(self) -> str | None:
        """/path 选项（路径列表时的第一项），兼容 cl.path 用法。"""
        return self.value("path")


def _split_tokens(args: List[str] | str) -> List[str]:
    """把命令行拆成 token。参数内可能带引号，用 shlex 处理。

    注意：Windows 下路径含反斜杠，shlex 的 posix 模式会把单个反斜杠
    当作转义符，因此需要在传给 shlex 之前先处理（本项目直接解析原始
    token，不依赖 shlex 解密）。
    """
    if isinstance(args, str):
        args = shlex.split(args, posix=True)
    tokens: List[str] = []
    for arg in args:
        if arg.startswith('"') and arg.endswith('"') and len(arg) > 1:
            arg = arg[1:-1]
        tokens.append(arg)
    return tokens


def parse(argv: List[str] | str) -> CommandLine:
    cl = CommandLine()
    for token in _split_tokens(argv):
        if token.startswith("/") or token.startswith("-"):
            body = token[1:]
            if not body:
                continue
            if ":" in body:
                name, _, raw_value = body.partition(":")
                name = name.strip()
                value = raw_value.strip().strip('"').strip("'")
                cl.options.setdefault(name, []).append(value)
            else:
                cl.switches.add(body.strip())
        else:
            cl.positional.append(token)

    if cl.has("command"):
        cl.verb = cl.value("command", "")
    elif cl.positional:
        # 支持老年版本用法：TortoiseProc /command:xxx，若不提供 command 则取第一个位置参数
        cl.verb = cl.positional[0]
    return cl