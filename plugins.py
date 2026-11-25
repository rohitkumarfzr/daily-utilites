"""Optional plugins that add backend routes for tools.

Plugins live outside this repo. At startup the app looks in WORKBENCH_PLUGINS_DIR
(default: ../local/plugins next to this folder). Each *.py file there that defines

    NAME = "my-plugin"          # used in the URL: /plugins/my-plugin/...
    router = APIRouter()        # FastAPI routes

is mounted at /plugins/<NAME>. A missing folder, or a plugin that fails to
import, is logged and skipped; the app always starts. Tools ask
GET /plugins/status which plugins are available and show a "no access"
message when theirs is missing.
"""
import importlib.util
import logging
import os
from pathlib import Path

from fastapi import APIRouter

log = logging.getLogger("uvicorn.error")

HERE = Path(__file__).resolve().parent
DEFAULT_DIR = HERE.parent / "local" / "plugins"

loaded = {}  # name -> module


def plugins_dir():
    return Path(os.environ.get("WORKBENCH_PLUGINS_DIR") or DEFAULT_DIR)


def load_plugins(app):
    folder = plugins_dir()
    if not folder.is_dir():
        log.info("No plugins folder at %s; plugin tools will show as unavailable", folder)
        return loaded
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"workbench_plugin_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            name, router = getattr(module, "NAME", None), getattr(module, "router", None)
            if not name or not isinstance(router, APIRouter):
                log.warning("Skipped plugin %s: it needs NAME and an APIRouter called router", path.name)
                continue
            app.include_router(router, prefix=f"/plugins/{name}")
            loaded[name] = module
            log.info("Loaded plugin %s", name)
        except Exception as e:  # a broken plugin must never stop the app
            log.warning("Skipped plugin %s: %s", path.name, e)
    return loaded


def status():
    return {"plugins": sorted(loaded)}
