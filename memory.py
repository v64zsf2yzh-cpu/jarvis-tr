"""Kalıcı bellek — notlar, profil, öğrenme kuyruğu."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORY_PATH = DATA / "memory.json"
JOURNAL_PATH = DATA / "journal.jsonl"

_lock = threading.Lock()

DEFAULT = {
    "user_name": None,
    "city": None,
    "notes": [],
    "prefs": {},
    "pending_learn": [],
    "stats": {
        "turns": 0,
        "learned": 0,
        "auto_retrains": 0,
        "last_evolve": None,
    },
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load() -> dict[str, Any]:
    if not MEMORY_PATH.exists():
        return json.loads(json.dumps(DEFAULT))
    with open(MEMORY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    out = json.loads(json.dumps(DEFAULT))
    out.update(data)
    out.setdefault("notes", [])
    out.setdefault("prefs", {})
    out.setdefault("pending_learn", [])
    out.setdefault("stats", dict(DEFAULT["stats"]))
    return out


def save(data: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = MEMORY_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(MEMORY_PATH)


def update(mutator) -> dict[str, Any]:
    with _lock:
        data = load()
        mutator(data)
        save(data)
        return data


def add_note(text: str) -> str:
    text = text.strip()
    if not text:
        return ""

    def _m(d):
        d["notes"].append({"text": text, "at": _now()})
        d["notes"] = d["notes"][-80:]

    update(_m)
    return text


def list_notes(limit: int = 12) -> list[str]:
    notes = load().get("notes") or []
    return [n["text"] if isinstance(n, dict) else str(n) for n in notes[-limit:]]


def set_profile(**kwargs) -> dict[str, Any]:
    def _m(d):
        for k, v in kwargs.items():
            if v is None:
                continue
            if k in {"user_name", "city"}:
                d[k] = v
            elif k == "prefs" and isinstance(v, dict):
                d["prefs"].update(v)

    return update(_m)


def enqueue_learn(question: str, answer: str, tag: str = "ogretilen") -> None:
    q, a = question.strip(), answer.strip()
    if not q or not a or len(q) < 3 or len(a) < 2:
        return
    if len(q) > 160 or len(a) > 400:
        return

    def _m(d):
        pending = d.setdefault("pending_learn", [])
        key = q.lower()
        if any((p.get("q") or "").lower() == key for p in pending):
            return
        pending.append({"q": q, "a": a, "tag": tag, "at": _now()})
        d["stats"]["learned"] = int(d["stats"].get("learned", 0)) + 1

    update(_m)


def pop_pending(max_n: int = 20) -> list[dict[str, str]]:
    taken: list[dict[str, str]] = []

    def _m(d):
        nonlocal taken
        pending = d.get("pending_learn") or []
        taken = pending[:max_n]
        d["pending_learn"] = pending[max_n:]

    update(_m)
    return taken


def bump_turn() -> None:
    def _m(d):
        d["stats"]["turns"] = int(d["stats"].get("turns", 0)) + 1

    update(_m)


def mark_evolve(extra: dict[str, Any] | None = None) -> None:
    def _m(d):
        d["stats"]["last_evolve"] = _now()
        if extra:
            d["stats"].update(extra)

    update(_m)


def journal(role: str, text: str, meta: dict[str, Any] | None = None) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    row = {"at": _now(), "role": role, "text": (text or "")[:800], "meta": meta or {}}
    with _lock:
        with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
