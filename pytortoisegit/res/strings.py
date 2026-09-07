"""strings.py —— 镜像 TortoiseGit 的 ResText。

界面文案统一放在中文字符串表，通过 tr() 取用，便于后续替换为完整 i18n。
"""

# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

from __future__ import annotations

from typing import Callable, Dict, Optional

# 缓存自实现，若启用 Qt QTranslator 可替换 _current_gettext
_translator: Optional[Callable[[str], str]] = None

STRINGS: Dict[str, str] = {
    # ---- 通用 ----
    "app_name": "PyTortoiseGit",
    "ok": "确定",
    "cancel": "取消",
    "close": "关闭",
    "apply": "应用",
    "yes": "是",
    "no": "否",
    "browse": "浏览...",
    "loading": "加载中...",
    "error": "错误",
    "warning": "警告",
    "information": "提示",
    "progress": "进度",
    "progress_title": "Git 命令进度",
    "progress_wait": "请稍候…",
    "progress_success": "成功",
    "progress_unclean": "git 未能干净退出（退出码 {}）",
    "menu_pull": "Pull",
    "menu_fetch": "Fetch",
    "menu_push": "Push",
    "push_no_remote": "请选择远程或填写 URL",
    "abort": "中止",
    "refresh": "刷新",
    "settings": "设置",
    "repository": "仓库",
    "file": "文件",
    "folder": "文件夹",

    # ---- 关于对话框 (AboutDlg) ----
    "about_title": "关于",
    "about_text": "PyTortoiseGit 是基于 PySide6 用 Python 重写的 TortoiseGit 跨平台客户端。",
    "about_version": "版本",
    "about_website": "仓库",
    "about_git_version": "Git 版本",

    # ---- 命令行分发 ----
    "unknown_command": "未知命令：{command}",
    "missing_command": "请使用 /command:<name> 指定要执行的命令",
    "command_failed": "命令执行失败：{name} —— {message}",

    # ---- 仓库 ----
    "repo_not_found": "不是 git 仓库：{path}",
    "select_repo_folder": "选择存放 Git 仓库的文件夹",
    "open_repo": "打开仓库...",

    # ---- Stash (StashDlg) ----
    "stash_title": "暂存 (Stash)",
    "stash_ref": "引用",
    "stash_subject": "说明",
    "stash_date": "时间",
    "stash_create": "创建暂存",
    "stash_apply": "应用",
    "stash_pop": "弹出并应用",
    "stash_drop": "丢弃",
    "stash_clear": "清空全部",
    "stash_msg": "暂存说明",
    "stash_untracked": "包含未跟踪文件",
    "stash_empty": "没有暂存的修改",
    "stash_confirm_clear": "确定清空全部暂存吗？",
    "stash_created": "已创建暂存",
    "stash_applied": "已应用暂存",
    "stash_popped": "已弹出暂存",
    "stash_dropped": "已丢弃暂存",

    # ---- 合并/变基与冲突 ----
    "merge_title": "合并",
    "merge_branch": "合并分支",
    "merge_noff": "不使用快进 (--no-ff)",
    "merge_squash": "压缩提交 (--squash)",
    "merge_nocommit": "不自动提交 (--no-commit)",
    "merge_message": "提交信息",
    "merge_perform": "开始合并",
    "merge_merged": "合并完成",
    "merge_conflicts": "存在冲突，请解决后在提交对话框中提交",
    "merge_in_progress": "仓库正处于合并状态",
    "merge_abort": "中止合并",
    "merge_aborted": "已中止合并",
    "merge_pick": "选择要合并的分支",
    "rebase_title": "变基 (Rebase)",
    "rebase_target": "目标分支",
    "rebase_interactive": "交互式 (-i)",
    "rebase_autostash": "自动暂存 (--autostash)",
    "rebase_start": "开始变基",
    "rebase_continue": "继续变基",
    "rebase_abort": "中止变基",
    "conflict_resolved": "已标记解决",
    "conflict_mark": "标记解决",
    "conflict_ours": "采用我方 (ours)",
    "conflict_theirs": "采用对方 (theirs)",
    "conflict_extmerge": "外部合并工具",
    "conflict_all": "全部标记解决",
    "conflicts_title": "合并冲突",
    "conflicts_none": "没有冲突",

    # ---- Submodule ----
    "submodule_title": "子模块",
    "submodule_path": "路径",
    "submodule_sha": "提交",
    "submodule_status": "状态",
    "submodule_desc": "远程/说明",
    "submodule_add": "添加子模块",
    "submodule_update": "更新",
    "submodule_update_recursive": "递归更新 (--recursive)",
    "submodule_update_init": "初始化后更新 (--init)",
    "submodule_sync": "同步",
    "submodule_deinit": "取消初始化",
    "submodule_url": "URL",
    "submodule_open_log": "打开日志",
    "submodule_empty": "没有子模块",
    "submodule_added": "已添加子模块",
    "submodule_updated": "子模块已更新",
    "submodule_deinited": "子模块已取消初始化",

    # ---- 外部工具 ----
    "xtool_diffcmd": "外部 diff 工具命令",
    "xtool_mergecmd": "外部 merge 工具命令",
    "xtool_diff_hint": "示例：\"d:\\bin\\bc.exe\" {left} {right}",
    "xtool_merge_hint": "示例：\"d:\\bin\\bc.exe\" {base} {ours} {theirs} {out}",
    "xtool_launch_diff": "外部工具比较",
    "xtool_launch_merge": "外部工具合并",
    "xtool_not_configured": "未配置外部工具，请在设置中填写命令模板",
    "xtool_diff": "外部差异工具 (tortoisegit.externaldiff)",
    "xtool_merge": "外部合并工具 (tortoisegit.externalmerge)",
    "rebase_aborted": "已中止变基",
    "status": "状态",
    "confirm": "确认",

    # ---- 设置 - General 页 ----
    "set_lang": "&语言：",
    "set_gitexe": "&Git.exe 路径：",
    "set_extrapath": "&额外 PATH：",
    "set_ver": "版本：",
    "set_browse": "选择 Git 目录",
    "set_env": "环境变量",
    "set_firststart": "First Start Wizard",
    "firststart_unavailable": "First Start Wizard 不可用。",
    "set_library": "Create Library",
    "set_library_done": "Python 版无需额外创建库。",
    "set_checknewer": "检查更新",
    "set_checknewer_msg": "当前版本：{ver}。此功能为占位，尚不支持自动联网检查。",

    # ---- TortoiseGitMerge 主窗口 ----
    "tm_title": "TortoiseGitMerge - {}",
    "tm_file": "文件(&F)",
    "tm_edit": "编辑(&E)",
    "tm_nav": "导航(&N)",
    "tm_view": "视图(&V)",
    "tm_help": "帮助(&H)",
    "tm_open": "打开",
    "tm_save": "保存",
    "tm_saveas": "另存为...",
    "tm_mark": "标记为已解决",
    "tm_patch": "创建补丁文件",
    "tm_reload": "重新加载",
    "tm_enable_edit": "允许编辑",
    "tm_exit": "退出",
    "tm_undo": "撤销",
    "tm_redo": "重做",
    "tm_copy": "复制",
    "tm_paste": "粘贴",
    "tm_use_left_block": "使用左侧块",
    "tm_use_left_file": "使用左侧文件",
    "tm_use_left_before": "先左后右",
    "tm_use_right_before": "先右后左",
    "tm_use_theirs": "使用左侧文本块",
    "tm_use_mine": "使用右侧文本块",
    "tm_use_theirs_then": "先左后右文本块",
    "tm_use_mine_then": "先右后左文本块",
    "tm_find": "查找",
    "tm_find_next": "查找下一个",
    "tm_find_prev": "查找上一个",
    "tm_goto": "跳转到行",
    "tm_regex": "配置正则过滤器",
    "tm_ignore_comments": "忽略注释",
    "tm_next_diff": "下一处差异",
    "tm_prev_diff": "上一处差异",
    "tm_next_conf": "下一处冲突",
    "tm_prev_conf": "上一处冲突",
    "tm_next_inline": "下一处行内差异",
    "tm_prev_inline": "上一处行内差异",
    "tm_toolbar": "工具栏",
    "tm_statusbar": "状态栏",
    "tm_linediffbar": "行差异条",
    "tm_locator": "定位条",
    "tm_wrap": "折行",
    "tm_moved": "移动块",
    "tm_inline": "行内差异",
    "tm_inline_word": "按词行内差异",
    "tm_cmp_ws": "比较空白",
    "tm_ign_ws": "忽略空白变化",
    "tm_ign_all_ws": "忽略全部空白变化",
    "tm_ignore_eol": "忽略换行符",
    "tm_show_ws": "显示空白",
    "tm_oneway": "单栏/双栏切换",
    "tm_switch": "左右视图对调",
    "tm_collapse": "折叠未改段",
    "tm_settings": "设置",
    "tm_filelist": "显示/隐藏补丁文件列表",
    "tm_help_topics": "帮助主题",
    "tm_about": "关于 TortoiseGitMerge...",
    "tm_help_text": "TortoiseGitMerge 文本比较 / 合并。",
    "tm_col": "列: 0",
    "tm_col_n": "列: {}",
    "tm_conflicts": "冲突",
    "tm_resolved": "已解决",
    "tm_no_result": "没有可保存的合并结果。",
    "tm_saved": "已写入 {}",
    "tm_saved_ok": "已保存。",
    "tm_save_which": "多个栏可写，保存哪一侧？",
    "tm_save_left": "保存左侧",
    "tm_save_right": "保存右侧",
    "tm_save_all": "全部保存",
    "tm_title_plain": "TortoiseGitMerge",
    "tm_has_conflicts": "文件仍有未解决冲突（约第 {} 行）。",
    "tm_save_anyway": "仍然保存",
    "tm_goto_conflict": "转到冲突处",
    "tm_mark_no_repo": "没有仓库路径，无法 git add。",
    "tm_mark_fail": "git add 失败，未能标记已解决。",
    "tm_mark_need_merge": "仅三路合并可将结果标记为已解决。",
    "tm_mark_ok": "已保存并 git add，冲突已标记解决。",
    "tm_ask_mark": "冲突已解决，是否 git add 标记该文件？",
    "tm_patch_none": "没有可导出的仓库文件。",
    "tm_open_two": "当前按左右两个文件比较。",
    "tm_file_tab": "文件",
    "tm_edit_tab": "编辑",
    "tm_group_edit": "编辑",
    "tm_group_nav": "导航",
    "tm_group_blocks": "块",
    "tm_group_ws": "空白",
    "tm_group_diff": "差异",
    "tm_group_view": "视图",
    "tm_view_bars": "栏",

    # ---- Log 对话框 ----
    "log_title": "日志",
    "log_graph": "图",
    "log_actions": "动作",
    "log_message": "信息",
    "log_author": "作者",
    "log_date": "日期",
    "log_hash": "SHA-1",
    "log_email": "电子邮件",
    "log_commit_name": "提交者",
    "log_commit_email": "提交者电子邮件",
    "log_commit_date": "提交日期",
    "log_file_path": "文件",
    "log_file_filename": "文件名",
    "log_file_ext": "扩展名",
    "log_file_status": "状态",
    "log_file_add": "增加",
    "log_file_del": "删除",
    "log_file_modified": "修改日期",
    "log_file_size": "大小",
    "log_file_from": "(来自 {})",
    "filediff_file": "文件",
    "filediff_ext": "扩展名",
    "filediff_action": "动作",
    "filediff_add": "增加",
    "filediff_del": "删除",
    "log_file_group": "已修改的文件",
    "status_group_unversioned": "未版本控制的文件",
    "status_group_ignored": "已忽略的文件",
    "status_group_localignore": "忽略本地更改的文件",
    "log_diff_parent": "与父提交 {} 的差异: {}",
    "log_st_modified": "已修改",
    "log_st_added": "已添加",
    "log_st_deleted": "已删除",
    "log_st_renamed": "已重命名",
    "log_st_copied": "已复制",
    "log_st_type": "类型变更",
    "log_st_unmerged": "未合并",
    "log_compare_wc": "与工作副本比较",
    "log_compare_prev": "与上一版本比较",
    "log_compare_base": "与基版本比较",
    "log_compare_two": "比较两个修订",
    "log_compare_changes": "比较两个提交的变更集",
    "log_gnudiff": "显示统一差异",
    "log_browse": "浏览版本库",
    "log_merge_to": "合并到「{}」",
    "log_reset": "重置「{}」到此…",
    "log_switch": "切换/签出…",
    "log_newbranch": "在此创建分支…",
    "log_newtag": "在此创建标签…",
    "log_export": "导出…",
    "log_revert": "还原此提交引入的更改",
    "log_cherry_pick": "Cherry Pick…",
    "log_create_patch": "创建补丁…",
    "log_copy_clip": "复制到剪贴板",
    "log_copyhash": "完整哈希",
    "log_copyshort": "短哈希",
    "log_copy_authors": "作者",
    "log_copy_emails": "电子邮件",
    "log_copy_subjects": "主题",
    "log_copy_messages": "完整信息",
    "log_copy_refs": "分支/标签",
    "log_show_branches": "显示此提交所在的引用",
    "log_find": "查找…",
    "log_show_log": "显示日志",
    "log_blame": "Blame",
    "log_revert_to_rev": "还原到此版本",
    "log_save_as": "另存为…",
    "log_view_rev": "查看修订",
    "log_open": "打开",
    "log_open_with": "打开方式…",
    "log_explore": "在资源管理器中打开",
    "log_copy_full": "完整路径",
    "log_copy_rel": "相对路径",
    "log_copy_name": "文件名",

    # ---- 仓库管理面板 (MainMenuDlg) ----
    "repo_manager_title": "仓库管理",
    "repo_manager_hint": "双击仓库切换；展开可查看子模块",
    "repo_menu_commit": "Commit…",
    "repo_menu_log": "Show log",
    "repo_menu_pull": "Pull…",
    "repo_menu_push": "Push…",
    "repo_menu_sync": "Sync",
    "repo_menu_revert": "Revert…",
    "repo_menu_cleanup": "Clean Up…",
    "repo_menu_remove": "从列表移除",
    "repo_menu_open_sub": "打开子模块",
    "browser_tab_repo": "仓库管理",
    "browser_tab_folder": "目录树",
    "folder_hint": "双击仓库目录打开；右键仓库目录可添加并执行操作",
    "menu_add_to_repo_list": "添加到仓库管理",
    "menu_left_panel": "左侧面板",
    "menu_submodule": "子模块",
    "menu_submodule_hint": "双击子模块打开其窗口",
}


def tr(key: str, default: str | None = None) -> str:
    """取界面文案。缺 key 时返回 default 或原 key。"""
    if _translator is not None:
        translated = _translator(key)
        if translated:
            return translated
    return STRINGS.get(key, default or key)


def set_translator(func: Optional[Callable[[str], str]]) -> None:
    """安装自定义翻译函数（例如接入 Qt QTranslator 后）。"""
    global _translator
    _translator = func


def format_string(text: str, **kwargs) -> str:
    """格式化字符串表项（未提供参数时保留原占位符）。"""
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text