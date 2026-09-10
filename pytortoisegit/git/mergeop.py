"""git/mergeop.py —— 镜像 TortoiseGit 的 Git/Merge、Git/Rebase。

构造 merge/rebase 参数与查询分支，冲突识别复用 git/status.py。
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

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .git import RunResult
from .repo import Repository
from .status import GitStatus, GitStatusEntry


class MergeInProgressError(RuntimeError):
    pass


@dataclass
class OpResult:
    """一次 merge/rebase 执行结果。conflicts 为冲突文件列表。"""

    returncode: int
    stdout: str
    stderr: str
    conflicts: List[GitStatusEntry] = field(default_factory=list)
    in_progress: bool = False    # 操作未完成（冲突待解决）

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def local_branches(repo: Repository) -> List[str]:
    """本地分支名列表（当前分支除外）。"""
    out = repo.runner.run("for-each-ref", "refs/heads",
                          "--format=%(refname:short)").stdout or ""
    names = [ln.strip() for ln in out.splitlines() if ln.strip()]
    current = repo.current_branch()
    return [n for n in names if n != current]


def remote_branches(repo: Repository, remote: str | None = None) -> List[str]:
    """远程跟踪分支名列表，如 origin/main。"""
    pattern = f"refs/remotes/{remote}" if remote else "refs/remotes"
    out = repo.runner.run("for-each-ref", pattern,
                          "--format=%(refname:short)").stdout or ""
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def build_merge_args(branch: str, no_ff: bool = False, squash: bool = False,
                     no_commit: bool = False, message: str = "") -> List[str]:
    args = ["merge"]
    if no_ff:
        args.append("--no-ff")
    if squash:
        args.append("--squash")
    if no_commit:
        args.append("--no-commit")
    if message:
        args += ["-m", message]
    args.append(branch)
    return args


def build_rebase_args(branch: str, interactive: bool = False,
                      autostash: bool = False) -> List[str]:
    args = ["rebase"]
    if interactive:
        args.append("-i")
    if autostash:
        args.append("--autostash")
    args.append(branch)
    return args


def conflicted_entries(repo: Repository) -> List[GitStatusEntry]:
    return [e for e in GitStatus(repo).get_status() if e.is_conflicted]


def index_has_merge_conflicts(repo: Repository) -> bool:
    from .index import index_has_conflicts
    return index_has_conflicts(repo)


def abort_merge(repo: Repository) -> bool:
    return repo.runner.run("merge", "--abort").returncode == 0


def abort_rebase(repo: Repository) -> bool:
    return repo.runner.run("rebase", "--abort").returncode == 0


def continue_rebase(repo: Repository) -> bool:
    return repo.runner.run("rebase", "--continue").returncode == 0


def do_merge(repo: Repository, branch: str, **opts) -> OpResult:
    """执行合并。成功返回 ok；冲突时 in_progress=True 且 conflicts 已填充。"""
    args = build_merge_args(branch, **opts)
    result = run_action(repo, args)
    return _finalize(repo, result)


def do_rebase(repo: Repository, branch: str, **opts) -> OpResult:
    args = build_rebase_args(branch, **opts)
    result = run_action(repo, args)
    return _finalize(repo, result)


def run_action(repo: Repository, args: List[str]) -> RunResult:
    in_progress = _repo_state(repo)
    if in_progress:
        raise MergeInProgressError(
            tr("merge_in_progress", "Repository is in {state} state; finish or abort it first").format(state=in_progress))
    return repo.runner.run(*args)


def _repo_state(repo: Repository) -> str:
    for marker, key, default in (("MERGE_HEAD", "state_merge", "merge"), ("rebase-merge", "state_rebase", "rebase"),
                         ("rebase-apply", "state_rebase", "rebase")):
        if repo.git_dir is None:
            continue
        import os
        path = os.path.join(repo.git_dir, marker)
        if os.path.exists(path):
            return tr(key, default)
    return ""


def _finalize(repo: Repository, result: RunResult) -> OpResult:
    conflicts = conflicted_entries(repo) if _repo_state(repo) else []
    return OpResult(result.returncode, result.stdout, result.stderr,
                    conflicts=conflicts, in_progress=_repo_state(repo) != "")


def resolve_as(repo: Repository, path: str, side: str) -> bool:
    """冲突解决：采用 ours/theirs 并 git add 标记已解决。"""
    if side not in ("ours", "theirs"):
        raise ValueError(side)
    repo.runner.run("checkout", f"--{side}", "--", path)
    return repo.runner.run("add", "--", path).returncode == 0


def mark_resolved(repo: Repository, path: str) -> bool:
    return repo.runner.run("add", "--", path).returncode == 0


def _extract_stage(repo: Repository, path: str):
    """将冲突文件的三个暂存阶段写到临时文件，供外部合并工具使用。

    返回 (base, local, remote) 三个文件路径；本地/远端工作区文件由 UI 另行处理。
    """
    import os
    import tempfile

    suffix = os.path.splitext(path)[1] or ".txt"
    fd, base = tempfile.mkstemp(prefix="base_", suffix=suffix)
    os.close(fd)
    fd, local = tempfile.mkstemp(prefix="ours_", suffix=suffix)
    os.close(fd)
    fd, remote = tempfile.mkstemp(prefix="theirs_", suffix=suffix)
    os.close(fd)
    try:
        for stage, dest in (("1", base), ("2", local), ("3", remote)):
            with open(dest, "wb") as f:
                f.write(repo.runner.run("show", f":{stage}:{path}").stdout.encode())
    except Exception:  # noqa: BLE001
        import os as _os
        for p in (base, local, remote):
            try:
                _os.remove(p)
            except OSError:
                pass
        raise
    return base, local, remote