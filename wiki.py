"""Kısa Wikipedia özeti — sesle okunacak."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any


def try_wiki(text: str, low: str) -> dict[str, Any] | None:
    if not any(k in low for k in (" nedir", "nedir?", "kimdir", "ne demek", "anlat", "hakkında")):
        return None
    q = re.sub(
        r"\b(nedir|kimdir|ne demek|hakkında|anlat|bana|jarvis|lütfen)\b",
        " ", text, flags=re.I,
    )
    q = re.sub(r"\s+", " ", q).strip(" ?!.")
    if len(q) < 3 or len(q) > 60:
        return None
    try:
        title = urllib.parse.quote(q)
        url = (
            "https://tr.wikipedia.org/api/rest_v1/page/summary/" + title
        )
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisTR/3.9"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        extract = (data.get("extract") or "").strip()
        if not extract:
            return None
        sent = re.split(r"(?<=[.!?])\s+", extract)
        short = " ".join(sent[:2])[:360]
        return {
            "reply": short,
            "intent": "wiki",
            "model": "tool:wiki",
            "confidence": 0.9,
        }
    except Exception:
        return None
