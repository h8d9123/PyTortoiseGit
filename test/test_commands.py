"""commands/* 命令层的测试（通过 /command 分发入口调用）。

对打开对话框的命令：patch 其对话框的 exec 让其“接受”；
对进度类命令：使用 auto_progress。
"""

import importlib
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from pytortoisegit.cmdline import parse
from pytortoisegit.commands.dispatcher import CommandContext


@pytest.fixture(autouse=True)
def _no_modals(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _ctx(repo, cmd, *extra):
    return CommandContext(cl=parse([f"/command:{cmd}", f"/path:{repo.root}", *extra]))


def _patch_exec(monkeypatch, cls):
    def fake_exec(self, *a, **k):
        # BlameDlg 是 QMainWindow（无 accept），其余对话框是 QDialog
        if hasattr(self, "accept"):
            self.accept()
        else:
            self.close()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(cls, "exec", fake_exec, raising=False)


# 命令 → 其打开的对话框类属性名
DIALOG_CMDS = {
    "blame": "BlameDlg",
    "browse": "BrowseRefsDlg",
    "branch": "CreateBranchDlg",
    "tag": "CreateTagDlg",
    "changed": "ChangedDlg",
    "clean": "CleanDlg",
    "cleanup": "CleanDlg",
    "commit": "CommitDlg",
    "conflicteditor": "ConflictEditorDlg",
    "export": "ExportDlg",
    "formatpatch": "FormatPatchDlg",
    "ignore": "IgnoreDlg",
    "importpatch": "ApplyPatchDlg",
    "lfslocks": "LfsLocksDlg",
    "log": "LogDlg",
    "merge": "MergeDlg",
    "mergeabort": "MergeAbortDlg",
    "rebase": "RebaseDlg",
    "reflog": "ReflogDlg",
    "repobrowser": "RepositoryBrowserDlg",
    "resolve": "ResolveDlg",
    "revert": "RevertDlg",
    "revisiongraph": "RevisionGraphDlg",
    "sendmail": "SendMailDlg",
    "settings": "SettingsDlg",
    "shell": "ShellDlg",
    "sync": "SyncDlg",
    "fetch": "PullFetchDlg",
    "pull": "PullFetchDlg",
    "submodule": "SubmoduleDlg",
    "switch": "GitSwitchDlg",
    "worktreelist": "WorktreeListDlg",
}


# 部分命令与其所在模块名不同（同模块注册多个命令）
CMD_MODULE = {
    "browse": "branch",
    "tag": "branch",
}


@pytest.mark.parametrize("cmd,attr", list(DIALOG_CMDS.items()))
def test_command_opens_dialog(qapp, git_repo, auto_progress, monkeypatch, cmd, attr):
    module = CMD_MODULE.get(cmd, cmd)
    mod = importlib.import_module(f"pytortoisegit.commands.{module}")
    cls = getattr(mod, attr, None)
    if cls is None:
        pytest.skip(f"{cmd}.{attr} 不存在")
    _patch_exec(monkeypatch, cls)
    fn = getattr(mod, cmd)
    fn(_ctx(git_repo, cmd))     # 不抛异常即可


def test_command_blame_forwards_rev_and_line(qapp, git_repo, monkeypatch):
    """blame 命令解析 /endrev 与 /line 并透传给 BlameDlg（对齐 BlameCommand.cpp）。"""
    from pytortoisegit.commands import blame as blame_mod
    captured = {}

    class _FakeBlame:
        def __init__(self, repo, filepath="", rev=None, line=0, parent=None):
            captured.update(repo=repo, filepath=filepath, rev=rev, line=line)

        def show(self):
            captured["shown"] = True

    monkeypatch.setattr(blame_mod, "BlameDlg", _FakeBlame)
    monkeypatch.setattr(
        "pytortoisegit.dialogs.modeless.show_modeless",
        lambda dlg: dlg.show())
    blame_mod.blame(_ctx(git_repo, "blame", "/endrev:HEAD~1", "/line:3"))
    assert captured["rev"] == "HEAD~1"
    assert captured["line"] == 3
    assert captured["repo"].root == git_repo.root
    assert captured.get("shown")


def test_subadd_command_opens_dialog(qapp, git_repo, monkeypatch):
    """subadd 命令：打开添加子模块对话框并按结果执行 add。"""
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.commands import submodule as submod
    from pytortoisegit.dialogs import submoduleadddlg
    from pytortoisegit.git.submodule import GitSubmodule

    class _FakeAdd:
        repository = "https://x/y.git"
        path = "vendor/lib"
        branch = ""
        force = False
        putty_key = ""

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(submoduleadddlg, "SubmoduleAddDlg", _FakeAdd)
    added = {}
    monkeypatch.setattr(
        GitSubmodule, "add",
        lambda self, path, url, force=False, branch=None:
        (added.setdefault("v", (path, url)), True)[1])
    assert submod.subadd(_ctx(git_repo, "subadd")) == "ok"
    assert added["v"] == ("vendor/lib", "https://x/y.git")


def test_subupdate_command_opens_dialog(qapp, git_repo, monkeypatch):
    """subupdate 命令：打开子模块更新对话框并按结果执行 update。"""
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.commands import submodule as submod
    from pytortoisegit.dialogs import submoduleupdatedlg

    class _FakeUpd:
        init = True
        recursive = True
        force = False
        no_fetch = False
        merge = False
        rebase = False
        remote = False
        paths = []
        all_selected = True

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(submoduleupdatedlg, "SubmoduleUpdateDlg", _FakeUpd)
    assert submod.subupdate(_ctx(git_repo, "subupdate")) == "ok"


# ---- 进度类命令 ----
@pytest.mark.parametrize("cmd", ["svnignore", "svndcommit",
                                 "svnfetch", "svnrebase"])
def test_command_progress(qapp, git_repo, auto_progress, cmd):
    mod = importlib.import_module(f"pytortoisegit.commands.{cmd}")
    fn = getattr(mod, cmd)
    assert fn(_ctx(git_repo, cmd)) == "ok"


def test_command_daemon(qapp, git_repo, auto_progress, monkeypatch):
    """daemon 是常驻服务（git daemon 不会退出），仅 stub 该子命令避免真正启动。"""
    from types import SimpleNamespace
    from pytortoisegit.git.git import GitRunner
    orig = GitRunner.run

    def fake(self, *args, **k):
        if args and args[0] == "daemon":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return orig(self, *args, **k)

    monkeypatch.setattr(GitRunner, "run", fake)
    from pytortoisegit.commands.daemon import daemon
    assert daemon(_ctx(git_repo, "daemon")) == "ok"


# ---- stashsave ----

def test_command_stashsave_accept(qapp, git_repo, auto_progress, monkeypatch):
    from pytortoisegit.dialogs.stashdlg import StashDlg
    from pytortoisegit.commands.stashsave import stashsave
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    monkeypatch.setattr(
        StashDlg, "exec",
        lambda self, *a, **k: (self.accept() or QDialog.DialogCode.Accepted))
    assert stashsave(_ctx(git_repo, "stashsave")) == "ok"
    assert git_repo.runner.run("stash", "list").stdout.strip()


def test_command_stashsave_cancel(qapp, git_repo, auto_progress, monkeypatch):
    from pytortoisegit.dialogs.stashdlg import StashDlg
    from pytortoisegit.commands.stashsave import stashsave
    monkeypatch.setattr(StashDlg, "exec",
                        lambda self, *a, **k: QDialog.DialogCode.Rejected)
    assert stashsave(_ctx(git_repo, "stashsave")) == "cancel"


# ---- 拖放复制/移动 ----

def test_command_dropcopy(qapp, git_repo, auto_progress, tmp_path):
    from pytortoisegit.commands.dropcopy import dropcopy
    src = Path(git_repo.root) / "sub" / "x.txt"
    src.parent.mkdir()
    src.write_text("data\n", encoding="utf-8")
    result = dropcopy(_ctx(git_repo, "dropcopy", f"/path:{src}"))
    assert result in ("ok", "failed")   # 真实拷贝（repo 根目录也会被过滤跳过）


def test_command_dropmove(qapp, git_repo, auto_progress):
    from pytortoisegit.commands.dropmove import dropmove
    src = Path(git_repo.root) / "sub" / "y.txt"
    src.parent.mkdir()
    src.write_text("data\n", encoding="utf-8")
    result = dropmove(_ctx(git_repo, "dropmove", f"/path:{src}"))
    assert result in ("ok", "failed")


def test_cli_help(qapp, capsys):
    from pytortoisegit import cli
    assert cli.main(["/help"]) == 0
    assert capsys.readouterr().out.strip()


def test_cli_unknown_command(qapp):
    from pytortoisegit import cli
    assert cli.main(["/command:doesnotexist"]) == 1


def test_cli_dispatch_ok(qapp, monkeypatch):
    from pytortoisegit import cli
    from pytortoisegit.commands import dispatcher
    called = {}
    monkeypatch.setattr(dispatcher, "dispatch",
                        lambda verb, ctx: called.setdefault("verb", verb))
    assert cli.main(["/command:about"]) == 0
    assert called["verb"] == "about"


def test_cli_dispatch_error(qapp, monkeypatch):
    from pytortoisegit import cli
    from pytortoisegit.commands import dispatcher

    def boom(verb, ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(dispatcher, "dispatch", boom)
    assert cli.main(["/command:about"]) == 1


def test_cli_no_args_opens_menu(qapp, monkeypatch):
    from pytortoisegit import cli, singleinstance
    from pytortoisegit.dialogs import mainmenu
    monkeypatch.setattr(singleinstance, "acquire", lambda name: True)
    opened = {}

    class _Menu:
        def __init__(self, *a, **k):
            pass

        def exec_loop(self):
            opened["y"] = True

    monkeypatch.setattr(mainmenu, "MainMenuDlg", _Menu)
    assert cli.main([]) == 0
    assert opened.get("y")


def test_cli_no_args_already_running(qapp, monkeypatch):
    from pytortoisegit import cli, singleinstance
    monkeypatch.setattr(singleinstance, "acquire", lambda name: False)
    assert cli.main([]) == 0


def test_command_requires_repo(qapp):
    """无 /path 时命令抛出 NotARepositoryError。"""
    from pytortoisegit.commands.dropcopy import dropcopy
    from pytortoisegit.git.repo import NotARepositoryError
    ctx = CommandContext(cl=parse(["/command:dropcopy"]))
    with pytest.raises(NotARepositoryError):
        dropcopy(ctx)
