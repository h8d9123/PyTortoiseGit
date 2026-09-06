"""rev.py —— 镜像 TortoiseGit 的 Git/GitRev、Git/GitRevLoglist、GitRevRefBrowser。

负责把 `git log` / `git rev-list` 输出解析为提交对象，并为画分支图计算 lane 布局。
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
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .repo import Repository

# 记录格式：每组 \x1f 开头；字段用 \x1e 分隔（不能用 \x00 —— Windows 上
# subprocess 会拒绝含 \x00 的参数）
LOG_FORMAT = (
    "\x1f%H\x1e%P\x1e%an\x1e%ae\x1e%ar\x1e%cn\x1e%ce"
    "\x1e%ct\x1e%ad\x1e%B"
)

_IFS = "\x1e"


@dataclass
class GitRev:
    """一个提交对象。"""

    hash: str
    parents: List[str] = field(default_factory=list)
    author_name: str = ""
    author_email: str = ""
    author_date_relative: str = ""
    committer_name: str = ""
    committer_email: str = ""
    committer_timestamp: int = 0
    author_date: str = ""
    message: str = ""
    refs: List[str] = field(default_factory=list)
    actions: str = ""  # 该提交文件变更字母：M/A/D/R/C
    lanes: List = field(default_factory=list)  # List[LaneType]

    # 图布局信息
    lane: int = 0
    row_symbol: str = "o"
    row_text: str = ""

    @property
    def subject(self) -> str:
        if not self.message:
            return self.hash
        first = self.message.splitlines()[0]
        return first.strip() if first else self.hash

    @property
    def body(self) -> str:
        lines = self.message.splitlines()
        return "\n".join(lines[1:]).strip()

    @property
    def short_hash(self) -> str:
        return self.hash[:8]

    @property
    def parents_str(self) -> str:
        return ", ".join(p[:8] for p in self.parents)

    @property
    def refs_str(self) -> str:
        return ", ".join(self.refs)

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def is_root(self) -> bool:
        return not self.parents

    @property
    def author_date_dt(self) -> Optional[datetime]:
        try:
            return datetime.fromtimestamp(self.committer_timestamp)
        except (OSError, ValueError, TypeError):
            return None

    def date_span(self) -> str:
        """返回简短日期文本（星期、月份短名）。"""
        dt = self.author_date_dt
        if dt is None:
            return ""
        return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "parents": list(self.parents),
            "subject": self.subject,
            "author": self.author_name,
            "date": self.date_span(),
            "refs": list(self.refs),
            "is_merge": self.is_merge,
        }


@dataclass
class RefInfo:
    """一个引用（分支/远程分支/标签）的解析结果。"""
    shortname: str      # 去除 refs/heads/ 等前缀的短名
    fullname: str       # refs/heads/main
    target: str         # 指向的提交 hash
    ref_type: str       # 'branch' | 'remote' | 'tag' | 'stash'


_REF_TYPE_PREFIX = (
    ("refs/heads/", "branch"),
    ("refs/remotes/", "remote"),
    ("refs/tags/", "tag"),
    ("refs/stash", "stash"),
)


class GitRevLoglist:
    """git log 结果的集合（维护顺序 + 分支图 lane）。"""

    def __init__(self, repo: Repository):
        self.repo = repo
        self.commits: List[GitRev] = []
        self._by_hash: Dict[str, GitRev] = {}
        self.refs: Dict[str, RefInfo] = {}
        self.refs_loaded = False
        self.limit = 0

    # ---- 加载 ----
    def load(self, limit: int = 500, search: str | None = None,
             pathspec: str | None = None,
             ordering: str = "default",
             all_branches: bool = False) -> None:
        """加载提交。search 非空时按 grep 过滤（作者/信息），pathspec 限定路径。
        ordering: default/topo-order/date-order/author-date-order。
        """
        args: List[str] = []
        if all_branches:
            args.append("--all")
        if limit and limit > 0:
            args += ["-n", str(limit)]
        if search:
            tokens = re.split(r"\s+", search.strip())
            for tok in tokens:
                if tok.startswith("author:"):
                    args += ["--author", tok[7:]]
                elif tok.startswith("grep:"):
                    args += ["--grep", tok[5:]]
                else:
                    args += ["--grep", tok]
        fmt = "--format=" + LOG_FORMAT
        order = ordering if ordering in ("topo-order", "date-order",
                                         "author-date-order") else "topo-order"
        cmd = ["log", fmt, f"--{order}", "--date=iso", "--name-status", *args]
        if pathspec:
            cmd += ["--", pathspec]
        out = self.repo.runner.run_checked(*cmd)
        records = _split_records(out)
        self.commits = []
        self._by_hash = {}
        for rec in records:
            comm = _parse_record(rec)
            refs = [r.shortname for r in self._refs_for(comm.hash)]
            comm.refs = list(refs)
            self.commits.append(comm)
            self._by_hash[comm.hash] = comm
        self._compute_lanes()
        from .lanes import assign_lanes
        assign_lanes(self.commits)

    def load_refs(self) -> None:
        """用 for-each-ref 填充 refs 映射。"""
        sep = _IFS  # for-each-ref 不支持 %xNN，直接嵌入控制字符
        out = self.repo.runner.run_checked(
            "for-each-ref",
            "--format=%(refname)" + sep + "%(objectname)" + sep + "%(subject)",
            "refs/heads", "refs/remotes", "refs/tags")
        self.refs = {}
        self.refs_loaded = True
        # 注意：不能使用 str.splitlines() —— 它会把 \x1e 也当作行边界
        for line in out.split("\n"):
            if not line.strip():
                continue
            fullname, objname, _ = line.split("\x1e", 2)
            shortname = fullname
            rtype = "branch"
            for prefix, t in _REF_TYPE_PREFIX:
                if fullname.startswith(prefix):
                    shortname = fullname[len(prefix):]
                    rtype = t
                    break
            self.refs[fullname] = RefInfo(shortname, fullname, objname, rtype)

    def _refs_for(self, hash: str) -> List[RefInfo]:
        if not self.refs_loaded:
            self.load_refs()
        return [r for r in self.refs.values() if r.target == hash]

    # ---- 图 lane ----
    def _compute_lanes(self) -> None:
        """基于提交顺序与 parents 计算 lane 布局，写入每个提交的 lane。"""
        rows = compute_lanes([(c.hash, c.parents) for c in self.commits])
        width = max((max(r) for r in rows), default=0) + 1
        for commit, row in zip(self.commits, rows):
            commit.lane = _commit_col(row)
            commit.row_symbol = row.get(commit.lane, "o")
            chars = [" "] * width
            for col, sym in row.items():
                if 0 <= col < width:
                    chars[col] = sym
            commit.row_text = "".join(chars).rstrip() or " "

    def row_indent(self) -> int:
        return max((c.lane for c in self.commits), default=0) + 1

    # ---- 查询 ----
    def get(self, hash: str) -> Optional[GitRev]:
        return self._by_hash.get(hash)

    def count(self) -> int:
        return len(self.commits)

    def __iter__(self):
        return iter(self.commits)


def compute_lanes(commits: Sequence[Tuple[str, Sequence[str]]]) -> List[Dict[int, str]]:
    """计算提交序列的分支图 lane 布局（两阶段）。

    - 阶段一：为每个提交分配 lane（先父在某列延续，第二父起新增列）。
    - 阶段二：根据父子 lane 关系画边 —— 父在右侧列画 '\\'，左侧画 '/'
      （方向相对于子树显示顺序），中间列补 '-'。

    返回与 commits 同序的每行 dict：{列号: 符号}，符号 ∈ {'o','-','\\','/'}。
    """
    if not commits:
        return []

    # ---- 阶段一：分配 lane ----
    reserve: List[Optional[str]] = []
    lane_of: Dict[str, int] = {}
    for chash, parents in commits:
        parents = list(parents)
        if chash in reserve:
            target = reserve.index(chash)
        else:
            reserve.append(chash)
            target = len(reserve) - 1
        lane_of[chash] = target

        if parents:
            reserve[target] = parents[0]
        else:
            reserve[target] = None
        existing = {p for p in reserve if p}
        for p in parents[1:]:
            if p not in existing:
                reserve.append(p)
                existing.add(p)
        while reserve and reserve[-1] is None:
            reserve.pop()

    # ---- 阶段二：画边 ----
    rows: List[Dict[int, str]] = []
    for chash, parents in commits:
        lane = lane_of[chash]
        parent_lanes = sorted({lane_of[p] for p in parents if p in lane_of})
        row: Dict[int, str] = {}
        if parent_lanes:
            lo = min(parent_lanes + [lane])
            hi = max(parent_lanes + [lane])
            for c in range(lo + 1, hi):
                row.setdefault(c, "-")
            for pl in parent_lanes:
                if pl > lane:
                    row[pl] = "\\"
                elif pl < lane:
                    row.setdefault(pl, "/")
        row[lane] = "o"
        rows.append(row)
    return rows


def _commit_col(row: Dict[int, str]) -> int:
    """取一行中 'o' 所在的列号。"""
    for col, sym in row.items():
        if sym == "o":
            return col
    return min(row, default=0)


_REF_PATTERN = re.compile(r"^([*+ ]) (\S+)(?:\s+(.*))?$")


def _split_records(out: str) -> List[str]:
    """把 git log 输出按 \x1f 记录头切分（保持多行正文）。

    注意：不能使用 str.splitlines() —— 它会把 \x1e 记录分隔符也当作行边界。
    """
    records: List[str] = []
    cur: Optional[str] = None
    for line in out.split("\n"):
        if line.startswith("\x1f"):
            if cur is not None:
                records.append(cur)
            cur = line[1:]
        elif cur is not None:
            cur += "\n" + line
    if cur is not None:
        records.append(cur)
    return records


def _parse_record(rec: str) -> GitRev:
    """解析 LOG_FORMAT 的一条记录（已按 \x00 切分）。"""
    fields = rec.split(_IFS)
    rev = GitRev(hash=rec[:40])
    if len(fields) < 10:
        # 退化情况：仅 hash
        return rev
    rev.hash = fields[0].strip()
    rev.parents = [p for p in fields[1].split() if p]
    rev.author_name = fields[2].strip()
    rev.author_email = fields[3].strip()
    rev.author_date_relative = fields[4].strip()
    rev.committer_name = fields[5].strip()
    rev.committer_email = fields[6].strip()
    try:
        rev.committer_timestamp = int(fields[7].strip())
    except (ValueError, TypeError):
        rev.committer_timestamp = 0
    rev.author_date = fields[8].strip()
    rev.message, rev.actions = _split_message_and_actions(
        "\x1e".join(fields[9:]).strip())
    return rev


_NAME_STATUS_RE = re.compile(r"^[A-Z]{1,2}\d*\t")


def _split_message_and_actions(text: str) -> Tuple[str, str]:
    """从 --name-status 附加行里抽出动作字母，避免污染提交说明。"""
    lines = text.split("\n")
    cut = len(lines)
    acts: set[str] = set()
    i = len(lines) - 1
    while i >= 0:
        ln = lines[i]
        if not ln.strip():
            i -= 1
            continue
        if _NAME_STATUS_RE.match(ln):
            acts.add(ln[0])
            cut = i
            i -= 1
            continue
        break
    return "\n".join(lines[:cut]).rstrip(), "".join(c for c in "MADRC" if c in acts)


def load_all_refs(repo: Repository) -> Dict[str, RefInfo]:
    log = GitRevLoglist(repo)
    log.load_refs()
    return dict(log.refs)