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