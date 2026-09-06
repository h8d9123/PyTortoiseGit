"""externaltools.py —— 外部 diff/合并工具支持。

命令模板保存在 git 配置：
  tortoisegit.externaldiff  外部差异工具模板，占位符 {path}/{repo}/{repo_name}
  tortoisegit.externalmerge 外部合并工具模板，占位符
                            {base}/{local}/{remote}/{merged}/{path}/{repo}/{repo_name}
示例：
  git config --global tortoisegit.externaldiff "C:/Tools/BComp.exe {path} {path}"
  git config --global tortoisegit.externalmerge \
    "C:/Tools/BComp.exe {base} {local} {remote} {merged}"
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
import shlex
import subprocess

from ..git.repo import Repository


def _split(cmd: str) -> list[str]:
    """按 shell 规则拆分命令行（保留引号与 Windows 反斜杠路径）。"""
    try:
        return [tok.strip('"') for tok in shlex.split(cmd, posix=False)]
    except ValueError:
        return cmd.split()


class DiffTool:
    def __init__(self, diff_cmd: str = "", merge_cmd: str = ""):
        self.diff_cmd = diff_cmd
        self.merge_cmd = merge_cmd

    @property
    def has_diff(self) -> bool:
        return bool(self.diff_cmd.strip())

    @property
    def has_merge(self) -> bool:
        return bool(self.merge_cmd.strip())

    @staticmethod
    def from_repo(repo: Repository) -> "DiffTool":
        def _get(key: str) -> str:
            r = repo.runner.run("config", "--get", key)
            if r.returncode == 0 and r.stdout and r.stdout.strip():
                return r.stdout.strip()
            r = repo.runner.run("config", "--global", "--get", key)
            if r.returncode == 0 and r.stdout and r.stdout.strip():
                return r.stdout.strip()
            return ""

        return DiffTool(diff_cmd=_get("tortoisegit.externaldiff"),
                        merge_cmd=_get("tortoisegit.externalmerge"))

    # ---- 占位符填充 ----
    def _fill(self, template: str, **kw) -> str:
        for key, val in kw.items():
            template = template.replace("{" + key + "}", val)
            template = template.replace("$" + key, val)
        return template

    def diff_command(self, repo: Repository, path_a: str, path_b: str) -> list[str]:
        full_a = os.path.join(repo.root, path_a)
        full_b = os.path.join(repo.root, path_b)
        filled = self._fill(
            self.diff_cmd, path=full_a, path_a=full_a, path_b=full_b,
            repo=repo.root, repo_name=repo.name)
        return _split(filled)

    def merge_command(self, repo: Repository, path: str) -> list[str]:
        """为冲突文件 path 构建外部合并命令（先提取三阶段到临时文件）。"""
        from ..git.mergeop import _extract_stage  # noqa: PLC0415
        base, local, remote = _extract_stage(repo, path)
        full = os.path.join(repo.root, path)
        filled = self._fill(
            self.merge_cmd, base=base, local=local, remote=remote, merged=full,
            path=full, repo=repo.root, repo_name=repo.name)
        return _split(filled)


def _run_blocking(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(cmd, close_fds=True)
        return True
    except OSError as exc:  # noqa: BLE001
        print(f"externaltools: 启动失败 {cmd}: {exc}", flush=True)
        return False


def launch_diff(repo: Repository, path_a: str, path_b: str) -> bool:
    tool = DiffTool.from_repo(repo)
    if not tool.has_diff:
        return False
    return _run_blocking(tool.diff_command(repo, path_a, path_b))


def launch_merge_for_conflict(repo: Repository, path: str) -> bool:
    tool = DiffTool.from_repo(repo)
    if not tool.has_merge:
        return False
    return _run_blocking(tool.merge_command(repo, path))