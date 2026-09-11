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

> **当前状态：主要代码完成移植，正在修复 bug**
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
#运行
python pytortoisegit/app.py
```
## 打包分发

```bash
pip install pyinstaller
python packaging/build.py --clean
```

产物在 `dist/PyTortoiseGit/PyTortoiseGit.exe`（onedir 模式，含 PySide6
运行时）。分发时把整个 `dist/PyTortoiseGit/` 目录拷贝即可；若拷贝到其他路径，
需重新运行一次右键菜单安装对话框以更新入口路径。

## 测试

功能测试点（手动 / UI 自动化）见 [docs/功能测试点.md](docs/功能测试点.md)。

```bash
pytest
```