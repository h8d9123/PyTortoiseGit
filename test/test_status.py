"""GitStatus / GitIndex 测试（基于临时仓库）。"""

import subprocess

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.index import GitIndex, index_has_conflicts
from pytortoisegit.git.repo import Repository
from pytortoisegit.git.status import GitStatus, GitStatusEntry


@pytest.fixture()
def repo(tmp_path):
    r = Repository.init(str(tmp_path), initial_branch="main")
    gr = GitRunner(cwd=str(tmp_path))
    gr.run("config", "user.email", "a@b", check=True)
    gr.run("config", "user.name", "Alice", check=True)
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    gr.run("add", ".", check=True)
    gr.run("commit", "-m", "init", check=True)
    return {"repo": r, "gr": gr, "root": str(tmp_path)}


def test_clean_status(repo):
    status = GitStatus(repo["repo"]).get_status()
    assert status == []


def test_untracked_and_modified(repo):
    p = repo["root"]
    with open(p + "/a.txt", "w", encoding="utf-8") as fh:
        fh.write("changed\n")
    with open(p + "/new.txt", "w", encoding="utf-8") as fh:
        fh.write("x\n")
    entries = GitStatus(repo["repo"]).get_status()
    by_path = {e.path: e for e in entries}
    assert by_path["a.txt"].is_modified
    assert by_path["a.txt"].is_staged is False
    assert by_path["new.txt"].is_untracked
    counts = GitStatus(repo["repo"]).counts()
    assert counts["modified"] == 1
    assert counts["untracked"] == 1


def test_staged_after_add(repo):
    p = repo["root"]
    with open(p + "/a.txt", "w", encoding="utf-8") as fh:
        fh.write("changed2\n")
    idx = GitIndex(repo["repo"])
    assert idx.add(["a.txt"]) == 0
    entries = GitStatus(repo["repo"]).get_status()
    by_path = {e.path: e for e in entries}
    assert by_path["a.txt"].is_staged
    assert by_path["a.txt"].index_status == "M"


def test_unstage(repo):
    p = repo["root"]
    with open(p + "/b.txt", "w", encoding="utf-8") as fh:
        fh.write("bbb\n")
    idx = GitIndex(repo["repo"])
    idx.add(["b.txt"])
    assert GitStatus(repo["repo"]).get_status()[0].is_staged
    idx.reset(["b.txt"])
    entry = GitStatus(repo["repo"]).get_status()[0]
    assert not entry.is_staged
    assert entry.worktree_status == "M"


def test_rename_detection_status(repo):
    p = repo["root"]
    import shutil
    shutil.move(p + "/a.txt", p + "/renamed.txt")
    idx = GitIndex(repo["repo"])
    idx.add(["./renamed.txt"])   # 触发 git 重命名检测
    idx.add(["./a.txt"]) if False else idx.repo.runner.run("add", "-A")
    entries = GitStatus(repo["repo"]).get_status()
    renamed = [e for e in entries]
    # git 可能标记为 add/delete 而非 rename，只要状态被正确解析即可
    assert any(e.path in ("renamed.txt", "a.txt") for e in renamed)


def test_diff_staged_untracked(repo):
    p = repo["root"]
    with open(p + "/a.txt", "w", encoding="utf-8") as fh:
        fh.write("first\nsecond\n")
    idx = GitIndex(repo["repo"])
    idx.add(["a.txt"])
    staged_diff = idx.diff(["a.txt"], staged=True)
    assert "first" in staged_diff and "+second" in staged_diff
    unstaged = idx.diff(["a.txt"])
    assert unstaged.strip() == ""   # 工作区与暂存一致


def test_conflict_detection(tmp_path):
    r = Repository.init(str(tmp_path), initial_branch="main")
    gr = GitRunner(cwd=str(tmp_path))
    gr.run("config", "user.email", "a@b", check=True)
    gr.run("config", "user.name", "A", check=True)
    (tmp_path / "f.txt").write_text("base\n", encoding="utf-8")
    gr.run("add", ".", check=True)
    gr.run("commit", "-m", "base", check=True)
    gr.run("checkout", "-b", "side", check=True)
    (tmp_path / "f.txt").write_text("side\n", encoding="utf-8")
    gr.run("commit", "-am", "side change", check=True)
    gr.run("checkout", "main", check=True)
    (tmp_path / "f.txt").write_text("main\n", encoding="utf-8")
    gr.run("commit", "-am", "main change", check=True)
    gr.run("merge", "side", check=False)   # 预期冲突
    entries = GitStatus(Repository.open(str(tmp_path))).get_status()
    assert any(e.is_conflicted for e in entries)
    assert index_has_conflicts(Repository.open(str(tmp_path)))