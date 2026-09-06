# PyTortoiseGit 设计文档

日期：2026-09-05
状态：已确认

## 目标

用 Python + PySide6 重写 TortoiseGit（Windows 与 Linux 跨平台），镜像 TortoiseGit 的 C++ 目录结构，按阶段逐个转换成 Python 模块。不实现 Explorer 右键菜单集成（pywin32 不支持 Linux），改为跨平台 GUI + 文件夹选择定位仓库。

## 架构（方案 B）

主入口 `app.py` 模拟 TortoiseProc.exe 的命令行分发：

```
pytortoisegit app.py /command:commit /path:D:\repo /message:"xxx"
```

- `cmdline.py` 解析 TortoiseGit 兼容参数（`/command:xxx /path:xxx` 等）
- `commands/dispatcher.py` 注册命令签名 → 命令类/函数
- 每个对话框独立窗口，命名与 C++ Dlg 文件对应
- 慢操作经 `asyncfw.py`（QThread worker）后台执行，UI 主线程刷新

## 目录映射

| TortoiseGit C++ | PyTortoiseGit Python |
|---|---|
| TortoiseProc/TortoiseProc.cpp | app.py（入口+分发） |
| Utils/CmdLineParser | cmdline.py |
| Utils/TGitPath | utils/paths.py |
| Utils/ClipboardHelper | utils/clipboard.py |
| Utils/Debug | utils/logging_utils.py |
| ResText | res/strings.py（中文字符串表）+ res/icons.py |
| Git/Git.cpp | git/git.py（GitRunner，subprocess 封装） |
| Git/GitAdminDir | git/admin.py |
| Git/TGitPath/GitRepo | git/repo.py |
| Git/GitRev/GitRevLoglist | git/rev.py |
| Git/GitStatus/GitIndex | git/status.py / git/index.py |
| Git/GitPatch | git/patch.py |
| TortoiseUDiff | udiff.py |
| TortoiseGitBlame | blame.py |
| AsyncFramework | asyncfw.py |
| TortoiseProc/*.cpp Dlg | dialogs/*.py |
| TortoiseProc/Commands/* | commands/*.py |

## 技术要点

- git 命令统一通过 GitRunner（subprocess）执行，`-c core.quotepath=false`，输出按 UTF-8 解析
- 数据流单向：对话框 → git 层 → 后台线程 → UI
- 界面文案中文，字符串集中在 res/strings.py（`tr()` 辅助）
- v1 直接脚本运行，不做 PyInstaller 打包

## 功能范围（阶段顺序）

1. 基础层：cmdline、utils、res/strings、git 核心（GitRunner/admin/repo）、app 入口 + about 命令
2. 只读：udiff、rev（GitRevLoglist）、logdlg、diffdlg、blame+blamedlg
3. 写操作：status/index、commitdlg（staging/amend/push-after-commit）、browserefs（分支/标签/checkout）、progress + asyncfw
4. 同步：clonedlg、sync（pull/push/fetch）、changedlg、settingsdlg
5. 进阶：rebase/merge 冲突、stash、cherry-pick/revert、错误处理打磨

## 验证

- 每阶段 `pytest test/` 跑单元测试
- demo.py 一键启动演示
- UI 手动验证