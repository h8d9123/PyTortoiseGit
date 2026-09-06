"""git/push.py —— 对齐 CGit::GetRemotePushBranch 与 CAppUtils::DoPush 的参数构造。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .repo import Repository


@dataclass
class PushOpts:
    remote: str
    local_branch: str = ""
    remote_branch: str = ""
    all_branches: bool = False
    force: bool = False
    force_with_lease: bool = False
    tags: bool = False
    set_upstream: bool = False
    push_option: str = ""
    recurse: str = ""


def strip_ref_name(ref: str) -> str:
    ref = (ref or "").strip()
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    if ref.startswith("refs/"):
        return ref.split("/", 2)[-1] if ref.count("/") >= 2 else ref[5:]
    return ref


def should_open_push_dialog(amend: bool, remote: str, remote_branch: str) -> bool:
    """对齐 CCommitDlg::DoPush：amend 或尚未配置 upstream 时才弹 Push 对话框。"""
    return bool(amend or not remote or not remote_branch)


def get_remote_push_branch(repo: Repository, local_branch: str) -> Tuple[str, str]:
    """对齐 CGit::GetRemotePushBranch。返回 (pushRemote, pushBranch)。"""
    if not local_branch:
        return "", ""
    remote = (repo.config(f"branch.{local_branch}.pushremote")
              or repo.config("remote.pushdefault")
              or repo.config(f"branch.{local_branch}.remote"))
    branch = repo.config(f"branch.{local_branch}.pushbranch")
    if not branch:
        branch = strip_ref_name(repo.config(f"branch.{local_branch}.merge"))
    return remote.strip(), branch.strip()


def build_push_args(opts: PushOpts) -> list[str]:
    """构造 `git push` 参数，对齐 CAppUtils::DoPush。

    远端分支名若误填成远程名（例如 origin），当作未指定，避免 `main:origin`。
    """
    args = ["push"]
    if opts.all_branches:
        args.append("--all")
    if opts.tags and not opts.all_branches:
        args.append("--tags")
    if opts.force:
        args.append("--force")
    if opts.force_with_lease:
        args.append("--force-with-lease")
    if opts.set_upstream:
        args.append("--set-upstream")
    if opts.recurse:
        args.append(f"--recurse-submodules={opts.recurse}")
    if opts.push_option:
        args.append(f"--push-option={opts.push_option}")
    args += ["--progress", "--", opts.remote]
    if opts.all_branches:
        return args
    local = (opts.local_branch or "").strip()
    dest = (opts.remote_branch or "").strip()
    if dest and dest == opts.remote:
        dest = ""
    if local and dest:
        args.append(f"{local}:{dest}")
    elif local:
        args.append(local)
    return args
