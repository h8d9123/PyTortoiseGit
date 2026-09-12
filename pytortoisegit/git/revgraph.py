"""revgraph.py —— 复刻 TortoiseGit RevisionGraph 的 Sugiyama 分层布局。

对齐 C++ `RevisionGraphWnd` / `RevisionGraphDlgFunc`：

* 建图：每个提交一个节点，边方向为 child -> parent（新 -> 旧）。
* 排名：最长路径分层（对 DAG 等价于 OGDF `OptimalRanking` 的最小总边跨度）。
* 降交叉：`MedianHeuristic`（中位数启发式，上下多轮扫描）。
* 坐标：优先级法思路——逐层对相邻层邻居位置做中位数/均值，并在保持
  左右次序与最小间距的前提下用保序回归（PAVA）求解，参数与
  `FastHierarchyLayout` 一致：nodeDistance=25、layerDistance=30。
* 长边插入虚拟节点（dummy），用于连线折点。

纯 Python，不依赖 Qt；文本量测由调用方通过 ``measure`` 回调提供。
"""

# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# FastHierarchyLayout 参数（C++ RevisionGraphWnd 构造函数）
NODE_DISTANCE = 25.0
LAYER_DISTANCE = 30.0
LEFT_RIGHT_MARGIN = 20.0
TOP_BOTTOM_MARGIN = 5.0


@dataclass
class LayoutNode:
    """布局后的提交节点（x/y 为节点中心，单位与 measure 一致）。"""

    hash: str
    lines: List[Tuple[str, str]] = field(default_factory=list)  # (文本, ref 类型)
    subject: str = ""
    width: float = 0.0
    height: float = 0.0
    layer: int = 0
    x: float = 0.0
    y: float = 0.0
    refs: List[str] = field(default_factory=list)


@dataclass
class LayoutEdge:
    source: str
    target: str
    points: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class GraphLayout:
    nodes: Dict[str, LayoutNode]
    order: List[str]
    edges: List[LayoutEdge]
    width: float = 0.0
    height: float = 0.0
    layers: List[List[str]] = field(default_factory=list)

    def node(self, key: str) -> Optional[LayoutNode]:
        return self.nodes.get(key)


class _V:
    """布局内部顶点：真实节点或虚拟（dummy）节点。"""

    __slots__ = ("key", "real", "width", "height", "layer", "x", "y",
                 "up", "down")

    def __init__(self, key: str, real: Optional[LayoutNode], width: float,
                 height: float):
        self.key = key
        self.real = real
        self.width = width
        self.height = height
        self.layer = 0
        self.x = 0.0
        self.y = 0.0
        self.up: List[_V] = []
        self.down: List[_V] = []


def _isotonic(z: Sequence[float]) -> List[float]:
    """保序回归（PAVA）：求非降序列 y 最小化 sum (y_i - z_i)^2。"""
    blocks: List[List[float]] = []  # [sum, count]
    for zi in z:
        blocks.append([float(zi), 1.0])
        while len(blocks) > 1:
            s1, c1 = blocks[-2]
            s2, c2 = blocks[-1]
            if s1 / c1 <= s2 / c2:
                break
            blocks.pop()
            blocks.pop()
            blocks.append([s1 + s2, c1 + c2])
    out: List[float] = []
    for s, c in blocks:
        out.extend([s / c] * int(c))
    return out


def _pack_layer(layer: List[_V], desired: Dict[int, float],
                gap: float) -> None:
    """在保持次序与最小间距前提下，把每层节点放到接近 desired 的位置。"""
    if not layer:
        return
    prefix: List[float] = []
    acc = 0.0
    for i, v in enumerate(layer):
        if i > 0:
            acc += layer[i - 1].width / 2 + gap + v.width / 2
        prefix.append(acc)
    z = [desired[id(v)] - prefix[i] for i, v in enumerate(layer)]
    y = _isotonic(z)
    for i, v in enumerate(layer):
        v.x = y[i] + prefix[i]


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _reduce_crossings(layers: List[List[_V]], iters: int = 8) -> None:
    """中位数启发式降交叉：上下往复扫描。"""
    if len(layers) < 2:
        return
    for it in range(iters):
        downward = it % 2 == 0
        seq = range(1, len(layers)) if downward else range(len(layers) - 2, -1, -1)
        for li in seq:
            layer = layers[li]
            if not layer:
                continue
            index = {id(v): i for i, v in enumerate(layer)}
            neigh_layer = layers[li - 1] if downward else layers[li + 1]
            nindex = {id(v): i for i, v in enumerate(neigh_layer)}
            keys: Dict[int, float] = {}
            for v in layer:
                neigh = v.up if downward else v.down
                if neigh:
                    keys[id(v)] = _median([nindex[id(n)] for n in neigh])
                else:
                    keys[id(v)] = float(index[id(v)])
            layer.sort(key=lambda v: keys[id(v)])


def _assign_x(layers: List[List[_V]], gap: float, iters: int = 6) -> None:
    """坐标分配：先左对齐打包，再上下往复做保序回归。"""
    for layer in layers:
        x = 0.0
        for v in layer:
            v.x = x + v.width / 2
            x += v.width + gap

    for sweep in range(iters):
        downward = sweep % 2 == 0
        seq = range(1, len(layers)) if downward else range(len(layers) - 2, -1, -1)
        for li in seq:
            layer = layers[li]
            if not layer:
                continue
            desired: Dict[int, float] = {}
            for v in layer:
                neigh = v.up if downward else v.down
                if neigh:
                    desired[id(v)] = sum(n.x for n in neigh) / len(neigh)
                else:
                    desired[id(v)] = v.x
            _pack_layer(layer, desired, gap)


