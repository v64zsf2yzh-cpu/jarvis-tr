"""Çalışan Skills nesnesine kanca takar."""

from __future__ import annotations

from brain import normalize
import fx
import learned_skills
import selfcode
import tools

TRIGGERS = (
    "kendini gelistir", "kendini geliştir", "kodunu guncelle", "kodunu güncelle",
    "kendine kod yaz", "oz kodla", "öz kodla", "self improve",
    "dosyalarini guncelle", "dosyalarını güncelle",
)


def install(skills) -> None:
    orig = skills._prepare

    def wrapped(text: str):
        raw = (text or "").strip()
        low = normalize(raw)
        if raw and any(k in low for k in TRIGGERS):
            return {"direct": selfcode.cycle_now(reason=raw)}
        hit = tools.try_reminder(raw, low) or fx.try_fx(raw, low)
        if hit:
            return {"direct": hit}
        try:
            import importlib
            importlib.reload(learned_skills)
            learned = learned_skills.try_handle(raw, low)
        except Exception:
            learned = None
        if learned and isinstance(learned, dict) and learned.get("reply"):
            learned.setdefault("intent", "learned")
            learned.setdefault("model", "learned_skills")
            learned.setdefault("confidence", 1.0)
            return {"direct": learned}
        return orig(text)

    skills._prepare = wrapped
