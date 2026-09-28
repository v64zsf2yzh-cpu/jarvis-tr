"""Döviz — Frankfurter, anahtarsız."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

MAP = {
    "dolar": "USD", "dollar": "USD", "usd": "USD",
    "euro": "EUR", "eur": "EUR",
    "sterlin": "GBP", "pound": "GBP", "gbp": "GBP",
    "tl": "TRY", "lira": "TRY", "try": "TRY", "türk lirası": "TRY",
}


def try_fx(text: str, low: str) -> dict[str, Any] | None:
    if not any(k in low for k in ("dolar", "euro", "sterlin", "döviz", "kur", "kaç tl", "kaç lira")):
        return None
    src = "USD"
    if "euro" in low:
        src = "EUR"
    elif "sterlin" in low or "pound" in low:
        src = "GBP"
    m = re.search(r"([\d]+(?:[.,]\d+)?)", low.replace(",", "."))
    amount = float(m.group(1)) if m else 1.0
    try:
        url = f"https://api.frankfurter.app/latest?from={src}&to=TRY"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rate = float((data.get("rates") or {}).get("TRY") or 0)
        if not rate:
            return None
        total = amount * rate
        label = {"USD": "dolar", "EUR": "euro", "GBP": "sterlin"}[src]
        return {
            "reply": f"{amount:g} {label} yaklaşık {total:.2f} TL.",
            "intent": "doviz",
            "model": "tool:fx",
            "confidence": 1.0,
        }
    except Exception:
        return {"reply": "Kur verisine şu an ulaşamadım.", "intent": "doviz", "model": "tool:fx", "confidence": 1.0}
