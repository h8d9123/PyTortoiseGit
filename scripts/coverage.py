"""coverage.py —— 运行测试并生成代码覆盖率报告。

用法：
    python scripts/coverage.py                 # 终端 + HTML 报告（默认）
    python scripts/coverage.py --junit         # 额外生成 build/test-report.xml
    python scripts/coverage.py --xml           # 额外生成 coverage.xml
    python scripts/coverage.py --fail-under 80 # 覆盖率低于 80% 时返回非 0
    python scripts/coverage.py --no-html       # 仅终端报告
    python scripts/coverage.py test/test_git.py -k stash   # 透传 pytest 参数

报告位置：
    HTML 覆盖率报告：build/coverage-html/index.html
    JUnit 测试报告： build/test-report.xml（--junit）
    Cobertura 报告：  coverage.xml（--xml）
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="运行测试并生成覆盖率报告")
    parser.add_argument("--xml", action="store_true", help="生成 coverage.xml")
    parser.add_argument("--junit", action="store_true",
                        help="生成 JUnit 测试报告 build/test-report.xml")
    parser.add_argument("--no-html", action="store_true", help="不生成 HTML 报告")
    parser.add_argument("--fail-under", type=float, default=None,
                        help="覆盖率低于该百分比时以非 0 退出")
    parser.add_argument("--source", default="pytortoisegit",
                        help="统计覆盖率的包/目录（默认 pytortoisegit）")
    args, pytest_args = parser.parse_known_args(argv)

    try:
        import pytest_cov  # noqa: F401
    except ImportError:
        print("缺少 pytest-cov，请先安装开发依赖：\n"
              "    pip install pytest-cov\n"
              "或：pip install -e .[dev]", file=sys.stderr)
        return 2

    cmd = [sys.executable, "-m", "pytest",
           f"--cov={args.source}",
           "--cov-report=term-missing"]
    if not args.no_html:
        cmd.append("--cov-report=html:build/coverage-html")
    if args.xml:
        cmd.append("--cov-report=xml:coverage.xml")
    if args.fail_under is not None:
        cmd.append(f"--cov-fail-under={args.fail_under}")
    if args.junit:
        cmd.append("--junitxml=build/test-report.xml")
    cmd += pytest_args

    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    print("运行：", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT), env=env)
    if not args.no_html:
        print(f"\nHTML 覆盖率报告：{ROOT / 'build' / 'coverage-html' / 'index.html'}")
    if args.junit:
        print(f"JUnit 测试报告：{ROOT / 'build' / 'test-report.xml'}")
    if args.xml:
        print(f"Cobertura 报告：{ROOT / 'coverage.xml'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
