"""cmdline 解析测试。"""

from pytortoisegit.cmdline import parse


def test_parse_ows_with_quotes():
    cl = parse('/command:commit /path:"D:\\my repo" /msg:"add new feature"')
    assert cl.verb == "commit"
    assert cl.value("path") == "D:\\my repo"
    assert cl.value("msg") == "add new feature"


def test_parse_switch_only():
    cl = parse(["/command:log", "/postcmd"])
    assert cl.verb == "log"
    assert cl.has("postcmd")
    assert cl.value("postcmd") == ""


def test_parse_repeated_option():
    cl = parse(["/command:log", "/path:a", "/path:b"])
    assert cl.verb == "log"
    assert cl.all_values("path") == ["b", "a"]


def test_parse_dash_prefix():
    cl = parse(["app.py", "-command:about"])
    assert cl.verb == "about"


def test_parse_empty():
    cl = parse([])
    assert cl.verb == ""


def test_parse_positional_only():
    cl = parse(["about"])
    assert cl.verb == "about"


def test_parse_multiple_update():
    cl = parse("/command:commit /path:X /path:Y")
    assert cl.all_values("path") == ["Y", "X"]


def test_parse_option_with_dash():
    cl = parse("/command:commit /msg:\"fix bug - see details\"")
    assert cl.value("msg") == "fix bug - see details"


def test_parse_keys_without_values():
    cl = parse("/closeonend")
    assert cl.has("closeonend")


def test_parse_option_newline_safe():
    cl = parse('/command:createbranch /branch:"feature/x"')
    assert cl.value("branch") == "feature/x"