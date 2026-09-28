"""Konuşmasan da sorun tarar."""

from __future__ import annotations

from typing import Any

import doorbell
import memory
import selfcode


def scan() -> list[str]:
    issues: list[str] = []
    snap = memory.load()
    prefs = snap.get("prefs") or {}
    if not snap.get("user_name"):
        issues.append("profil: kullanıcı adı yok")
    if not snap.get("city"):
        issues.append("profil: şehir yok")
    door = doorbell.status()
    if door.get("error"):
        issues.append("kapı: " + str(door["error"])[:80])
    if door.get("configured") and not door.get("has_frame"):
        issues.append("kapı: kare yok")
    sc = selfcode.status()
    if sc.get("last_error"):
        issues.append("selfcode: " + str(sc["last_error"])[:80])
    pending = snap.get("pending_learn") or []
    if len(pending) > 20:
        issues.append("öğrenme kuyruğu şişti")
    if not (prefs.get("tasks") or []) and not (prefs.get("facts") or []):
        issues.append("iş bağlamı zayıf: görev/fact yok")
    return issues[:8]


def prompt_blob() -> str:
    issues = scan()
    if not issues:
        return "Kritik sorun yok. Küçük kullanışlı bir skill veya intent ekle."
    return "Sorunlar: " + "; ".join(issues)


def status() -> dict[str, Any]:
    issues = scan()
    return {"issues": issues, "ok": not issues}
