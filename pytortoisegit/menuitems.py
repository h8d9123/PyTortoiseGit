"""menuitems.py —— 镜像原版 TortoiseGit Shell 右键菜单的状态驱动引擎。

数据与算法均移植自：
  * TortoiseShell/MenuInfo.cpp —— menuInfo[] 菜单项表及 YesNoPair 条件
  * TortoiseShell/ContextMenu.cpp—— ShouldEnableMenu/ShouldInsertItem/QueryContextMenu 过滤
  * TortoiseShell/Globals.h      —— ITEMIS_* 选中项状态位
  * TortoiseShell/ShellCache.h   —— defaultMenuEntries / defaultTopMenuEntries /
                                    defaultExtMenuEntries 掩码

关键：右键菜单不再依赖前端写死的固定列表，而是根据被右击对象计算出的
`itemStates`（选中状态位）配合菜单表里的 4 组 YesNoPair 条件动态决定
显示哪些菜单项（与 TortoiseGit 行为一致）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .git.repo import Repository
from .git.status import GitStatus# ---------------------------------------------------------------- ITEMIS_*
# 选中对象的状态位（Globals.h）
ITEMIS_ONLYONE = 0x00000001          # 只选中一个对象
ITEMIS_EXTENDED = 0x00000002         # 按住 Shift（CMF_EXTENDEDVERBS）
ITEMIS_INGIT = 0x00000004            # 在 git 工作中（已版本化）
ITEMIS_CONFLICTED = 0x00000008       # 冲突
ITEMIS_FOLDER = 0x00000010           # 目录
ITEMIS_FOLDERINGIT = 0x00000020      # 目录且在 git 中
ITEMIS_NORMAL = 0x00000040           # 正常（已版本化且无修改）
ITEMIS_IGNORED = 0x00000080          # 被忽略
ITEMIS_INVERSIONEDFOLDER = 0x00000100  # 位于已版本化目录/仓库内
ITEMIS_ADDED = 0x00000200            # 新增
ITEMIS_DELETED = 0x00000400          # 删除
ITEMIS_PATCHFILE = 0x00001000        # 补丁文件 (.diff/.patch)
ITEMIS_PATCHINCLIPBOARD = 0x00008000  # 剪贴板有补丁
ITEMIS_PATHINCLIPBOARD = 0x00010000  # 剪贴板有路径
ITEMIS_TWO = 0x00020000              # 选中两个对象（diff 双文件）
ITEMIS_SUBMODULECONTAINER = 0x00040000  # 仓库包含子模块
ITEMIS_GITSVN = 0x00080000           # git-svn 工作树
ITEMIS_STASH = 0x00100000            # 有 stash
ITEMIS_WCROOT = 0x00200000           # 仓库工作树根
ITEMIS_BISECT = 0x00400000           # bisect 进行中
ITEMIS_BAREREPO = 0x00800000         # 裸仓库
ITEMIS_SUBMODULE = 0x01000000        # 子模块
ITEMIS_MERGEACTIVE = 0x02000000      # 合并进行中
ITEMIS_HASDIFFLATER = 0x04000000     # 有 diff-later 暂存
ITEMIS_INACCESSIBLE = 0x08000000     # 不可访问

# ------------------------------------------------- TGitContextMenuEntries
# 菜单项对应的位标记（Globals.h TGitContextMenuEntries，用于默认掩码）
_M_SYNC = 0x0000000000000002
_M_COMMIT = 0x0000000000000004
_M_ADD = 0x0000000000000008
_M_REVERT = 0x0000000000000010
_M_CLEANUP = 0x0000000000000020
_M_RESOLVE = 0x0000000000000040
_M_SWITCH = 0x0000000000000080
_M_SENDMAIL = 0x0000000000000100
_M_EXPORT = 0x0000000000000200
_M_CREATEREPO = 0x0000000000000400
_M_BRANCH = 0x0000000000000800
_M_MERGE = 0x0000000000001000
_M_REMOVE = 0x0000000000002000
_M_RENAME = 0x0000000000004000
_M_SUBMODULEUPDATE = 0x0000000000008000
_M_DIFF = 0x0000000000010000
_M_LOG = 0x0000000000020000
_M_CONFLICTEDITOR = 0x0000000000040000
_M_REFBROWSER = 0x0000000000080000
_M_SHOWCHANGED = 0x0000000000100000
_M_IGNORE = 0x0000000000200000
_M_REFLOG = 0x0000000000400000
_M_BLAME = 0x0000000000800000
_M_REPOBROWSER = 0x0000000001000000
_M_APPLYPATCH = 0x0000000002000000
_M_REMOVEKEEP = 0x0000000004000000
_M_SVNREBASE = 0x0000000008000000
_M_SVNDCOMMIT = 0x0000000010000000
_M_SVNIGNORE = 0x0000000040000000
_M_LOGSUBMODULE = 0x0000000100000000
_M_PREVDIFF = 0x0000000200000000
_M_PULL = 0x0000000800000000
_M_PUSH = 0x0000001000000000
_M_CLONE = 0x0000002000000000
_M_TAG = 0x0000004000000000
_M_FORMATPATCH = 0x0000008000000000
_M_IMPORTPATCH = 0x0000010000000000
_M_DIFFLATER = 0x0000020000000000
_M_FETCH = 0x0000040000000000
_M_REBASE = 0x0000080000000000
_M_STASHSAVE = 0x0000100000000000
_M_STASHAPPLY = 0x0000200000000000
_M_STASHLIST = 0x0000400000000000
_M_SUBMODULEADD = 0x0000800000000000
_M_SUBMODULESYNC = 0x0001000000000000
_M_STASHPOP = 0x0002000000000000
_M_DIFFTWO = 0x0004000000000000
_M_BISECT = 0x0008000000000000
_M_INACCESSIBLE = 0x0010000000000000
_M_SVNFETCH = 0x0080000000000000
_M_REVISIONGRAPH = 0x0100000000000000
_M_DAEMON = 0x0200000000000000
_M_WORKTREE = 0x0400000000000000
_M_LFS = 0x1000000000000000
_M_SETTINGS = 0x2000000000000000
_M_HELP = 0x4000000000000000
_M_ABOUT = 0x8000000000000000
_M_NONE = 0x0000000000000000
_M_SEPARATOR = 0x0000000000000000

# ------------------------------------------- 默认掩码（ShellCache.cpp / .h）
defaultMenuEntries = (
    _M_SYNC | _M_COMMIT | _M_SWITCH | _M_REVERT | _M_CONFLICTEDITOR | _M_DIFF |
    _M_PULL | _M_PUSH | _M_REPOBROWSER | _M_LOG | _M_BLAME | _M_CLONE |
    _M_MERGE | _M_STASHSAVE | _M_SETTINGS)
defaultTopMenuEntries = _M_SYNC | _M_CREATEREPO | _M_CLONE | _M_COMMIT
defaultExtMenuEntries = _M_SVNIGNORE | _M_STASHAPPLY | _M_SUBMODULESYNC


@dataclass
class MenuEntry:
    """menuInfo[] 的一行。conds 为 4 组 (yes, no) 状态位组合。"""
    command: str                    # pyTortoise 命令名（如 "diff"）
    menu_id: int                    # TGitContextMenuEntries 位
    icon_id: str                    # TortoiseGit 图标 ID（"" 表无图标）
    label_key: str                  # 文案键（res/strings.py）
    label: str                      # 默认文案（英文字串）
    conds: Tuple[Tuple[int, int], ...] = ()  # 4 组 (yes, no)


def _e(command, menu_id, icon_id, label_key, label, *conds):
    return MenuEntry(command, menu_id, icon_id, label_key, label,
                     tuple(conds))


# ---------------------------------------- menuInfo[]（MenuInfo.cpp 逐行移植）
# 条件用法：{yes,no} 表示「yes 位都命中、no 位都不命中」才显示。
# 按原版顺序保留 Separator 项以驱动分隔线。
MENU_INFO: List[MenuEntry] = [
    _e("inaccessible", _M_INACCESSIBLE, "IDI_CLEANUP", "menu_cmd_inaccessible", "Inaccessible",
       (ITEMIS_INACCESSIBLE, ITEMIS_INGIT | ITEMIS_FOLDERINGIT | ITEMIS_BAREREPO)),
    _e("clone", _M_CLONE, "IDI_CLONE", "repo_menu_clone", "Git Clone…",
       (ITEMIS_FOLDER, ITEMIS_INGIT | ITEMIS_FOLDERINGIT | ITEMIS_BAREREPO | ITEMIS_INACCESSIBLE),
       (ITEMIS_FOLDER | ITEMIS_IGNORED, 0),
       (ITEMIS_FOLDER | ITEMIS_EXTENDED, 0)),
    _e("pull", _M_PULL, "IDI_PULL", "repo_menu_pull", "Pull…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_BISECT | ITEMIS_MERGEACTIVE),
       (ITEMIS_WCROOT, ITEMIS_BISECT | ITEMIS_MERGEACTIVE)),
    _e("fetch", _M_FETCH, "IDI_UPDATE", "menu_cmd_fetch", "Fetch…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0), (ITEMIS_BAREREPO, 0), (ITEMIS_WCROOT, 0)),
    _e("push", _M_PUSH, "IDI_PUSH", "menu_cmd_push", "Push…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0), (ITEMIS_BAREREPO, 0), (ITEMIS_WCROOT, 0)),
    _e("sync", _M_SYNC, "IDI_RELOCATE", "repo_menu_sync", "Sync",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_BISECT | ITEMIS_MERGEACTIVE)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("commit", _M_COMMIT, "IDI_COMMIT", "repo_menu_commit", "Commit…",
       (ITEMIS_INGIT, 0), (ITEMIS_FOLDERINGIT, 0)),
    _e("svndcommit", _M_SVNDCOMMIT, "IDI_COMMIT", "menu_cmd_svndcommit", "DCommit…",
       (ITEMIS_INGIT | ITEMIS_GITSVN, ITEMIS_BISECT | ITEMIS_MERGEACTIVE),
       (ITEMIS_FOLDERINGIT | ITEMIS_GITSVN, ITEMIS_BISECT | ITEMIS_MERGEACTIVE)),
    _e("svnrebase", _M_SVNREBASE, "IDI_REBASE", "menu_cmd_svnrebase", "SVN Rebase…",
       (ITEMIS_FOLDERINGIT | ITEMIS_GITSVN | ITEMIS_ONLYONE, ITEMIS_BISECT | ITEMIS_MERGEACTIVE)),
    _e("svnfetch", _M_SVNFETCH, "IDI_UPDATE", "menu_cmd_svnfetch", "SVN Fetch…",
       (ITEMIS_FOLDERINGIT | ITEMIS_GITSVN | ITEMIS_ONLYONE, 0)),
    _e("svnignore", _M_SVNIGNORE, "IDI_IGNORE", "menu_cmd_svnignore", "Import SVN Ignore ...",
       (ITEMIS_FOLDERINGIT | ITEMIS_GITSVN | ITEMIS_ONLYONE, 0)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("diff", _M_DIFF, "IDI_DIFF", "file_menu_diff", "Diff…",
       (ITEMIS_INGIT | ITEMIS_ONLYONE, 0), (ITEMIS_TWO, ITEMIS_FOLDER)),
    _e("showcompare", _M_DIFFLATER, "IDI_DIFF", "menu_cmd_showcompare", "Compare with later",
       (ITEMIS_ONLYONE, ITEMIS_FOLDER)),
    _e("prevdiff", _M_PREVDIFF, "IDI_DIFF", "menu_cmd_prevdiff", "Diff with previous",
       (ITEMIS_INGIT | ITEMIS_ONLYONE, ITEMIS_ADDED)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("log", _M_LOG, "IDI_LOG", "repo_menu_log", "Show log",
       (ITEMIS_INGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_FOLDER | ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_BAREREPO, 0)),
    _e("log", _M_LOGSUBMODULE, "IDI_LOG", "menu_cmd_logsubmodule", "Show submodule log",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_WCROOT | ITEMIS_SUBMODULE, 0)),
    _e("reflog", _M_REFLOG, "IDI_LOG", "menu_cmd_reflog", "Reflog…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0), (ITEMIS_BAREREPO, 0)),
    _e("browserefs", _M_REFBROWSER, "IDI_REPOBROWSE", "menu_cmd_browserefs", "Browse References…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0), (ITEMIS_BAREREPO, 0)),
    _e("daemon", _M_DAEMON, "IDI_DAEMON", "menu_cmd_daemon", "Daemon…",
       (ITEMIS_INGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_FOLDER | ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_BAREREPO, 0)),
    _e("revisiongraph", _M_REVISIONGRAPH, "IDI_REVISIONGRAPH", "menu_cmd_revisiongraph", "Revision Graph",
       (ITEMIS_INGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_FOLDER | ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_ADDED),
       (ITEMIS_BAREREPO, 0)),
    _e("repobrowser", _M_REPOBROWSER, "IDI_REPOBROWSE", "menu_cmd_repobrowser", "Repo Browser",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0),
       (ITEMIS_BAREREPO | ITEMIS_ONLYONE, 0)),
    _e("changed", _M_SHOWCHANGED, "IDI_SHOWCHANGED", "menu_cmd_changed", "Show Changed…",
       (ITEMIS_INGIT, 0), (ITEMIS_FOLDER | ITEMIS_FOLDERINGIT, 0)),
    _e("rebase", _M_REBASE, "IDI_REBASE", "menu_cmd_rebase", "Rebase…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_BISECT | ITEMIS_MERGEACTIVE)),
    _e("stashsave", _M_STASHSAVE, "IDI_SHELVE", "menu_cmd_stash", "Stash changes…",
       (ITEMIS_INGIT | ITEMIS_ONLYONE, ITEMIS_MERGEACTIVE)),
    _e("stashapply", _M_STASHAPPLY, "IDI_UNSHELVE", "menu_cmd_stashapply", "Stash Apply",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_STASH, 0)),
    _e("stashpop", _M_STASHPOP, "IDI_UNSHELVE", "menu_cmd_stashpop", "Stash pop…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_STASH, 0)),
    _e("stashlist", _M_STASHLIST, "IDI_LOG", "menu_cmd_stashlist", "Stash list…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_STASH, 0)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("bisect", _M_BISECT, "IDI_BISECT", "menu_cmd_bisect", "Bisect…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_BISECT | ITEMIS_MERGEACTIVE)),
    _e("bisect", _M_BISECT, "IDI_THUMB_UP", "menu_cmd_bisectgood", "Bisect Good",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_BISECT, 0)),
    _e("bisect", _M_BISECT, "IDI_THUMB_DOWN", "menu_cmd_bisectbad", "Bisect Bad",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_BISECT, 0)),
    _e("bisect", _M_BISECT, "IDI_BISECT", "menu_cmd_bisectskip", "Bisect Skip",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_BISECT, 0)),
    _e("bisect", _M_BISECT, "IDI_BISECT_RESET", "menu_cmd_bisectreset", "Bisect Reset",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE | ITEMIS_BISECT, 0)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("conflicteditor", _M_CONFLICTEDITOR, "IDI_CONFLICT", "menu_cmd_conflicteditor", "Conflict Editor…",
       (ITEMIS_INGIT | ITEMIS_CONFLICTED, ITEMIS_FOLDER)),
    _e("resolve", _M_RESOLVE, "IDI_RESOLVE", "menu_cmd_resolve", "Resolve…",
       (ITEMIS_INGIT | ITEMIS_CONFLICTED, 0),
       (ITEMIS_INGIT | ITEMIS_FOLDER, 0),
       (ITEMIS_FOLDERINGIT, 0)),
    _e("mergeabort", _M_MERGE, "IDI_MERGEABORT", "menu_cmd_mergeabort", "Abort Merge…",
       (ITEMIS_INGIT | ITEMIS_MERGEACTIVE, 0),
       (ITEMIS_FOLDERINGIT | ITEMIS_MERGEACTIVE, 0)),
    _e("rename", _M_RENAME, "IDI_RENAME", "menu_cmd_rename", "Rename…",
       (ITEMIS_INGIT | ITEMIS_ONLYONE | ITEMIS_INVERSIONEDFOLDER, ITEMIS_WCROOT),
       (ITEMIS_WCROOT | ITEMIS_SUBMODULE, 0)),
    _e("remove", _M_REMOVE, "IDI_DELETE", "menu_cmd_remove", "Remove…",
       (ITEMIS_INGIT | ITEMIS_INVERSIONEDFOLDER, ITEMIS_ADDED | ITEMIS_WCROOT),
       (ITEMIS_FOLDERINGIT | ITEMIS_WCROOT | ITEMIS_SUBMODULE, 0)),
    _e("remove", _M_REMOVEKEEP, "IDI_DELETE", "menu_cmd_removekeep", "Remove (keep local)…",
       (ITEMIS_INGIT | ITEMIS_INVERSIONEDFOLDER, ITEMIS_ADDED | ITEMIS_WCROOT)),
    _e("revert", _M_REVERT, "IDI_REVERT", "repo_menu_revert", "Revert…",
       (ITEMIS_INGIT, ITEMIS_NORMAL), (ITEMIS_FOLDERINGIT, 0)),
    _e("cleanup", _M_CLEANUP, "IDI_CLEANUP", "repo_menu_cleanup", "Clean Up…",
       (ITEMIS_FOLDERINGIT | ITEMIS_FOLDER, 0)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("lfslock", _M_LFS, "IDI_LFS", "menu_cmd_lfslock", "LFS…",
       (ITEMIS_INVERSIONEDFOLDER | ITEMIS_INGIT, 0)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("switch", _M_SWITCH, "IDI_SWITCH", "menu_cmd_switch", "Switch/Checkout…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0)),
    _e("merge", _M_MERGE, "IDI_MERGE", "menu_cmd_merge", "Merge…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, ITEMIS_BISECT | ITEMIS_MERGEACTIVE)),
    _e("branch", _M_BRANCH, "IDI_COPY", "menu_cmd_branch", "Branch…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0)),
    _e("branch", _M_TAG, "IDI_TAG", "menu_cmd_tag", "Tag…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0)),
    _e("export", _M_EXPORT, "IDI_EXPORT", "menu_cmd_export", "Export…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0), (ITEMIS_BAREREPO, 0)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("repocreate", _M_CREATEREPO, "IDI_CREATEREPOS", "menu_cmd_repocreate", "Create repository…",
       (ITEMIS_FOLDER, ITEMIS_INGIT | ITEMIS_FOLDERINGIT | ITEMIS_BAREREPO | ITEMIS_INACCESSIBLE),
       (ITEMIS_FOLDER | ITEMIS_IGNORED, 0),
       (ITEMIS_FOLDER | ITEMIS_EXTENDED, ITEMIS_INGIT)),
    _e("add", _M_ADD, "IDI_ADD", "menu_cmd_add", "Add…",
       (ITEMIS_INVERSIONEDFOLDER, ITEMIS_INGIT),
       (ITEMIS_INGIT | ITEMIS_FOLDER, 0),
       (ITEMIS_IGNORED, 0),
       (ITEMIS_DELETED, ITEMIS_FOLDER | ITEMIS_ONLYONE)),
    _e("blame", _M_BLAME, "IDI_BLAME", "menu_cmd_blame", "Blame…",
       (ITEMIS_INGIT | ITEMIS_ONLYONE, ITEMIS_FOLDER | ITEMIS_ADDED)),
    _e("ignore", _M_IGNORE, "IDI_IGNORE", "menu_cmd_ignore", "Add to .gitignore",
       (ITEMIS_INVERSIONEDFOLDER, ITEMIS_IGNORED | ITEMIS_INGIT | ITEMIS_WCROOT)),
    _e("unignore", _M_IGNORE, "IDI_IGNORE", "menu_cmd_unignore", "Remove from .gitignore",
       (ITEMIS_INVERSIONEDFOLDER | ITEMIS_INGIT, ITEMIS_IGNORED | ITEMIS_WCROOT)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("worktreelist", _M_WORKTREE, "IDI_COPY", "menu_cmd_worktreelist", "Worktrees…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0), (ITEMIS_BAREREPO, 0)),
    _e("submodule", _M_SUBMODULEADD, "IDI_ADD", "menu_cmd_submoduleadd", "Add submodule…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0)),
    _e("submodule", _M_SUBMODULEUPDATE, "IDI_UPDATE", "menu_cmd_submoduleupdate", "Submodule Update…",
       (ITEMIS_FOLDERINGIT | ITEMIS_SUBMODULECONTAINER, 0)),
    _e("subsync", _M_SUBMODULESYNC, "IDI_MENUSYNC", "menu_cmd_subsync", "Submodule Sync…",
       (ITEMIS_FOLDERINGIT | ITEMIS_SUBMODULECONTAINER, 0)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("formatpatch", _M_FORMATPATCH, "IDI_CREATEPATCH", "menu_cmd_formatpatch", "Format Patch…",
       (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0)),
    _e("importpatch", _M_IMPORTPATCH, "IDI_PATCH", "menu_cmd_importpatch", "Import Patch…",
       (ITEMIS_PATCHFILE, 0), (ITEMIS_FOLDERINGIT | ITEMIS_ONLYONE, 0)),
    _e("sendmail", _M_SENDMAIL, "IDI_MENUSENDMAIL", "menu_cmd_sendmail", "Send Mail…",
       (ITEMIS_PATCHFILE, 0), (ITEMIS_EXTENDED, ITEMIS_FOLDER)),
    MenuEntry("separator", _M_SEPARATOR, "", "", ""),
    _e("settings", _M_SETTINGS, "IDI_SETTINGS", "repo_menu_settings", "Settings",
       (ITEMIS_FOLDER, 0), (0, ITEMIS_FOLDER)),
    _e("help", _M_HELP, "IDI_HELP", "menu_cmd_help", "Help",
       (ITEMIS_FOLDER, 0), (0, ITEMIS_FOLDER)),
    _e("about", _M_ABOUT, "IDI_ABOUT", "menu_cmd_about", "About",
       (ITEMIS_FOLDER, 0), (0, ITEMIS_FOLDER)),
]


# ------------------------------------------------------- 已注册命令集合
def _registered_commands() -> set:
    from .commands.dispatcher import _ensure_imports, available_commands
    try:
        _ensure_imports()
        return set(available_commands())
    except Exception:
        return set()


_REGISTERED: set = _registered_commands()


# ------------------------------------------------------------ 过滤逻辑
def _should_enable(pair: Tuple[int, int], states: int) -> bool:
    yes, no = pair
    if yes and no:
        return ((yes & states) == yes) and ((no & (~states)) == no)
    if yes:
        return (yes & states) == yes
    if no:
        return (no & (~states)) == no
    return False


def should_insert_entry(entry: MenuEntry, states: int) -> bool:
    if not entry.conds:
        return False
    return any(_should_enable(c, states) for c in entry.conds)


def menu_entries(states: int, *, extended: bool = False,
                 include_unavailable: bool = False) -> List[MenuEntry]:
    """按状态位返回应显示的菜单项（含 separator 位置）。

    完全对应 QueryContextMenu 的过滤顺序：
      * menuex 扩展位 → 只在 Shift（ITEMIS_EXTENDED）时显示（Inaccessible 除外）
      * menumask 掩码（默认 0 → 不过滤）
      * ShouldInsertItem 条件
    `include_unavailable=False` 会剔除 pyTortoise 未注册的命令，避免点无效项。
    """
    states_i = states | (ITEMIS_EXTENDED if extended else 0)
    result: List[MenuEntry] = []
    for entry in MENU_INFO:
        if entry.command == "separator":
            result.append(entry)
            continue
        if not include_unavailable and entry.command not in _REGISTERED:
            continue
        # menuex：扩展项必须按住 Shift
        if (entry.menu_id & defaultExtMenuEntries):
            if not (states_i & ITEMIS_EXTENDED) and entry.command != "inaccessible":
                continue
        # menumask：默认掩码为 0 → 天然不过滤（镜像原版 GetMenuMask()==0）
        if not should_insert_entry(entry, states_i):
            continue
        result.append(entry)
    return _prune_separators(result)


def _prune_separators(entries: List[MenuEntry]) -> List[MenuEntry]:
    """去掉开头/连续的分隔线（镜像原版不立即插入分隔线的逻辑）。"""
    pruned: List[MenuEntry] = []
    prev_sep = True  # 前一个是分隔线 / 空，跳过开头的分隔线
    for e in entries:
        if e.command == "separator":
            if prev_sep:
                continue
            prev_sep = True
            pruned.append(e)
        else:
            prev_sep = False
            pruned.append(e)
    # 末尾多余分隔线
    while pruned and pruned[-1].command == "separator":
        pruned.pop()
    return pruned


# ------------------------------------------------------- 状态计算
def has_stash(repo: Repository) -> bool:
    r = repo.runner.run("stash", "list")
    return bool(r.stdout and r.stdout.strip())


def has_gitsvn(repo: Repository) -> bool:
    r = repo.runner.run("config", "--get", "svn-remote.svn.url")
    return r.returncode == 0 and bool(r.stdout and r.stdout.strip())


def is_bisect_active(repo: Repository) -> bool:
    r = repo.runner.run("rev-parse", "--verify", "-q", "BISECT_HEAD")
    if r.returncode == 0:
        return True
    r = repo.runner.run("rev-parse", "--git-path", "BISECT_START")
    return r.returncode == 0 and bool(r.stdout and os.path.exists(r.stdout.strip()))


def is_merge_active(repo: Repository) -> bool:
    r = repo.runner.run("rev-parse", "--verify", "-q", "MERGE_HEAD")
    return r.returncode == 0


def is_rebase_active(repo: Repository) -> bool:
    git_dir = repo.runner.run("rev-parse", "--git-path", ".").stdout.strip()
    for name in ("rebase-merge", "rebase-apply"):
        p = os.path.join(git_dir if os.path.isabs(git_dir) else os.path.join(repo.root, git_dir), name)
        if git_dir and os.path.exists(p):
            return True
    return False


def path_status(repo: Repository, path: str) -> int:
    """计算单个路径（文件/目录）的状态位（INGIT/NORMAL/ADDED/DELETED/CONFLICTED/IGNORED…）。

    返回 flags（ITEMIS_* 组合），不含 FOLDER/FOLDERINGIT/WCROOT/EXTENDED。
    目录的"是否版本化"按 TortoiseGit 的保守策略：仓库内目录视为版本化文件夹。
    """
    flags = 0
    try:
        rel = os.path.relpath(path, repo.root).replace("\\", "/")
    except ValueError:
        return 0
    if rel == ".":
        return 0
    rel = rel.strip("/")
    if not rel:
        return 0

    entry = None
    try:
        for e in GitStatus(repo).get_status():
            if e.path.replace("\\", "/") == rel or e.orig_path.replace("\\", "/") == rel:
                entry = e
                break
    except Exception:
        entry = None

    if entry is None:
        # 未出现在 status 里 → 视为已版本化且无修改（normal）
        flags |= ITEMIS_INGIT | ITEMIS_NORMAL
        return flags

    if entry.is_untracked:
        flags |= ITEMIS_IGNORED if (_looks_ignored(repo, rel)) else ITEMIS_INVERSIONEDFOLDER
        # unversioned：不置 INGIT
        flags &= ~ITEMIS_INGIT
        return flags

    # 已版本化
    flags |= ITEMIS_INGIT
    if entry.is_conflicted:
        flags |= ITEMIS_CONFLICTED
    elif entry.is_staged and entry.index_status == "A" and not entry.is_modified:
        flags |= ITEMIS_ADDED
    elif entry.is_conflicted:
        flags |= ITEMIS_CONFLICTED
    elif (entry.index_status, entry.worktree_status) in {("D", "D"), ("D", " ")}:
        flags |= ITEMIS_DELETED
    elif not entry.is_modified and not entry.is_staged:
        flags |= ITEMIS_NORMAL
    return flags


def _looks_ignored(repo: Repository, rel: str) -> bool:
    try:
        r = repo.runner.run("check-ignore", "-q", rel)
        return r.returncode == 0
    except Exception:
        return False


def compute_item_states(path: str, *, extended: bool = False) -> int:
    """对一个被右键的路径计算完整 itemStates（对应于 ContextMenu.cpp Initialize）。"""
    states = ITEMIS_ONLYONE  # 单对象选中
    if extended:
        states |= ITEMIS_EXTENDED

    is_dir = os.path.isdir(path)

    # 找到仓库根
    try:
        root = _find_repo_root(path)
    except Exception:
        root = None

    if root is None:
        # 不在仓库：仅目录本身
        if is_dir:
            states |= ITEMIS_FOLDER | ITEMIS_INVERSIONEDFOLDER
        else:
            # 非仓库文件：无 INGIT
            pass
        return states

    repostate = _repo_context_states(path, root, is_dir)
    return states | repostate


def _repo_context_states(path: str, root: str, is_dir: bool) -> int:
    flags = 0
    try:
        repo = Repository.open(root)
    except Exception:
        repo = None

    abs_root = os.path.abspath(root)
    abs_path = os.path.abspath(path)

    # 父目录：仓库内（可能未版本化）→ INVERSIONEDFOLDER
    if _inside_worktree(abs_path, abs_root) and abs_path != abs_root:
        flags |= ITEMIS_INVERSIONEDFOLDER

    if is_dir:
        flags |= ITEMIS_FOLDER
        if abs_path == abs_root:
            flags |= ITEMIS_WCROOT
            if repo and repo.is_bare():
                flags |= ITEMIS_BAREREPO
            # 仓库根目录本身在 git 中
            flags |= ITEMIS_FOLDERINGIT | ITEMIS_INGIT
            # 根下的未版本化判断交给具体文件；目录根视为版本化。
        else:
            # 仓库内子目录：保守视为版本化文件夹
            flags |= ITEMIS_FOLDERINGIT | ITEMIS_INGIT
            # 若子目录是子模块根则加 SUBMODULE
            if _is_submodule_root(repo, abs_path, abs_root):
                flags |= ITEMIS_SUBMODULE
    else:
        # 文件
        flags |= path_status(repo, abs_path)

    if repo:
        if _repo_has_submodules(repo):
            flags |= ITEMIS_SUBMODULECONTAINER
        if has_gitsvn(repo):
            flags |= ITEMIS_GITSVN
        if has_stash(repo):
            flags |= ITEMIS_STASH
        if is_bisect_active(repo):
            flags |= ITEMIS_BISECT
        if is_merge_active(repo) or is_rebase_active(repo):
            flags |= ITEMIS_MERGEACTIVE
        if repo.is_bare():
            flags |= ITEMIS_BAREREPO | ITEMIS_INGIT
    return flags


def _inside_worktree(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def _is_submodule_root(repo: Repository | None, path: str, root: str) -> bool:
    if repo is None:
        return False
    try:
        rel = os.path.relpath(path, root).replace("\\", "/").strip("/")
        if not rel:
            return False
        r = repo.runner.run("config", "--get", f"submodule.{rel}.url")
        return r.returncode == 0
    except Exception:
        return False


def _repo_has_submodules(repo: Repository) -> bool:
    try:
        r = repo.runner.run("config", "--get-regexp", r"^submodule\..*\.path$")
        return r.returncode == 0 and bool(r.stdout and r.stdout.strip())
    except Exception:
        return False


def _find_repo_root(path: str):
    from .git.admin import find_repo_root as _f
    return _f(path)


# ------------------------------------------------------- 便捷查询
def available_commands_for(path: str, *, extended: bool = False) -> Iterable[str]:
    """返回在给定路径下会显示的可用命令名（供测试/预览）。"""
    states = compute_item_states(path, extended=extended)
    return [e.command for e in menu_entries(states, extended=extended)
            if e.command != "separator"]
