from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_request(method: str, url: str, *, headers: dict[str, str] | None = None, body: dict | None = None, timeout: int = 60) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, data=data, headers=headers or {}, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as r:  # noqa: S310
            return r.status, r.read().decode("utf-8", errors="ignore")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except URLError as e:
        raise RuntimeError(str(e)) from e


def http_get_text(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> tuple[int, str]:
    return http_request("GET", url, headers=headers, timeout=timeout)
