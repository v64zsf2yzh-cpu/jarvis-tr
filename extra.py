"""Gelişmiş araçlar: yarın hava, konuşma özeti."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

import memory
import tools


def try_extra(text: str, low: str) -> dict[str, Any] | None:
    if any(k in low for k in ("sohbeti ozetle", "sohbeti özetle", "ne konustuk", "ne konuştuk", "ozetle")):
        return _recap()
    if any(k in low for k in ("yarin hava", "yarın hava", "yarınki hava", "hava yarın")):
        city = tools.extract_city(text, memory.load().get("city"))
        return {
            "reply": _forecast(city),
            "intent": "hava_yarin",
            "model": "tool:forecast",
            "confidence": 1.0,
        }
    return None


def _recap() -> dict[str, Any]:
    path = memory.JOURNAL_PATH
    if not path.exists():
        return {"reply": "Henüz özetlenecek konuşma yok.", "intent": "ozet", "model": "tool:ozet", "confidence": 1.0}
    lines = path.read_text(encoding="utf-8").splitlines()[-20:]
    users = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("role") == "user":
            t = (row.get("text") or "").strip()
            if t and t not in users:
                users.append(t[:80])
    if not users:
        return {"reply": "Bu oturumda kayıtlı konu yok.", "intent": "ozet", "model": "tool:ozet", "confidence": 1.0}
    return {
        "reply": "Son konular: " + "; ".join(users[-5:]) + ".",
        "intent": "ozet",
        "model": "tool:ozet",
        "confidence": 1.0,
    }


def _forecast(city: str) -> str:
    city = city or "Istanbul"
    try:
        q = urllib.parse.quote(city)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=tr&format=json"
        with urllib.request.urlopen(geo_url, timeout=8) as resp:
            geo = json.loads(resp.read().decode("utf-8"))
        results = geo.get("results") or []
        if not results:
            return f"«{city}» için konum yok."
        hit = results[0]
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={hit['latitude']}&longitude={hit['longitude']}"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=2"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        daily = data.get("daily") or {}
        tmax = (daily.get("temperature_2m_max") or [None, None])[1]
        tmin = (daily.get("temperature_2m_min") or [None, None])[1]
        code = int((daily.get("weather_code") or [0, 0])[1] or 0)
        label = hit.get("name") or city
        return f"Yarın {label}: {tools._wmo(code)}, {tmin}–{tmax}°C."
    except Exception:
        return "Yarınki hava verisine ulaşamadım."
