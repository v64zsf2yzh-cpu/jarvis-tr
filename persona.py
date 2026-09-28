"""Kullanıcıyı tanı: profil, iş, görev, hatırlanan gerçekler."""

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

    m = re.search(r"(?:çalıştığım yer|şirketim|ofisim)\s+(.+)$", text, flags=re.I)
    if m:
        company = m.group(1).strip(" .!")
        memory.set_profile(prefs={"company": company})
        return _ok(f"Şirketi kaydettim: {company}.")

    m = re.search(r"(?:beni çağır|çağır beni|lakabım)\s+(.+)$", text, flags=re.I)
    if m:
        nick = m.group(1).strip(" .!")
        memory.set_profile(prefs={"nick": nick})
        return _ok(f"Tamam. Sana {nick} diyeceğim.")

    if re.search(r"(?:beni tan[iı]|ben kimim|profilim|beni anlat)", low) and len(low) < 48:
        return _ok(_who())

    m = re.search(
        r"(?:aklında tut|aklinda tut|bunu hatırla|bunu hatirla|bil ki|not et ki)\s+(.+)",
        text, flags=re.I,
    )
    if m:
        fact = m.group(1).strip(" .")
        _add_fact(fact)
        return _ok(f"Aklımda: {fact}.")

    if any(k in low for k in ("ne biliyorsun", "hakkımda ne", "beni ne biliyorsun")):
        facts = _facts()
        if not facts:
            return _ok("Hakkında kayıtlı ekstra yok. 'Aklında tut ...' de.")
        return _ok("Hakkında: " + "; ".join(facts[-6:]) + ".")

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

    if any(k in low for k in ("işlerimi yap", "islerimi yap", "görevlerimi yap", "sıradaki iş")):
        tasks = _tasks()
        if not tasks:
            return _ok("Yapacak görev yok. Önce 'görev ekle' de.")
        return _ok(f"Sırada: {tasks[0]}. Bitince 'görevi bitir {tasks[0]}' de.")

    m = re.search(r"(?:görevi bitir|tamamladım|işi bitir)\s+(.+)", text, flags=re.I)
    if m:
        item = m.group(1).strip()
        left = _done_task(item)
        nxt = _tasks()
        extra = f" Sırada: {nxt[0]}." if nxt else " Liste boş."
        return _ok(f"Kapatıldı. Kalan {left} görev.{extra}")

    m = re.search(r"(?:taslak yaz|şunu yaz|mail yaz|mesaj yaz)\s+(.+)", text, flags=re.I)
    if m:
        body = m.group(1).strip()
        memory.add_note("taslak: " + body)
        return _ok(f"Taslağı nota aldım: {body[:180]}.")

    return None


def _ok(reply: str) -> dict[str, Any]:
    return {"reply": reply, "intent": "persona", "model": "tool:persona", "confidence": 1.0}


def _who() -> str:
    snap = memory.load()
    prefs = snap.get("prefs") or {}
    bits = []
    nick = prefs.get("nick")
    if snap.get("user_name"):
        bits.append(snap["user_name"] + (f" ({nick})" if nick else ""))
    elif nick:
        bits.append(nick)
    if prefs.get("job"):
        bits.append(prefs["job"])
    if prefs.get("company"):
        bits.append(prefs["company"])
    if snap.get("city"):
        bits.append(snap["city"])
    tasks = _tasks()
    facts = _facts()
    if not bits:
        return "Seni henüz tanımıyorum. Adını, şehrini ve işini söyle."
    msg = "Seni böyle kaydettim: " + ", ".join(bits) + "."
    if tasks:
        msg += f" Açık görev: {len(tasks)}."
    if facts:
        msg += " Hatırladığım: " + "; ".join(facts[-3:]) + "."
    return msg


def _tasks() -> list[str]:
    return list((memory.load().get("prefs") or {}).get("tasks") or [])


def _facts() -> list[str]:
    return list((memory.load().get("prefs") or {}).get("facts") or [])


def _add_fact(item: str) -> None:
    def _m(d):
        prefs = d.setdefault("prefs", {})
        facts = prefs.setdefault("facts", [])
        if item not in facts:
            facts.append(item)
        prefs["facts"] = facts[-40:]
    memory.update(_m)


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
