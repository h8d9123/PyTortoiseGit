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


def test_add_with_branch(repo, subrepo):
    """git submodule add -b <branch> 写入 .gitmodules 的 branch。"""
    GitRunner(cwd=subrepo["root"]).run("branch", "devel", check=True)
    sub = GitSubmodule(repo["repo"])
    assert sub.add("vendor/lib", _url_of(subrepo["root"]), branch="devel")
    modules = open(os.path.join(repo["root"], ".gitmodules"),
                   encoding="utf-8").read()
    assert "branch = devel" in modules


def test_submodule_add_dialog_ok(qapp, repo):
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs.submoduleadddlg import SubmoduleAddDlg

    dlg = SubmoduleAddDlg(repo["repo"])
    dlg.repo_combo.setEditText("/path/to/lib.git")
    dlg.path_combo.setEditText("vendor/lib")
    dlg._on_ok()
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.repository == "/path/to/lib.git"
    assert dlg.path == "vendor/lib"
    assert dlg.branch == "" and dlg.force is False


def test_submodule_add_dialog_requires_fields(qapp, repo, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox
    from pytortoisegit.dialogs.submoduleadddlg import SubmoduleAddDlg

    warned = {}
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.setdefault("shown", True)))
    dlg = SubmoduleAddDlg(repo["repo"])
    dlg._on_ok()                       # 仓库/路径均为空
    assert warned.get("shown")
    assert dlg.result() != QDialog.DialogCode.Accepted


def test_submodule_dlg_add_uses_dialog(qapp, repo, subrepo, monkeypatch):
    """SubmoduleDlg 的“添加子模块”走新对话框并按结果执行 git submodule add。"""
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs import submoduleadddlg
    from pytortoisegit.dialogs.submoduledlg import SubmoduleDlg

    url = _url_of(subrepo["root"])

    class _FakeAdd:
        def __init__(self, repo_, parent=None, initial_path=""):
            self.repository = url
            self.path = "vendor/lib"
            self.branch = ""
            self.force = False
            self.putty_key = ""

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(submoduleadddlg, "SubmoduleAddDlg", _FakeAdd)
    dlg = SubmoduleDlg(repo["repo"])
    dlg._on_add()

    assert (repo["root"] and os.path.isdir(
        os.path.join(repo["root"], "vendor", "lib")))
    modules = open(os.path.join(repo["root"], ".gitmodules"),
                   encoding="utf-8").read()
    assert "vendor/lib" in modules


def test_submodule_update_dialog(qapp, ui, repo, subrepo):
    """Submodule Update 对话框：列出子模块、默认全选，OK 收集选项。"""
    from pytortoisegit.dialogs.submoduleupdatedlg import SubmoduleUpdateDlg

    sub = GitSubmodule(repo["repo"])
    assert sub.add("vendor/lib", _url_of(subrepo["root"]))

    dlg = SubmoduleUpdateDlg(repo["repo"], init=True)
    dlg.show()
    assert ui.wait_until(lambda: dlg.list.count() == 1, timeout_ms=8000)
    assert dlg.list.item(0).text() == "vendor/lib"
    assert dlg.list.item(0).isSelected()
    assert dlg.chk_init.isChecked()
    assert dlg.btn_ok.isEnabled()

    # 取消全选 → OK 置灰
    dlg.chk_selectall.setChecked(False)
    assert not dlg.btn_ok.isEnabled()
    dlg.chk_selectall.setChecked(True)

    dlg._on_ok()
    assert dlg.paths == ["vendor/lib"]
    assert dlg.all_selected is True
    assert dlg.init is True and dlg.recursive is False


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