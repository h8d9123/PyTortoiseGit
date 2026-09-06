"""逐 hunk 暂存/取消暂存 测试（index.blob 手术）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.index import GitIndex
from pytortoisegit.git.repo import Repository
from pytortoisegit.udiff import split_patch_hunks, visible_hunk_ranges


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("hunkrepo")
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    runner.run("config", "user.email", "t@t")
    runner.run("config", "user.name", "T")
    runner.run("config", "core.autocrlf", "false")
    lines = [f"line{i}" for i in range(50)]
    (root / "f.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    runner.add(["f.txt"])
    assert runner.run("commit", "-m", "init").returncode == 0
    # 两处相距很远 → 两个独立 @@ hunk
    modified = list(lines)
    modified[2] = "line2-CHANGED"
    modified[40] = "line40-CHANGED"
    (root / "f.txt").write_text("\n".join(modified) + "\n", encoding="utf-8", newline="\n")
    return Repository.open(str(root))


def test_split_patch_hunks(repo):
    index = GitIndex(repo)
    patches = index.hunk_patches("f.txt", staged=False)
    assert len(patches) == 2
    assert all(p.startswith("diff --git ") for p in patches)
    assert all("@@ " in p for p in patches)
    assert "line2" in patches[0]
    assert "line40" in patches[1]


def test_stage_single_hunk(repo):
    index = GitIndex(repo)
    patches = index.hunk_patches("f.txt", staged=False)
    assert index.stage_hunk("f.txt", patches[0]) is True
    staged = index.diff(["f.txt"], staged=True)
    unstaged = index.diff(["f.txt"], staged=False)
    assert "line2" in staged and "line40" not in staged
    assert "line40" in unstaged and "line2" not in unstaged
    # 复原
    index.reset(["f.txt"])


def test_unstage_single_hunk(repo):
    index = GitIndex(repo)
    index.add(["f.txt"])  # 全量暂存
    patches = index.hunk_patches("f.txt", staged=True)
    assert len(patches) == 2
    assert index.unstage_hunk("f.txt", patches[0]) is True
    staged = index.diff(["f.txt"], staged=True)
    unstaged = index.diff(["f.txt"], staged=False)
    assert "line40" in staged and "line2" not in staged
    assert "line2" in unstaged and "line40" not in unstaged
    index.reset(["f.txt"])


def test_split_patch_hunks_multifile(repo):
    from pathlib import Path
    root = Path(repo.root)
    (root / "g.txt").write_text("x\n", encoding="utf-8", newline="\n")
    runner = repo.runner
    runner.run("add", "g.txt")
    runner.run("commit", "-m", "g")
    (root / "g.txt").write_text("y\n", encoding="utf-8", newline="\n")
    out = runner.run("diff", "-U0", "--no-color").stdout
    # f.txt 两 hunk + g.txt 一 hunk = 3
    assert len(split_patch_hunks(out)) == 3


def test_stage_hunk_crlf_file(tmp_path):
    root = tmp_path
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    runner.run("config", "user.email", "t@t")
    runner.run("config", "user.name", "T")
    runner.run("config", "core.autocrlf", "false")
    lines = [f"l{i}" for i in range(12)]
    (root / "crlf.txt").write_text("\r\n".join(lines) + "\r\n",
                                  encoding="utf-8", newline="")
    runner.add(["crlf.txt"])
    runner.run("commit", "-m", "init")
    m = list(lines)
    m[1] = "l1-X"
    m[9] = "l9-X"
    (root / "crlf.txt").write_text("\r\n".join(m) + "\r\n",
                                   encoding="utf-8", newline="")
    repo = Repository.open(str(root))
    index = GitIndex(repo)
    patches = index.hunk_patches("crlf.txt", staged=False)
    assert len(patches) == 2
    assert index.stage_hunk("crlf.txt", patches[0]) is True
    staged = index.diff(["crlf.txt"], staged=True)
    unstaged = index.diff(["crlf.txt"], staged=False)
    assert "l1-X" in staged and "l9-X" not in staged
    assert "l9-X" in unstaged and "l1-X" not in unstaged


def test_visible_hunk_ranges():
    text = "header\ndiff --git a\n@@ -1 +1 @@\n-a\n+b\n@@ -5,2 +5,2 @@\n-c\n+d\n"
    ranges = visible_hunk_ranges(text)
    assert len(ranges) == 2
    lines = text.splitlines()
    s1, e1 = ranges[0]
    s2, e2 = ranges[1]
    assert lines[s1].startswith("@@")
    assert lines[s2].startswith("@@")
    assert s1 < e1 < s2 < e2
    assert lines[e1] == "-a" or lines[e1] == "+b"