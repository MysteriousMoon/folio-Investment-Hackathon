"""Generate a temporary browser test page; remove it after verification."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
scripts = [
    "vendor/marked/lib/marked.umd.js",
    "vendor/dompurify/dist/purify.min.js",
    "vendor/katex/dist/katex.min.js",
    "js/richtext.js",
]
html = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Renderer checks</title>
<link rel="stylesheet" href="/static/vendor/katex/dist/katex.min.css">
<link rel="stylesheet" href="/static/css/richtext.css">
<style>body{font:14px/1.8 sans-serif;color:#273950;background:#f8fafd;margin:30px}main{background:white;max-width:620px;padding:30px;margin:auto;border:1px solid #e1e8f2;border-radius:12px}pre#results{font-size:12px;color:#4564ad}</style>
<main><pre id="results">Running…</pre><div id="fixture"></div></main>"""
html += "".join('<script src="/static/' + p + '"></script>' for p in scripts)
html += (
    "<script>" + (root / "tests/richtext.browser.js").read_text() + "</script></html>"
)
out = root / "static/.richtext-check.html"
out.write_text(html)
print("Open http://127.0.0.1:5050/static/.richtext-check.html to run 12 checks.")
