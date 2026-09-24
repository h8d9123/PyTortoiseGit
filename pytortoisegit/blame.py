"""blame.py —— 镜像 TortoiseGit 的 src/TortoiseGitBlame。

解析 `git blame --porcelain` 输出，得到每行对应提交、作者与原始行号。
对齐原版 CTortoiseGitBlameData：

* 同一提交的元数据只输出一次，必须按 sha 缓存，否则复现提交会丢作者；
* 保存 filename / previous，供重命名与“Blame previous”使用；
* 按文件编码探测并解码内容（UTF-8 BOM / UTF-8 / 本地代码页）。
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

import locale
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .git.repo import Repository

_HEADER_RE = re.compile(rb"^([0-9a-f]{40}) (\d+) (\d+)(?: (\d+))?$")
_TAB = "\t"

# 移动/复制行检测档位（对齐 BlameDetectMovedOrCopiedLines.h）
DETECT_MOVED_OR_COPIED_LINES_DISABLED = 0
DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE = 1
DETECT_MOVED_OR_COPIED_LINES_FROM_MODIFIED_FILES = 2
DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES_AT_FILE_CREATION = 3
DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES = 4

DETECT_NUM_CHARACTERS_WITHIN_FILE_DEFAULT = 20
DETECT_NUM_CHARACTERS_FROM_FILES_DEFAULT = 40


def is_limited_to_one_filename(detect: int) -> bool:
    """对齐 BlameIsLimitedToOneFilename（用于 Show complete log / Follow renames）。"""
    return detect in (DETECT_MOVED_OR_COPIED_LINES_DISABLED,
                      DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE)


def detect_moved_arguments(
        detect: int,
        chars_within: int = DETECT_NUM_CHARACTERS_WITHIN_FILE_DEFAULT,
        chars_from: int = DETECT_NUM_CHARACTERS_FROM_FILES_DEFAULT,
) -> List[str]:
    """把检测档位映射为 git blame 的 -M/-C 参数（对齐 TortoiseGitBlameDoc.cpp）。"""
    if detect == DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE:
        return [f"-M{max(1, int(chars_within))}"]
    if detect == DETECT_MOVED_OR_COPIED_LINES_FROM_MODIFIED_FILES:
        return [f"-C{max(1, int(chars_from))}"]
    if detect == DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES_AT_FILE_CREATION:
        return ["-C", f"-C{max(1, int(chars_from))}"]
    if detect == DETECT_MOVED_OR_COPIED_LINES_FROM_EXISTING_FILES:
        return ["-C", "-C", f"-C{max(1, int(chars_from))}"]
    return []


@dataclass
class BlameLine:
    sha: str
    original_line: int          # 在原文件中该行的行号
    final_line: int             # 在当前文件中的行号
    filename: str = ""          # 该行来源文件（重命名/跨文件检测）
    author: str = ""
    author_email: str = ""
    author_date: int = 0
    summary: str = ""
    content: str = ""
    previous_sha: str = ""      # 该行在父提交中的来源提交
    previous_filename: str = ""
    boundary: bool = False

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


@dataclass
class CommitInfo:
    """逐行提交的完整属性（镜像 GitRevLoglist 的可用字段）。"""

    sha: str
    author_name: str = ""
    author_email: str = ""
    author_date: str = ""
    committer_name: str = ""
    committer_email: str = ""
    committer_date: str = ""
    subject: str = ""
    body: str = ""
    parents: List[str] = field(default_factory=list)


_IFS = "\x1f"
_SHOW_FORMAT = _IFS.join([
    "%H", "%P", "%an", "%ae", "%ad", "%cn", "%ce", "%cd", "%s", "%b"])


@dataclass
class BlameData:
    """逐行 blame 数据及查询辅助（镜像 CTortoiseGitBlameData）。"""

    lines: List[BlameLine] = field(default_factory=list)
    encoding: str = "utf-8"
    contains_other_filenames: bool = False
    commits: Dict[str, CommitInfo] = field(default_factory=dict)

    # ---- 基本访问 ----
    def number_of_lines(self) -> int:
        return len(self.lines)

    def is_valid_line(self, line: int) -> bool:
        return 0 <= line < len(self.lines)

    def hash(self, line: int) -> str:
        return self.lines[line].sha

    def hashes(self) -> List[str]:
        return [ln.sha for ln in self.lines]

    def author(self, line: int) -> str:
        return self.lines[line].author

    def date(self, line: int) -> str:
        return self.lines[line].date_span()

    def filename(self, line: int) -> str:
        return self.lines[line].filename

    def original_line_number(self, line: int) -> int:
        return self.lines[line].original_line

    def content(self, line: int) -> str:
        return self.lines[line].content

    # ---- 查询（对齐原版） ----
    def contains_only_filename(self, filename: str) -> bool:
        return all(ln.filename == filename for ln in self.lines)

    def find_first_line(self, sha: str, start: int = 0) -> int:
        for i in range(max(0, start), len(self.lines)):
            if self.lines[i].sha == sha:
                return i
        return -1

    def find_first_line_in_block(self, sha: str, line: int) -> int:
        while line >= 0:
            if self.lines[line].sha != sha:
                return line + 1
            line -= 1
        return line

    def find_next_line(self, hashes: Sequence[str], line: int,
                       up: bool = False) -> int:
        """查找下一段与给定 hash 集合匹配的块（对齐 FindNextLine）。"""
        if not hashes:
            return -1
        wanted = set(hashes)
        start = line
        find_no_match = False
        while 0 <= line < len(self.lines):
            matches = self.lines[line].sha in wanted
            if not matches:
                find_no_match = True
            if matches and find_no_match:
                if line == start + 2:
                    find_no_match = False
                else:
                    if up:
                        line = self.find_first_line_in_block(self.lines[line].sha, line)
                    return line
            line += -1 if up else 1
        return -1

    def find_first_line_wrap_around(self, direction: int, what: str, line: int,
                                    case_sensitive: bool,
                                    default_hashes: bool = False) -> int:
        """在作者名与内容中查找文本，环绕整份文件（对齐 FindFirstLineWrapAround）。

        direction: 0=向下(SearchNext) 1=向上(SearchPrevious)
        """
        if not what:
            return -1
        n = len(self.lines)
        if n == 0:
            return -1
        needle = what if case_sensitive else what.casefold()
        i = line
        if direction == 1:
            i -= 2
            if i < 0:
                i = n - 1
        elif line < 0 or line + 1 >= n:
            i = 0

        for _ in range(n + 1):
            if not self.is_valid_line(i):
                break
            author = self.lines[i].author
            content = self.lines[i].content
            hay_a = author if case_sensitive else author.casefold()
            hay_c = content if case_sensitive else content.casefold()
            if needle in hay_a or needle in hay_c:
                return i
            if direction == 1:
                i -= 1
                if i < 0:
                    i = n - 1
            else:
                i += 1
                if i >= n:
                    i = 0
            if i == line:
                break
        return -1


def _detect_encoding(content_blob: bytes) -> str:
    """探测内容编码（对齐 CTortoiseGitBlameData::GetEncode 的简化版）。"""
    if content_blob.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if content_blob.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        content_blob.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return locale.getpreferredencoding(False) or "cp1252"


def _decode_content(raw: bytes, encoding: str, first: bool) -> str:
    if encoding == "utf-8-sig":
        if first and raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        return raw.decode("utf-8", errors="replace")
    if encoding == "utf-16":
        # 单字节切分后内容可能残留 \x00，尽力还原
        return raw.decode("utf-16-le", errors="replace").rstrip("\x00")
    return raw.decode(encoding, errors="replace")


def _unquote_filename(value: str) -> str:
    """反解 git 的 C 风格引用文件名（含控制字符时仍会加引号）。"""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        body = value[1:-1]
        try:
            return bytes(body, "latin-1").decode("unicode_escape")
        except (UnicodeDecodeError, ValueError):
            return body
    return value


class GitBlame:
    """blame 解析器。"""

    def __init__(self, repo: Repository):
        self.repo = repo

    # ---- 参数组装 ----
    def _relative_path(self, filepath: str) -> str:
        if os.path.isabs(filepath):
            try:
                return os.path.relpath(filepath, self.repo.root)
            except ValueError:  # 不同盘符
                return filepath
        return filepath

    def _build_args(self, filepath: str, rev: str | None,
                    start_line: int | None, end_line: int | None,
                    ignore_whitespace: bool, detect: int,
                    chars_within: int, chars_from: int,
                    first_parent: bool) -> List[str]:
        args = ["blame", "--porcelain"]
        if ignore_whitespace:
            args.append("-w")
        if first_parent:
            args.append("--first-parent")
        args += detect_moved_arguments(detect, chars_within, chars_from)
        if rev:
            args.append(rev)
        if start_line is not None and end_line is not None:
            args += ["-L", f"{int(start_line)},{int(end_line)}"]
        args += ["--", self._relative_path(filepath)]
        return args

    # ---- 公开接口 ----
    def load(self, filepath: str, rev: str | None = None,
             start_line: int | None = None, end_line: int | None = None,
             ignore_whitespace: bool = False, detect: int = 0,
             chars_within: int = DETECT_NUM_CHARACTERS_WITHIN_FILE_DEFAULT,
             chars_from: int = DETECT_NUM_CHARACTERS_FROM_FILES_DEFAULT,
             first_parent: bool = False,
             encoding: str | None = None) -> BlameData:
        """执行 blame 并返回完整 BlameData。"""
        args = self._build_args(filepath, rev, start_line, end_line,
                                ignore_whitespace, detect, chars_within,
                                chars_from, first_parent)
        result = self.repo.runner.run_bytes(*args, check=True)
        data = self._parse_porcelain(result.stdout, encoding=encoding)
        rel = self._relative_path(filepath).replace("\\", "/")
        data.contains_other_filenames = not data.contains_only_filename(rel)
        data.commits = self.load_commit_infos(data.hashes())
        return data

    def load_commit_infos(self, hashes: Sequence[str]) -> Dict[str, CommitInfo]:
        """批量读取提交属性（镜像 CTortoiseGitBlameData 从日志缓存取提交）。"""
        # blame 对 boundary 行可能给出全零 sha（无父提交），必须过滤，
        # 否则 `git show` 会以 "bad object 000...0" 失败。
        zero = "0" * 40
        unique = [h for h in dict.fromkeys(hashes) if h and h != zero]
        if not unique:
            return {}
        infos: Dict[str, CommitInfo] = {}
        # 分批，避免命令行长度超限
        for i in range(0, len(unique), 200):
            chunk = unique[i:i + 200]
            out = self.repo.runner.run_checked(
                "show", "-s", f"--format={_SHOW_FORMAT}", "--date=iso",
                *chunk)
            for record in out.split("\n"):
                if not record:
                    continue
                parts = (record.split(_IFS) + [""] * 10)[:10]
                infos[parts[0]] = CommitInfo(
                    sha=parts[0],
                    author_name=parts[2], author_email=parts[3],
                    author_date=parts[4],
                    committer_name=parts[5], committer_email=parts[6],
                    committer_date=parts[7], subject=parts[8],
                    body=parts[9].strip(),
                    parents=[p for p in parts[1].split() if p])
        return infos

    def blame(self, filepath: str, rev: str | None = None,
              start_line: int | None = None, end_line: int | None = None,
              ignore_whitespace: bool = False, detect: int = 0,
              chars_within: int = DETECT_NUM_CHARACTERS_WITHIN_FILE_DEFAULT,
              chars_from: int = DETECT_NUM_CHARACTERS_FROM_FILES_DEFAULT,
              first_parent: bool = False,
              encoding: str | None = None) -> List[BlameLine]:
        """兼容旧接口：返回逐行列表。"""
        return self.load(
            filepath, rev=rev, start_line=start_line, end_line=end_line,
            ignore_whitespace=ignore_whitespace, detect=detect,
            chars_within=chars_within, chars_from=chars_from,
            first_parent=first_parent, encoding=encoding).lines

    # ---- 解析 ----
    @staticmethod
    def _parse_porcelain(data: bytes,
                         encoding: str | None = None) -> BlameData:
        """解析 `git blame --porcelain` 字节输出。

        每个内容行都有自己的头部行；同一提交的元数据只在首次出现时输出，
        因此按 sha 缓存，复现提交才能拿到 author/summary。
        """
        raw_lines = data.split(b"\n")
        occurrences: List[Tuple[str, int, int, bytes]] = []
        meta_cache: Dict[str, Dict[str, str]] = {}

        last_sha: Optional[str] = None
        last_orig = 0
        last_final = 0
        i = 0
        n = len(raw_lines)

        while i < n:
            raw = raw_lines[i]
            if not raw or raw == b"\x00":
                i += 1
                continue

            m = _HEADER_RE.match(raw)
            if m:
                sha = m.group(1).decode("ascii")
                orig = int(m.group(2))
                final = int(m.group(3))
                last_sha, last_orig, last_final = sha, orig, final
                i += 1
                meta = _read_meta(raw_lines, i)
                i = meta[0]
                cache = meta_cache.setdefault(sha, {})
                if meta[1]:
                    cache.update(meta[1])
                content = b""
                if i < n and raw_lines[i][:1] == b"\t":
                    content = raw_lines[i][1:]
                    i += 1
                occurrences.append((sha, orig, final, content))
                continue

            if raw[:1] == b"\t" and last_sha is not None:
                # 紧凑续行（个别 git 版本对组内后续行省略头部）
                last_orig += 1
                last_final += 1
                occurrences.append((last_sha, last_orig, last_final, raw[1:]))
                i += 1
                continue

            i += 1

        # 探测内容编码
        blob = b"\n".join(o[3] for o in occurrences if o[3])
        used_encoding = encoding or _detect_encoding(blob)

        lines: List[BlameLine] = []
        for idx, (sha, orig, final, content) in enumerate(occurrences):
            meta = meta_cache.get(sha, {})
            prev_sha, prev_name = _split_previous(meta.get("previous", ""))
            lines.append(BlameLine(
                sha=sha,
                original_line=orig,
                final_line=final,
                filename=_unquote_filename(meta.get("filename", "")),
                author=meta.get("author", ""),
                author_email=meta.get("author-mail", "").strip("<>"),
                author_date=_safe_int(meta.get("author-time")),
                summary=meta.get("summary", "")[:120],
                content=_decode_content(content, used_encoding, idx == 0),
                previous_sha=prev_sha,
                previous_filename=_unquote_filename(prev_name),
                boundary="boundary" in meta,
            ))

        return BlameData(lines=lines, encoding=used_encoding)


def _read_meta(raw_lines: List[bytes], i: int) -> Tuple[int, Dict[str, str]]:
    """从第 i 行起读取提交元数据，返回 (新下标, meta)。"""
    meta: Dict[str, str] = {}
    n = len(raw_lines)
    while i < n:
        seg = raw_lines[i]
        if not seg or seg[:1] == b"\t" or _HEADER_RE.match(seg):
            break
        key, _, value = seg.partition(b" ")
        meta[key.decode("ascii", "replace")] = value.decode("utf-8", "replace")
        i += 1
    return i, meta


def _split_previous(value: str) -> Tuple[str, str]:
    if not value:
        return "", ""
    parts = value.split(" ", 1)
    sha = parts[0]
    if sha == "0" * 40:  # boundary：没有真正的父提交
        return "", ""
    return sha, parts[1] if len(parts) > 1 else ""


def _safe_int(value: Optional[str]) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# 兼容命名
def blame_file(repo: Repository, filepath: str,
               rev: str | None = None) -> List[BlameLine]:
    return GitBlame(repo).blame(filepath, rev)
