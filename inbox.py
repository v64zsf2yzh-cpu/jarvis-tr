"""Sadece proje data/inbox — tüm PC yok."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent / "data" / "inbox"
ALLOWED = {".txt", ".md"}


def try_inbox(text: str, low: str) -> dict[str, Any] | None:
    if any(k in low for k in ("kutuyu aç", "inbox", "iş kutusu", "dosyalarım ne")):
        return _ok(_list())
    m = re.search(r"(?:kutuya yaz|inboxa yaz)\s+(.+)", text, flags=re.I)
    if m:
        return _ok(_write(m.group(1).strip()))
    m = re.search(r"(?:kutuyu oku|dosyayı oku)\s+(.+)", text, flags=re.I)
    if m:
        return _ok(_read(m.group(1).strip()))
    return None


def _ok(reply: str) -> dict[str, Any]:
    return {"reply": reply, "intent": "inbox", "model": "tool:inbox", "confidence": 1.0}


def _safe(name: str) -> Path | None:
    name = re.sub(r"[^A-Za-z0-9._\-]", "_", name)[:40]
    if not name:
        return None
    if not any(name.endswith(ext) for ext in ALLOWED):
        name += ".txt"
    path = (ROOT / name).resolve()
    if ROOT.resolve() not in path.parents and path != ROOT.resolve():
        return None
    return path


def _list() -> str:
    ROOT.mkdir(parents=True, exist_ok=True)
    files = [p.name for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED]
    if not files:
        return "İş kutusu boş. 'Kutuya yaz ...' de veya VPS'te data/inbox içine txt koy."
    return "Kutuda: " + ", ".join(files[:12]) + "."


def _write(body: str) -> str:
    ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%m%d-%H%M")
    path = ROOT / f"not-{stamp}.txt"
    path.write_text(body[:2000], encoding="utf-8")
    return f"Yazdım: {path.name}."


def _read(name: str) -> str:
    path = _safe(name)
    if not path or not path.exists():
        return "O dosya kutuda yok."
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return (text[:280] + ".") if text else "Dosya boş."
