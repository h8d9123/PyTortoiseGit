"""udiff.py —— 镜像 TortoiseGit 的 src/TortoiseUDiff。

解析统一 diff（unified diff）文本：文件块、hunks、行数据。
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
from typing import List, Optional

_METADATA_RE = re.compile(
    r"^diff --git a/(.*) b/(.*)$"
)
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$"
)

_BINARY_PATTERNS = (
    "Binary files ", "GIT binary patch", "index ",
)


@dataclass
class DiffLine:
    """diff 中的一行。kind: '  '(上下文)/'+'/'-'/'\\'(警告行)。"""
    kind: str          # '+', '-', ' ', '\\'
    text: str          # 去掉一个 kind 前缀后的内容
    old_lineno: int = 0
    new_lineno: int = 0

    @property
    def is_addition(self) -> bool:
        return self.kind == "+"

    @property
    def is_deletion(self) -> bool:
        return self.kind == "-"

    @property
    def is_context(self) -> bool:
        return self.kind == " "

    @property
    def content(self) -> str:
        return self.text


@dataclass
class Hunk:
    old_start: int
    new_start: int
    old_count: int = 0
    new_count: int = 0
    lines: List[DiffLine] = field(default_factory=list)
    header: str = ""

    @property
    def added(self) -> int:
        return sum(1 for ln in self.lines if ln.is_addition)

    @property
    def removed(self) -> int:
        return sum(1 for ln in self.lines if ln.is_deletion)


@dataclass
class FilePatch:
    """一个文件的完整 diff。"""

    old_path: str = ""
    new_path: str = ""
    old_mode: str = ""
    new_mode: str = ""
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    is_rename: bool = False
    old_sha: str = ""
    new_sha: str = ""
    hunks: List[Hunk] = field(default_factory=list)
    raw: str = ""

    @property
    def filename_display(self) -> str:
        if self.is_rename and self.old_path != self.new_path:
            return f"{self.old_path} → {self.new_path}"
        return self.new_path or self.old_path

    @property
    def added(self) -> int:
        return sum(h.added for h in self.hunks)

    @property
    def removed(self) -> int:
        return sum(h.removed for h in self.hunks)

    def line_for(self, new_lineno: int) -> Optional[DiffLine]:
        """按新文件行号查对应 diff 行。"""
        for h in self.hunks:
            for ln in h.lines:
                if ln.new_lineno == new_lineno and ln.kind in ("+", " "):
                    return ln
        return None


def split_diff(data: str) -> List[str]:
    """把完整 diff 输出切成每个文件的块。"""
    blocks: List[str] = []
    current: List[str] = []
    for line in data.splitlines(keepends=True):
        if line.startswith("diff --git ") and current:
            blocks.append("".join(current))
            current = []
        current.append(line)
    if current:
        blocks.append("".join(current))
    return blocks


def parse_file_patch(data: str) -> Optional[FilePatch]:
    if not data.strip():
        return None

    patch = FilePatch(raw=data)
    lines = data.splitlines()
    in_hunk = False
    hunk: Optional[Hunk] = None
    old_lineno = 0
    new_lineno = 0

    # 文件名可能带 a/ b/ 前缀别名；用 re 匹配带引号的奇怪路径时不靠谱，取每行剩余部分
    for raw_line in lines:
        if raw_line.startswith("diff --git "):
            rest = raw_line[len("diff --git "):]
            # 拆分成两段：a/... b/...
            m = re.match(r"a/(.*) b/(.*)$", rest)
            if m:
                patch.old_path = _unquote_path(m.group(1))
                patch.new_path = _unquote_path(m.group(2))
            continue

        if raw_line.startswith(("old mode ", "new mode ", "deleted file mode ", "new file mode ")):
            _handle_metadata(patch, raw_line)
            continue
        if raw_line.startswith("index "):
            _handle_index(patch, raw_line)
            continue
        if raw_line.startswith("similarity index "):
            patch.is_rename = True
            continue
        if raw_line.startswith("rename from "):
            patch.old_path = raw_line[len("rename from "):].strip()
            patch.is_rename = True
            continue
        if raw_line.startswith("rename to "):
            patch.new_path = raw_line[len("rename to "):].strip()
            patch.is_rename = True
            continue

        if raw_line.startswith("Binary files ") or raw_line == "Binary file":
            patch.is_binary = True
            continue
        if raw_line.startswith("GIT binary patch"):
            patch.is_binary = True
            continue

        m = _HUNK_HEADER_RE.match(raw_line)
        if m:
            old_start, old_cnt_raw, new_start, new_cnt_raw, header = m.groups()
            hunk = Hunk(
                old_start=int(old_start),
                new_start=int(new_start),
                old_count=int(old_cnt_raw or 1),
                new_count=int(new_cnt_raw or 1),
                header=header.strip(),
            )
            patch.hunks.append(hunk)
            old_lineno = hunk.old_start - 1
            new_lineno = hunk.new_start - 1
            in_hunk = True
            continue

        if in_hunk and hunk is not None and raw_line:
            if raw_line[0] == "\\":
                hunk.lines.append(DiffLine("\\", raw_line[1:]))
                continue
            kind = raw_line[0]
            if kind in "+- ":
                if kind == "+":
                    new_lineno += 1
                elif kind == "-":
                    old_lineno += 1
                else:
                    old_lineno += 1
                    new_lineno += 1
                hunk.lines.append(DiffLine(
                    kind, raw_line[1:], old_lineno, new_lineno))
                continue

        if in_hunk:
            in_hunk = False

    patch.is_rename = patch.is_rename and (patch.raw.find("rename ") >= 0 or patch.old_path != patch.new_path)
    return patch


def _handle_metadata(patch: FilePatch, line: str) -> None:
    if line.startswith("old mode "):
        patch.old_mode = line[len("old mode "):].strip()
    elif line.startswith("new mode "):
        patch.new_mode = line[len("new mode "):].strip()
    elif line.startswith("new file mode"):
        patch.is_new = True
    elif line.startswith("deleted file mode"):
        patch.is_deleted = True


def _handle_index(patch: FilePatch, line: str) -> None:
    # line: index <oldsha>..<newsha> <mode?>
    parts = line[len("index "):].strip().split()
    if not parts:
        return
    shas = parts[0]
    if ".." in shas:
        old, _, new = shas.partition("..")
        if old and old != "0000000000000000000000000000000000000000":
            patch.old_sha = old
        if new:
            patch.new_sha = new
    else:
        patch.new_sha = shas
    if len(parts) > 1:
        patch.new_mode = parts[1]


def _unquote_path(name: str) -> str:
    """去掉 git 可能添加的引号转义（如 a/"foo bar"）。"""
    if name.startswith('"') and name.endswith('"'):
        try:
            return name[1:-1].encode().decode("unicode_escape")
        except Exception:
            return name[1:-1]
    return name


def parse_diff(data: str) -> List[FilePatch]:
    """解析 git diff 输出全文，返回文件补丁列表。"""
    patches: List[FilePatch] = []
    for block in split_diff(data):
        patch = parse_file_patch(block)
        if patch is not None:
            patches.append(patch)
    return patches


def diff_stat(patches: List[FilePatch]) -> int:
    return sum(p.added + p.removed for p in patches)


def split_patch_hunks(data: str) -> List[str]:
    """把一份 diff 拆成「逐 hunk 可应用补丁」的列表。

    每项保留文件头（diff --git / --- / +++）且只含一个 @@ hunk，
    可直接交给 `git apply`（临时索引操作场景）。
    没有 @@ 的块（纯元数据，如 mode 变更）整体返回。
    """
    result: List[str] = []
    for block in split_diff(data):
        lines = block.splitlines(keepends=True)
        head: List[str] = []
        hunks: List[List[str]] = []
        current: List[str] | None = None
        for line in lines:
            if line.startswith("@@"):
                if current is not None:
                    hunks.append(current)
                current = []
            if current is not None:
                current.append(line)
            else:
                head.append(line)
        if current is not None:
            hunks.append(current)
        if hunks:
            for h in hunks:
                result.append("".join(head + h))
        elif head:
            result.append("".join(head))
    return result


def visible_hunk_ranges(diff_text: str) -> List[tuple]:
    """返回每个 @@ hunk 在 diff 文本中的行号区间（用于定位光标所在 hunk）。

    返回 [(start, end), ...]，0 基（不含行尾的排除逻辑）。
    """
    ranges: List[tuple] = []
    start: int | None = None
    for idx, line in enumerate(diff_text.splitlines()):
        if line.startswith("@@"):
            if start is not None:
                ranges.append((start, idx - 1))
            start = idx
    if start is not None:
        ranges.append((start, len(diff_text.splitlines()) - 1))
    return ranges


def apply_hunk_text(base_text: str, hunk_patch: str,
                    reverse: bool = False) -> str:
    """在 Python 里手工应用一个 -U0 单 hunk，返回结果文本。

    依赖 hunk 的精确行号（零上下文）直接对 base 做增删替换；
    reverse=True 时反向应用（用于取消暂存）。忽略 '\\ No newline' 标记。
    """
    lines = hunk_patch.split("\n")
    header_idx: int | None = None
    for idx, ln in enumerate(lines):
        if ln.startswith("@@"):
            header_idx = idx
            break
    if header_idx is None:
        return base_text
    m = _HUNK_HEADER_RE.match(lines[header_idx])
    if not m:
        return base_text
    new_start = int(m.group(3))
    old_start = int(m.group(1))
    old_count = int(m.group(2) or 1)
    new_count = int(m.group(4) or 1)

    body = []
    for ln in lines[header_idx + 1:]:
        if ln == "" or ln.startswith("\\ No newline"):
            continue
        body.append(ln)

    if reverse:
        anchor = new_start
        remove = [b[1:] for b in body if b.startswith("+")]
        insert = [b[1:] for b in body if b.startswith("-")]
    else:
        anchor = old_start
        remove = [b[1:] for b in body if b.startswith("-")]
        insert = [b[1:] for b in body if b.startswith("+")]
    if reverse and len(remove) == 0:
        remove = [] if new_count == 0 else remove
    remove_count = new_count if reverse else old_count

    base_lines = base_text.split("\n")
    ends_newline = base_text.endswith("\n")
    if ends_newline:
        base_lines.pop()

    before = base_lines[:anchor - 1]
    rest = base_lines[anchor - 1:]
    remove_count = new_count if reverse else old_count
    if len(rest) < remove_count or rest[:remove_count] != remove:
        # 基址与 hunk 预期不符，回退（保持原样）
        return base_text
    new_lines = before + insert + rest[remove_count:]
    result = "\n".join(new_lines)
    if ends_newline or (insert and insert[-1] != ""):
        result += "\n"
    return result