"""Kendi kapı kameran — RTSP veya JPEG. Başkasının kamerası yok."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import memory

ROOT = Path(__file__).resolve().parent
FRAME = ROOT / "data" / "door.jpg"
PREV = ROOT / "data" / "door_prev.jpg"

_state: dict[str, Any] = {
    "running": False,
    "configured": False,
    "last_check": None,
    "last_motion": None,
    "alert": None,
    "error": None,
}
_stop = threading.Event()
_thread = None


def url() -> str:
    env = os.environ.get("DOORBELL_URL", "").strip()
    if env:
        return env
    return str((memory.load().get("prefs") or {}).get("doorbell_url") or "").strip()


def set_url(value: str) -> None:
    memory.set_profile(prefs={"doorbell_url": value.strip()})
    _state["configured"] = bool(value.strip())


def status() -> dict[str, Any]:
    return {**_state, "configured": bool(url()), "has_frame": FRAME.exists()}


def peek() -> str:
    if not url():
        return (
            "Kapı kamerası bağlı değil. Zilin uygulama ayarından RTSP veya anlık JPEG adresini al, "
            "sonra 'kapı adresi ...' de."
        )
    ok, msg = grab()
    if not ok:
        return msg
    if _state.get("last_motion"):
        return f"Kapı hattı açık. Son hareket {_state['last_motion']}."
    return "Kapı hattı açık. Şu an belirgin hareket yok."


def pop_alert() -> str | None:
    text = _state.get("alert")
    _state["alert"] = None
    return text


def grab() -> tuple[bool, str]:
    src = url()
    if not src:
        return False, "Kapı adresi yok."
    FRAME.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.lower().startswith(("rtsp://", "rtsps://")):
            cmd = [
                "ffmpeg", "-y", "-rtsp_transport", "tcp", "-i", src,
                "-frames:v", "1", "-q:v", "5", str(FRAME),
            ]
            r = subprocess.run(cmd, capture_output=True, timeout=12)
            if r.returncode != 0 or not FRAME.exists():
                _state["error"] = "ffmpeg kare alamadı"
                return False, "Kapı görüntüsü alınamadı. RTSP adresini kontrol et."
        else:
            import urllib.request
            req = urllib.request.Request(src, headers={"User-Agent": "JarvisTR/4.3"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
            FRAME.write_bytes(data)
        _state["last_check"] = datetime.now().isoformat(timespec="seconds")
        _state["error"] = None
        _state["configured"] = True
        moved = _motion()
        if moved:
            stamp = datetime.now().strftime("%H:%M")
            _state["last_motion"] = stamp
            _state["alert"] = f"Kapıda hareket var, saat {stamp}."
        return True, "Tamam."
    except Exception as e:
        _state["error"] = str(e)[:120]
        return False, f"Kapıya ulaşılamadı: {e.__class__.__name__}."


def _motion() -> bool:
    if not FRAME.exists() or not PREV.exists():
        if FRAME.exists():
            PREV.write_bytes(FRAME.read_bytes())
        return False
    try:
        import numpy as np
        from pathlib import Path as _P
        a = np.fromfile(FRAME, dtype=np.uint8)
        b = np.fromfile(PREV, dtype=np.uint8)
        n = min(len(a), len(b), 12000)
        if n < 200:
            PREV.write_bytes(FRAME.read_bytes())
            return False
        diff = float(np.mean(np.abs(a[:n].astype(np.int16) - b[:n].astype(np.int16))))
        PREV.write_bytes(FRAME.read_bytes())
        return diff > 18.0
    except Exception:
        try:
            PREV.write_bytes(FRAME.read_bytes())
        except Exception:
            pass
        return False


def start(interval_sec: int = 12) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return

    def loop():
        _state["running"] = True
        while not _stop.is_set():
            if url():
                grab()
            _stop.wait(interval_sec)
        _state["running"] = False

    _stop.clear()
    _thread = threading.Thread(target=loop, name="jarvis-door", daemon=True)
    _thread.start()


def try_door(text: str, low: str) -> dict[str, Any] | None:
    if any(k in low for k in ("kapıya bak", "kapiya bak", "kapıda kim", "kapıda ne", "zile bak", "kapı kamer")):
        return {"reply": peek(), "intent": "kapi", "model": "tool:doorbell", "confidence": 1.0}
    if low.startswith("kapı adresi") or low.startswith("kapi adresi"):
        rest = text.split(None, 2)
        addr = rest[2] if len(rest) >= 3 else ""
        if not addr:
            return {"reply": "RTSP veya JPEG adresini söyle.", "intent": "kapi", "model": "tool:doorbell", "confidence": 1.0}
        set_url(addr)
        return {"reply": "Kapı adresini kaydettim. İzlemeye başladım.", "intent": "kapi", "model": "tool:doorbell", "confidence": 1.0}
    return None
