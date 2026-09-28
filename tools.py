"""Yerel araçlar — hava, birim, çeviri, rastgele, yazı, hatırlatıcı."""

from __future__ import annotations

import json
import random
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any

import memory

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

_TR_EN = {
    "merhaba": "hello", "selam": "hi", "teşekkürler": "thank you", "lütfen": "please",
    "evet": "yes", "hayır": "no", "günaydın": "good morning", "iyi geceler": "good night",
    "nasılsın": "how are you", "ben": "I", "sen": "you", "su": "water", "ekmek": "bread",
    "kitap": "book", "ev": "house", "araba": "car", "bugün": "today", "yarın": "tomorrow",
    "saat": "hour", "tarih": "date",
}

CITIES = (
    "istanbul", "ankara", "izmir", "bursa", "antalya", "adana", "konya", "trabzon",
    "eskişehir", "gaziantep", "kayseri", "mersin", "diyarbakır", "samsun", "denizli",
    "sakarya", "kocaeli", "gebze", "van", "erzurum", "malatya", "hatay", "tekirdağ",
)


def weather(city: str | None = None) -> str:
    city = (city or "Istanbul").strip() or "Istanbul"
    try:
        q = urllib.parse.quote(city)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=tr&format=json"
        with urllib.request.urlopen(geo_url, timeout=8) as resp:
            geo = json.loads(resp.read().decode("utf-8"))
        results = geo.get("results") or []
        if not results:
            return f"«{city}» için konum bulunamadı."
        hit = results[0]
        lat, lon = hit["latitude"], hit["longitude"]
        label = hit.get("name") or city
        wurl = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,"
            "weather_code,wind_speed_10m&timezone=auto"
        )
        with urllib.request.urlopen(wurl, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cur = data.get("current") or {}
        temp = cur.get("temperature_2m")
        hum = cur.get("relative_humidity_2m")
        wind = cur.get("wind_speed_10m")
        code = int(cur.get("weather_code") or 0)
        return f"{label}: {temp}°C, {_wmo(code)}. Nem %{hum}, rüzgar {wind} km/s."
    except Exception as e:
        return f"Hava verisine ulaşılamadı ({e.__class__.__name__})."


def _wmo(code: int) -> str:
    table = {
        0: "açık", 1: "çoğunlukla açık", 2: "parçalı bulutlu", 3: "kapalı",
        45: "sisli", 48: "kırağılı sis", 51: "hafif çisenti", 61: "hafif yağmur",
        63: "yağmur", 65: "şiddetli yağmur", 71: "hafif kar", 73: "kar",
        80: "sağanak", 95: "gök gürültülü",
    }
    return table.get(code, "değişken")


def extract_city(text: str, fallback: str | None = None) -> str:
    m = re.search(
        r"(?:hava|sıcaklık|yağmur).{0,24}?(?:için|de|da|'de|'da)?\s*([A-ZÇĞİÖŞÜ][\wçğıöşü]+)",
        text, flags=re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"\b(?:" + "|".join(CITIES) + r")\b", text, flags=re.I)
    if m:
        return m.group(0).title()
    return fallback or "Istanbul"


def convert_units(text: str) -> str | None:
    low = text.lower().replace(",", ".")
    pairs = [
        (r"([\d.]+)\s*(?:km|kilometre)\b", lambda n: f"{n} km = {n * 0.621371:.2f} mil"),
        (r"([\d.]+)\s*(?:mil|mile)\b", lambda n: f"{n} mil = {n * 1.60934:.2f} km"),
        (r"([\d.]+)\s*(?:c|°c|santigrat|derece)\b", lambda n: f"{n}°C = {n * 9 / 5 + 32:.1f}°F"),
        (r"([\d.]+)\s*(?:f|°f|fahrenhayt|fahrenheit)\b", lambda n: f"{n}°F = {(n - 32) * 5 / 9:.1f}°C"),
        (r"([\d.]+)\s*(?:kg|kilo|kilogram)\b", lambda n: f"{n} kg = {n * 2.20462:.2f} lb"),
        (r"([\d.]+)\s*(?:lb|pound)\b", lambda n: f"{n} lb = {n * 0.453592:.2f} kg"),
        (r"([\d.]+)\s*(?:m|metre)\b", lambda n: f"{n} m = {n * 3.28084:.2f} ft"),
        (r"([\d.]+)\s*(?:cm)\b", lambda n: f"{n} cm = {n / 2.54:.2f} inç"),
        (r"([\d.]+)\s*(?:inch|inç|in)\b", lambda n: f"{n} inç = {n * 2.54:.2f} cm"),
    ]
    for pat, fmt in pairs:
        m = re.search(pat, low)
        if m:
            try:
                return fmt(float(m.group(1)))
            except Exception:
                continue
    return None


def translate_lite(text: str) -> str | None:
    raw = text.strip()
    low = raw.lower()
    if not any(k in low for k in ("çevir", "cevir", "translate", "ingilizce", "türkçe", "turkce")):
        return None
    cleaned = re.sub(
        r"\b(çevir|cevir|tercüme et|translate|ingilizceye|türkçeye|turkceye|ingilizcesi ne|türkçesi ne)\b",
        " ", raw, flags=re.I,
    ).strip(" :.-")
    if not cleaned:
        return "Çevrilecek ifadeyi söyleyin."
    words = cleaned.lower().split()
    mapped = [_TR_EN.get(w.strip(".,!?"), None) for w in words]
    if all(mapped):
        return "İngilizce: " + " ".join(mapped)
    en_tr = {v: k for k, v in _TR_EN.items()}
    mapped2 = [en_tr.get(w.lower(), w) for w in words]
    if mapped2 != words:
        return "Türkçe yaklaşığı: " + " ".join(mapped2)
    return None


def text_ops(text: str) -> str | None:
    low = text.lower()
    payload = re.sub(
        r"\b(büyük harf yap|küçük harf yap|ters çevir|kaç kelime|kaç harf|yazıyı büyüt|yazıyı küçült|kelime sayısı|karakter sayısı|metni ters çevir)\b",
        " ", text, flags=re.I,
    ).strip()
    if "büyük harf" in low or "yazıyı büyüt" in low:
        return payload.upper() if payload else text.upper()
    if "küçük harf" in low or "yazıyı küçült" in low:
        return payload.lower() if payload else text.lower()
    if "ters çevir" in low:
        return (payload or text)[::-1]
    if "kaç kelime" in low or "kelime sayısı" in low:
        return f"Kelime sayısı: {len((payload or text).split())}"
    if "kaç harf" in low or "karakter sayısı" in low:
        return f"Karakter sayısı: {len(payload or text)}"
    return None


def random_fun(text: str) -> str | None:
    low = text.lower()
    if "zar" in low:
        n = 2 if "2" in low or "iki" in low else 1
        rolls = [random.randint(1, 6) for _ in range(n)]
        return "Zar: " + ", ".join(str(x) for x in rolls)
    if "yazı tura" in low or "tura mı" in low or "yazı mı" in low:
        return "Yazı" if random.random() < 0.5 else "Tura"
    if "rastgele sayı" in low or "bir sayı söyle" in low:
        return f"Rastgele sayı: {random.randint(1, 100)}"
    m = re.search(r"seç\s+(.+)", text, flags=re.I)
    if m and ("," in m.group(1) or " veya " in m.group(1).lower()):
        parts = [p.strip() for p in re.split(r",| veya | ya da ", m.group(1), flags=re.I) if p.strip()]
        if len(parts) >= 2:
            return f"Seçimim: {random.choice(parts)}"
    if "karar ver" in low:
        return random.choice(["Evet.", "Hayır.", "Biraz bekleyin, sonra evet.", "Risk alma."])
    return None


def try_reminder(text: str, low: str) -> dict[str, Any] | None:
    if any(k in low for k in ("hatirlatmalarim", "hatırlatmalarım", "alarmlarim", "alarmlarım", "ne hatirlatacaksin")):
        items = (memory.load().get("prefs") or {}).get("reminders") or []
        if not items:
            return {"reply": "Kayıtlı hatırlatıcı yok, efendim.", "intent": "hatirlatma", "model": "tool:hatirlatma", "confidence": 1.0}
        lines = [f"{r.get('when', '?')} — {r.get('text', '')}" for r in items[-8:]]
        return {"reply": "Hatırlatıcılar: " + "; ".join(lines), "intent": "hatirlatma", "model": "tool:hatirlatma", "confidence": 1.0}
    if not any(k in low for k in ("hatirlat", "hatırlat", "alarm kur", "dakika sonra", "saat sonra")):
        return None
    minutes = None
    m = re.search(r"(\d+)\s*dakika", low)
    if m:
        minutes = int(m.group(1))
    m = re.search(r"(\d+)\s*saat", low)
    if m:
        minutes = int(m.group(1)) * 60
    m = re.search(r"saat\s+(\d{1,2})(?:[:.](\d{2}))?", low)
    when = None
    if minutes is not None:
        when = (datetime.now() + timedelta(minutes=max(1, min(minutes, 24 * 60)))).strftime("%H:%M")
    elif m:
        hh = int(m.group(1))
        mm = int(m.group(2) or 0)
        when = f"{hh:02d}:{mm:02d}"
    else:
        when = datetime.now().strftime("%H:%M")
    body = re.sub(
        r"\b(hatırlat|hatirlat|alarm kur|bana|dakika sonra|saat sonra|saat \d{1,2}([:.]\d{2})?)\b",
        " ", text, flags=re.I,
    )
    body = re.sub(r"\d+", " ", body)
    body = re.sub(r"\s+", " ", body).strip(" .,:-") or "hatırlatıcı"
    def _m(d):
        prefs = d.setdefault("prefs", {})
        items = prefs.setdefault("reminders", [])
        items.append({"text": body, "when": when, "at": datetime.now().isoformat(timespec="seconds")})
        prefs["reminders"] = items[-30:]
    memory.update(_m)
    return {
        "reply": f"Tamam. {when} için hatırlatıcı: {body}.",
        "intent": "hatirlatma",
        "model": "tool:hatirlatma",
        "confidence": 1.0,
    }


def city_from_profile(mem: dict[str, Any]) -> str | None:
    return mem.get("city")
