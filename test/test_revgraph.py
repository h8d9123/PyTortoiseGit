"""修订图布局：对齐 C++ RevisionGraph 的 Sugiyama 分层算法。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pytortoisegit.git.rev import RefInfo
from pytortoisegit.git.revgraph import build_layout


def _commit(h, parents=(), refs=()):
    infos = []
    for name, rtype in refs:
        infos.append(RefInfo(name, "refs/x/" + name, h, rtype))

    class _C:
        pass

    c = _C()
    c.hash = h
    c.parents = list(parents)
    c.refs = [n for n, _ in refs]
    c.ref_infos = infos
    c.subject = h
    c.short_hash = h[:8]
    return c


def _measure(text):
    return len(text) * 8.0, 16.0


def test_linear_layers_top_down():
    commits = [
        _commit("a", ["b"], [("main", "branch")]),
        _commit("b", ["c"]),
        _commit("c", [], [("v1", "tag")]),
    ]
    layout = build_layout(commits, _measure)
    assert layout.nodes["a"].layer == 0
    assert layout.nodes["b"].layer == 1
    assert layout.nodes["c"].layer == 2
    # 新提交在上、父提交在下
    assert layout.nodes["a"].y < layout.nodes["b"].y < layout.nodes["c"].y
    assert layout.layers[-1] == ["c"]
    assert layout.edges[0].source == "a"
    assert layout.edges[0].target == "b"


def test_node_lines_and_size():
    commits = [
        _commit("a", [], [("br", "branch"), ("origin/br", "remote")]),
    ]
    layout = build_layout(commits, _measure)
    node = layout.nodes["a"]
    assert len(node.lines) == 2
    assert node.height == (2 * 5 + 16) * 2
    # 宽度 = 2*20 + 最长文本宽
    assert node.width == 2 * 20 + len("origin/br") * 8


def test_same_layer_no_overlap():
    commits = [
        _commit("a", ["m"]),
        _commit("b", ["m"]),
        _commit("m", [], [("main", "branch")]),
    ]
    layout = build_layout(commits, _measure)
    a = layout.nodes["a"]
    b = layout.nodes["b"]
    assert a.layer == b.layer == 0
    gap = abs(a.x - b.x) - (a.width / 2 + b.width / 2)
    assert gap >= 25 - 1e-6
    # 两子都指向同一父，父在下一层
    assert layout.nodes["m"].layer == 1
    targets = {e.source: e.target for e in layout.edges}
    assert targets == {"a": "m", "b": "m"}


def test_long_edge_has_bends():
    commits = [
        _commit("t", ["m"]),
        _commit("s", ["r"]),
        _commit("m", ["r"]),
        _commit("r", [], [("root", "branch")]),
    ]
    layout = build_layout(commits, _measure)
    assert layout.nodes["t"].layer == 0
    assert layout.nodes["s"].layer == 0
    assert layout.nodes["m"].layer == 1
    assert layout.nodes["r"].layer == 2
    edge = next(e for e in layout.edges if e.source == "s")
    # s -> r 跨两层，中间插入一个折点
    assert len(edge.points) == 3


def test_parent_placeholder_added():
    commits = [_commit("a", ["deadbeef" * 5])]
    layout = build_layout(commits, _measure)
    assert len(layout.order) == 2
    placeholder = layout.nodes["deadbeef" * 5]
    assert placeholder.lines[0][1] == "commit"
