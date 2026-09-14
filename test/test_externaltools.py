"""externaltools.py 测试：占位符填充与命令拆分。"""

import os

from pytortoisegit.git.repo import Repository
from pytortoisegit.utils.externaltools import DiffTool


def test_placeholder_fill(tmp_path):
    repo = Repository.init(str(tmp_path), initial_branch="main")
    tool = DiffTool(diff_cmd="BC.exe {path} {path_b} {repo} {repo_name}")
    cmd = tool.diff_command(repo, "a.txt", "b.txt")
    assert cmd[0] == "BC.exe"
    assert cmd[1] == os.path.join(repo.root, "a.txt")
    assert cmd[2] == os.path.join(repo.root, "b.txt")
    assert cmd[3] == repo.root
    assert cmd[4] == repo.name


def test_quote_split():
    tool = DiffTool(diff_cmd='"C:/Program Files/BCompare.exe" {path} "{path}"')
    cmd = tool.diff_command(_fake_repo(), "a.txt", "a.txt")
    assert cmd[0] == "C:/Program Files/BCompare.exe"
    assert cmd[1] == os.path.join("repo", "a.txt")
    assert cmd[2] == os.path.join("repo", "a.txt")


def _fake_repo():
    class _R:
        root = "repo"
        name = "repo"
    return _R()


def test_diff_command_paths(tmp_path):
    repo = Repository.init(str(tmp_path), initial_branch="main")
    tool = DiffTool(diff_cmd='"C:/Program Files/BCompare.exe" "{path_a}" "{path_b}"')
    cmd = tool.diff_command_paths(repo, r"C:\w\a.txt", r"C:\t\a.txt")
    assert cmd == ["C:/Program Files/BCompare.exe", r"C:\w\a.txt", r"C:\t\a.txt"]


def test_materialize_revision_head(git_repo):
    from pytortoisegit.utils.externaltools import materialize_revision
    p = materialize_revision(git_repo, "HEAD", "a.txt")
    assert p and os.path.isfile(p)
    with open(p, encoding="utf-8") as fh:
        assert "line1" in fh.read()


def test_materialize_revision_working_tree(git_repo):
    from pytortoisegit.utils.externaltools import materialize_revision
    p = materialize_revision(git_repo, "", "a.txt")
    assert p == os.path.join(git_repo.root, "a.txt")


def test_launch_diff_paths_uses_config(git_repo, monkeypatch):
    from pytortoisegit.utils import externaltools
    git_repo.runner.run("config", "tortoisegit.externaldiff",
                        'BC.exe "{path_a}" "{path_b}"')
    captured = {}

    def fake_run(cmd):
        captured["cmd"] = cmd
        return True

    monkeypatch.setattr(externaltools, "_run_blocking", fake_run)
    assert externaltools.launch_diff_paths(git_repo, "A", "B") is True
    assert captured["cmd"][0] == "BC.exe"
    assert captured["cmd"][1:] == ["A", "B"]


def test_launch_diff_paths_without_config(git_repo, monkeypatch):
    from pytortoisegit.utils import externaltools
    # 隔离宿主机全局 git 配置（可能设置了 tortoisegit.externaldiff）
    monkeypatch.setattr(externaltools.DiffTool, "from_repo",
                        staticmethod(lambda repo: externaltools.DiffTool()))
    called = {"n": 0}
    monkeypatch.setattr(externaltools, "_run_blocking",
                        lambda cmd: called.__setitem__("n", called["n"] + 1))
    assert externaltools.launch_diff_paths(git_repo, "A", "B") is False
    assert called["n"] == 0