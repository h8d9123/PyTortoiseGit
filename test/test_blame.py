"""GitBlame 解析测试（基于临时仓库，多次提交修改同一文件不同行）。"""

import os
from pathlib import Path

import pytest

from pytortoisegit.blame import GitBlame
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