def build_layout(commits: Sequence,
                 measure: Callable[[str], Tuple[float, float]],
                 node_gap: float = NODE_DISTANCE,
                 layer_gap: float = LAYER_DISTANCE,
                 iters: int = 8) -> GraphLayout:
    """按 C++ 修订图的 Sugiyama 分层算法计算节点/连线布局。

    ``commits`` 需按拓扑序（子在前、父在后）给出，每项含 ``hash``、
    ``parents``、``refs``、``ref_infos``、``subject``、``short_hash``。
    ``measure(text)`` 返回文本的 (宽, 高)。
    """
    order: List = []
    by_hash: Dict[str, object] = {}
    for c in commits:
        by_hash[c.hash] = c
        order.append(c)

    # 补全缺失的父提交为占位节点（对齐 C++：图中新增父节点）
    parents_of: Dict[str, List[str]] = {c.hash: list(c.parents) for c in order}
    i = 0
    while i < len(order):
        c = order[i]
        for p in parents_of.get(c.hash, []):
            if p not in by_hash:
                ph = _Placeholder(p)
                by_hash[p] = ph
                parents_of[p] = []
                order.append(ph)
        i += 1

    line_h = measure("Ag")[1] or 15.0

    # 节点尺寸
    nodes: Dict[str, LayoutNode] = {}
    for c in order:
        ref_infos = list(getattr(c, "ref_infos", []) or [])
        if ref_infos:
            lines = [(ri.shortname, ri.ref_type) for ri in ref_infos]
        else:
            lines = [(c.hash[:8], "commit")]
        tw = max(measure(t)[0] for t, _ in lines)
        th = max(measure(t)[1] for t, _ in lines)
        ln = LayoutNode(
            hash=c.hash,
            lines=lines,
            subject=getattr(c, "subject", ""),
            refs=[t for t, _ in lines],
            width=2 * LEFT_RIGHT_MARGIN + tw,
            height=(2 * TOP_BOTTOM_MARGIN + th) * len(lines),
        )
        nodes[c.hash] = ln

    # 排名：最长路径（子 -> 父，rank 递增）
    rank: Dict[str, int] = {c.hash: 0 for c in order}
    for c in order:
        for p in parents_of.get(c.hash, []):
            if rank[p] < rank[c.hash] + 1:
                rank[p] = rank[c.hash] + 1

    max_rank = max(rank.values(), default=0)
    layers: List[List[_V]] = [[] for _ in range(max_rank + 1)]

    verts: Dict[str, _V] = {}
    for c in order:
        ln = nodes[c.hash]
        v = _V(c.hash, ln, ln.width, ln.height)
        v.layer = rank[c.hash]
        verts[c.hash] = v
        layers[v.layer].append(v)

    edges: List[LayoutEdge] = []
    dummy_verts: Dict[str, _V] = {}
    dummy_id = 0
    for c in order:
        for p in parents_of.get(c.hash, []):
            src = verts[c.hash]
            dst = verts[p]
            chain: List[_V] = [src]
            if dst.layer - src.layer > 1:
                for li in range(src.layer + 1, dst.layer):
                    dkey = f"\x00dummy{dummy_id}"
                    dummy_id += 1
                    d = _V(dkey, None, 0.0, 0.0)
                    d.layer = li
                    layers[li].append(d)
                    dummy_verts[dkey] = d
                    chain.append(d)
            chain.append(dst)
            for a, b in zip(chain, chain[1:]):
                a.down.append(b)
                b.up.append(a)
            edges.append(LayoutEdge(c.hash, p, [v.key for v in chain]))

    # 降交叉 + 坐标
    _reduce_crossings(layers, iters=max(1, iters))
    _assign_x(layers, node_gap, iters=max(1, iters // 2))

    # 纵向：按层最大高度排布
    top = 0.0
    for layer in layers:
        h = max((v.height for v in layer), default=0.0)
        h = max(h, line_h)
        for v in layer:
            v.y = top + h / 2
        top += h + layer_gap

    # 回填真实节点坐标
    max_x = 0.0
    max_y = 0.0
    for v in verts.values():
        ln = v.real
        if ln is None:
            continue
        ln.layer = v.layer
        ln.x = v.x
        ln.y = v.y
        max_x = max(max_x, v.x + ln.width / 2)
        max_y = max(max_y, v.y + ln.height / 2)

    # 连线折点坐标（中心点）
    out_edges: List[LayoutEdge] = []
    for e in edges:
        pts: List[Tuple[float, float]] = []
        for k in e.points:
            d = dummy_verts.get(k)
            if d is not None:
                pts.append((d.x, d.y))
            else:
                ln = nodes[k]
                pts.append((ln.x, ln.y))
        out_edges.append(LayoutEdge(e.source, e.target, pts))

    width = max_x + LEFT_RIGHT_MARGIN
    height = max_y + TOP_BOTTOM_MARGIN
    order_keys = [c.hash for c in order]
    return GraphLayout(
        nodes=nodes,
        order=order_keys,
        edges=out_edges,
        width=width,
        height=height,
        layers=[[v.key for v in layer] for layer in layers],
    )


class _Placeholder:
    """缺失父提交的占位对象。"""

    __slots__ = ("hash", "parents", "refs", "ref_infos", "subject")

    def __init__(self, hash_: str):
        self.hash = hash_
        self.parents: List[str] = []
        self.refs: List[str] = []
        self.ref_infos: List = []
        self.subject = hash_[:8]
