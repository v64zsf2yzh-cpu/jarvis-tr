"""Jarvis çekirdek motoru — niyet yönlendirici + Gemini/Ollama + yerel araçlar."""

from __future__ import annotations

import ast
import operator
import re
import secrets
import string
from datetime import datetime
from typing import Any, Callable

import evolve
import gemini_client
import memory
import ollama_client
import tools
from brain import JarvisBrain, normalize, teach_qa, tokenize, train

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}

BASE_KNOWLEDGE = {
    "jarvis": "Jarvis, Iron Man tarzı kişisel asistandır. Türkçe konuşur; Gemini/Ollama + sıfırdan eğitilmiş niyet modeli kullanır.",
    "yapay zeka": "Yapay zeka, makinelerin öğrenme ve karar verme yetenekleridir.",
    "python": "Python, okunabilir sözdizimli bir programlama dilidir.",
    "iron man": "Iron Man, Tony Stark'ın zırhlı kimliğidir. Jarvis onun yapay zeka yardımcısıdır.",
    "türkiye": "Türkiye; başkenti Ankara, en büyük şehri İstanbul olan bir ülkedir.",
    "istanbul": "İstanbul, Boğaz ile iki kıtayı birleştiren Türkiye'nin en kalabalık şehridir.",
}

LOCAL_TAGS = {
    "saat", "tarih", "hesap", "hava", "sifre", "hatirla", "hatirlat", "sistem",
    "ad_kaydet", "yeniden_egit", "ceviri", "birim", "yazi", "rastgele", "saka",
    "motivasyon", "tesekkur", "selamlama", "veda", "kimlik", "yardim", "ipucu",
    "espri_durum", "ogret",
}


