"""分支图 lane 分配：应对齐 TortoiseGit Lanes。"""

from pytortoisegit.git.lanes import LaneType, assign_lanes, is_active
from pytortoisegit.git.rev import GitRev


def _rev(h, *parents):
    return GitRev(hash=h, parents=list(parents))


def test_linear_history_has_active_node():
    commits = [_rev("c", "b"), _rev("b", "a"), _rev("a")]
    assign_lanes(commits)
    assert all(c.lanes for c in commits)
    assert any(is_active(t) for t in commits[0].lanes)


def test_merge_uses_square_node():
    # E merge C+D, then C, D, A
    e = _rev("E", "C", "D")
    c = _rev("C", "A")
    d = _rev("D", "A")
    a = _rev("A")
    assign_lanes([e, c, d, a])
    merge_types = {LaneType.MERGE_FORK, LaneType.MERGE_FORK_L, LaneType.MERGE_FORK_R}
    assert any(t in merge_types for t in e.lanes)
    assert len(e.lanes) >= 2
