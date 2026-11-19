"""Export the app as a static site (for GitHub Pages or any static host).

    python export_static.py            # writes ./dist
    python export_static.py out_dir

Every tool page is copied as-is. Tools that call the Python server (the CORS
checker) detect the static build and explain that checks need the local server.
"""
import json
import os
import shutil
import sys

from app import TOOLS_DIR, _tool_meta

STATIC_MARK = '<meta name="workbench-mode" content="static" />'
SERVER_CALL = 'fetch("../'  # tools that post to the FastAPI backend


def _mark_static(html):
    return html.replace("<head>", "<head>\n  " + STATIC_MARK, 1)


def _copy_page(src, dest):
    with open(src, encoding="utf-8") as f:
        html = f.read()
    with open(dest, "w", encoding="utf-8", newline="") as f:
        f.write(_mark_static(html))
    return html


def export(out="dist"):
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "tools"))
    os.makedirs(os.path.join(out, "api"))

    _copy_page("templates/index.html", os.path.join(out, "index.html"))
    shutil.copytree("static", os.path.join(out, "static"))

    tools = []
    for name in sorted(f for f in os.listdir(TOOLS_DIR) if f.endswith(".html")):
        html = _copy_page(os.path.join(TOOLS_DIR, name), os.path.join(out, "tools", name))
        meta = _tool_meta(name)
        if SERVER_CALL in html:
            meta["description"] += " Needs the local server to run checks."
        tools.append(meta)

    with open(os.path.join(out, "api", "tools.json"), "w", encoding="utf-8") as f:
        json.dump(tools, f, indent=2)

    # GitHub Pages: serve files as-is, skip Jekyll processing
    open(os.path.join(out, ".nojekyll"), "w").close()
    print(f"Exported {len(tools)} tools to {os.path.abspath(out)}")


if __name__ == "__main__":
    export(sys.argv[1] if len(sys.argv) > 1 else "dist")
