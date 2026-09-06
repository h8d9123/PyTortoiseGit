"""GitStash 测试（基于临时仓库）。"""

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository
from pytortoisegit.git.stash import GitStash


@pytest.fixture()
def repo(tmp_path):
    r = Repository.init(str(tmp_path), initial_branch="main")
    gr = GitRunner(cwd=str(tmp_path))
    gr.run("config", "user.email", "a@b", check=True)
    gr.run("config", "user.name", "Alice", check=True)
    (tmp_path / "f.txt").write_text("a\nb\n", encoding="utf-8")
    gr.run("add", ".", check=True)
    gr.run("commit", "-m", "init", check=True)
    return {"repo": r, "gr": gr, "root": str(tmp_path)}


def test_stash_empty_by_default(repo):
    assert GitStash(repo["repo"]).list() == []


def test_create_list_show_drop(repo):
    stash = GitStash(repo["repo"])
    with open(repo["root"] + "/f.txt", "w", encoding="utf-8") as fh:
        fh.write("a\nb\nwip\n")
    assert stash.create(message="wip work")
    entries = stash.list()
    assert len(entries) == 1
    assert entries[0].gd == "stash@{0}"
    assert "wip work" in entries[0].subject   # git 会加上 "On main: " 前缀
    assert entries[0].hash
    assert "+wip" in stash.show(entries[0].gd)
    assert stash.drop(entries[0].gd)
    assert GitStash(repo["repo"]).list() == []


def test_pop_restores_worktree(repo):
    stash = GitStash(repo["repo"])
    with open(repo["root"] + "/f.txt", "w", encoding="utf-8") as fh:
        fh.write("a\nb\npopped\n")
    assert stash.create(message="keep")
    # 清掉工作区修改
    import subprocess
    subprocess.run(["git", "checkout", "--", "f.txt"],
                   cwd=repo["root"], check=True, capture_output=True)
    entries = stash.list()
    assert stash.pop(entries[0].gd)
    content = open(repo["root"] + "/f.txt", encoding="utf-8").read()
    assert "popped" in content
    assert GitStash(repo["repo"]).list() == []


def test_clear(repo):
    stash = GitStash(repo["repo"])
    with open(repo["root"] + "/f.txt", "w", encoding="utf-8") as fh:
        fh.write("zzz\n")
    assert stash.create(message="tmp")
    assert stash.clear()
    assert GitStash(repo["repo"]).list() == []