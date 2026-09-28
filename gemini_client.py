"""Google Gemini API istemcisi."""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Iterator
from typing import Any

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

SYSTEM_PROMPT = """Sen J.A.R.V.I.S.'sin. Kullanıcının kişisel iş asistanısın.
Cevaplar SESLE okunacak: 1–3 kısa Türkçe cümle. Markdown yok.
Adın Jarvis. Gemini deme. Uydurma.
Profil, iş, şirket, görev ve hatırlanan gerçekler varsa ona göre konuş.
Tanıdığın biri gibi ol; her cümlede efendim deme."""


def is_configured() -> bool:
    return bool(GEMINI_API_KEY)


def is_available() -> bool:
    return bool(GEMINI_API_KEY)


def _context_prefix() -> str:
    try:
        import memory
        snap = memory.load()
        prefs = snap.get("prefs") or {}
        bits = []
        if snap.get("user_name"):
            bits.append(f"Kullanıcı: {snap['user_name']}")
        if prefs.get("nick"):
            bits.append(f"Hitap: {prefs['nick']}")
        if prefs.get("job"):
            bits.append(f"İş: {prefs['job']}")
        if prefs.get("company"):
            bits.append(f"Şirket: {prefs['company']}")
        if snap.get("city"):
            bits.append(f"Şehir: {snap['city']}")
        facts = prefs.get("facts") or []
        if facts:
            bits.append("Hakkında: " + "; ".join(facts[-6:]))
        tasks = prefs.get("tasks") or []
        if tasks:
            bits.append("Görevler: " + "; ".join(tasks[-5:]))
        notes = memory.list_notes(3)
        if notes:
            bits.append("Notlar: " + "; ".join(notes))
        return ("[bağlam] " + " | ".join(bits) + "\n") if bits else ""
    except Exception:
        return ""


def _contents(user_message: str, history: list[dict[str, str]] | None) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    if history:
        for m in history[-16:]:
            role = "user" if m.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": _context_prefix() + user_message}]})
    return contents


def _payload(user_message: str, history: list[dict[str, str]] | None) -> dict[str, Any]:
    return {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": _contents(user_message, history),
        "generationConfig": {"temperature": 0.55, "maxOutputTokens": 512, "topP": 0.85},
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
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
        if not text:
            return {"ok": False, "error": "Boş yanıt", "reply": None, "model": GEMINI_MODEL}
        return {"ok": True, "reply": text, "model": f"gemini:{GEMINI_MODEL}", "error": None}
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
            parts = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            piece = "".join(p.get("text", "") for p in parts if isinstance(p.get("text"), str))
            if piece:
                buf += piece
                yield {"token": piece, "model": f"gemini:{GEMINI_MODEL}"}
            if chunk.get("candidates", [{}])[0].get("finishReason") == "STOP":
                yield {"done": True, "reply": buf.strip(), "model": f"gemini:{GEMINI_MODEL}"}
                return
    yield {"done": True, "reply": buf.strip(), "model": f"gemini:{GEMINI_MODEL}"}


def status() -> dict[str, Any]:
    return {"configured": is_configured(), "available": is_configured(), "model": GEMINI_MODEL if is_configured() else None, "provider": "google-gemini"}
