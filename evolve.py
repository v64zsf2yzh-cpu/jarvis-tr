"""Jarvis açıkken arka planda kendini geliştirir."""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

import memory
import selfcode
from brain import teach_qa

_stop = threading.Event()
_thread = None
_train_lock = threading.Lock()
_state = {"running": False, "training": False, "last_error": None, "last_result": None, "ticks": 0}


def status() -> dict[str, Any]:
    snap = memory.load()
    return {
        **_state,
        "pending_learn": len(snap.get("pending_learn") or []),
        "turns": (snap.get("stats") or {}).get("turns", 0),
        "learned": (snap.get("stats") or {}).get("learned", 0),
        "auto_retrains": (snap.get("stats") or {}).get("auto_retrains", 0),
        "last_evolve": (snap.get("stats") or {}).get("last_evolve"),
        "selfcode": selfcode.status(),
    }


def start(retrain_fn: Callable[[], dict[str, Any]], interval_sec: int = 180) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return

    def loop():
        _state["running"] = True
        time.sleep(40)
        while not _stop.is_set():
            try:
                tick(retrain_fn)
            except Exception as e:
                _state["last_error"] = str(e)
            _stop.wait(interval_sec)
        _state["running"] = False

    _stop.clear()
    _thread = threading.Thread(target=loop, name="jarvis-evolve", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()


def observe(user: str, reply: str, intent: str | None = None) -> None:
    memory.bump_turn()
    memory.journal("user", user, {"intent": intent})
    memory.journal("assistant", reply, {"intent": intent})
    _maybe_profile(user)
    _maybe_correction(user, reply)


def _maybe_profile(user: str) -> None:
    m = re.search(r"(?:benim adım|adım|ismim)\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)", user, flags=re.I)
    if m:
        memory.set_profile(user_name=m.group(1).strip().title())
    m = re.search(r"(?:şehirim|yaşadığım yer|yaşıyorum|şehir)\s*:?\s*([A-Za-zÇĞİÖŞÜçğıöşü]+)", user, flags=re.I)
    if m:
        memory.set_profile(city=m.group(1).strip().title())


def _maybe_correction(user: str, reply: str) -> None:
    low = user.lower()
    m = re.match(r"^\s*(?:hayır|yanlış|değil)[,:]?\s+(?:doğrusu|aslında)?\s*(.+)$", user, flags=re.I)
    if m and len(m.group(1)) > 3:
        memory.enqueue_learn(user, m.group(1).strip(), tag="duzeltme")
        return
    if any(k in low for k in ("öğret ", "ogret ", "bunu öğren", "aklında tut ki")):
        return
    if 12 <= len(user) <= 120 and re.search(r"\b(nedir|kimdir|nerede|kaç)\b", low):
        if reply and 8 <= len(reply) <= 280 and "ulaşılamadı" not in reply.lower():
            if intent_ok(low):
                memory.enqueue_learn(user, reply.split("\n")[0][:280], tag="gozlem")


def intent_ok(low: str) -> bool:
    return not any(b in low for b in ("şifre", "parola", "password", "anahtar", "api key", "token"))


def tick(retrain_fn: Callable[[], dict[str, Any]]) -> None:
    _state["ticks"] = int(_state.get("ticks") or 0) + 1
    pending = memory.load().get("pending_learn") or []
    if pending:
        batch = memory.pop_pending(12)
        for item in batch:
            try:
                teach_qa(item["q"], item["a"], tag=item.get("tag") or "ogretilen")
            except Exception:
                continue
        memory.mark_evolve({"flushed": len(batch)})
        _state["last_result"] = f"{len(batch)} öğreti işlendi"
        snap = memory.load()
        learned = int((snap.get("stats") or {}).get("learned") or 0)
        retrains = int((snap.get("stats") or {}).get("auto_retrains") or 0)
        if learned >= 4 and learned // 8 > retrains:
            background_train(retrain_fn)
    if _state["ticks"] % 3 == 0:
        try:
            patch = selfcode.cycle(force=False, reason="idle-tick")
            if patch.get("ok"):
                _state["last_result"] = patch.get("summary") or "selfcode"
        except Exception as e:
            _state["last_error"] = str(e)


def background_train(retrain_fn: Callable[[], dict[str, Any]]) -> bool:
    if _state["training"]:
        return False
    if not _train_lock.acquire(blocking=False):
        return False

    def job():
        _state["training"] = True
        try:
            meta = retrain_fn()
            memory.update(lambda d: d["stats"].__setitem__("auto_retrains", int(d["stats"].get("auto_retrains", 0)) + 1))
            memory.mark_evolve({"last_acc": meta.get("accuracy")})
            _state["last_result"] = f"auto-retrain acc={meta.get('accuracy')}"
        except Exception as e:
            _state["last_error"] = str(e)
        finally:
            _state["training"] = False
            _train_lock.release()

    threading.Thread(target=job, name="jarvis-retrain", daemon=True).start()
    return True
