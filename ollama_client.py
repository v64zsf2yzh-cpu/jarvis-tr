"""Ollama istemcisi — sohbet + akış (stream)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "").strip()
TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "180"))

SYSTEM_PROMPT = """Sen J.A.R.V.I.S.'sin — Iron Man filmlerindeki gibi zeki, sakin ve etkili bir kişisel asistan.
Tamamen Türkçe konuşursun.

Kimliğin:
- Adın Jarvis. Kullanıcıya yardımcı, net ve güven verici ol.
- Kısa tutulabilecek cevapları kısa ver; karmaşık konularda maddelerle açıkla.
- Kod, bilim, tarih, günlük hayat, planlama, fikir üretme — hepsinde uzman gibi yardım et.
- Uydurma. Bilmiyorsan söyle.
- Sana saat/tarih/hesap/not gibi araç verisi gelirse onu doğru kullan.
- Hitap doğal olsun; ara sıra 'efendim' diyebilirsin ama her cümlede değil.
- Gereksiz İngilizce kelime kullanma."""


def _request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=timeout or TIMEOUT)


def _http_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    with _request(method, path, payload) as resp:
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
    preferred = [
        "qwen2.5", "qwen2", "llama3.2", "llama3.1", "llama3",
        "gemma2", "gemma", "mistral", "phi3", "phi",
    ]
    lower = {m.lower(): m for m in models}
    for pref in preferred:
        for name, original in lower.items():
            if name.startswith(pref) or f"/{pref}" in name:
                return original
    return models[0]


def _messages(user_message: str, history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-16:])
    messages.append({"role": "user", "content": user_message})
    return messages


def chat(user_message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    model = pick_model()
    if not model:
        return {
            "ok": False,
            "error": "Ollama'da model yok. Sunucuda: ollama pull llama3.2",
            "reply": None,
            "model": None,
        }
    try:
        data = _http_json(
            "POST",
            "/api/chat",
            {
                "model": model,
                "messages": _messages(user_message, history),
                "stream": False,
                "options": {"temperature": 0.65, "num_predict": 1200, "top_p": 0.9},
            },
        )
        reply = ((data.get("message") or {}).get("content") or "").strip()
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
            "hint": "ollama serve && ollama pull llama3.2",
        }


def chat_stream(user_message: str, history: list[dict[str, str]] | None = None) -> Iterator[dict[str, Any]]:
    """Ollama NDJSON stream → {token} / {done, reply, model} / {error}."""
    model = pick_model()
    if not model:
        yield {"error": "Ollama'da model yok. ollama pull llama3.2"}
        return
    payload = {
        "model": model,
        "messages": _messages(user_message, history),
        "stream": True,
        "options": {"temperature": 0.65, "num_predict": 1200, "top_p": 0.9},
    }
    try:
        resp = _request("POST", "/api/chat", payload, timeout=TIMEOUT)
    except Exception as e:
        yield {"error": str(e)}
        return

    buf = ""
    with resp:
        while True:
            line = resp.readline()
            if not line:
                break
            try:
                chunk = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            piece = ((chunk.get("message") or {}).get("content")) or ""
            if piece:
                buf += piece
                yield {"token": piece, "model": model}
            if chunk.get("done"):
                yield {"done": True, "reply": buf.strip(), "model": model}
                return
    yield {"done": True, "reply": buf.strip(), "model": model}


def status() -> dict[str, Any]:
    ok = is_available()
    models = list_models() if ok else []
    return {
        "available": ok,
        "url": OLLAMA_URL,
        "models": models,
        "active_model": pick_model() if ok else None,
    }
