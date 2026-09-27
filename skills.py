"""
Jarvis çekirdek motoru — Ollama ana beyin, yerel beceriler araç olarak.
"""

from __future__ import annotations

import ast
import operator
import random
import re
import secrets
import string
from datetime import datetime
from typing import Any, Callable

import ollama_client
from brain import JarvisBrain, normalize, teach_qa, tokenize, train

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

BASE_KNOWLEDGE: dict[str, str] = {
    "jarvis": "Jarvis, Iron Man tarzı kişisel asistandır. Bu sürüm Türkçe konuşur; Ollama LLM + sıfırdan eğitilmiş niyet modeli kullanır.",
    "yapay zeka": "Yapay zeka, makinelerin öğrenme ve karar verme yetenekleridir.",
    "python": "Python, okunabilir sözdizimli bir programlama dilidir.",
    "iron man": "Iron Man, Tony Stark'ın zırhlı kimliğidir. Jarvis onun yapay zeka yardımcısıdır.",
    "türkiye": "Türkiye; başkenti Ankara, en büyük şehri İstanbul olan bir ülkedir.",
    "istanbul": "İstanbul, Boğaz ile iki kıtayı birleştiren Türkiye'nin en kalabalık şehridir.",
}


class Skills:
    def __init__(self, brain: JarvisBrain) -> None:
        self.brain = brain
        self.memory: list[str] = []
        self.user_name: str | None = None
        self._retrain_fn: Callable[[], dict[str, Any]] | None = None
        self.chat_history: list[dict[str, str]] = []

    def set_retrain(self, fn: Callable[[], dict[str, Any]]) -> None:
        self._retrain_fn = fn

    def _refresh_knowledge(self) -> None:
        from brain import KNOWLEDGE_PATH, TAUGHT_PATH, load_json

        self.brain.knowledge = {
            **load_json(KNOWLEDGE_PATH, {}),
            **load_json(TAUGHT_PATH, {"knowledge": {}}).get("knowledge", {}),
        }

    def handle(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {"reply": "Bir şey söyleyin efendim.", "intent": "bos", "confidence": 1.0, "model": "local"}

        # Öğret komutu
        taught = self._try_inline_teach(text)
        if taught:
            return taught

        low = normalize(text)

        # Yerel hızlı komutlar (LLM'siz)
        local = self._try_local_command(text, low)
        if local:
            self._remember_turn(text, local["reply"])
            return local

        # Yeniden eğit
        if any(k in low for k in ("yeniden egit", "yeniden eğit", "retrain", "modeli egit", "sıfırdan egit")):
            reply = self._yeniden_egit(text)
            return {"reply": reply, "intent": "yeniden_egit", "confidence": 1.0, "model": "trainer"}

        # Öğretilmiş bilgi
        self._refresh_knowledge()
        kb = self._knowledge_lookup(text)
        tool_context = self._build_tool_context(text, low)
        if kb:
            tool_context.append(f"Yerel bilgi bankası: {kb}")

        # Ana beyin: Ollama
        prompt = text
        if tool_context:
            prompt = (
                "Aşağıdaki güncel araç verilerini kullanarak Türkçe cevap ver.\n"
                + "\n".join(f"- {c}" for c in tool_context)
                + f"\n\nKullanıcı: {text}"
            )

        result = ollama_client.chat(prompt, self.chat_history)
        if result.get("ok") and result.get("reply"):
            reply = result["reply"]
            self._remember_turn(text, reply)
            return {
                "reply": reply,
                "intent": "sohbet",
                "confidence": 0.99,
                "model": f"ollama:{result.get('model')}",
            }

        # Ollama yoksa: niyet modeli + yerel yanıt
        tag, conf = self.brain.classify(text)
        fallback = self._local_fallback(tag, text, kb, result)
        self._remember_turn(text, fallback)
        return {
            "reply": fallback,
            "intent": tag,
            "confidence": round(conf, 3),
            "model": "local-fallback",
            "error": result.get("error"),
        }

    def _remember_turn(self, user: str, assistant: str) -> None:
        self.chat_history.append({"role": "user", "content": user})
        self.chat_history.append({"role": "assistant", "content": assistant})
        if len(self.chat_history) > 30:
            self.chat_history = self.chat_history[-30:]

    def _build_tool_context(self, text: str, low: str) -> list[str]:
        ctx: list[str] = []
        now = datetime.now()
        ctx.append(f"Şu anki saat: {now.strftime('%H:%M')}")
        gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        ctx.append(f"Bugünün tarihi: {gunler[now.weekday()]} {now.strftime('%d.%m.%Y')}")
        if self.user_name:
            ctx.append(f"Kullanıcı adı: {self.user_name}")
        if self.memory:
            ctx.append("Kayıtlı notlar: " + "; ".join(self.memory[-8:]))
        calc = self._extract_calc(text)
        if calc is not None:
            ctx.append(f"Hesap sonucu: {calc}")
        oll = ollama_client.status()
        if oll.get("available"):
            ctx.append(f"Aktif LLM modeli: {oll.get('active_model')}")
        return ctx

    def _try_local_command(self, text: str, low: str) -> dict[str, Any] | None:
        # Saat
        if any(k in low for k in ("saat kac", "saat kaç", "saati soyle", "saati söyle", "şu an saat")):
            return {
                "reply": f"Şu an saat {datetime.now().strftime('%H:%M')}, efendim.",
                "intent": "saat",
                "confidence": 1.0,
                "model": "tool:saat",
            }
        # Tarih
        if any(k in low for k in ("tarih ne", "bugunun tarihi", "bugünün tarihi", "hangi gundeyiz", "hangi gündeyiz", "gunlerden ne")):
            gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
            now = datetime.now()
            return {
                "reply": f"Bugün {gunler[now.weekday()]}, {now.strftime('%d.%m.%Y')}.",
                "intent": "tarih",
                "confidence": 1.0,
                "model": "tool:tarih",
            }
        # Şifre
        if any(k in low for k in ("sifre uret", "şifre üret", "parola olustur", "parola oluştur", "password")):
            m = re.search(r"(\d{1,2})", text)
            n = max(8, min(int(m.group(1)) if m else 16, 32))
            alphabet = string.ascii_letters + string.digits + "!@#$%*?-"
            pwd = "".join(secrets.choice(alphabet) for _ in range(n))
            return {
                "reply": f"Güçlü parola ({n}): {pwd}",
                "intent": "sifre",
                "confidence": 1.0,
                "model": "tool:sifre",
            }
        # Not kaydet
        if low.startswith("hatirla") or low.startswith("hatırla") or "bunu not et" in low:
            cleaned = re.sub(
                r"\b(hatırla|hatirla|bunu not et|aklında tut|not al|kaydet)\b",
                "",
                text,
                flags=re.I,
            ).strip(" .,:;-")
            if cleaned:
                self.memory.append(cleaned)
                return {
                    "reply": f"Kaydedildi: «{cleaned}»",
                    "intent": "hatirla",
                    "confidence": 1.0,
                    "model": "tool:hafiza",
                }
        if any(k in low for k in ("ne hatirliyorsun", "ne hatırlıyorsun", "notlarim", "notlarım", "hatirlat")):
            if not self.memory:
                return {
                    "reply": "Henüz notum yok. 'Hatırla ...' diyerek ekleyin.",
                    "intent": "hatirlat",
                    "confidence": 1.0,
                    "model": "tool:hafiza",
                }
            notes = "\n".join(f"• {m}" for m in self.memory[-12:])
            return {
                "reply": f"Notlarınız:\n{notes}",
                "intent": "hatirlat",
                "confidence": 1.0,
                "model": "tool:hafiza",
            }
        # Ad
        m = re.search(r"(?:benim adım|adım|ismim)\s+(.+)$", text, flags=re.I)
        if m:
            name = m.group(1).strip(" .!")
            self.user_name = name.title()
            teach_qa("kullanıcı adı nedir", self.user_name)
            return {
                "reply": f"Memnun oldum, {self.user_name}. Bundan sonra size böyle hitap ederim.",
                "intent": "ad_kaydet",
                "confidence": 1.0,
                "model": "tool:ad",
            }
        # Sistem
        if any(k in low for k in ("sistem durumu", "durum raporu", "status")):
            return {
                "reply": self._sistem_text(),
                "intent": "sistem",
                "confidence": 1.0,
                "model": "tool:sistem",
            }
        # Saf matematik
        if re.search(r"\d+\s*([+\-*/x×]|arti|artı|eksi|çarpı|carpi|bölü|bolu)\s*\d+", low):
            calc = self._extract_calc(text)
            if calc is not None:
                return {
                    "reply": f"Hesap tamam. Sonuç: {calc}",
                    "intent": "hesap",
                    "confidence": 1.0,
                    "model": "tool:hesap",
                }
        return None

    def _extract_calc(self, text: str) -> str | None:
        expr = text.lower()
        for pat, rep in [
            (r"\barti\b|\bartı\b", "+"),
            (r"\beksi\b", "-"),
            (r"\bçarpı\b|\bcarpi\b|\bx\b", "*"),
            (r"\bbölü\b|\bbolu\b", "/"),
            (r"\büzeri\b|\buzeri\b", "**"),
        ]:
            expr = re.sub(pat, rep, expr)
        match = re.search(r"[\d\.\s\+\-\*\/\(\)]+", expr)
        if not match:
            return None
        raw = re.sub(r"\s+", "", match.group(0))
        raw = re.sub(r"[^0-9\.\+\-\*\/\(\)]", "", raw)
        if not raw or not re.search(r"\d", raw):
            return None
        try:
            node = ast.parse(raw, mode="eval")

            def _eval(n: ast.AST) -> float:
                if isinstance(n, ast.Expression):
                    return _eval(n.body)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                    return float(n.value)
                if isinstance(n, ast.BinOp):
                    op = _OPS[type(n.op)]
                    return float(op(_eval(n.left), _eval(n.right)))
                if isinstance(n, ast.UnaryOp):
                    op = _OPS[type(n.op)]
                    return float(op(_eval(n.operand)))
                raise ValueError("bad")

            result = _eval(node)
            return str(int(result)) if result == int(result) else f"{result:.4f}".rstrip("0").rstrip(".")
        except Exception:
            return None

    def _sistem_text(self) -> str:
        m = self.brain.meta
        oll = ollama_client.status()
        oll_line = (
            f"Ollama açık · {oll.get('active_model')}"
            if oll.get("available")
            else "Ollama kapalı — genel sorular için: ollama pull llama3.2"
        )
        return (
            f"Jarvis çevrimiçi. Niyet modeli doğruluk {m.get('accuracy', 0):.0%}. "
            f"Not: {len(self.memory)}. Öğreti: {len(self.brain.knowledge)}. {oll_line}."
        )

    def _knowledge_lookup(self, text: str) -> str | None:
        low = normalize(text)
        bank = {**BASE_KNOWLEDGE, **self.brain.knowledge}
        for key, val in sorted(bank.items(), key=lambda kv: -len(kv[0])):
            if len(key) >= 3 and key in low:
                return val
        return None

    def _try_inline_teach(self, text: str) -> dict[str, Any] | None:
        m = re.match(
            r"^\s*(?:öğret|ogret)\s*[:\-]?\s*(.+?)\s*(?:\||=>|->)\s*(.+)\s*$",
            text,
            flags=re.I | re.DOTALL,
        )
        if not m:
            return None
        info = teach_qa(m.group(1).strip(), m.group(2).strip())
        self._refresh_knowledge()
        return {
            "reply": f"Öğrendim: «{info['question']}» → «{info['answer']}». İsterseniz 'yeniden eğit' deyin.",
            "intent": "ogret",
            "confidence": 1.0,
            "model": "teacher",
            "taught": info,
        }

    def _yeniden_egit(self, _t: str) -> str:
        if self._retrain_fn:
            meta = self._retrain_fn()
        else:
            meta = train(epochs=1200)
            self.brain.reload()
        return (
            f"Yeniden eğitim bitti. Doğruluk {meta.get('accuracy', 0):.0%}, "
            f"örnek {meta.get('samples')}."
        )

    def _local_fallback(self, tag: str, text: str, kb: str | None, oll: dict[str, Any]) -> str:
        if kb:
            return kb
        canned = self.brain.pick_response(tag)
        if canned and tag not in {"bilinmeyen", "bilgi"}:
            return canned
        err = oll.get("error") or "Ollama yok"
        return (
            "Şu an genel zekâ motorum (Ollama) kapalı veya model yok.\n\n"
            "VPS'te şunu çalıştırın:\n"
            "  ollama pull llama3.2\n"
            "  ollama serve\n"
            "  cd ~/jarvis-tr && git pull && python3 app.py\n\n"
            f"Detay: {err}"
        )
