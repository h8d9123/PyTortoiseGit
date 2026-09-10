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

"""patch.py —— TortoiseMerge 的 CPatch（unified diff 解析/应用）。

翻译 Patch.h：解析 unified diff 文件、取出文件/修订/路径、应用补丁。
用 git 子命令实现应用；解析基于 udiff。
"""

from __future__ import annotations

from ..res.strings import tr

import os
import re
from typing import List, Optional, Tuple

from ..git.repo import Repository
from ..udiff import parse_diff, split_diff
from .filetextlines import FileTextLines

# PATCHSTATE_*（翻译 Patch.h）
PATCHSTATE_REMOVED = 0
PATCHSTATE_ADDED = 1
PATCHSTATE_CONTEXT = 2


class _FileDiff:
    """一个文件的补丁块。"""
    path = ""
    revision = ""
    path2 = ""
    revision2 = ""
    chunks: List[tuple] = []  # (lRemoveStart, lRemoveLength, lAddStart, lAddLength, lines, states, eols)


def _strip(filename: str, n_strip: int) -> str:
    """Strip：去掉路径前 n_strip 段（翻译 CPatch::Strip）。"""
    parts = filename.replace("\\", "/").split("/")
    return "/".join(parts[n_strip:]) if n_strip < len(parts) else filename


class Patch:
    """处理 unified diff 文件（解析 + 应用）。"""

    def __init__(self, repo: Optional[Repository] = None):
        self.repo = repo
        self._file_diffs: List[_FileDiff] = []
        self._error: str = ""
        self._raw: str = ""
        self._strip_n: int = 0

    # ---- GetNumberOfFiles / GetFilename / GetRevision ----
    def get_number_of_files(self) -> int:
        return len(self._file_diffs)

    def get_filename(self, index: int) -> str:
        return self._file_diffs[index].path if 0 <= index < len(self._file_diffs) else ""

    def get_filename2(self, index: int) -> str:
        return self._file_diffs[index].path2 if 0 <= index < len(self._file_diffs) else ""

    def get_revision(self, index: int) -> str:
        return self._file_diffs[index].revision if 0 <= index < len(self._file_diffs) else ""

    def get_revision2(self, index: int) -> str:
        return self._file_diffs[index].revision2 if 0 <= index < len(self._file_diffs) else ""

    def get_error_message(self) -> str:
        return self._error

    def get_full_path(self, s_path: str, index: int, fileno: int = 0) -> str:
        target = self.get_filename(index) if fileno == 0 else self.get_filename2(index)
        if target:
            return os.path.join(s_path, target)
        return s_path

    # ---- 解析（OpenUnifiedDiffFile / ParsePatchFile）----
    def open_unified_diff_file(self, filename: str) -> bool:
        try:
            with open(filename, encoding="utf-8", errors="replace") as fh:
                return self.parse_text(fh.read())
        except OSError as exc:
            self._error = str(exc)
            return False

    def parse_text(self, diff_text: str) -> bool:
        self._raw = diff_text or ""
        patches = parse_diff(diff_text)
        self._file_diffs = []
        for p in patches:
            fd = _FileDiff()
            fd.path = p.old_path or p.new_path
            fd.path2 = p.new_path or ""
            fd.revision = ""
            fd.revision2 = ""
            self._file_diffs.append(fd)
        if not self._file_diffs:
            self._error = tr("patch_no_diff", "No patch could be parsed")
        return bool(self._file_diffs)

    # ---- 路径检查 / 匹配计数（对齐 CheckPatchPath/CountMatches/CountDirMatches）----
    @staticmethod
    def check_patch_path(path: str) -> str:
        """拒绝绝对路径与 ..（返回空串表示不安全）。"""
        p = (path or "").replace("\\", "/")
        if re.match(r"^[A-Za-z]:", p) or p.startswith("/"):
            return ""
        if ".." in p.split("/"):
            return ""
        return path

    def count_matches(self, path: str) -> int:
        norm = (path or "").replace("\\", "/")
        n = 0
        for fd in self._file_diffs:
            for cand in (fd.path, fd.path2):
                if cand and cand.replace("\\", "/").endswith(norm):
                    n += 1
                    break
        return n

    def count_dir_matches(self, path: str) -> int:
        norm = (path or "").replace("\\", "/").rstrip("/") + "/"
        return sum(1 for fd in self._file_diffs
                   if fd.path.replace("\\", "/").startswith(norm))

    @staticmethod
    def has_unicode_bom(text: str) -> bool:
        return text.startswith("\ufeff")

    @staticmethod
    def remove_unicode_bom(text: str) -> str:
        return text[1:] if text.startswith("\ufeff") else text

    # ---- 应用补丁（PatchFile → git apply）----
    def patch_file(self, strip: int, n_index: int, s_path: str,
                   s_save_path: str = "", s_base_file: str = "",
                   force: bool = False) -> int:
        """把补丁第 n_index 个文件应用到 s_path。成功返回 0。

        用 `git apply -p<strip> [--3way]` 实现；s_save_path 指定时输出到该路径。
        """
        if not self._raw:
            return -1
        import tempfile
        from ..git.git import GitRunner
        runner = self.repo.runner if self.repo else GitRunner(cwd=s_path)
        with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False,
                                         encoding="utf-8", newline="") as fh:
            fh.write(self._raw)
            tmp = fh.name
        try:
            args = ["apply", f"-p{strip}"]
            if force:
                args.append("--3way")
            if s_save_path:
                args += ["--directory", s_save_path]
            args.append(tmp)
            res = runner.run(*args, cwd=s_path)
            if res.returncode != 0:
                self._error = (res.stderr or "").strip()
            return res.returncode
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def apply_patch(self, diff_text: str, cwd: str | None = None,
                    strip: int = 1, force: bool = False) -> int:
        """用 git apply 应用补丁（需 repo）。成功返回 0。"""
        if self.repo is None:
            return -1
        runner = self.repo.runner
        args = ["apply", f"-p{strip}"]
        if force:
            args.append("--3way")
        args.append("-")
        res = runner.run(*args, input=diff_text, cwd=cwd)
        if res.returncode != 0:
            self._error = (res.stderr or "").strip()
        return res.returncode