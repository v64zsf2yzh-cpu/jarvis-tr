"""Çalışan Skills nesnesine kanca takar."""

from __future__ import annotations

from brain import normalize
import doorbell
import extra
import fx
import news
import persona
import research
import selfcode
import tools
import wiki

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
        hit = (
            doorbell.try_door(raw, low)
            or persona.try_persona(raw, low)
            or extra.try_extra(raw, low)
            or tools.try_reminder(raw, low)
            or fx.try_fx(raw, low)
            or news.try_news(raw, low)
            or research.try_research(raw, low)
            or wiki.try_wiki(raw, low)
        )
        if hit:
            return {"direct": hit}
        for modname in ("learned_skills", "autonomy"):
            try:
                import importlib
                mod = importlib.import_module(modname)
                importlib.reload(mod)
                learned = mod.try_handle(raw, low)
            except Exception:
                learned = None
            if learned and isinstance(learned, dict) and learned.get("reply"):
                learned.setdefault("intent", modname)
                learned.setdefault("model", modname)
                learned.setdefault("confidence", 1.0)
                return {"direct": learned}
        return orig(text)

    skills._prepare = wrapped
