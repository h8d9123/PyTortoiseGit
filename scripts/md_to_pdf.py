"""md_to_pdf.py —— 把 Markdown 文档转换为 PDF（内置图片、A4 分页）。

用法：
    python scripts/md_to_pdf.py                          # 默认取仓库根目录的速览文档
    python scripts/md_to_pdf.py 文档.md                   # 指定输入
    python scripts/md_to_pdf.py 文档.md -o build/out.pdf  # 指定输出
    python scripts/md_to_pdf.py 文档.md --keep-html       # 保留中间 HTML
    python scripts/md_to_pdf.py 文档.md --browser <路径>  # 指定 Chrome/Edge

依赖：Python 包 `markdown`，以及本机的 Chrome / Edge（无头模式打印 PDF）。
Markdown 中形如 ![](screenshots/x.png) 的相对图片会被 base64 内嵌进 HTML，
因此中间 HTML 与源文件位置无关，也不会因缺文件而显示成裂图。
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)

CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "Segoe UI", "Noto Sans CJK SC", sans-serif;
       font-size: 11pt; line-height: 1.55; color: #1a1a1a; margin: 0; }
h1 { font-size: 22pt; border-bottom: 2px solid #2b579a; padding-bottom: 6px;
     color: #1f3864; }
h2 { font-size: 15pt; color: #1f3864; border-bottom: 1px solid #c9d3e4;
     padding-bottom: 3px; margin-top: 18px; break-after: avoid; }
h3 { font-size: 12.5pt; color: #2b579a; margin-top: 12px; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
blockquote { margin: 8px 0; padding: 6px 12px; background: #f4f6fa;
             border-left: 3px solid #9db2d6; color: #444; font-size: 10pt; }
img { max-width: 100%; height: auto; border: 1px solid #d0d0d0;
      border-radius: 2px; background: #fff; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; break-inside: avoid; }
th, td { border: 1px solid #d0d0d0; padding: 4px; text-align: center;
         vertical-align: middle; }
th { background: #eef2f9; }
table img { max-width: 100%; }
h1, h2, h3, figure, tr { break-inside: avoid; }
a { color: #2b579a; text-decoration: none; }
"""

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}


def find_browser(explicit: str | None) -> str | None:
    if explicit:
        return explicit if Path(explicit).exists() else None
    for path in BROWSER_CANDIDATES:
        if path and Path(path).exists():
            return path
    return None


def embed_images(html: str, base_dir: Path) -> str:
    """把 <img src="相对路径"> 替换为 base64 data URI。"""
    def repl(m: re.Match) -> str:
        attr, src = m.group(1), m.group(2)
        if src.startswith(("data:", "http://", "https://", "file:")):
            return m.group(0)
        path = (base_dir / src.replace("/", os.sep)).resolve()
        if not path.exists():
            print(f"警告：图片不存在 {src}", file=sys.stderr)
            return m.group(0)
        mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'{attr}src="data:{mime};base64,{data}"'

    return re.sub(r'(<img[^>]*?)src="([^"]+)"', repl, html)


def build_html(src: Path) -> str:
    text = src.read_text(encoding="utf-8")
    body = markdown_to_html(text)
    body = embed_images(body, src.parent)
    body = re.sub(r'<div class="toc">.*?</div>\s*', "", body, flags=re.S)
    title = src.stem
    return (f'<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
            f"<title>{title}</title>\n<style>{CSS}</style></head>\n"
            f"<body>{body}</body></html>")


def markdown_to_html(text: str) -> str:
    try:
        import markdown
    except ImportError:
        print("缺少 markdown，请先安装：\n    pip install markdown",
              file=sys.stderr)
        raise SystemExit(2)
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "toc"],
        output_format="html5",
    )


def default_input() -> Path | None:
    for candidate in sorted(ROOT.glob("PyTortoiseGit*速览*.md")):
        return candidate
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="把 Markdown 转换为 PDF")
    parser.add_argument("input", nargs="?", type=Path,
                        help="输入的 Markdown 文件（默认取仓库根目录的速览文档）")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="输出 PDF 路径（默认与输入同名 .pdf）")
    parser.add_argument("--html", type=Path, default=None,
                        help="中间 HTML 输出路径（默认写入系统临时目录）")
    parser.add_argument("--keep-html", action="store_true",
                        help="保留中间 HTML 到输出 PDF 同目录")
    parser.add_argument("--browser", default=None,
                        help="Chrome/Edge 可执行文件路径")
    args = parser.parse_args(argv)

    src = args.input or default_input()
    if src is None:
        parser.error("未找到默认 Markdown，请显式指定输入文件")
    src = src.resolve()
    if not src.exists():
        parser.error(f"输入文件不存在：{src}")
    out = (args.output or src.with_suffix(".pdf")).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    browser = find_browser(args.browser)
    if browser is None:
        print("未找到 Chrome/Edge，请用 --browser 指定可执行文件。", file=sys.stderr)
        return 2

    html = build_html(src)
    if args.keep_html:
        html_path = out.with_suffix(".html")
    elif args.html is not None:
        html_path = args.html.resolve()
    else:
        tmp = Path(tempfile.mkdtemp(prefix="md_to_pdf_"))
        html_path = tmp / (src.stem + ".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML：{html_path}（{html_path.stat().st_size} 字节）")

    cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--no-pdf-header-footer", f"--print-to-pdf={out}",
           "file:///" + str(html_path).replace("\\", "/")]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout.decode("utf-8", "replace")[-2000:])
        sys.stderr.write(result.stderr.decode("utf-8", "replace")[-2000:])
        return result.returncode
    if not out.exists():
        print("浏览器未生成 PDF。", file=sys.stderr)
        return 1
    print(f"PDF：{out}（{out.stat().st_size} 字节）")
    if not (args.keep_html or args.html is not None):
        try:
            html_path.unlink()
            html_path.parent.rmdir()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
