"""日志文件列表解析、提交说明与 name-status 分离。"""

from pytortoisegit.dialogs.loglists import (
    ChangedFile, filediff_action_color, parse_show_files, status_color,
    status_text,
)
from pytortoisegit.git.rev import _parse_record, _split_message_and_actions


def test_parse_show_files_status_and_numstat():
    text = """M\tsrc/app.py
A\tnew.txt
R100\told.py\tnew.py
3\t1\tsrc/app.py
10\t0\tnew.txt
4\t4\tnew.py
"""
    rows = parse_show_files(text)
    by = {r.path: r for r in rows}
    assert by["src/app.py"].status.startswith("M")
    assert by["src/app.py"].added == "3"
    assert by["src/app.py"].deleted == "1"
    assert by["src/app.py"].ext == ".py"
    assert by["new.txt"].status.startswith("A")
    assert by["new.py"].status.startswith("R")
    assert by["new.py"].old_path == "old.py"


def test_display_name_rename():
    row = ChangedFile("new.py", "R100", old_path="old.py")
    assert "new.py" in row.display_name()
    assert "old.py" in row.display_name()
    assert row.filename == "new.py"
    assert status_color("M") == (0, 50, 160)
    assert status_color("A") == (100, 0, 100)
    assert filediff_action_color("A") == (100, 0, 100)
    assert filediff_action_color("D") == (100, 0, 0)
    assert filediff_action_color("R") == (0, 50, 160)


def test_status_text():
    assert "修改" in status_text("M")
    assert "添加" in status_text("A")


def test_split_message_and_actions():
    msg, acts = _split_message_and_actions("subject\n\nbody\n\nM\tfoo\nA\tbar")
    assert msg.startswith("subject")
    assert "body" in msg
    assert acts == "MA"


def test_parse_record_strips_name_status():
    rec = (
        "abc123def456abc123def456abc123def456abc1\x1e"
        "parent\x1eAlice\x1ea@b\x1e1 day ago\x1eAlice\x1ea@b\x1e"
        "1700000000\x1e2023-11-15\x1e"
        "hello world\n\nM\tfile.txt"
    )
    rev = _parse_record(rec)
    assert rev.subject == "hello world"
    assert "file.txt" not in rev.message
    assert "M" in rev.actions
