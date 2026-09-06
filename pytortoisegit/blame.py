"""blame.py —— 镜像 TortoiseGit 的 src/TortoiseGitBlame。

解析 `git blame --porcelain` 输出，得到每行对应提交与作者。
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

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .git.repo import Repository

_SHA_RE = re.compile(r"^[0-9a-f]{40}(?:\s|$)")
_TAB = "\t"


@dataclass
class BlameLine:
    sha: str
    original_line: int          # 在原文件中该行的行号
    final_line: int             # 在当前文件中的行号
    author: str = ""
    author_email: str = ""
    author_date: int = 0
    summary: str = ""
    content: str = ""

    @property
    def short_sha(self) -> str:
        return self.sha[:8]

    @property
    def author_date_dt(self) -> Optional[datetime]:
        try:
            return datetime.fromtimestamp(self.author_date)
        except (OSError, ValueError, TypeError, OverflowError):
            return None

    def date_span(self) -> str:
        dt = self.author_date_dt
        return f"{dt:%Y-%m-%d}" if dt else ""


class GitBlame:
    """blame 解析器。"""

    def __init__(self, repo: Repository):
        self.repo = repo

    def blame(self, filepath: str, rev: str | None = None,
              start_line: int | None = None, end_line: int | None = None,
              ignore_whitespace: bool = False) -> List[BlameLine]:
        args = ["blame", "--porcelain"]
        if ignore_whitespace:
            args.append("-w")
        if rev:
            args.append(rev)
        if start_line is not None and end_line is not None:
            args += ["-L", f"{start_line},{end_line}"]
        args += ["--", filepath]
        out = self.repo.runner.run_checked(*args)
        return self._parse(out)

    @staticmethod
    def _parse(out: str) -> List[BlameLine]:
        """解析 git blame --porcelain 输出。

        结构：一行头部 `<sha> <orig> <final> [count]`，随后可选元数据行，
        再跟一行 `\t<内容>`。若 count>1，后续 count-1 行以"重新头部 + \t内容"
        或紧凑 `\t内容` 形式出现。
        """
        lines = out.split("\n")
        result: List[BlameLine] = []
        i = 0
        n = len(lines)

        def read_meta(start: int):
            meta: Dict[str, str] = {}
            j = start
            while j < n and lines[j] and not lines[j].startswith(_TAB):
                seg = lines[j]
                if seg.startswith("author "):
                    meta["author"] = seg[_len("author "):]
                elif seg.startswith("author-mail "):
                    meta["author_mail"] = seg[_len("author-mail "):].strip("<>")
                elif seg.startswith("author-time "):
                    meta["author_time"] = seg[_len("author-time "):]
                elif seg.startswith("committer-time "):
                    meta["committer_time"] = seg[_len("committer-time "):]
                elif seg.startswith("summary "):
                    meta["summary"] = seg[_len("summary "):]
                j += 1
            return meta, j

        while i < n:
            raw = lines[i]
            if not raw:
                i += 1
                continue
            m = _SHA_RE.match(raw)
            if not m:
                i += 1
                continue
            parts = raw.split()
            sha = parts[0]
            orig = int(parts[1])
            final = int(parts[2])
            count = int(parts[3]) if len(parts) > 3 else 1

            meta, i = read_meta(i + 1)
            # 首个内容行
            content = lines[i][len(_TAB):] if i < n and lines[i].startswith(_TAB) else ""
            i += 1
            result.append(_make_line(sha, orig, final, meta, content))

            for k in range(max(count - 1, 0)):
                if i >= n:
                    break
                nxt = lines[i]
                if nxt.startswith(_TAB):
                    result.append(_make_line(sha, orig + k + 1, final + k + 1, meta, nxt[len(_TAB):]))
                    i += 1
                    continue
                sub = re.match(_SHA_RE, nxt)
                if sub and nxt.split()[0] == sha:
                    sp = nxt.split()
                    seg_orig = int(sp[1])
                    seg_final = int(sp[2])
                    i += 1
                    if i < n and lines[i].startswith(_TAB):
                        result.append(_make_line(sha, seg_orig, seg_final, meta, lines[i][len(_TAB):]))
                        i += 1
                else:
                    break
        return result


def _len(prefix: str) -> int:
    return len(prefix)


def _make_line(sha: str, orig: int, final: int, meta: Dict[str, str],
               content: str) -> BlameLine:
    return BlameLine(
        sha=sha,
        original_line=orig,
        final_line=final,
        content=content,
        author=meta.get("author", ""),
        author_email=meta.get("author_mail", ""),
        author_date=int(meta.get("author_time") or 0),
        summary=meta.get("summary", "")[:120],
    )


# 兼容命名
def blame_file(repo: Repository, filepath: str,
               rev: str | None = None) -> List[BlameLine]:
    return GitBlame(repo).blame(filepath, rev)