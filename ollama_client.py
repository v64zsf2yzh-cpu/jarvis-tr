"""Ollama istemcisi — genel sorular için yerel LLM."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "").strip()  # boşsa otomatik seç
TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

SYSTEM_PROMPT = """Sen Jarvis'sin: Iron Man tarzı, Türkçe konuşan kişisel yapay zeka asistanı.
Kısa, net ve yardımcı cevap ver. Gereksiz uzatma.
Türkçe yanıtla. Bilmiyorsan dürüstçe söyle.
Matematik, bilgi, kod, günlük sorular ve sohbette yardımcı ol.
Kullanıcıya 'efendim' diye hitap edebilirsin ama abartma."""


def _http_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_available() -> bool:
    try:
        _http_json("GET", "/api/tags")
        return True
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        data = _http_json("GET", "/api/tags")
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def pick_model() -> str | None:
    if OLLAMA_MODEL:
        return OLLAMA_MODEL
    models = list_models()
    if not models:
        return None
    # Türkçe / genel için tercih sırası
    preferred = [
        "llama3.2",
        "llama3.1",
        "llama3",
        "qwen2.5",
        "qwen2",
        "gemma2",
        "gemma",
        "mistral",
        "phi3",
        "phi",
    ]
    lower = {m.lower(): m for m in models}
    for pref in preferred:
        for name, original in lower.items():
            if name.startswith(pref) or f"/{pref}" in name:
                return original
    return models[0]


def chat(user_message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Ollama /api/chat ile yanıt üret."""
    model = pick_model()
    if not model:
        return {
            "ok": False,
            "error": "Ollama'da model yok. Sunucuda: ollama pull llama3.2",
            "reply": None,
            "model": None,
        }

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-12:])  # son 6 tur
    messages.append({"role": "user", "content": user_message})

    try:
        data = _http_json(
            "POST",
            "/api/chat",
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 512},
            },
        )
        reply = (data.get("message") or {}).get("content") or ""
        reply = reply.strip()
        if not reply:
            return {"ok": False, "error": "Boş yanıt", "reply": None, "model": model}
        return {"ok": True, "reply": reply, "model": model, "error": None}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"HTTP {e.code}: {body[:200]}", "reply": None, "model": model}
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "reply": None,
            "model": model,
            "hint": "Ollama çalışıyor mu? ollama serve && ollama pull llama3.2",
        }


def status() -> dict[str, Any]:
    ok = is_available()
    models = list_models() if ok else []
    return {
        "available": ok,
        "url": OLLAMA_URL,
        "models": models,
        "active_model": pick_model() if ok else None,
    }
