"""Kısa gün özeti — Wikipedia günlük öne çıkan."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Any


def try_news(text: str, low: str) -> dict[str, Any] | None:
    if not any(k in low for k in ("haber", "gündem", "ne oldu", "bugün ne", "başlıklar")):
        return None
    now = datetime.utcnow()
    url = f"https://tr.wikipedia.org/api/rest_v1/feed/featured/{now:%Y}/{now:%m}/{now:%d}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisTR/3.9"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        titles = []
        most = (data.get("mostread") or {}).get("articles") or []
        for item in most[:3]:
            t = (item.get("titles") or {}).get("normalized") or item.get("title")
            if t:
                titles.append(t)
        news = data.get("news") or []
        for item in news[:2]:
            links = item.get("links") or []
            if links:
                t = (links[0].get("titles") or {}).get("normalized") or links[0].get("title")
                if t:
                    titles.append(t)
        titles = list(dict.fromkeys(titles))[:4]
        if not titles:
            return {"reply": "Gündem özetine şu an ulaşamadım.", "intent": "haber", "model": "tool:news", "confidence": 1.0}
        return {
            "reply": "Gündem: " + "; ".join(titles) + ".",
            "intent": "haber",
            "model": "tool:news",
            "confidence": 1.0,
        }
    except Exception:
        return {"reply": "Haber kaynağına ulaşamadım, efendim.", "intent": "haber", "model": "tool:news", "confidence": 1.0}
