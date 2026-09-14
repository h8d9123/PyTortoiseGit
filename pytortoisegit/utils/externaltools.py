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


# 支持 {}、$、% 三种占位符风格；命令模板含任一即视为“已自带参数”。
_DIFF_PLACEHOLDERS = ("{path}", "{path_a}", "{path_b}", "%path",
                      "%base", "%mine")
_MERGE_PLACEHOLDERS = ("{base}", "{local}", "{remote}", "{merged}", "{path}",
                       "%base", "%theirs", "%mine", "%merged", "%path")


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
            template = template.replace("%" + key, val)
        return template

    def diff_command_paths(self, repo: Repository, full_a: str,
                           full_b: str) -> list[str]:
        """用两个绝对路径构造外部比较命令。

        对齐原版 StartExtDiff：模板未含占位符时，自动追加两个文件参数
        （这样只填“程序路径”也能正常比较）。
        """
        has_pos = any(p in self.diff_cmd for p in _DIFF_PLACEHOLDERS)
        filled = self._fill(
            self.diff_cmd, path=full_a, path_a=full_a, path_b=full_b,
            base=full_a, mine=full_b, repo=repo.root, repo_name=repo.name)
        cmd = _split(filled)
        if not has_pos:
            cmd += [full_a, full_b]
        return cmd

    def diff_command(self, repo: Repository, path_a: str, path_b: str) -> list[str]:
        full_a = os.path.join(repo.root, path_a)
        full_b = os.path.join(repo.root, path_b)
        return self.diff_command_paths(repo, full_a, full_b)

    def merge_command(self, repo: Repository, path: str) -> list[str]:
        """为冲突文件 path 构建外部合并命令（先提取三阶段到临时文件）。

        对齐原版 StartExtMerge：模板未含占位符时，自动追加
        ``base theirs mine merged`` 四个文件参数。
        """
        from ..git.mergeop import _extract_stage  # noqa: PLC0415
        base, local, remote = _extract_stage(repo, path)
        full = os.path.join(repo.root, path)
        has_pos = any(p in self.merge_cmd for p in _MERGE_PLACEHOLDERS)
        filled = self._fill(
            self.merge_cmd, base=base, local=local, remote=remote,
            mine=local, theirs=remote, merged=full, path=full,
            repo=repo.root, repo_name=repo.name)
        cmd = _split(filled)
        if not has_pos:
            # 原版顺序：%base %theirs %mine %merged
            cmd += [base, remote, local, full]
        return cmd


def _run_blocking(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(cmd, close_fds=True)
        return True
    except OSError as exc:  # noqa: BLE001
        print(f"externaltools: failed to start {cmd}: {exc}", flush=True)
        return False


def launch_diff(repo: Repository, path_a: str, path_b: str) -> bool:
    tool = DiffTool.from_repo(repo)
    if not tool.has_diff:
        return False
    return _run_blocking(tool.diff_command(repo, path_a, path_b))


def launch_diff_paths(repo: Repository, full_a: str, full_b: str) -> bool:
    """用两个绝对路径启动外部比较工具。"""
    tool = DiffTool.from_repo(repo)
    if not tool.has_diff:
        return False
    return _run_blocking(tool.diff_command_paths(repo, full_a, full_b))


def materialize_revision(repo: Repository, rev: str, git_path: str) -> str | None:
    """把 rev:git_path 的内容导出到临时文件；rev 为空表示工作区文件。

    返回绝对路径；失败返回 None。
    """
    import tempfile  # noqa: PLC0415

    if not rev or rev.upper() in ("WORKING", "WORKTREE", "WORKINGTREE", "WORKING_DIR"):
        full = os.path.join(repo.root, git_path)
        return full if os.path.isfile(full) else None
    result = repo.runner.run("show", f"{rev}:{git_path}")
    if result.returncode != 0:
        return None
    suffix = os.path.splitext(git_path)[1]
    fd, tmp = tempfile.mkstemp(prefix="ptg_extdiff_", suffix=suffix)
    os.close(fd)
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(result.stdout)
    return tmp


def launch_merge_for_conflict(repo: Repository, path: str) -> bool:
    tool = DiffTool.from_repo(repo)
    if not tool.has_merge:
        return False
    return _run_blocking(tool.merge_command(repo, path))


def diff_enabled() -> bool:
    """设置页“差异查看器”是否选择了“外部”(DiffUseExternal)。"""
    try:
        from ..dialogs.settingsdlg import general_settings
        return general_settings().value("DiffUseExternal", 0, type=int) == 1
    except Exception:  # noqa: BLE001
        return False


def start_diff(parent, repo: Repository, git_path: str,
               rev1: str | None, rev2: str | None = None) -> bool:
    """打开文件差异：按设置选择外部工具，否则内置 TortoiseGitMerge。

    对齐原版 CAppUtils::StartExtDiff / StartDiff：差异列表双击、
    “与基准比较”等入口统一走这里。
    """
    if diff_enabled():
        tool = DiffTool.from_repo(repo)
        if tool.has_diff:
            a = materialize_revision(repo, rev1, git_path)
            b = materialize_revision(repo, rev2, git_path)
            if a and b and launch_diff_paths(repo, a, b):
                return True
    from ..merge.mergefrm import MergeFrm
    MergeFrm(repo, git_path, rev1, rev2, parent=parent).show()
    return True