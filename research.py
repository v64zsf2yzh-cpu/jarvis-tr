"""Kısa web özeti — Wikipedia."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

TRIG = ("araştır", "arastir", "nedir", "kimdir", "ne demek", "hakkında bilgi")


def try_research(text: str, low: str) -> dict[str, Any] | None:
    if not any(k in low for k in TRIG):
        return None
    q = re.sub(r"(?:jarvis|,|lütfen|araştır|arastir|nedir|kimdir|ne demek|hakkında bilgi)", " ", text, flags=re.I)
    q = re.sub(r"\s+", " ", q).strip(" ?!.")
    if len(q) < 3:
        return {"reply": "Neyi araştırayım?", "intent": "arastir", "model": "tool:wiki", "confidence": 1.0}
    summary = _wiki(q)
    return {"reply": summary, "intent": "arastir", "model": "tool:wiki", "confidence": 1.0}


def _wiki(q: str) -> str:
    try:
        title = urllib.parse.quote(q)
        url = (
            "https://tr.wikipedia.org/api/rest_v1/page/summary/" + title
        )
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisTR/4.6"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        extract = (data.get("extract") or "").strip()
        if extract:
            return extract.split(". ")[0][:280] + "."
        return f"«{q}» için net madde yok."
    except Exception:
        try:
            q2 = urllib.parse.quote(q)
            url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + q2
            req = urllib.request.Request(url, headers={"User-Agent": "JarvisTR/4.6"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            extract = (data.get("extract") or "").strip()
            if extract:
                return extract.split(". ")[0][:280] + "."
        except Exception:
            pass
        return "Araştırma hattına şimdi ulaşamadım."
