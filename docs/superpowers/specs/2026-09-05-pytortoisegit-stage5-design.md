# PyTortoiseGit 进阶功能设计（Stage 5）

日期：2026-09-05
状态：已确认
关联：docs/superpowers/specs/2026-09-05-pytortoisegit-design.md（总设计，第 5 阶段）

## 目标

补齐设计文档第 5 阶段与落地缺口，共五个功能块：
Stash 管理、Merge/Rebase 与冲突解决、Submodule 管理、外部 diff/merge 工具、Error/UX 打磨。

全部沿用现有架构约定：
- 对话框 → git 层 helper（`GitRunner`/`Repository`）→ `asyncfw` 后台线程 / `ProgressDialog` → UI
- 文案进 `res/strings.py`，经 `tr()` / `format_string()` 取用
- 新命令按 TortoiseGit 命令名注册进 `commands/dispatcher.py` 的 `_ensure_imports()`
- 每块配 pytest 单测

## 1. Stash 管理

- `git/stash.py`：`GitStash(repo)`，数据类 `StashEntry(gd, subject, date, hash)`。
  - `list()` 解析 `git stash list --format=%gd\x00%s\x00%ci\x00%H`（NUL 分隔）
  - `create(message="", include_untracked=False)` → `git stash push -m …`；`apply(gd)`、`pop(gd)`、`drop(gd)`、`clear()`
  - `show(gd)` → `git stash show -p`（DiffView 预览）
- `dialogs/stashdlg.py` `StashDlg`：QTreeWidget（引用/说明/日期）+ DiffView；按钮 创建/应用/弹出/丢弃/清空；后台线程加载列表（`asyncfw`）。
- `commands/stash.py`：`@register("stash")`。
- 测试：`stash list` 解析（跨 `-z` 风格）。

## 2. Merge/Rebase 与冲突解决

- `git/mergeop.py`：
  - `local_branches(repo)` → `git for-each-ref refs/heads --format=%(refname:short)`
  - `build_merge_args(branch, no_ff, squash, no_commit)`、`build_rebase_args(branch, interactive, autostash)`
  - 冲突存在判断：复用 `git/status.py::GitStatus.is_conflicted` 与 `git/index.py::index_has_conflicts`
  - `abort()` → `git merge --abort` / `git rebase --abort`；`continue_rebase()`
- `dialogs/mergedlg.py` `MergeDlg`：分支下拉 + 三个选项 + 提交信息输入；执行走 `ProgressDialog`；结果含冲突时切换到冲突列表视图。
- `dialogs/rebasedlg.py` `RebaseDlg`：目标分支 + interactive/autostash 选项；`--continue/--abort` 按钮。
- 冲突解决视图（供 Merge/Rebase 结果用）：列出 `GitStatus` 冲突文件；行内动作 标记解决(`git add`)/采用`--ours`/采用`--theirs`/外部合并工具/abort；全部解决后刷新。
- `commands/merge.py`、`commands/rebase.py`：`@register("merge")`、`@register("rebase")`。
- 测试：参数构造单测；冲突文件识别复用现有 status 测试。

## 3. Submodule 管理

- `git/submodule.py`：数据类 `SubmoduleEntry(path, status_char, sha1, description)`；`list()` 解析 `git submodule status --recursive`（前缀 `-`未初始化 / `+` sha 不匹配 / `u`merge 冲突 / 空格正常）与 `.gitmodules` 描述；`add(path, url)`、`update(init, recursive)`、`deinit(path, force)`、`sync()`。
- `dialogs/submoduledlg.py` `SubmoduleDlg`：QTreeWidget（路径/sha1/状态/描述）+ 按钮 添加/更新(含 --init --recursive)/同步/取消初始化；双击行跳转 `LogDlg(submodule_path)`。
- `commands/submodule.py`：`@register("submodule")`、`@register("subupdate")=update`、`@register("subadd")=add`。
- 测试：`git submodule status` 输出解析用例。

## 4. 外部 diff/merge 工具

- `utils/externaltools.py`：
  - 配置键：`externaltools/diffcmd`、`externaltools/mergetoolcmd`（QSettings，organization `PyTortoiseGit`）
  - `get_diff_cmd()` 优先 QSettings，回退 `git config diff.tool`；`launch_diff_files(left, right)`、`launch_merge(base, ours, theirs, out)` 用 `subprocess.Popen`
  - 命令模板展开 `launch_diff_cmd_template(cmd, left, right)`（支持 `{left}`/`{right}`/`{base}`/`{ours}`/`{theirs}`/`{out}`），纯函数可单测
- `dialogs/settingsdlg.py` 增两行：外部 diff / 外部 merge 命令模板，保存到 QSettings。
- 集成点：
  - `diffdlg.py` / `commitdlg.py` / `changedlg.py` / `blamedlg.py` 增「外部工具打开」按钮
  - 冲突解决视图加「外部合并工具」
  - 无路径（如纯 diff 对话框）时从工作树/HEAD 取内容写临时文件（`%TEMP%`）
- 测试：模板展开、命令示例解析。

## 5. Error / UX 打磨

- `utils/logging_utils.py`：logging 初始化（`DEBUG` 写 `~/.pytortoisegit/log`），供调试与错误上报。
- 错误呈现：GUI 命令失败弹 `QMessageBox.critical`（`cli.py` 检测有无 qapp/dialog 上下文）；后台任务异常走已有 `on_error` → 对话框内文本。
- 字符串补全：本批次全部新对话框文案注册进 `res/strings.py`。
- 快捷键与次要体验：新对话框装载 Esc 取消、Enter 默认按钮等 Qt 默认行为核对。

## 实施顺序与验证

1. git 层 helper（stash → mergeop → submodule）+ 各自单测
2. 对话框（stashdlg → mergedlg/rebasedlg → submoduledlg）+ 命令注册
3. 外部工具（externaltools + settingsdlg + 各对话框按钮）+ 单测
4. Error/UX 打磨
5. 全量 `pytest test/` 回归 + `demo.py` / 命令冒烟

## 不在本期范围

- rebase 交互式编辑器、历史改写（reword/fixup）
- submodule 的嵌套递归 UI 展示
- 外部工具自动发现（只用手工配置模板）