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


def _spy_subprocess_env(monkeypatch):
    """拦截 subprocess.run，返回捕获到的 env 字典。"""
    import subprocess

    captured = {}
    real = subprocess.run

    def fake(cmd, **kwargs):
        captured["env"] = kwargs.get("env")
        return real(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake)
    return captured


def test_run_env_argument_is_per_call(monkeypatch, git_repo):
    """run(env=...) 只作用于本次调用，不得改写共享实例状态。

    GitRunner 由 Repository 缓存并被多个后台线程共用，改写 self.env 会造成
    线程间互相污染。
    """
    captured = _spy_subprocess_env(monkeypatch)
    runner = git_repo["runner"]
    original = runner.env

    sentinel = dict(original)
    sentinel["PTG_ENV_MARK"] = "1"
    runner.run("--version", env=sentinel)

    assert captured["env"] is sentinel, "传入的 env 应原样交给子进程"
    assert runner.env is original, "实例 env 不应被改写"


def test_run_interactive_does_not_mutate_shared_env(monkeypatch, git_repo):
    """run_interactive 曾临时改写 self.env（数据竞态），现在必须只走参数。"""
    from pytortoisegit import askpass

    captured = _spy_subprocess_env(monkeypatch)
    monkeypatch.setattr(
        askpass, "setup_askpass",
        lambda env, root=None: {**env, "PTG_ASKPASS": "1"})

    runner = git_repo["runner"]
    original = runner.env

    runner.run_interactive("--version")

    assert captured["env"].get("PTG_ASKPASS") == "1", "askpass 环境应生效"
    assert runner.env is original, "运行期间不应改写实例 env"


def test_run_interactive_keeps_working(git_repo):
    """走真实 askpass 桥接时命令仍能正常执行。"""
    runner = git_repo["runner"]
    before = len(runner.env)
    result = runner.run_interactive("--version")
    assert result.returncode == 0
    assert "git version" in result.stdout
    assert len(runner.env) == before, "调用后实例 env 应保持原样"