class Skills:
    def __init__(self, brain: JarvisBrain) -> None:
        self.brain = brain
        snap = memory.load()
        self.memory = memory.list_notes(80)
        self.user_name = snap.get("user_name")
        self._retrain_fn = None
        self.chat_history = []

    def set_retrain(self, fn):
        self._retrain_fn = fn

    def _refresh_knowledge(self) -> None:
        from brain import KNOWLEDGE_PATH, TAUGHT_PATH, load_json
        self.brain.knowledge = {
            **load_json(KNOWLEDGE_PATH, {}),
            **load_json(TAUGHT_PATH, {"knowledge": {}}).get("knowledge", {}),
        }
        snap = memory.load()
        self.memory = memory.list_notes(80)
        if snap.get("user_name"):
            self.user_name = snap["user_name"]

    def handle(self, text: str) -> dict[str, Any]:
        prepared = self._prepare(text)
        if prepared.get("direct"):
            out = prepared["direct"]
            evolve.observe(text, out.get("reply") or "", out.get("intent"))
            return out
        routed = self._route_local(text, prepared)
        if routed:
            self._remember_turn(text, routed["reply"])
            evolve.observe(text, routed["reply"], routed.get("intent"))
            return routed
        result = None
        if gemini_client.is_configured():
            result = gemini_client.chat(prepared["prompt"], self.chat_history)
            if result.get("ok") and result.get("reply"):
                reply = result["reply"]
                self._remember_turn(text, reply)
                evolve.observe(text, reply, "sohbet")
                return {"reply": reply, "intent": "sohbet", "confidence": 0.99, "model": result.get("model")}
        result = ollama_client.chat(prepared["prompt"], self.chat_history)
        if result.get("ok") and result.get("reply"):
            reply = result["reply"]
            self._remember_turn(text, reply)
            evolve.observe(text, reply, "sohbet")
            return {"reply": reply, "intent": "sohbet", "confidence": 0.99, "model": f"ollama:{result.get('model')}"}
        tag, conf = self.brain.classify(text)
        fallback = self._local_fallback(tag, text, prepared.get("kb"), result or {})
        self._remember_turn(text, fallback)
        evolve.observe(text, fallback, tag)
        return {"reply": fallback, "intent": tag, "confidence": round(conf, 3), "model": "local-fallback", "error": (result or {}).get("error")}

    def stream(self, text: str):
        prepared = self._prepare(text)
        if prepared.get("direct"):
            d = prepared["direct"]
            evolve.observe(text, d.get("reply") or "", d.get("intent"))
            yield {"type": "meta", "intent": d.get("intent"), "model": d.get("model")}
            yield {"type": "token", "token": d["reply"]}
            yield {"type": "done", "reply": d["reply"], "intent": d.get("intent"), "model": d.get("model")}
            return
        routed = self._route_local(text, prepared)
        if routed:
            self._remember_turn(text, routed["reply"])
            evolve.observe(text, routed["reply"], routed.get("intent"))
            yield {"type": "meta", "intent": routed.get("intent"), "model": routed.get("model")}
            yield {"type": "token", "token": routed["reply"]}
            yield {"type": "done", "reply": routed["reply"], "intent": routed.get("intent"), "model": routed.get("model")}
            return
        if gemini_client.is_configured():
            yield {"type": "meta", "intent": "sohbet", "model": "gemini"}
            full = ""; model = None; had_token = False
            for ev in gemini_client.chat_stream(prepared["prompt"], self.chat_history):
                if ev.get("error"):
                    break
                if ev.get("token"):
                    had_token = True
                    full += ev["token"]
                    model = ev.get("model") or model
                    yield {"type": "token", "token": ev["token"], "model": model}
                if ev.get("done") and (ev.get("reply") or full):
                    reply = (ev.get("reply") or full).strip()
                    self._remember_turn(text, reply)
                    evolve.observe(text, reply, "sohbet")
                    yield {"type": "done", "reply": reply, "intent": "sohbet", "model": ev.get("model") or model}
                    return
            if had_token and full.strip():
                self._remember_turn(text, full.strip())
                evolve.observe(text, full.strip(), "sohbet")
                yield {"type": "done", "reply": full.strip(), "intent": "sohbet", "model": model}
                return
        yield {"type": "meta", "intent": "sohbet", "model": "ollama"}
        full = ""; model = None
        for ev in ollama_client.chat_stream(prepared["prompt"], self.chat_history):
            if ev.get("error"):
                msg = "Zekâ motoruna ulaşılamadı. Gemini anahtarı veya Ollama gerekli.\n" + f"Detay: {ev['error']}"
                yield {"type": "token", "token": msg}
                yield {"type": "done", "reply": msg, "intent": "llm_offline", "model": "offline"}
                self._remember_turn(text, msg)
                evolve.observe(text, msg, "llm_offline")
                return
            if ev.get("token"):
                full += ev["token"]
                model = ev.get("model") or model
                yield {"type": "token", "token": ev["token"], "model": model}
            if ev.get("done"):
                reply = (ev.get("reply") or full).strip()
                self._remember_turn(text, reply)
                evolve.observe(text, reply, "sohbet")
                yield {"type": "done", "reply": reply, "intent": "sohbet", "model": f"ollama:{ev.get('model') or model}"}

    def _prepare(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"direct": {"reply": "Bir şey söyleyin efendim.", "intent": "bos", "confidence": 1.0, "model": "local"}}
        taught = self._try_inline_teach(text)
        if taught:
            return {"direct": taught}
        low = normalize(text)
        local = self._try_local_command(text, low)
        if local:
            self._remember_turn(text, local["reply"])
            return {"direct": local}
        if any(k in low for k in ("yeniden egit", "yeniden eğit", "retrain", "modeli egit", "sıfırdan egit")):
            return {"direct": {"reply": self._yeniden_egit(text), "intent": "yeniden_egit", "confidence": 1.0, "model": "trainer"}}
        self._refresh_knowledge()
        kb = self._knowledge_lookup(text)
        tool_context = self._build_tool_context(text, low)
        if kb:
            tool_context.append(f"Yerel bilgi bankası: {kb}")
        prompt = text
        if tool_context:
            prompt = "Aşağıdaki güncel araç verilerini kullanarak Türkçe cevap ver.\n" + "\n".join(f"- {c}" for c in tool_context) + f"\n\nKullanıcı: {text}"
        return {"prompt": prompt, "kb": kb}

    def _route_local(self, text: str, prepared: dict[str, Any]):
        tag, conf = self.brain.classify(text)
        if tag not in LOCAL_TAGS or conf < 0.42:
            return None
        handled = self._dispatch_tag(tag, text, normalize(text), prepared.get("kb"))
        if handled:
            handled.setdefault("confidence", round(conf, 3))
            return handled
        return None

    def _dispatch_tag(self, tag, text, low, kb):
        if tag in {"saat", "tarih", "hesap", "sifre", "hatirla", "hatirlat", "sistem", "ad_kaydet"}:
            return self._try_local_command(text, low)
        if tag == "hava":
            city = tools.extract_city(text, memory.load().get("city"))
            return {"reply": tools.weather(city), "intent": "hava", "model": "tool:hava"}
        if tag == "birim":
            conv = tools.convert_units(text)
            if conv:
                return {"reply": conv, "intent": "birim", "model": "tool:birim"}
        if tag == "ceviri":
            tr = tools.translate_lite(text)
            if tr:
                return {"reply": tr, "intent": "ceviri", "model": "tool:ceviri"}
            return None
        if tag == "yazi":
            out = tools.text_ops(text)
            if out:
                return {"reply": out, "intent": "yazi", "model": "tool:yazi"}
        if tag == "rastgele":
            out = tools.random_fun(text)
            if out:
                return {"reply": out, "intent": "rastgele", "model": "tool:rastgele"}
        if tag in {"saka", "motivasyon", "tesekkur", "selamlama", "veda", "kimlik", "yardim", "ipucu", "espri_durum", "ogret"}:
            canned = self.brain.pick_response(tag)
            if canned:
                if self.user_name and tag == "selamlama":
                    canned = canned.replace("efendim", self.user_name)
                return {"reply": canned, "intent": tag, "model": "local-intent"}
        if tag == "bilgi" and kb:
            return {"reply": kb, "intent": "bilgi", "model": "kb"}
        return None

    def _remember_turn(self, user, assistant):
        self.chat_history.append({"role": "user", "content": user})
        self.chat_history.append({"role": "assistant", "content": assistant})
        if len(self.chat_history) > 30:
            self.chat_history = self.chat_history[-30:]

    def _build_tool_context(self, text, low):
        ctx = []
        now = datetime.now()
        ctx.append(f"Şu anki saat: {now.strftime('%H:%M')}")
        ctx.append(f"Bugünün tarihi: {tools.GUNLER[now.weekday()]} {now.strftime('%d.%m.%Y')}")
        snap = memory.load()
        if snap.get("user_name") or self.user_name:
            ctx.append(f"Kullanıcı adı: {snap.get('user_name') or self.user_name}")
        if snap.get("city"):
            ctx.append(f"Kullanıcı şehri: {snap['city']}")
        notes = memory.list_notes(8)
        if notes:
            ctx.append("Kayıtlı notlar: " + "; ".join(notes))
        calc = self._extract_calc(text)
        if calc is not None:
            ctx.append(f"Hesap sonucu: {calc}")
        conv = tools.convert_units(text)
        if conv:
            ctx.append(f"Birim dönüşümü: {conv}")
        if any(k in low for k in ("hava", "sicaklik", "sıcaklık", "yagmur", "yağmur")):
            ctx.append("Hava: " + tools.weather(tools.extract_city(text, snap.get("city"))))
        ev = evolve.status()
        ctx.append(f"Öğrenme: {ev.get('learned', 0)} kayıt, kuyruk {ev.get('pending_learn', 0)}")
        return ctx

    def _try_local_command(self, text, low):
        if any(k in low for k in ("saat kac", "saat kaç", "saati soyle", "saati söyle", "şu an saat")):
            return {"reply": f"Şu an saat {datetime.now().strftime('%H:%M')}, efendim.", "intent": "saat", "confidence": 1.0, "model": "tool:saat"}
        if any(k in low for k in ("tarih ne", "bugunun tarihi", "bugünün tarihi", "hangi gundeyiz", "hangi gündeyiz", "gunlerden ne")):
            now = datetime.now()
            return {"reply": f"Bugün {tools.GUNLER[now.weekday()]}, {now.strftime('%d.%m.%Y')}.", "intent": "tarih", "confidence": 1.0, "model": "tool:tarih"}
        if any(k in low for k in ("hava nasil", "hava nasıl", "hava durumu", "hava raporu", "sicaklik", "sıcaklık")):
            city = tools.extract_city(text, memory.load().get("city"))
            return {"reply": tools.weather(city), "intent": "hava", "confidence": 1.0, "model": "tool:hava"}
        if any(k in low for k in ("sifre uret", "şifre üret", "parola olustur", "parola oluştur", "password")):
            m = re.search(r"(\d{1,2})", text)
            n = max(8, min(int(m.group(1)) if m else 16, 32))
            alphabet = string.ascii_letters + string.digits + "!@#$%*?-"
            pwd = "".join(secrets.choice(alphabet) for _ in range(n))
            return {"reply": f"Güçlü parola ({n}): {pwd}", "intent": "sifre", "confidence": 1.0, "model": "tool:sifre"}
        if low.startswith("hatirla") or low.startswith("hatırla") or "bunu not et" in low:
            cleaned = re.sub(r"\b(hatırla|hatirla|bunu not et|aklında tut|not al|kaydet)\b", "", text, flags=re.I).strip(" .,:;-")
            if cleaned:
                memory.add_note(cleaned)
                self.memory = memory.list_notes(80)
                return {"reply": f"Kaydedildi: «{cleaned}»", "intent": "hatirla", "confidence": 1.0, "model": "tool:hafiza"}
        if any(k in low for k in ("ne hatirliyorsun", "ne hatırlıyorsun", "notlarim", "notlarım", "hatirlat")):
            notes = memory.list_notes(12)
            if not notes:
                return {"reply": "Henüz notum yok. 'Hatırla ...' diyerek ekleyin.", "intent": "hatirlat", "confidence": 1.0, "model": "tool:hafiza"}
            return {"reply": "Notlarınız:\n" + "\n".join(f"• {m}" for m in notes), "intent": "hatirlat", "confidence": 1.0, "model": "tool:hafiza"}
        m = re.search(r"(?:benim adım|adım|ismim)\s+(.+)$", text, flags=re.I)
        if m:
            name = m.group(1).strip(" .!").title()
            self.user_name = name
            memory.set_profile(user_name=name)
            teach_qa("kullanıcı adı nedir", name, tag="profil")
            return {"reply": f"Memnun oldum, {name}. Bundan sonra size böyle hitap ederim.", "intent": "ad_kaydet", "confidence": 1.0, "model": "tool:ad"}
        if any(k in low for k in ("sistem durumu", "durum raporu", "status")):
            return {"reply": self._sistem_text(), "intent": "sistem", "confidence": 1.0, "model": "tool:sistem"}
        conv = tools.convert_units(text)
        if conv and any(k in low for k in ("km", "mil", "derece", "santigrat", "fahrenhayt", "kg", "pound", "inç", "inch", "çevir", "donustur", "dönüştür")):
            return {"reply": conv, "intent": "birim", "confidence": 1.0, "model": "tool:birim"}
        rnd = tools.random_fun(text)
        if rnd:
            return {"reply": rnd, "intent": "rastgele", "confidence": 1.0, "model": "tool:rastgele"}
        tx = tools.text_ops(text)
        if tx and any(k in low for k in ("büyük harf", "küçük harf", "ters çevir", "kaç kelime", "kaç harf")):
            return {"reply": tx, "intent": "yazi", "confidence": 1.0, "model": "tool:yazi"}
        if re.search(r"\d+\s*([+\-*/x×]|arti|artı|eksi|çarpı|carpi|bölü|bolu)\s*\d+", low):
            calc = self._extract_calc(text)
            if calc is not None:
                return {"reply": f"Hesap tamam. Sonuç: {calc}", "intent": "hesap", "confidence": 1.0, "model": "tool:hesap"}
        return None

    def _extract_calc(self, text):
        expr = text.lower()
        for pat, rep in [(r"\barti\b|\bartı\b", "+"), (r"\beksi\b", "-"), (r"\bçarpı\b|\bcarpi\b|\bx\b", "*"), (r"\bbölü\b|\bbolu\b", "/"), (r"\büzeri\b|\buzeri\b", "**")]:
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
            def _eval(n):
                if isinstance(n, ast.Expression): return _eval(n.body)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return float(n.value)
                if isinstance(n, ast.BinOp): return float(_OPS[type(n.op)](_eval(n.left), _eval(n.right)))
                if isinstance(n, ast.UnaryOp): return float(_OPS[type(n.op)](_eval(n.operand)))
                raise ValueError("bad")
            result = _eval(node)
            return str(int(result)) if result == int(result) else f"{result:.4f}".rstrip("0").rstrip(".")
        except Exception:
            return None

    def _sistem_text(self):
        m = self.brain.meta
        gem = gemini_client.status(); oll = ollama_client.status(); ev = evolve.status()
        if gem.get("configured"): brain = f"Gemini açık · {gem.get('model')}"
        elif oll.get("available"): brain = f"Ollama açık · {oll.get('active_model')}"
        else: brain = "Zekâ motoru kapalı — GEMINI_API_KEY veya ollama gerekli"
        train_s = "eğitim sürüyor" if ev.get("training") else "eğitim bekliyor"
        return (f"Jarvis çevrimiçi. Niyet modeli doğruluk {m.get('accuracy', 0):.0%}. "
                f"Not: {len(memory.list_notes(80))}. Öğreti: {len(self.brain.knowledge)}. {brain}. "
                f"Kendini geliştirme açık ({train_s}, kuyruk {ev.get('pending_learn', 0)}).")

    def _knowledge_lookup(self, text):
        low = normalize(text)
        bank = {**BASE_KNOWLEDGE, **self.brain.knowledge}
        for key, val in sorted(bank.items(), key=lambda kv: -len(kv[0])):
            if len(key) >= 3 and key in low:
                return val
        return None

    def _try_inline_teach(self, text):
        m = re.match(r"^\s*(?:öğret|ogret)\s*[:\-]?\s*(.+?)\s*(?:\||=>|->)\s*(.+)\s*$", text, flags=re.I | re.DOTALL)
        if not m:
            return None
        q, a = m.group(1).strip(), m.group(2).strip()
        tag = "ogretilen_" + "_".join(tokenize(q)[:3])[:40] or "ogretilen"
        info = teach_qa(q, a, tag=tag)
        self._refresh_knowledge()
        memory.enqueue_learn(q, a, tag=tag)
        return {"reply": f"Öğrendim: «{info['question']}» → «{info['answer']}». Arka planda modele işleyeceğim.", "intent": "ogret", "confidence": 1.0, "model": "teacher", "taught": info}

    def _yeniden_egit(self, _t):
        if evolve.status().get("training"):
            return "Eğitim zaten arka planda çalışıyor. Bitince doğruluk güncellenecek."
        fn = self._retrain_fn or (lambda: train(epochs=1200))
        if evolve.background_train(fn):
            return "Yeniden eğitimi arka planda başlattım. Sohbete devam edebilirsiniz."
        if self._retrain_fn:
            meta = self._retrain_fn()
        else:
            meta = train(epochs=1200)
            self.brain.reload()
        return f"Yeniden eğitim bitti. Doğruluk {meta.get('accuracy', 0):.0%}, örnek {meta.get('samples')}."

    def _local_fallback(self, tag, text, kb, oll):
        if kb:
            return kb
        canned = self.brain.pick_response(tag)
        if canned and tag not in {"bilinmeyen", "bilgi"}:
            return canned
        err = oll.get("error") or "Ollama yok"
        return ("Şu an genel zekâ motorum (Ollama/Gemini) kapalı veya model yok.\n\n"
                "VPS'te şunu çalıştırın:\n  ollama pull llama3.2\n  ollama serve\n  cd ~/jarvis-tr && git pull && python3 app.py\n\n"
                f"Detay: {err}")
