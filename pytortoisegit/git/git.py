"""git.py —— 镜像 TortoiseGit 的 Git/Git.cpp。git 命令封装（GitRunner）。

统一通过 subprocess 执行 git，输出按 UTF-8 解码，路径不经转义处理
（`-c core.quotepath=false`）。
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
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


class GitError(Exception):
    """git 命令执行失败。"""

    def __init__(self, cmd_line: Sequence[str], returncode: int,
                 stdout: str = "", stderr: str = ""):
        self.cmd_line = cmd_line
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        message = " ".join(cmd_line) or "(empty cmd)"
        if returncode:
            message += f"\n{tr('exit_code', 'Exit code')}: {returncode}"
        if stderr:
            message += "\nstderr: " + stderr.strip()
        if stdout and returncode:
            message += "\nstdout: " + stdout.strip()
        super().__init__(message)


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    cmd_line: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def stdout_lines(self) -> list:
        return self.stdout.splitlines()


def _settings_value(key: str, default: str = "") -> str:
    """读取 General 设置页保存的应用级配置（避免 GUI 依赖，用 try 包裹）。"""
    try:
        from PySide6.QtCore import QSettings
        return str(QSettings("PyTortoiseGit", "PyTortoiseGit").value(key, default) or "")
    except Exception:  # noqa: BLE001
        return default


def find_git_executable() -> str:
    """定位 git 可执行文件。优先级：GIT_PATH > 设置页 gitPath > PATH 中的 git。"""
    env_path = os.environ.get("GIT_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    settings_path = _settings_value("gitPath")
    if settings_path and os.path.isfile(settings_path):
        return settings_path
    found = shutil.which("git")
    if found:
        return found
    raise RuntimeError(tr("git_not_found", "git executable not found; install git or set the GIT_PATH environment variable"))


class GitRunner:
    """执行 git 命令的轻量封装。"""

    DEFAULT_ENCODING = "utf-8"

    def __init__(self, git_executable: str | None = None,
                 cwd: str | os.PathLike | None = None,
                 quote_path: bool = False):
        self.git = git_executable or find_git_executable()
        self.cwd = cwd
        self.quote_path = quote_path
        self.env = os.environ.copy()
        self.env.setdefault("GIT_TERMINAL_PROMPT", "0")
        extra_path = _settings_value("extraPath")
        if extra_path:
            self.env["PATH"] = extra_path + os.pathsep + self.env.get("PATH", "")
        self.extra_args: List[str] = []

    # ---- 低层 ----
    def _build_args(self, args: List[str]) -> List[str]:
        base = [self.git]
        if not self.quote_path:
            base.append("-c")
            base.append("core.quotepath=false")
        base.extend(self.extra_args)
        base.extend(args)
        return base

    def run(self, *args: str, check: bool = False,
            cwd: str | os.PathLike | None = None,
            input: str | bytes | None = None,
            timeout: float | None = None,
            capture_output: bool = True
            ) -> RunResult:
        cmd = self._build_args(list(args))
        final_cwd = cwd or self.cwd
        stdout = subprocess.PIPE if capture_output else None
        stderr = subprocess.PIPE if capture_output else None
        try:
            proc = subprocess.run(
                cmd,
                cwd=final_cwd,
                input=input.encode(self.DEFAULT_ENCODING) if isinstance(input, str) else input,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                env=self.env,
                shell=False,
            )
        except OSError as exc:
            raise GitError(cmd, 127, stderr=str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(cmd, 124, stderr=tr("command_timeout", "Command timed out")) from exc

        out = _decode(proc.stdout) if proc.stdout is not None else ""
        err = _decode(proc.stderr) if proc.stderr is not None else ""
        result = RunResult(proc.returncode, out, err, cmd)
        if check and result.returncode != 0:
            raise GitError(cmd, result.returncode, result.stdout, result.stderr)
        return result

    def run_checked(self, *args: str, **kwargs) -> str:
        """执行并返回 stdout（失败抛出 GitError）。"""
        result = self.run(*args, **kwargs, check=True)
        return result.stdout

    def run_interactive(self, *args: str, **kwargs) -> RunResult:
        """执行可能需认证的 git 命令，启用 Askpass 桥接自动弹认证框。"""
        from .. import askpass  # 延迟导入避免循环
        env = askpass.setup_askpass(self.env, root=self.cwd)
        prev = self.env
        self.env = env
        try:
            return self.run(*args, **kwargs)
        finally:
            self.env = prev

    # ---- 常用命令 ----
    def version(self) -> str:
        return self.run("--version").stdout.strip()

    def init(self, path: str | os.PathLike, bare: bool = False,
             initial_branch: str | None = None) -> RunResult:
        args = ["init"]
        if bare:
            args.append("--bare")
        if initial_branch:
            args += ["--initial-branch", initial_branch]
        return self.run(*args, cwd=path)

    def status(self, porcelain: bool = True) -> RunResult:
        if porcelain:
            return self.run("status", "--porcelain=v1", "-z", "--untracked-files=all")
        return self.run("status")

    def add(self, paths: Sequence[str | os.PathLike]) -> RunResult:
        return self.run("add", "--", *[os.fspath(p) for p in paths])

    def reset(self, *paths: str) -> RunResult:
        if paths:
            return self.run("reset", "--", *paths)
        return self.run("reset")

    def commit(self, message: str = "", amend: bool = False,
               author: str | None = None, sign_off: bool = False,
               allow_empty: bool = False) -> RunResult:
        args = ["commit"]
        if message:
            args += ["-m", message]
        if amend:
            args.append("--amend")
        if author:
            args += ["--author", author]
        if sign_off:
            args.append("--signoff")
        if allow_empty:
            args.append("--allow-empty")
        return self.run(*args)

    def diff(self, *args: str) -> RunResult:
        return self.run("diff", *args)

    def log(self, *args: str, extra: Iterable[str] = ()) -> RunResult:
        return self.run("log", *args, *extra)

    def branch(self, *args: str) -> RunResult:
        return self.run("branch", *args)

    def tag(self, *args: str) -> RunResult:
        return self.run("tag", *args)

    # ---- 定位 ----
    @staticmethod
    def rev_parse_git_dir(path: str | os.PathLike) -> str:
        """返回给定目录所属仓库的 .git 目录（绝对路径）。"""
        return GitRunner._rev_parse(path, "--git-dir")

    @staticmethod
    def _rev_parse(path: str | os.PathLike, arg: str) -> str:
        runner = GitRunner(cwd=path)
        result = runner.run("rev-parse", arg)
        if result.returncode != 0:
            return ""
        value = result.stdout.strip()
        return os.path.abspath(os.path.join(os.fspath(path), value)) \
            if not os.path.isabs(value) else value


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")