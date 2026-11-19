"""Make Python trust the corporate CA (SSL inspection proxy).

Builds a bundle = certifi public roots + corporate CA, and points requests/boto3
at it via REQUESTS_CA_BUNDLE / AWS_CA_BUNDLE. Import this before making HTTPS calls.

Corporate CA is taken from CORP_CA_BUNDLE, else NODE_EXTRA_CA_CERTS,
else the first *.pem file in ~/.certs/.
"""
import os
import tempfile
from pathlib import Path

import certifi


def _corp_ca():
    for candidate in (os.environ.get("CORP_CA_BUNDLE"), os.environ.get("NODE_EXTRA_CA_CERTS")):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    certs_dir = Path.home() / ".certs"
    pems = sorted(certs_dir.glob("*.pem")) if certs_dir.is_dir() else []
    return pems[0] if pems else None


def setup():
    # Respect an explicitly configured bundle
    if os.environ.get("REQUESTS_CA_BUNDLE"):
        return os.environ["REQUESTS_CA_BUNDLE"]
    corp = _corp_ca()
    if not corp:
        return certifi.where()
    combined = Path(tempfile.gettempdir()) / "tools-ca-bundle.pem"
    combined.write_text(
        Path(certifi.where()).read_text(encoding="utf-8") + "\n"
        + corp.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    os.environ["REQUESTS_CA_BUNDLE"] = str(combined)
    os.environ.setdefault("AWS_CA_BUNDLE", str(combined))
    return str(combined)


CA_BUNDLE = setup()
