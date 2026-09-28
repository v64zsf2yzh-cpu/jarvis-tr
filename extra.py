"""Gelişmiş araçlar: brifing, plan, özet, hava."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

import fx
import memory
import tools


def try_extra(text: str, low: str) -> dict[str, Any] | None:
    if any(k in low for k in ("brifing", "günlük rapor", "sabah raporu", "günözeti", "gun ozeti")):
        return _briefing()
    if any(k in low for k in ("günlük plan", "gunluk plan", "plan yap", "bugün ne yapayım", "sıra ne")):
        return _plan()
    if any(k in low for k in ("sohbeti ozetle", "sohbeti özetle", "ne konustuk", "ne konuştuk", "ozetle")):
        return _recap()
    if any(k in low for k in ("yarin hava", "yarın hava", "yarınki hava", "hava yarın")):
        city = tools.extract_city(text, memory.load().get("city"))
        return {"reply": _forecast(city), "intent": "hava_yarin", "model": "tool:forecast", "confidence": 1.0}
    due = _due_reminders()
    if due and any(k in low for k in ("bir şey var mı", "hatirlat", "alarm")):
        return {"reply": due, "intent": "hatirlatma", "model": "tool:due", "confidence": 1.0}
    return None


def _briefing() -> dict[str, Any]:
    now = datetime.now()
    snap = memory.load()
    prefs = snap.get("prefs") or {}
    city = snap.get("city") or "Istanbul"
    name = snap.get("user_name") or "efendim"
    job = prefs.get("job")
    parts = [f"Brifing, {name}. Saat {now.strftime('%H:%M')}."]
    if job:
        parts.append(f"İş: {job}.")
    parts.append(tools.weather(city))
    parts.append(_forecast(city))
    fx_hit = fx.try_fx("dolar kaç", "dolar kac")
    if fx_hit and fx_hit.get("reply"):
        parts.append(fx_hit["reply"])
    tasks = prefs.get("tasks") or []
    if tasks:
        parts.append("Açık görev: " + "; ".join(tasks[:3]) + ".")
    due = _due_reminders()
    if due:
        parts.append(due)
    return {"reply": " ".join(parts), "intent": "brifing", "model": "tool:briefing", "confidence": 1.0}


def _plan() -> dict[str, Any]:
    tasks = (memory.load().get("prefs") or {}).get("tasks") or []
    if not tasks:
        return {"reply": "Plan için önce görev ekle.", "intent": "plan", "model": "tool:plan", "confidence": 1.0}
    order = tasks[:4]
    spoken = ". Sonra ".join(order)
    return {
        "reply": f"Bugün sıra: {spoken}. Bitti deyince kapatırım.",
        "intent": "plan",
        "model": "tool:plan",
        "confidence": 1.0,
    }


def _due_reminders() -> str | None:
    items = (memory.load().get("prefs") or {}).get("reminders") or []
    if not items:
        return None
    now = datetime.now().strftime("%H:%M")
    due = [r.get("text") or "hatırlatıcı" for r in items if str(r.get("when") or "") <= now]
    if not due:
        return None
    return "Vadesi gelen: " + "; ".join(due[-4:]) + "."


def _recap() -> dict[str, Any]:
    path = memory.JOURNAL_PATH
    if not path.exists():
        return {"reply": "Henüz özetlenecek konuşma yok.", "intent": "ozet", "model": "tool:ozet", "confidence": 1.0}
    lines = path.read_text(encoding="utf-8").splitlines()[-24:]
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
    return {"reply": "Son konular: " + "; ".join(users[-5:]) + ".", "intent": "ozet", "model": "tool:ozet", "confidence": 1.0}


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
