# PyTortoiseGit 速览

基于 PySide6 用 Python 重写的跨平台 TortoiseGit 客户端——保留其对话框布局、
命令行协议与操作习惯。本页汇总主要对话框的实际界面截图。

> 截图由 `python scripts/screenshots.py` 在 offscreen 平台自动生成，输出到
> `screenshots/`（该目录在 `.gitignore` 中，不随仓库提交）。

## 目录

- [主窗口](#主窗口)
- [资源管理器右键菜单](#资源管理器右键菜单)
- [首次启动向导](#首次启动向导)
- [克隆仓库](#克隆仓库)
- [提交](#提交)
- [日志](#日志)
- [差异查看](#差异查看)
- [引用日志 reflog](#引用日志-reflog)
- [切换 / 检出](#切换--检出)
- [拉取 / 抓取](#拉取--抓取)
- [推送](#推送)
- [合并](#合并)
- [变基](#变基)
- [修订图](#修订图)
- [设置](#设置)

## 主窗口

PyTortoiseGit 主窗口（`PyTortoiseGit 主窗口`），列出常用仓库入口。

![PyTortoiseGit 主窗口](screenshots/mainwindow.png)

## 资源管理器右键菜单

在资源管理器空白处 / 文件上右键弹出的 TortoiseGit 菜单。

![资源管理器右键菜单](screenshots/contextmenu.png)

## 首次启动向导

首次运行时引导完成基础 Git 配置（语言、Git 路径、用户信息、身份验证）。

| 界面语言 | 欢迎 |
| --- | --- |
| ![](screenshots/wizard_0.png) | ![](screenshots/wizard_1.png) |

| Git 可执行文件 | 用户信息 | 身份验证 |
| --- | --- | --- |
| ![](screenshots/wizard_2.png) | ![](screenshots/wizard_3.png) | ![](screenshots/wizard_4.png) |

## 克隆仓库

克隆远程仓库（`Git clone - TortoiseGit`）。

![克隆仓库](screenshots/clone.png)

## 提交

提交对话框（`Commit - TortoiseGit`），可分类查看已修改 / 未跟踪文件。

![提交](screenshots/commit.png)

## 日志

日志窗口（`Log Messages`），含提交列表、文件列表与下方差异预览。

![日志](screenshots/log.png)

## 差异查看

"更改的文件"对话框，比较两个修订之间的差异。

![差异查看](screenshots/diff.png)

## 引用日志 reflog

引用日志窗口（`引用日志 (reflog)`），查看分支引用的移动历史。

![引用日志](screenshots/reflog.png)

## 切换 / 检出

切换分支 / 检出提交（`Switch/Checkout`）。

![切换/检出](screenshots/switch.png)

## 拉取 / 抓取

| 拉取（拉取/抓取） | 抓取（抓取） |
| --- | --- |
| ![](screenshots/pull.png) | ![](screenshots/fetch.png) |

## 推送

推送对话框（`Push`）。

![推送](screenshots/push.png)

## 合并

合并对话框（`合并`）。

![合并](screenshots/merge.png)

## 变基

变基对话框（`变基 (Rebase)`）。

![变基](screenshots/rebase.png)

## 修订图

修订图窗口（`修订图`），图形化展示提交历史。

![修订图](screenshots/revisiongraph.png)

## 设置

设置对话框（`设置`），树形页面结构对齐 TortoiseGit 的 `CSettings`。

### 常规

| 常规 | 右键菜单 |
| --- | --- |
| ![](screenshots/settings_general.png) | ![](screenshots/settings_contextmenu.png) |

| 右键菜单 2 | Windows 11 右键菜单 | 备用编辑器 |
| --- | --- | --- |
| ![](screenshots/settings_contextmenu2.png) | ![](screenshots/settings_win11menu.png) | ![](screenshots/settings_alternativeeditor.png) |

| 对话框 1 | 对话框 2 | 对话框 3 |
| --- | --- | --- |
| ![](screenshots/settings_dialogs1.png) | ![](screenshots/settings_dialogs2.png) | ![](screenshots/settings_dialogs3.png) |

| 颜色 1 | 颜色 2 | 颜色 3 |
| --- | --- | --- |
| ![](screenshots/settings_colors1.png) | ![](screenshots/settings_colors2.png) | ![](screenshots/settings_colors3.png) |

### Git

| Git | 远程 | 凭据 |
| --- | --- | --- |
| ![](screenshots/settings_git.png) | ![](screenshots/settings_gitremote.png) | ![](screenshots/settings_gitcredential.png) |

### 钩子脚本

| 钩子脚本 | 问题跟踪集成 | 问题跟踪配置 |
| --- | --- | --- |
| ![](screenshots/settings_hooks.png) | ![](screenshots/settings_bugtraq.png) | ![](screenshots/settings_bugtraqconfig.png) |

### 图标覆盖

| 图标覆盖 | 图标集 | 覆盖处理程序 |
| --- | --- | --- |
| ![](screenshots/settings_overlay.png) | ![](screenshots/settings_overlays.png) | ![](screenshots/settings_overlayhandlers.png) |

### 网络

| 网络 | 邮件 |
| --- | --- |
| ![](screenshots/settings_network.png) | ![](screenshots/settings_email.png) |

### 差异查看器 / 合并工具

| 差异查看器 | 合并工具 |
| --- | --- |
| ![](screenshots/settings_diff.png) | ![](screenshots/settings_merge.png) |

### 其他

| 保存的数据 | TortoiseGitBlame | TortoiseGitUDiff |
| --- | --- | --- |
| ![](screenshots/settings_saveddata.png) | ![](screenshots/settings_blame.png) | ![](screenshots/settings_udiff.png) |

| 高级 |
| --- |
| ![](screenshots/settings_advanced.png) |
