import ca_bundle  # trust corporate CA for HTTPS
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from cors_checker import run_cors_check

app = FastAPI()

TOOLS_DIR = "tools"
templates = Jinja2Templates(directory="templates")


def _tool_meta(filename):
    """Read <title> and <meta name="description"> from a tool page."""
    with open(os.path.join(TOOLS_DIR, filename), encoding="utf-8") as f:
        head = f.read(4000)
    title = re.search(r"<title>(.*?)</title>", head, re.S)
    desc = re.search(r'<meta\s+name="description"\s+content="(.*?)"', head, re.S)
    return {
        "file": filename,
        "name": title.group(1).strip() if title else filename[:-5].replace("-", " ").title(),
        "description": desc.group(1).strip() if desc else "",
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/tools")
@app.get("/api/tools.json")
def get_tools():
    files = sorted(f for f in os.listdir(TOOLS_DIR) if f.endswith(".html"))
    return JSONResponse([_tool_meta(f) for f in files])


@app.post("/cors/check")
def cors_check(payload: dict):
    """Server-side CORS check: sends the preflight + actual request a browser would send."""
    return JSONResponse(run_cors_check(**payload))


@app.get("/tools/{filename}")
def serve_tool(filename: str):
    path = os.path.join(TOOLS_DIR, os.path.basename(filename))
    if not filename.endswith(".html") or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Tool not found")
    return FileResponse(path)


app.mount("/static", StaticFiles(directory="static"), name="static")
