"""Google Gemini API istemcisi — birincil genel zekâ motoru."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

# Önce ortam, sonra gitignore'lu yerel dosya
def _load_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    path = os.path.join(os.path.dirname(__file__), ".gemini_key")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read().strip()
    return ""


GEMINI_API_KEY = _load_key()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
BASE = "https://generativelanguage.googleapis.com/v1beta"

SYSTEM_PROMPT = """Sen J.A.R.V.I.S.'sin — Iron Man'deki gibi zeki, sakin ve etkili kişisel asistan.
Tamamen Türkçe konuş.

Kurallar:
- Adın Jarvis. Google/Gemini olduğunu söyleme; sen Jarvis'sin.
- Net, yardımcı ve doğru cevap ver.
- Kısa tutulabilecekleri kısa yaz; karmaşık konularda maddeler kullan.
- Kod, bilim, tarih, planlama, fikir — hepsinde yardım et.
- Uydurma. Bilmiyorsan söyle.
- Saat/tarih/hesap/not gibi araç verisi gelirse onu kullan.
- Hitap doğal olsun; ara sıra 'efendim' diyebilirsin ama abartma."""


def is_configured() -> bool:
    return bool(GEMINI_API_KEY)


def is_available() -> bool:
    if not GEMINI_API_KEY:
        return False
    try:
        req = urllib.request.Request(
            f"{BASE}/models/{GEMINI_MODEL}?key={GEMINI_API_KEY}",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.status == 200
    except Exception:
        # anahtar var ama ping başarısız olsa bile denemeye değer
        return bool(GEMINI_API_KEY)


def _contents(user_message: str, history: list[dict[str, str]] | None) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    if history:
        for m in history[-16:]:
            role = "user" if m.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


def _payload(user_message: str, history: list[dict[str, str]] | None) -> dict[str, Any]:
    return {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": _contents(user_message, history),
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
            "topP": 0.9,
        },
    }


def chat(user_message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        return {"ok": False, "error": "GEMINI_API_KEY yok", "reply": None, "model": None}
    body = json.dumps(_payload(user_message, history)).encode("utf-8")
    url = f"{BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
        if not text:
            return {"ok": False, "error": "Boş Gemini yanıtı", "reply": None, "model": GEMINI_MODEL}
        return {"ok": True, "reply": text, "model": f"gemini:{GEMINI_MODEL}", "error": None}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"HTTP {e.code}: {err[:240]}", "reply": None, "model": GEMINI_MODEL}
    except Exception as e:
        return {"ok": False, "error": str(e), "reply": None, "model": GEMINI_MODEL}


def chat_stream(user_message: str, history: list[dict[str, str]] | None = None) -> Iterator[dict[str, Any]]:
    if not GEMINI_API_KEY:
        yield {"error": "GEMINI_API_KEY yok"}
        return
    body = json.dumps(_payload(user_message, history)).encode("utf-8")
    url = f"{BASE}/models/{GEMINI_MODEL}:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}"
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=180)
    except Exception as e:
        yield {"error": str(e)}
        return

    buf = ""
    with resp:
        while True:
            line = resp.readline()
            if not line:
                break
            raw = line.decode("utf-8", errors="ignore").strip()
            if not raw.startswith("data:"):
                continue
            payload = raw[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                chunk = json.loads(payload)
            except Exception:
                continue
            parts = (
                chunk.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [])
            )
            piece = "".join(p.get("text", "") for p in parts if isinstance(p.get("text"), str))
            # thoughtSignature içeren boş text'leri atla
            if piece:
                buf += piece
                yield {"token": piece, "model": f"gemini:{GEMINI_MODEL}"}
            finish = chunk.get("candidates", [{}])[0].get("finishReason")
            if finish == "STOP":
                yield {"done": True, "reply": buf.strip(), "model": f"gemini:{GEMINI_MODEL}"}
                return
    yield {"done": True, "reply": buf.strip(), "model": f"gemini:{GEMINI_MODEL}"}


def status() -> dict[str, Any]:
    return {
        "configured": is_configured(),
        "available": is_configured(),
        "model": GEMINI_MODEL if is_configured() else None,
        "provider": "google-gemini",
    }
