"""Çalışan Skills nesnesine kendini-kodlama kancası takar."""

from __future__ import annotations

from brain import normalize
import learned_skills
import selfcode

TRIGGERS = (
    "kendini gelistir",
    "kendini geliştir",
    "kodunu guncelle",
    "kodunu güncelle",
    "kendine kod yaz",
    "oz kodla",
    "öz kodla",
    "self improve",
    "dosyalarini guncelle",
    "dosyalarını güncelle",
)


def install(skills) -> None:
    orig = skills._prepare

    def wrapped(text: str):
        raw = (text or "").strip()
        low = normalize(raw)
        if raw and any(k in low for k in TRIGGERS):
            return {"direct": selfcode.cycle_now(reason=raw)}
        try:
            import importlib
            importlib.reload(learned_skills)
            hit = learned_skills.try_handle(raw, low)
        except Exception:
            hit = None
        if hit and isinstance(hit, dict) and hit.get("reply"):
            hit.setdefault("intent", "learned")
            hit.setdefault("model", "learned_skills")
            hit.setdefault("confidence", 1.0)
            return {"direct": hit}
        return orig(text)

    skills._prepare = wrapped
