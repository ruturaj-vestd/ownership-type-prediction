from __future__ import annotations

import json
import os
import re

from app.utils.http import http_request

OPENAI_URL = "https://api.openai.com/v1/responses"


def openai_responses_text(*, model: str, messages: list[dict], tools: list[dict] | None = None, api_key: str | None = None) -> str:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY env var")
    payload: dict = {"model": model, "input": messages}
    if tools:
        payload["tools"] = tools
    status, text = http_request(
        "POST",
        OPENAI_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        body=payload,
        timeout=180,
    )
    if not (200 <= status < 300):
        raise RuntimeError(f"OpenAI API error {status}: {text[:1500]}")
    data = json.loads(text)
    if isinstance(data, dict) and data.get("output_text"):
        return str(data["output_text"]).strip()
    chunks: list[str] = []
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and c.get("text"):
                chunks.append(c["text"])
    out = "".join(chunks).strip()
    if not out:
        raise RuntimeError("OpenAI response missing output_text")
    return out


def strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"^\s*```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def safe_json_parse_strict(s: str) -> dict:
    cleaned = strip_code_fences(s)
    try:
        obj = json.loads(cleaned)
    except Exception:
        m = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not m:
            raise ValueError("Failed to parse JSON: no JSON object found")
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("Parsed JSON is not an object")
    return obj
