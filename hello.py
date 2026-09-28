"""Açılış: sistemler çevrimiçi, kısa durum."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import doorbell
import extra
import memory
import selfcode


def compose(text_only: bool = False) -> dict[str, Any]:
    now = datetime.now()
    snap = memory.load()
    prefs = snap.get("prefs") or {}
    name = snap.get("user_name") or prefs.get("nick") or "efendim"
    hour = now.hour
    if hour < 6:
        greet = "İyi geceler"
    elif hour < 12:
        greet = "Günaydın"
    elif hour < 18:
        greet = "İyi günler"
    else:
        greet = "İyi akşamlar"
    parts = []
    if not text_only:
        parts.append("Sistemler çevrimiçi.")
    parts.append(f"{greet} {name}.")
    job = prefs.get("job")
    if job:
        parts.append(f"{job} hattı hazır.")
    tasks = prefs.get("tasks") or []
    if tasks:
        parts.append(f"Sırada {len(tasks)} görev. İlki: {tasks[0]}.")
    door = doorbell.status()
    if door.get("configured"):
        if door.get("last_motion"):
            parts.append(f"Kapı hattı açık. Son hareket {door['last_motion']}.")
        else:
            parts.append("Kapı hattı izlemede.")
    patch = (selfcode.status().get("last_patch") or {})
    if patch.get("summary"):
        parts.append(f"Son öz yama: {patch['summary']}.")
    speak = " ".join(parts)
    return {"speak": speak, "name": name, "tasks": len(tasks), "at": now.isoformat(timespec="seconds")}
