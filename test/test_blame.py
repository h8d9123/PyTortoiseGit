"""GitBlame 解析测试（基于临时仓库，多次提交修改同一文件不同行）。"""

import os
from pathlib import Path

import pytest

from pytortoisegit.blame import (
    DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE,
    GitBlame,
    detect_moved_arguments,
    is_limited_to_one_filename,
)
from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository


@pytest.fixture()
def blame_repo(tmp_path):
    seed = "line one\nline two\nline three\nline four\nline five\n"
    (tmp_path / "doc.txt").write_text(seed, encoding="utf-8")
    runner = GitRunner(cwd=str(tmp_path))
    runner.run("init", check=True)
    runner.run("config", "user.email", "a@b", check=True)
    runner.run("config", "user.name", "Alice", check=True)
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "initial", check=True)
    # 修改第三行为新内容 —— 第三次提交
    content = seed.replace("line three", "changed line")
    (tmp_path / "doc.txt").write_text(content, encoding="utf-8")
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "modify three", check=True)
    return Repository.open(str(tmp_path))


def test_blame_line_count(blame_repo):
    lines = GitBlame(blame_repo).blame("doc.txt")
    assert len(lines) == 5


def test_blame_content_and_original_lines(blame_repo):
    lines = GitBlame(blame_repo).blame("doc.txt")
    third = lines[2]
    assert third.content == "changed line"
    assert third.author == "Alice"
    assert third.original_line == 3
    assert third.final_line == 3
    assert "modify three" in third.summary


def test_blame_untouched_lines_initial_commit(blame_repo):
    lines = GitBlame(blame_repo).blame("doc.txt")
    first = lines[0]
    assert first.content == "line one"
    assert "initial" in first.summary


def test_blame_short_sha(blame_repo):
    lines = GitBlame(blame_repo).blame("doc.txt")
    assert len(lines[0].short_sha) == 8


def test_blame_file_range(blame_repo):
    lines = GitBlame(blame_repo).blame("doc.txt", start_line=1, end_line=2)
    assert all(1 <= ln.final_line <= 2 for ln in lines)


def test_blame_repeated_commit_keeps_metadata(blame_repo):
    """同一提交的行非连续出现时，元数据必须复用（回归：曾丢失 author）。"""
    lines = GitBlame(blame_repo).blame("doc.txt")
    assert all(ln.author == "Alice" for ln in lines)
    assert all(ln.content for ln in lines)
    # 第 4、5 行仍来自初始提交，summary 不能为空
    assert "initial" in lines[3].summary
    assert "initial" in lines[4].summary


def test_blame_filename_and_previous(blame_repo):
    data = GitBlame(blame_repo).load("doc.txt")
    assert all(ln.filename == "doc.txt" for ln in data.lines)
    changed = data.lines[2]
    assert changed.previous_sha
    assert changed.previous_filename == "doc.txt"
    assert data.find_first_line(changed.sha, 0) == 2
    assert data.find_first_line_in_block(changed.sha, 2) == 2


def test_detect_moved_arguments_mapping():
    assert detect_moved_arguments(0) == []
    assert detect_moved_arguments(1, 20, 40) == ["-M20"]
    assert detect_moved_arguments(2, 20, 40) == ["-C40"]
    assert detect_moved_arguments(3, 20, 40) == ["-C", "-C40"]
    assert detect_moved_arguments(4, 20, 40) == ["-C", "-C", "-C40"]
    assert is_limited_to_one_filename(0)
    assert is_limited_to_one_filename(1)
    assert not is_limited_to_one_filename(2)


@pytest.fixture()
def moved_repo(tmp_path):
    order_a = ("alpha alpha alpha alpha alpha\n"
               "bravo bravo bravo bravo bravo\n"
               "charlie charlie charlie charlie\n"
               "delta delta delta delta delta")
    order_b = ("charlie charlie charlie charlie\n"
               "bravo bravo bravo bravo bravo\n"
               "alpha alpha alpha alpha alpha\n"
               "delta delta delta delta delta")
    (tmp_path / "m.txt").write_text(order_a, encoding="ascii")
    runner = GitRunner(cwd=str(tmp_path))
    runner.run("init", check=True)
    runner.run("config", "user.email", "a@b", check=True)
    runner.run("config", "user.name", "Alice", check=True)
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "A", check=True)
    (tmp_path / "m.txt").write_text(order_b, encoding="ascii")
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "B", check=True)
    return Repository.open(str(tmp_path))


def test_blame_detect_moved_lines(moved_repo):
    plain = GitBlame(moved_repo).blame("m.txt")
    detected = GitBlame(moved_repo).blame(
        "m.txt", detect=DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE)
    assert len(plain) == len(detected) == 4
    # 关闭检测时并非所有行都归属初始提交；开启 -M 后全部归属初始提交
    assert len({ln.sha for ln in plain}) > 1
    assert len({ln.sha for ln in detected}) == 1


def test_blame_ignore_whitespace(tmp_path):
    (tmp_path / "w.txt").write_text("keep this line\n", encoding="utf-8")
    runner = GitRunner(cwd=str(tmp_path))
    runner.run("init", check=True)
    runner.run("config", "user.email", "a@b", check=True)
    runner.run("config", "user.name", "Alice", check=True)
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "A", check=True)
    (tmp_path / "w.txt").write_text("  keep this line  \n", encoding="utf-8")
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "B", check=True)
    repo = Repository.open(str(tmp_path))
    plain = GitBlame(repo).blame("w.txt")
    ignored = GitBlame(repo).blame("w.txt", ignore_whitespace=True)
    assert "B" in plain[0].summary
    assert "A" in ignored[0].summary


def test_blame_utf8_bom_stripped(tmp_path):
    (tmp_path / "b.txt").write_bytes(b"\xef\xbb\xbfhello world\n")
    runner = GitRunner(cwd=str(tmp_path))
    runner.run("init", check=True)
    runner.run("config", "user.email", "a@b", check=True)
    runner.run("config", "user.name", "Alice", check=True)
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "A", check=True)
    repo = Repository.open(str(tmp_path))
    data = GitBlame(repo).load("b.txt")
    assert data.encoding == "utf-8-sig"
    assert data.lines[0].content == "hello world"


def test_blame_encoding_override(tmp_path):
    (tmp_path / "e.txt").write_bytes(b"caf\xe9\n")
    runner = GitRunner(cwd=str(tmp_path))
    runner.run("init", check=True)
    runner.run("config", "user.email", "a@b", check=True)
    runner.run("config", "user.name", "Alice", check=True)
    runner.run("add", ".", check=True)
    runner.run("commit", "-m", "A", check=True)
    repo = Repository.open(str(tmp_path))
    data = GitBlame(repo).load("e.txt", encoding="latin-1")
    assert data.lines[0].content == "café"


def test_blame_absolute_path(blame_repo):
    lines = GitBlame(blame_repo).blame(
        os.path.join(blame_repo.root, "doc.txt"))
    assert len(lines) == 5