# PyTortoiseGit

基于 PySide6 用 Python 重写的 TortoiseGit 跨平台 Git 客户端。

镜像 TortoiseGit 的 C++ 目录结构，按阶段逐步转换为 Python 模块。

> **为什么做这个项目**
>
> 我非常喜欢使用 TortoiseGit，但遗憾的是它只支持 Windows。
> 因此我打算借助 AI 的能力，用 Python 重新实现一个跨平台的、
> 尽可能忠于 TortoiseGit 体验的 Git 客户端——也就是本项目。

它以 TortoiseGit 为蓝本，保留其对话框布局、命令行协议与操作习惯，
同时利用 Python / PySide6 的跨平台能力，让同一套工具也能跑在
macOS 与 Linux 上。

> **当前状态：迁移中**
>
> 本项目正处于从 TortoiseGit 到 Python 的迁移阶段，很多功能还在逐步
> 复刻与完善中。欢迎喜欢 TortoiseGit 的用户一起加入，和我共同完成
> 这个跨平台的 TortoiseGit 复刻项目。你可以通过提交代码、提出问题、
> 或是反馈使用体验来贡献力量。

## 许可 / License

PyTortoiseGit 基于（并镜像）开源项目 **TortoiseGit**，以 **GNU General
Public License v2 (GPLv2)** 发布。完整许可文本见 [LICENSE](LICENSE)。
图标资源来自 TortoiseSVN，受其图标许可约束，见 [NOTICE](NOTICE) 与
`LICENSE` 中的说明。

- 上游 TortoiseGit：<https://tortoisegit.org>（GPLv2）
- 图标来源 TortoiseSVN：<https://tortoisesvn.net>

本项目与 TortoiseGit / TortoiseSVN 项目无隶属关系，亦非后者官方成果。

## 运行

```bash
# 安装依赖（推荐，版本已固定）
pip install -r requirements-dev.txt

# 或：以可编辑模式安装本项目（含 dev 依赖）
pip install -e .[dev]

# 打开「关于」对话框
python pytortoisegit/app.py /command:about

# 提交对话框（TortoiseGit 兼容命令行）
python pytortoisegit/app.py /command:commit /path:D:\repo

# 打开仓库日志（分支图 + diff 预览 + 搜索 + 右键操作）
python pytortoisegit/app.py /command:log /path:D:\repo

# 克隆仓库
python pytortoisegit/app.py /command:clone

# 查看完整命令列表
python pytortoisegit/app.py /help
```

可用命令：`about` `clone` `commit` `log` `diff` `blame` `browse` `reflog`
`branch` `tag` `settings` `sync` `pull` `push` `fetch` `shell`
`check_modifications`(别名 `changed`)

## 右键菜单集成（Windows）

```bash
python pytortoisegit/app.py /command:shell
```

安装后，在文件 / 文件夹 / 文件夹空白处的右键菜单出现 PyTortoiseGit 各项，
通过 `pythonw.exe` 启动（不弹控制台窗口）。仅写 HKCU 注册表，无需管理员权限；
重新打开资源管理器生效。卸载在同一个对话框完成。

## 打包分发

```bash
pip install pyinstaller
python packaging/build.py --clean
```

产物在 `dist/PyTortoiseGit/PyTortoiseGit.exe`（onedir 模式，含 PySide6
运行时）。分发时把整个 `dist/PyTortoiseGit/` 目录拷贝即可；若拷贝到其他路径，
需重新运行一次右键菜单安装对话框以更新入口路径。

## 目录与 TortoiseGit 对应

| TortoiseGit C++ | 本仓库 |
|---|---|
| TortoiseProc.exe | `pytortoisegit/app.py` |
| Utils/CmdLineParser | `pytortoisegit/cmdline.py` |
| Utils/TGitPath | `pytortoisegit/utils/paths.py` |
| ResText | `pytortoisegit/res/strings.py` |
| Git/Git.cpp | `pytortoisegit/git/git.py` |
| TortoiseProc/Commands | `pytortoisegit/commands/` |
| TortoiseProc/*Dlg | `pytortoisegit/dialogs/` |

## 测试

```bash
pytest
```