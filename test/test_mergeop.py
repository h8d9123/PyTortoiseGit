"""GitMergeOp / GitRebaseOp 测试（临时仓库）。"""

import os
from pathlib import Path

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.mergeop import (
    build_merge_args,
    build_rebase_args,
    conflicted_entries,
    do_merge,
    local_branches,
    mark_resolved,
    resolve_as,
)
from pytortoisegit.git.repo import Repository


@pytest.fixture()
def repo(tmp_path):
    r = Repository.init(str(tmp_path), initial_branch="main")
    gr = GitRunner(cwd=str(tmp_path))
    gr.run("config", "user.email", "a@b", check=True)
    gr.run("config", "user.name", "Alice", check=True)
    (tmp_path / "f.txt").write_text("base\n", encoding="utf-8")
    gr.run("add", ".", check=True)
    gr.run("commit", "-m", "base", check=True)
    return {"repo": r, "gr": gr, "root": str(tmp_path)}


def test_build_merge_args_plain():
    assert build_merge_args("feature") == ["merge", "feature"]


def test_build_merge_args_opts():
    assert build_merge_args("feature", no_ff=True, squash=True,
                            no_commit=True, message="m") == [
        "merge", "--no-ff", "--squash", "--no-commit", "-m", "m", "feature"]


def test_build_rebase_args_plain():
    assert build_rebase_args("main") == ["rebase", "main"]


def test_build_rebase_args_opts():
    assert build_rebase_args("main", interactive=True, autostash=True) == [
        "rebase", "-i", "--autostash", "main"]


def test_local_branches_excludes_current(repo):
    repo["gr"].run("checkout", "-b", "feature", check=True)
    repo["gr"].run("checkout", "main", check=True)
    branches = local_branches(repo["repo"])
    assert "feature" in branches
    assert "main" not in branches


def test_merge_clean(repo):
    repo["gr"].run("checkout", "-b", "feature", check=True)
    Path(repo["root"], "new.txt").write_text("x\n", encoding="utf-8")
    repo["gr"].run("add", ".", check=True)
    repo["gr"].run("commit", "-m", "feature commit", check=True)
    repo["gr"].run("checkout", "main", check=True)
    result = do_merge(repo["repo"], "feature")
    assert result.ok
    assert result.conflicts == []
    assert "feature" in local_branches(repo["repo"])


def test_merge_clean_fast_forward_disabled(repo):
    repo["gr"].run("checkout", "-b", "feature", check=True)
    Path(repo["root"], "new2.txt").write_text("y\n", encoding="utf-8")
    repo["gr"].run("add", ".", check=True)
    repo["gr"].run("commit", "-m", "ff commit", check=True)
    repo["gr"].run("checkout", "main", check=True)
    result = do_merge(repo["repo"], "feature", no_ff=True)
    assert result.ok


def test_conflict_flow(repo):
    repo["gr"].run("checkout", "-b", "side", check=True)
    Path(repo["root"], "f.txt").write_text("side\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "side", check=True)
    repo["gr"].run("checkout", "main", check=True)
    Path(repo["root"], "f.txt").write_text("main\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "main", check=True)
    result = do_merge(repo["repo"], "side")
    assert not result.ok
    assert result.in_progress
    assert len(result.conflicts) == 1
    # 采用 ours 解决
    assert mark_resolved(repo["repo"], "f.txt")
    from pytortoisegit.git.index import index_has_conflicts
    assert not index_has_conflicts(repo["repo"])


def test_resolve_as_theirs(repo):
    repo["gr"].run("checkout", "-b", "side", check=True)
    Path(repo["root"], "f.txt").write_text("side\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "side", check=True)
    repo["gr"].run("checkout", "main", check=True)
    Path(repo["root"], "f.txt").write_text("main\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "main", check=True)
    do_merge(repo["repo"], "side")
    assert resolve_as(repo["repo"], "f.txt", "theirs")
    content = open(os.path.join(repo["root"], "f.txt"), encoding="utf-8").read()
    assert content == "side\n"
    assert conflicted_entries(repo["repo"]) == []


def test_merge_in_progress_guard(repo):
    repo["gr"].run("checkout", "-b", "side", check=True)
    Path(repo["root"], "f.txt").write_text("side\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "side", check=True)
    repo["gr"].run("checkout", "main", check=True)
    Path(repo["root"], "f.txt").write_text("main\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "main", check=True)
    repo["gr"].run("merge", "side", check=False)
    from pytortoisegit.git.mergeop import MergeInProgressError, abort_merge, do_merge
    with pytest.raises(MergeInProgressError):
        do_merge(repo["repo"], "side")
    assert abort_merge(repo["repo"])
    assert conflicted_entries(repo["repo"]) == []


def test_extract_stage(repo):
    from pytortoisegit.git.mergeop import _extract_stage
    repo["gr"].run("checkout", "-b", "side", check=True)
    Path(repo["root"], "f.txt").write_text("side\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "side", check=True)
    repo["gr"].run("checkout", "main", check=True)
    Path(repo["root"], "f.txt").write_text("main\n", encoding="utf-8")
    repo["gr"].run("commit", "-am", "main", check=True)
    do_merge(repo["repo"], "side")
    base, local, remote = _extract_stage(repo["repo"], "f.txt")
    try:
        assert open(base, encoding="utf-8").read() == "base\n"
        assert open(local, encoding="utf-8").read() == "main\n"
        assert open(remote, encoding="utf-8").read() == "side\n"
    finally:
        for p in (base, local, remote):
            os.path.exists(p) and os.remove(p)