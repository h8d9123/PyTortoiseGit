"""GitSubmodule 测试：解析 + 真实子模块操作（临时仓库）。"""

import os
import subprocess
import sys

import pytest

# git ≥2.38 默认禁止 file 协议抓取子模块；测试里用 env 放行（不污染全局配置）
os.environ["GIT_ALLOW_PROTOCOL"] = "file"

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository
from pytortoisegit.git.submodule import GitSubmodule, _parse_submodule_status


def _git_available():
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _git_available(), reason="git 不可用")
class TestSubmoduleParse:
    def test_parse_status_lines(self):
        sha = "6a5f0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a"
        zero = "0" * 40
        out = (
            f" {sha} src/libfoo (heads/main)\n"
            f"-{zero} src/notinit (untracked)\n"
            f"+{sha} src/moved\n"
            f"U{sha} src/conflict\n"
        )
        entries = _parse_submodule_status(out)
        assert len(entries) == 4
        assert entries[0].status_char == " " and entries[0].status_text == "正常"
        assert entries[1].status_char == "-" and entries[1].status_text == "未初始化"
        assert entries[2].status_char == "+" and entries[2].status_text == "提交不一致"
        assert entries[3].status_char == "U" and entries[3].status_text == "冲突"
        assert entries[0].path == "src/libfoo"
        assert entries[0].description == "heads/main"
        assert entries[1].path == "src/notinit"
        assert entries[0].sha1 == sha

    def test_parse_empty(self):
        assert _parse_submodule_status("") == []

    def test_ignores_short_lines(self):
        assert _parse_submodule_status("x\nshort\n") == []


@pytest.fixture()
def repo(tmp_path):
    r = Repository.init(str(tmp_path), initial_branch="main")
    gr = GitRunner(cwd=str(tmp_path))
    gr.run("config", "user.email", "a@b", check=True)
    gr.run("config", "user.name", "Alice", check=True)
    gr.run("config", "protocol.file.allow", "always", check=True)
    (tmp_path / "f.txt").write_text("base\n", encoding="utf-8")
    gr.run("add", "--", "f.txt", check=True)
    gr.run("commit", "-m", "base", check=True)
    return {"repo": r, "gr": gr, "root": str(tmp_path)}


@pytest.fixture()
def subrepo(tmp_path):
    s = Repository.init(str(tmp_path / "lib"), initial_branch="main",
                        create_dir=True)
    gr = GitRunner(cwd=str(tmp_path / "lib"))
    gr.run("config", "user.email", "a@b", check=True)
    gr.run("config", "user.name", "Alice", check=True)
    (tmp_path / "lib" / "lib.txt").write_text("lib\n", encoding="utf-8")
    gr.run("add", ".", check=True)
    gr.run("commit", "-m", "lib init", check=True)
    return {"repo": s, "root": str(tmp_path / "lib")}


def _url_of(path):
    return path.replace("\\", "/")


def test_add_list_update_sync(repo, subrepo):
    root = repo["root"]
    url = _url_of(subrepo["root"])
    sub = GitSubmodule(repo["repo"])
    assert sub.add("vendor/lib", url)
    repo["gr"].run("commit", "-m", "add submodule", check=True)

    entries = sub.list()
    assert len(entries) == 1
    assert entries[0].path == "vendor/lib"
    assert entries[0].status_char in (" ", "-")
    # url 从 .gitmodules 读出，作为描述
    assert entries[0].description == url

    assert sub.update(init=True)
    assert sub.inited("vendor/lib")
    assert sub.sync()
    assert sub.deinit("vendor/lib")
    assert not sub.inited("vendor/lib")