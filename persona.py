"""Kullanıcıyı tanı: iş, görev, profil."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import memory


def try_persona(text: str, low: str) -> dict[str, Any] | None:
    m = re.search(r"(?:işim|mesleğim|uğraştığım iş|iş olarak)\s+(.+)$", text, flags=re.I)
    if m:
        job = m.group(1).strip(" .!")
        memory.set_profile(prefs={"job": job})
        return _ok(f"Kaydettim. İşin: {job}.")
    m = re.search(r"(?:beni tan[iı]|ben kimim|profilim)", low)
    if m and len(low) < 40:
        return _ok(_who())
    if any(k in low for k in ("görevlerim", "gorevlerim", "yapılacaklar", "işlerim ne", "islerim ne")):
        tasks = _tasks()
        if not tasks:
            return _ok("Açık görev yok. 'Görev ekle ...' de.")
        return _ok("Görevler: " + "; ".join(tasks[-8:]))
    m = re.search(r"(?:görev ekle|gorev ekle|yapılacak ekle|işe ekle)\s+(.+)", text, flags=re.I)
    if m:
        item = m.group(1).strip(" .")
        _add_task(item)
        return _ok(f"Listeye aldım: {item}.")
    m = re.search(r"(?:görevi bitir|tamamladım|işi bitir)\s+(.+)", text, flags=re.I)
    if m:
        item = m.group(1).strip()
        left = _done_task(item)
        return _ok(f"Kapatıldı. Kalan {left} görev.")
    return None


def _ok(reply: str) -> dict[str, Any]:
    return {"reply": reply, "intent": "persona", "model": "tool:persona", "confidence": 1.0}


def _who() -> str:
    snap = memory.load()
    bits = []
    if snap.get("user_name"):
        bits.append(snap["user_name"])
    job = (snap.get("prefs") or {}).get("job")
    if job:
        bits.append(job)
    if snap.get("city"):
        bits.append(snap["city"])
    tasks = _tasks()
    if not bits:
        return "Seni henüz tanımıyorum. Adını, şehrini ve işini söyle."
    msg = "Seni böyle kaydettim: " + ", ".join(bits) + "."
    if tasks:
        msg += " Açık görev: " + str(len(tasks)) + "."
    return msg


def _tasks() -> list[str]:
    return list((memory.load().get("prefs") or {}).get("tasks") or [])


def _add_task(item: str) -> None:
    def _m(d):
        prefs = d.setdefault("prefs", {})
        tasks = prefs.setdefault("tasks", [])
        if item not in tasks:
            tasks.append(item)
        prefs["tasks"] = tasks[-40:]
        prefs["last_task_at"] = datetime.now().isoformat(timespec="seconds")
    memory.update(_m)


def _done_task(item: str) -> int:
    def _m(d):
        prefs = d.setdefault("prefs", {})
        tasks = prefs.get("tasks") or []
        low = item.lower()
        prefs["tasks"] = [t for t in tasks if low not in t.lower() and t.lower() not in low]
    snap = memory.update(_m)
    return len((snap.get("prefs") or {}).get("tasks") or [])
