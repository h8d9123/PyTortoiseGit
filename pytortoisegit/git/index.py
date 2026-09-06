"""index.py —— 镜像 TortoiseGit 的 Git/GitIndex。暂存区操作。"""

from __future__ import annotations

from typing import List, Optional, Sequence

from ..udiff import split_patch_hunks
from .repo import Repository
from .status import GitStatusEntry


class GitIndex:
    """索引/暂存区封装。"""

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

    def __init__(self, repo: Repository):
        self.repo = repo

    # ---- 暂存 ----
    def add(self, paths: Sequence[str]) -> int:
        """git add，返回是否成功（0 失败）。"""
        if not paths:
            return 1
        result = self.repo.runner.run("add", "--", *paths, check=False)
        return result.returncode

    def add_all(self) -> int:
        return self.repo.runner.run("add", "-A").returncode

    def remove(self, paths: Sequence[str], cached: bool = False) -> int:
        args = ["rm"]
        if cached:
            args.append("--cached")
        args += ["--", *paths]
        return self.repo.runner.run(*args).returncode

    def reset(self, paths: Sequence[str]) -> int:
        """取消暂存（保留工作区）。"""
        if not paths:
            return self.repo.runner.run("reset").returncode
        return self.repo.runner.run("reset", "--", *paths).returncode

    # ---- 提交 ----
    def commit(self, message: str = "", amend: bool = False,
               author: str | None = None, sign_off: bool = False,
               allow_empty: bool = False):
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
        result = self.repo.runner.run(*args)
        return result

    def commit_revert(self, message_sep: str = "# ------------------------ >8 ------------------------"):
        """(占位) 提交多个文件时使用临时 commit。"""
        raise NotImplementedError

    # ---- 文件级 diff（暂存/未暂存）----
    def diff(self, paths: Sequence[str] | None = None, staged: bool = False,
             unified: int = 3) -> str:
        args = ["diff", f"-U{unified}"]
        if staged:
            args.append("--cached")
        if paths:
            args += ["--", *paths]
        else:
            args.append("--")
        result = self.repo.runner.run(*args)
        return result.stdout

    def ls_files(self, stage: bool = False) -> List[str]:
        args = ["ls-files"]
        if stage:
            args.append("-s")
        result = self.repo.runner.run(*args)
        return result.stdout.splitlines()

    @staticmethod
    def diff_for_entry(entry: GitStatusEntry, staged: bool) -> tuple:
        """决定 diff 使用哪边状态。"""
        if entry.is_untracked:
            return (False, "add")       # 未跟踪：普通 diff 无内容，显示为空新增
        return (staged and entry.is_staged, "worktree")

    # ---- 逐 hunk 暂存（blob 手术）----
    def _index_entry(self, path: str) -> tuple | None:
        """返回 (mode, blob) 或 None（路径不在索引中）。"""
        result = self.repo.runner.run("ls-files", "-s", "--", path)
        line = (result.stdout or "").splitlines()
        if not line:
            return None
        parts = line[0].split()
        if len(parts) < 2:
            return None
        return parts[0], parts[1]

    def _apply_hunk_to_index(self, path: str, hunk_patch: str,
                             reverse: bool = False) -> bool:
        """把单个 hunk 的应用结果写回索引。

        基址取索引 blob（`git show :path`），在 Python 内按 hunk 精确
        行号做增删替换（见 udiff.apply_hunk_text），随后 hash-object 写新
        blob 并用 update-index --index-info 更新。绕开 git apply 在无仓库
        目录对换行/上下文的种种判断（Skipped patch）。
        """
        from ..udiff import apply_hunk_text
        entry = self._index_entry(path)
        if entry is None:
            return False
        _mode, _base_blob = entry

        base = self.repo.runner.run("show", f":{path}")
        if base.returncode != 0 or base.stdout is None:
            return False

        base_text = base.stdout.replace("\r\n", "\n")
        newline = "\r\n" if "\r\n" in base.stdout else "\n"
        norm_patch = hunk_patch.replace("\r\n", "\n")
        new_text = apply_hunk_text(base_text, norm_patch, reverse=reverse)
        if new_text == base_text:
            return False
        if newline == "\r\n":
            new_text = new_text.replace("\n", "\r\n")

        blob = self.repo.runner.run("hash-object", "-w", "--stdin",
                                    input=new_text)
        if blob.returncode != 0:
            return False
        blob_hash = (blob.stdout or "").strip()
        if not blob_hash:
            return False

        # mode 保留原值（100644/100755…），路径在 tab 之后
        rel = path.replace("\\", "/")
        info = f"{_mode} {blob_hash}\t{rel}\n"
        upd = self.repo.runner.run("update-index", "--index-info",
                                   input=info)
        return upd.returncode == 0

    def stage_hunk(self, path: str, hunk_patch: str) -> bool:
        """暂存文件中处于光标的一个 hunk。"""
        return self._apply_hunk_to_index(path, hunk_patch, reverse=False)

    def unstage_hunk(self, path: str, hunk_patch: str) -> bool:
        """取消暂存文件中处于光标的一个 hunk（反向应用）。"""
        return self._apply_hunk_to_index(path, hunk_patch, reverse=True)

    def hunk_patches(self, path: str, staged: bool = False) -> List[str]:
        """取某文件 -U0 diff 并按 hunk 拆分（用于暂存/取消暂存）。"""
        args = ["diff", "-U0", "--no-color"]
        if staged:
            args.append("--cached")
        args += ["--", path]
        out = self.repo.runner.run(*args).stdout or ""
        return split_patch_hunks(out)


def index_has_conflicts(repo: Repository) -> bool:
    """index 是否处于未合并（冲突）状态。"""
    result = repo.runner.run("ls-files", "--unmerged")
    return bool(result.stdout.strip())