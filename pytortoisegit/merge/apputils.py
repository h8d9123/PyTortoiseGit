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

"""apputils.py —— TortoiseMerge 的 CAppUtils（应用工具）。

翻译 AppUtils.h：获取某修订文件(Git 实现)、创建统一 diff、启动外部
diff/merge 工具。
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

from ..git.repo import Repository


def get_versioned_file(repo: Repository, path: str, version: str,
                       save_path: str) -> bool:
    """把指定修订的某文件版本保存到 save_path（翻译 GetVersionedFile）。"""
    try:
        out = repo.runner.run("show", f"{version}:{path}").stdout or ""
        with open(save_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
        return True
    except Exception:
        return False


def create_unified_diff(repo: Repository, path1: str, path2: str) -> str:
    """两个文件/修订之间的统一 diff（翻译 CreateUnifiedDiff）。"""
    try:
        return repo.runner.run("diff", "--no-color", path1, path2).stdout or ""
    except Exception:
        return ""


def run_external_merge(repo: Optional[Repository], base: str, theirs: str,
                       ours: str, merged: str):
    """用外部 merge 工具打开（git mergetool 语义）。"""
    try:
        subprocess.Popen(["git", "mergetool", "--tool-help"], shell=False)
    except OSError:
        pass


def write_merge_output(merged_path: str, text: str):
    os.makedirs(os.path.dirname(os.path.abspath(merged_path)), exist_ok=True)
    with open(merged_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)