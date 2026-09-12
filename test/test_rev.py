"""GitRev / GitRevLoglist / 分支图测试。"""

import os
import subprocess
from pathlib import Path

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository
from pytortoisegit.git.rev import GitRevLoglist, compute_lanes


@pytest.fixture()
def repo(tmp_path):
    """构造一个含分支和合并的仓库：
    main: A - B - C
    feature: A - D
    merge: C 合并 D - E
    """
    r = Repository.init(str(tmp_path), initial_branch="main")
    gr = GitRunner(cwd=str(tmp_path))
    gr.run("config", "user.email", "a@b", check=True)
    gr.run("config", "user.name", "Alice", check=True)

    def commit(msg, fname="f.txt"):
        with open(tmp_path / fname, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
        gr.run("add", ".", check=True)
        gr.run("commit", "-m", msg, check=True)
        return gr.run_checked("rev-parse", "HEAD").strip()

    Ha = commit("A")
    Hb = commit("B")
    gr.run("checkout", "-b", "feature", check=True)
    Hd = commit("D", fname="fd.txt")       # 不同文件，避免与 main 冲突
    gr.run("checkout", "main", check=True)
    Hc = commit("C")
    gr.run("merge", "--no-ff", "feature", "-m", "Merge feature", check=True)
    He = gr.run_checked("rev-parse", "HEAD").strip()
    return {
        "root": str(tmp_path),
        "runner": gr,
        "sha": {"A": Ha, "B": Hb, "C": Hc, "D": Hd, "E": He},
    }


def _log(repo_d):
    r = Repository.open(repo_d["root"])
    log = GitRevLoglist(r)
    log.load(limit=100)
    log.load_refs()
    return log


def test_load_linear_history(repo):
    log = _log(repo)
    hashes = [c.hash for c in log.commits]
    assert hashes[0] == repo["sha"]["E"]      # 最新在前
    assert repo["sha"]["A"] in hashes
    assert len(log.commits) >= 5


def test_merge_and_subject(repo):
    log = _log(repo)
    by_hash = {c.hash: c for c in log.commits}
    e = by_hash[repo["sha"]["E"]]
    assert e.is_merge
    assert set(e.parents) == {repo["sha"]["C"], repo["sha"]["D"]}
    assert e.subject == "Merge feature"


def test_root_commit(repo):
    log = _log(repo)
    by_hash = {c.hash: c for c in log.commits}
    a = by_hash[repo["sha"]["A"]]
    assert a.is_root and a.parents == []


def test_refs_decorated(repo):
    log = _log(repo)
    by_hash = {c.hash: c for c in log.commits}
    assert "main" in by_hash[repo["sha"]["E"]].refs
    assert "feature" in by_hash[repo["sha"]["D"]].refs


def test_author_fields(repo):
    log = _log(repo)
    top = log.commits[0]
    assert top.author_name == "Alice"
    assert top.author_email == "a@b"
    assert len(top.short_hash) == 8
    assert "Merge" in top.message


def test_lanes_non_negative_and_merged_connects(repo):
    log = _log(repo)
    for c in log.commits:
        assert c.lane >= 0
    # 合并提交应有多个连接（它自己 + 右侧父提交列）
    by_hash = {c.hash: c for c in log.commits}
    e = by_hash[repo["sha"]["E"]]
    assert e.lane is not None


def test_compute_lanes_invariants():
    # E 是 C 与 D 的合并；B 是 C 与 D 的共同祖先
    commits = [
        ("E", ["C", "D"]),
        ("C", ["B"]),
        ("D", ["B"]),
        ("B", ["A"]),
        ("A", []),
    ]
    rows = compute_lanes(commits)
    assert len(rows) == len(commits)
    # 每个提交都能找到自己的 'o'
    for (chash, _), row in zip(commits, rows):
        cols = [c for c, s in row.items() if s == "o"]
        assert cols, f"{chash} 没有节点符号"
    # 合并提交行：须有连接到右边父提交列的 '\'（父提交 D 在新列）
    merge_row = rows[0]
    assert merge_row[1] == "\\" and merge_row[0] == "o"
    # 分支提交 D 位于独立列 1，其父 B 在列 0 → 画 '/' 回连
    assert rows[2][1] == "o" and rows[2][0] == "/"


def test_compute_lanes_exact_positions():
    commits = [
        ("E", ["C", "D"]),
        ("C", ["B"]),
        ("D", ["B"]),
        ("B", ["A"]),
        ("A", []),
    ]
    rows = compute_lanes(commits)
    assert rows[0] == {0: "o", 1: "\\"}
    assert rows[1] == {0: "o"}
    assert rows[2] == {0: "/", 1: "o"}
    assert rows[3] == {0: "o"}
    assert rows[4] == {0: "o"}


def test_compute_lanes_simple_linear():
    rows = compute_lanes([("A", []), ("B", []), ("C", [])])
    # 无合并时每行只有自己的 o
    for row in rows:
        assert row == {0: "o"}


def test_search_filter(repo):
    r = Repository.open(repo["root"])
    log = GitRevLoglist(r)
    log.load(limit=100, search="Merge")
    subjects = [c.subject for c in log.commits]
    assert all("Merge" in s for s in subjects)
    assert subjects, "应至少筛到合并提交"


def test_ref_infos_typed(repo):
    log = _log(repo)
    by_hash = {c.hash: c for c in log.commits}
    infos = by_hash[repo["sha"]["E"]].ref_infos
    assert all(ri.ref_type for ri in infos)
    assert ("main", "branch") in {(ri.shortname, ri.ref_type) for ri in infos}


def test_load_simplify_by_decoration(repo):
    full = _log(repo)
    r = Repository.open(repo["root"])
    log = GitRevLoglist(r)
    log.load(limit=100, all_branches=True, simplify=True)
    hashes = {c.hash for c in log.commits}
    assert repo["sha"]["E"] in hashes       # main 指向的提交
    assert repo["sha"]["D"] in hashes       # feature 指向的提交
    assert len(hashes) <= len(full.commits)
