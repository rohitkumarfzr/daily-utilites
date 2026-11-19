"""Server-side CORS checker.

Replays what a browser does (preflight OPTIONS + actual request with an Origin
header) from the server, then evaluates the response headers with the same
rules the browser applies.
"""
import requests

SIMPLE_METHODS = {"GET", "HEAD", "POST"}
# Request headers a browser can send without triggering a preflight
SAFELISTED_HEADERS = {"accept", "accept-language", "content-language", "content-type"}
SIMPLE_CONTENT_TYPES = {"application/x-www-form-urlencoded", "multipart/form-data", "text/plain"}


def _split(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _cors_headers(resp):
    return {
        k: v for k, v in resp.headers.items()
        if k.lower().startswith("access-control-") or k.lower() in ("vary", "location")
    }


def _check_origin(headers, origin, credentials, problems):
    acao = headers.get("Access-Control-Allow-Origin")
    if acao is None:
        problems.append("Missing Access-Control-Allow-Origin header.")
        return False
    if acao == "*":
        if credentials:
            problems.append("Access-Control-Allow-Origin is '*' which is not allowed with credentials.")
            return False
    elif acao != origin:
        problems.append(f"Access-Control-Allow-Origin is '{acao}', does not match origin '{origin}'.")
        return False
    if credentials and headers.get("Access-Control-Allow-Credentials", "").lower() != "true":
        problems.append("Credentials requested but Access-Control-Allow-Credentials is not 'true'.")
        return False
    return True


def _needs_preflight(method, req_headers, content_type):
    if method not in SIMPLE_METHODS:
        return True
    if any(h.lower() not in SAFELISTED_HEADERS for h in req_headers):
        return True
    if content_type and content_type.split(";")[0].strip().lower() not in SIMPLE_CONTENT_TYPES:
        return True
    return False


def run_cors_check(url, origin, method="GET", request_headers="", content_type="",
                   credentials=False, verify_ssl=True, timeout=15, **_):
    method = (method or "GET").upper()
    req_headers = _split(request_headers)
    if content_type and "content-type" not in [h.lower() for h in req_headers]:
        req_headers.append("Content-Type")

    result = {
        "url": url, "origin": origin, "method": method,
        "preflight_required": _needs_preflight(method, req_headers, content_type),
        "preflight": None, "actual": None, "allowed": False, "problems": [],
    }
    problems = result["problems"]
    opts = {"timeout": timeout, "verify": verify_ssl, "allow_redirects": False}

    # ---- Preflight ----
    preflight_ok = True
    if result["preflight_required"]:
        pf_headers = {"Origin": origin, "Access-Control-Request-Method": method}
        if req_headers:
            pf_headers["Access-Control-Request-Headers"] = ",".join(h.lower() for h in req_headers)
        try:
            r = requests.options(url, headers=pf_headers, **opts)
            h = r.headers
            result["preflight"] = {"status": r.status_code, "sent": pf_headers, "headers": _cors_headers(r)}
            pf_problems = []
            if not 200 <= r.status_code < 300:
                pf_problems.append(f"Returned HTTP {r.status_code}. A preflight must get a 2xx response, and redirects are not followed.")
            _check_origin(h, origin, credentials, pf_problems)

            allowed_methods = [m.upper() for m in _split(h.get("Access-Control-Allow-Methods"))]
            if method not in SIMPLE_METHODS and method not in allowed_methods and \
                    not ("*" in allowed_methods and not credentials):
                pf_problems.append(f"Method {method} not in Access-Control-Allow-Methods {allowed_methods}.")

            allowed_headers = [x.lower() for x in _split(h.get("Access-Control-Allow-Headers"))]
            wildcard = "*" in allowed_headers and not credentials
            for hdr in req_headers:
                hl = hdr.lower()
                if hl in SAFELISTED_HEADERS and hl != "content-type":
                    continue
                if hl == "content-type" and not _needs_preflight("GET", [], content_type):
                    continue
                if hl == "authorization" and hl not in allowed_headers:
                    pf_problems.append("'Authorization' must be listed explicitly (wildcard does not cover it).")
                elif hl not in allowed_headers and not wildcard:
                    pf_problems.append(f"Header '{hdr}' not in Access-Control-Allow-Headers {allowed_headers}.")

            problems.extend(f"[preflight] {p}" for p in pf_problems)
            preflight_ok = not pf_problems
        except requests.RequestException as e:
            problems.append(f"[preflight] Request failed: {e}")
            preflight_ok = False

    # ---- Actual request ----
    actual_ok = False
    sent = {"Origin": origin}
    if content_type:
        sent["Content-Type"] = content_type
    try:
        r = requests.request(method, url, headers=sent, **opts)
        result["actual"] = {"status": r.status_code, "sent": sent, "headers": _cors_headers(r)}
        a_problems = []
        actual_ok = _check_origin(r.headers, origin, credentials, a_problems)
        problems.extend(f"[actual] {p}" for p in a_problems)
        if 300 <= r.status_code < 400:
            problems.append(f"[actual] Got redirect {r.status_code} -> {r.headers.get('Location')}; "
                            "check the final URL too.")
    except requests.RequestException as e:
        problems.append(f"[actual] Request failed: {e}")

    result["allowed"] = preflight_ok and actual_ok
    return result
