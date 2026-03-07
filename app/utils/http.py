from __future__ import annotations

from urllib.request import Request, urlopen

DEFAULT_HEADERS = {
    "User-Agent": "ownership-type-agent/1.0 (+https://example.local)",
    "Accept-Language": "en-GB,en;q=0.9",
}


def get_text(url: str, timeout: int = 20) -> str:
    req = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(req, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="ignore")
