# Daily utilities

A small FastAPI app with browser-based dev tools. Tools open as tabs inside one page, and Back/Forward move between them.

## Tools

- **CORS checker**: checks whether APIs accept cross-origin requests from your sites. The server sends the preflight and the actual request, so it works where browser-side testing is blocked. Check many URLs against many origins at once.
- **URL encoder**: percent-encode or decode text and URLs.
- **Code formatter**: format JSON, JavaScript and TypeScript (Prettier, bundled locally so it works offline), and minify JSON.
- **S3 finder**: find files and folders in an S3 bucket by exact name, wildcard or regex. Needs its plugin; without it the tab says you don't have access.

## Run

```bat
python -m venv venv
run.bat
```

Then open http://localhost:5555.

## Corporate SSL inspection

If HTTPS requests fail with `CERTIFICATE_VERIFY_FAILED`, point the app at your company's root CA:

- set `CORP_CA_BUNDLE` (or `NODE_EXTRA_CA_CERTS`) to the `.pem` file, or
- put the `.pem` file in `~/.certs/`.

`ca_bundle.py` merges it with certifi's public roots and sets `REQUESTS_CA_BUNDLE`.

## Adding a tool

Drop an `.html` file into `tools/` with a `<title>` and a `<meta name="description">`. It shows up in the tool list automatically. Use `/static/theme.css` for the shared styles.

## Plugins

Some tools need backend code that isn't in this repo. At startup the app loads every `*.py` file in `WORKBENCH_PLUGINS_DIR` (default `../local/plugins`) that defines `NAME` and a FastAPI `APIRouter` called `router`, and mounts it at `/plugins/<NAME>`. A missing folder or a plugin that fails to load is skipped, and `GET /plugins/status` lists what loaded. Plugin tools show a no-access message when their plugin isn't there.

Mark a plugin tool with `<meta name="workbench-export" content="skip">` to leave it out of the static site.

## Static site (GitHub Pages)

```bat
venv\Scripts\python export_static.py
```

This writes a static copy to `dist/`. Plugin tools are left out. The URL encoder and code formatter work fully. The CORS checker needs the Python server, so in the static copy it shows how to run the app locally instead.

`.github/workflows/pages.yml` rebuilds and deploys `dist/` on every push to `main`. To turn it on, go to the repo's **Settings → Pages** and set **Source** to **GitHub Actions**.
