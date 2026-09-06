"""Push 参数构造与 upstream 解析（对齐 CAppUtils::DoPush / CGit::GetRemotePushBranch）。"""

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.push import (
    PushOpts,
    build_push_args,
    get_remote_push_branch,
    should_open_push_dialog,
    strip_ref_name,
)
from pytortoisegit.git.repo import Repository


def test_strip_ref_name():
    assert strip_ref_name("refs/heads/main") == "main"
    assert strip_ref_name("refs/heads/feature/x") == "feature/x"
    assert strip_ref_name("main") == "main"


def test_build_push_args_never_uses_remote_as_branch():
    args = build_push_args(PushOpts(
        remote="origin", local_branch="main", remote_branch="origin"))
    assert "main:origin" not in args
    assert args == ["push", "--progress", "--", "origin", "main"]


def test_build_push_args_refspec():
    args = build_push_args(PushOpts(
        remote="origin", local_branch="main", remote_branch="main"))
    assert args == ["push", "--progress", "--", "origin", "main:main"]


def test_build_push_args_local_only():
    args = build_push_args(PushOpts(
        remote="origin", local_branch="main", remote_branch=""))
    assert args == ["push", "--progress", "--", "origin", "main"]


def test_build_push_args_all_skips_tags_flag():
    args = build_push_args(PushOpts(remote="origin", all_branches=True, tags=True))
    assert "--all" in args
    assert "--tags" not in args
    assert args[-1] == "origin"


def test_build_push_args_flags():
    args = build_push_args(PushOpts(
        remote="origin",
        local_branch="main",
        force=True,
        set_upstream=True,
        recurse="on-demand",
        push_option="ci.skip",
    ))
    assert "--force" in args
    assert "--set-upstream" in args
    assert "--recurse-submodules=on-demand" in args
    assert "--push-option=ci.skip" in args
    assert args[-2:] == ["origin", "main"]


def test_should_open_push_dialog():
    assert should_open_push_dialog(True, "origin", "main")
    assert should_open_push_dialog(False, "", "main")
    assert should_open_push_dialog(False, "origin", "")
    assert not should_open_push_dialog(False, "origin", "main")


def test_get_remote_push_branch(tmp_path):
    repo = Repository.init(str(tmp_path), initial_branch="main")
    runner = GitRunner(cwd=str(tmp_path))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "init").returncode == 0
    runner.run("remote", "add", "origin", "https://example.com/repo.git")
    runner.run("config", "branch.main.remote", "origin")
    runner.run("config", "branch.main.merge", "refs/heads/main")
    remote, branch = get_remote_push_branch(repo, "main")
    assert remote == "origin"
    assert branch == "main"

    runner.run("config", "branch.main.pushremote", "upstream")
    runner.run("config", "branch.main.pushbranch", "release")
    remote, branch = get_remote_push_branch(repo, "main")
    assert remote == "upstream"
    assert branch == "release"
