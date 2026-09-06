# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""inlinediff.py —— 对齐 TortoiseMerge SVNLineDiff（行内按字/按词 diff）。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List, Tuple

# (start, end) 半开区间，标记为本侧相对另一侧的差异片段
InlineSpan = Tuple[int, int]

_WORD_RE = re.compile(r"\s+|\w+|[^\s\w]", re.UNICODE)


def _tokens(text: str, word_wise: bool) -> List[str]:
    if not text:
        return []
    if word_wise:
        return _WORD_RE.findall(text)
    return list(text)


def inline_spans(left: str, right: str, word_wise: bool = True
                 ) -> Tuple[List[InlineSpan], List[InlineSpan]]:
    """返回左右两侧需要高亮的 [start, end) 字符区间。"""
    if left == right:
        return [], []
    lt = _tokens(left, word_wise)
    rt = _tokens(right, word_wise)
    sm = SequenceMatcher(a=lt, b=rt, autojunk=False)
    left_spans: List[InlineSpan] = []
    right_spans: List[InlineSpan] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        lchunk = "".join(lt[i1:i2])
        rchunk = "".join(rt[j1:j2])
        lpos = len("".join(lt[:i1]))
        rpos = len("".join(rt[:j1]))
        if tag == "equal":
            continue
        if tag in ("replace", "delete") and lchunk:
            left_spans.append((lpos, lpos + len(lchunk)))
        if tag in ("replace", "insert") and rchunk:
            right_spans.append((rpos, rpos + len(rchunk)))
    return left_spans, right_spans
