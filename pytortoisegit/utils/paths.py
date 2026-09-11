"""paths.py —— 镜像 TortoiseGit 的 Utils/TGitPath。提供跨平台路径处理。"""

from __future__ import annotations

from ..res.strings import tr

import os
import re
from pathlib import Path
from typing import Iterable, List, Optional


class TGitPath:
    """表示一个文件/文件夹路径。同时用于 git 输出中的相对路径。"""

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

    __slots__ = ("_path",)

    def __init__(self, path: str | os.PathLike | "TGitPath" | None = ""):
        if path is None:
            path = ""
        if isinstance(path, TGitPath):
            path = path._path
        path = os.fspath(path)
        self._path = path

    # ---- 基础访问 ----
    @property
    def full(self) -> str:
        """原始字符串形式的路径。"""
        return self._path

    def __str__(self) -> str:
        return self._path

    def __repr__(self) -> str:
        return f"TGitPath({self._path!r})"

    def __eq__(self, other) -> bool:
        if isinstance(other, TGitPath):
            return self._path == other._path
        return self._path == other

    def __hash__(self) -> int:
        return hash(self._path)

    # ---- 转换 ----
    def to_forward(self) -> str:
        return self._path.replace("\\", "/")

    def to_backslash(self) -> str:
        return self._path.replace("/", "\\")

    def norm(self) -> "TGitPath":
        return TGitPath(os.path.normpath(self._path))

    def abs(self) -> "TGitPath":
        return TGitPath(os.path.abspath(os.path.expanduser(self._path)))

    def lower(self) -> "TGitPath":
        return TGitPath(self._path.lower())

    # ---- 判定 ----
    @property
    def is_absolute(self) -> bool:
        return os.path.isabs(self._path)

    @property
    def is_empty(self) -> bool:
        return not self._path

    @property
    def exists(self) -> bool:
        return os.path.exists(self._path)

    @property
    def is_file(self) -> bool:
        return os.path.isfile(self._path)

    @property
    def is_directory(self) -> bool:
        return os.path.isdir(self._path)

    @property
    def is_dir(self) -> bool:
        return self.is_directory

    # ---- 组件 ----
    @property
    def filename(self) -> str:
        parts = [p for p in re.split(r"[\\/]", self._path) if p]
        return parts[-1] if parts else self._path

    @property
    def dirname(self) -> str:
        """父目录。路径以分隔符结尾时先去掉尾部再取 dirname（等价 SDirectoryName）。"""
        stripped = self._path.rstrip("/\\")
        idx = max(stripped.rfind("/"), stripped.rfind("\\"))
        if idx < 0:
            return ""
        parent = stripped[:idx]
        # 保留盘符根，如 "D:\repo" -> "D:\"
        if len(parent) == 2 and parent[1] == ":":
            parent += self._path[idx]
        return parent

    @property
    def extension(self) -> str:
        return os.path.splitext(self._path)[1]

    # ---- 关系 ----
    def is_child_of(self, parent: str | "TGitPath") -> bool:
        """判断 self 是否位于 parent 之下（子孙路径）。同时兼容 / 与 \\ 分隔符。"""
        parent_str = os.path.normcase(str(parent).replace("\\", "/").rstrip("/"))
        self_str = os.path.normcase(self._path.replace("\\", "/"))
        if not parent_str or parent_str == self_str:
            return False
        return self_str.startswith(parent_str + "/")

    def is_same(self, other: str | "TGitPath") -> bool:
        return os.path.normcase(os.path.abspath(self._path)) == os.path.normcase(
            os.path.abspath(str(other))
        )

    def relative_to(self, base: str | "TGitPath") -> str:
        base_str = str(base).replace("\\", "/").rstrip("/")
        self_str = self._path.replace("\\", "/")
        if os.path.normcase(self_str) == os.path.normcase(base_str):
            return ""
        if base_str and os.path.normcase(self_str).startswith(
                os.path.normcase(base_str) + "/"):
            rel = self_str[len(base_str) + 1:]
            parts = rel.split("/")
            return os.path.join(*parts) if parts else ""
        return os.path.relpath(self._path, str(base))

    # ---- 组合 ----
    def join(self, *parts) -> "TGitPath":
        return TGitPath(os.path.join(self._path, *parts))

    def __truediv__(self, other: str) -> "TGitPath":
        return self.join(other)

    # ---- 工具 ----
    def zip_trailing_spaces(self) -> bool:
        """git 标志位：路径是否以空格结尾（git 里用 {} 或换行转义表示）。"""
        return self._path.endswith((" ", "\t"))


def is_in_path(path: str | "TGitPath", parent: str | "TGitPath") -> bool:
    return TGitPath(path).is_child_of(parent)


def same_file_system_reserved(path: str) -> bool:
    """路径是否位于系统保留目录（windows 系统目录等）。简单实现。"""
    drive = os.path.splitdrive(os.path.abspath(path))[0]
    sysdrive = os.path.splitdrive(os.environ.get("SystemRoot", "C:\\Windows"))[0]
    return drive.casefold() == sysdrive.casefold()


GIT_FORBIDDEN_NAMES = ("con", "prn", "aux", "nul", "com1", "com2", "com3", "com4",
                       "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2",
                       "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9")
GIT_FORBIDDEN_CHARS = "\\/:*?\"<>|"

_FORBIDDEN_PATH_RE = re.compile(r"[\\/:*?\"<>|]")


def is_valid_filename(filename: str) -> bool:
    """校验单个文件名是否符合 Windows/git 命名规则（跨平台保守校验）。"""
    if not filename or filename in (".", ".."):
        return False
    if _FORBIDDEN_PATH_RE.search(filename):
        return False
    base = filename.rsplit(".", 1)[0]
    if base.casefold() in GIT_FORBIDDEN_NAMES:
        return False
    if filename.endswith((" ", ".")):
        return False
    return True


def validate_path_for_git(path: str) -> Optional[str]:
    """校验路径能否被 git 接受，返回错误说明或 None。

    采用 Windows/git 的保守命名规则，跨平台均执行校验。
    """
    base = os.path.basename(os.path.abspath(path).replace("\\", "/"))
    if not is_valid_filename(base):
        return tr("invalid_filename", "Invalid file name: {name}").format(name=base)
    return None


def as_paths(items: Iterable[str | TGitPath]) -> List[TGitPath]:
    return [it if isinstance(it, TGitPath) else TGitPath(it) for it in items]


def get_drive(path: str) -> str:
    drive, _ = os.path.splitdrive(os.path.abspath(path))
    return drive


def is_relative_path(path: str) -> bool:
    return not os.path.isabs(path)


def absolutize(path: str, base_cwd: str | None = None) -> str:
    cwd = base_cwd or os.getcwd()
    p = path
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.normpath(p)