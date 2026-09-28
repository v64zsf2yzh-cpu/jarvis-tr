"""Vadesi gelen hatırlatıcıyı bir kez söyle."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import memory


def pop_due() -> str | None:
    now = datetime.now().strftime("%H:%M")
    spoken: list[str] = []

    def _m(d):
        prefs = d.setdefault("prefs", {})
        items = prefs.get("reminders") or []
        keep = []
        for r in items:
            when = str(r.get("when") or "")
            if when and when <= now and not r.get("said"):
                spoken.append(r.get("text") or "hatırlatıcı")
                r["said"] = True
            keep.append(r)
        prefs["reminders"] = keep[-30:]

    memory.update(_m)
    if not spoken:
        return None
    return "Hatırlatma: " + "; ".join(spoken) + "."


def status_blob() -> dict[str, Any]:
    items = (memory.load().get("prefs") or {}).get("reminders") or []
    return {"count": len(items), "open": sum(1 for r in items if not r.get("said"))}
