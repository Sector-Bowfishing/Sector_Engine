"""Fixture transport for dry runs and tests: answers each request from a directory instead of the network.

`index.json` maps a URL prefix to a file in the same directory: {"<url prefix>": {"file": "tva-GVDA1-observed.json", "status": 200}}. The
longest matching prefix wins; an unmatched URL is a connection error (never an invented answer)."""
from __future__ import annotations

import json
import os

from .http import Response, TransportError


def fixture_transport(directory: str):
    with open(os.path.join(directory, "index.json"), encoding="utf-8") as fh:
        index = json.load(fh)["responses"]

    def transport(url: str, headers: dict, timeout: float) -> Response:
        hits = [p for p in index if url.startswith(p)]
        if not hits:
            raise TransportError("connection", f"no fixture for {url}")
        e = index[max(hits, key=len)]
        if e.get("requiresAccept") and e["requiresAccept"] not in (headers.get("Accept") or ""):
            with open(os.path.join(directory, e["fallbackFile"]), "rb") as fh:
                return Response(200, fh.read())
        with open(os.path.join(directory, e["file"]), "rb") as fh:
            return Response(int(e.get("status", 200)), fh.read())
    return transport
