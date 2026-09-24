"""Record and replay LLM HTTP exchanges, keyed by a hash of the request body.

Recorded cassettes let tests and the CI smoke eval run the real prompts against real recorded
responses without an API key. In ``replay`` mode a request with no cassette raises
``CassetteMiss`` (it never falls through to the network).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import httpx2  # the openai SDK is built on httpx2 (same API as httpx)

from aegisops.domain.canonical import canonical_json, sha256_hex

CassetteMode = Literal["record", "replay"]


class CassetteMiss(RuntimeError):
    """Replay mode found no recording for this request."""


def request_key(body: bytes) -> str:
    try:
        return sha256_hex(canonical_json(json.loads(body)))
    except json.JSONDecodeError:
        return sha256_hex(body.decode("utf-8", errors="replace"))


class CassetteTransport(httpx2.BaseTransport):
    def __init__(
        self, directory: Path, mode: CassetteMode, inner: httpx2.BaseTransport | None = None
    ) -> None:
        self._directory = directory
        self._mode = mode
        self._inner = inner or httpx2.HTTPTransport()

    def _path(self, request: httpx2.Request) -> Path:
        return self._directory / f"{request_key(request.content)}.json"

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        request.read()
        path = self._path(request)
        if path.exists():
            recorded = json.loads(path.read_text(encoding="utf-8"))
            return httpx2.Response(
                recorded["status_code"],
                json=recorded["response"],
                headers={"content-type": "application/json"},
            )
        if self._mode == "replay":
            raise CassetteMiss(f"no cassette {path.name} for {request.url.path}")
        response = self._inner.handle_request(request)
        response.read()
        if response.status_code == 200:
            self._directory.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "request": json.loads(request.content),
                        "status_code": response.status_code,
                        "response": response.json(),
                    },
                    indent=1,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        return httpx2.Response(
            response.status_code, content=response.content, headers=response.headers
        )
