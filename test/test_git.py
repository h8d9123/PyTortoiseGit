"""GitRunner / Repository 集成测试（基于临时仓库）。"""

import os
from pathlib import Path

import pytest

from pytortoisegit.git.admin import find_repo_root, is_git_repo
from pytortoisegit.git.git import GitError, GitRunner
from pytortoisegit.git.repo import NotARepositoryError, Repository


@pytest.fixture()
def git_repo(tmp_path):
    """初始化一个临时 git 仓库（含一次提交）。"""
    repo = Repository.init(str(tmp_path), initial_branch="main")
    runner = GitRunner(cwd=str(tmp_path))
    runner.run("config", "user.email", "test@example.com", check=True)
    runner.run("config", "user.name", "tester", check=True)
    (tmp_path / "readme.txt").write_text("hello\n", encoding="utf-8")

    def commit(msg: str):
        r = GitRunner(cwd=str(tmp_path))
        with open(tmp_path / "readme.txt", "a", encoding="utf-8") as fh:
            fh.write(f"\n{msg}\n")
        r.run("add", ".", check=True)
        return r.run("commit", "-m", msg, check=True)

    commit("initial commit")
    return {
        "root": str(tmp_path),
        "runner": GitRunner(cwd=str(tmp_path)),
        "commit": commit,
    }


def test_is_git_repo_and_root(git_repo):
    assert is_git_repo(git_repo["root"])
    assert find_repo_root(git_repo["root"]) == os.path.abspath(git_repo["root"])


def test_repository_open_from_subdir(git_repo):
    sub = os.path.join(git_repo["root"], "subdir")
    os.makedirs(sub, exist_ok=True)
    repo = Repository.open(sub)
    assert repo.root == os.path.abspath(git_repo["root"])
    assert repo.name


def test_repository_open_fails_outside(tmp_path):
    no_repo = tmp_path / "not_a_repo"
    no_repo.mkdir(exist_ok=True)
    with pytest.raises(NotARepositoryError):
        Repository.open(str(no_repo))


def test_git_runner_version():
    runner = GitRunner()
    assert runner.version().startswith("git version")


def test_commit_and_log(git_repo):
    git_repo["commit"]("second commit")
    out = git_repo["runner"].run_checked("log", "--oneline", "-1")
    assert "second commit" in out


def test_core_quotepath_encoding(git_repo):
    fname = "中文文件.txt"
    (Path(git_repo["root"]) / fname).write_text("x\n", encoding="utf-8")
    runner = git_repo["runner"]
    runner.run("add", ".", check=True)
    out = runner.run_checked("status", "--porcelain")
    assert fname in out


def test_git_error_raised():
    runner = GitRunner(cwd="C:/definitely-not-any-repo")
    with pytest.raises(GitError) as excinfo:
        runner.run("status", check=True)
    assert excinfo.value.returncode != 0


def test_repository_config(git_repo):
    repo = Repository.open(git_repo["root"])
    repo.set_config("user.name", "测试者")
    assert repo.config("user.name") == "测试者"


def test_unicode_message_roundtrip(git_repo):
    git_repo["commit"]("提交：修复中文乱码")
    out = git_repo["runner"].run_checked("log", "--oneline", "-2")
    assert "提交：修复中文乱码" in out