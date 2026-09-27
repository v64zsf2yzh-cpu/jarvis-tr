"""Jarvis beceri motoru — niyetlere göre Türkçe eylem / yanıt."""

from __future__ import annotations

import ast
import operator
import random
import re
import secrets
import string
from datetime import datetime
from typing import Any, Callable

from brain import JarvisBrain, normalize, teach_qa, tokenize, train
import ollama_client

# Bu niyetler beceri motorunda kalsın; diğerleri / bilinmeyen Ollama'ya gidebilir
SKILL_TAGS = {
    "saat",
    "tarih",
    "hesap",
    "sistem",
    "hatirla",
    "hatirlat",
    "yeniden_egit",
    "ceviri",
    "birim",
    "sifre",
    "yazi",
    "rastgele",
    "ad_kaydet",
    "saka",
    "motivasyon",
    "tesekkur",
    "selamlama",
    "veda",
    "kimlik",
    "yardim",
    "espri_durum",
    "hava",
    "ipucu",
    "ogret",
}

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
    "jarvis": "Jarvis, Iron Man tarzı kişisel asistanınızdır. Bu sürüm Türkçe konuşur; beyni NumPy ile sıfırdan eğitilir ve sizin öğrettiklerinizle gelişir.",
    "yapay zeka": "Yapay zeka, makinelerin öğrenme ve karar verme yetenekleridir. Ben küçük ölçekli, yerelde eğitilmiş bir örneğim.",
    "python": "Python, okunabilir sözdizimli bir programlama dilidir. Jarvis'in beyni Python + NumPy ile yazıldı.",
    "iron man": "Iron Man, Tony Stark'ın zırhlı kimliğidir. Jarvis onun yapay zeka yardımcısıdır.",
    "türkiye": "Türkiye; başkenti Ankara, en büyük şehri İstanbul olan bir ülkedir.",
    "istanbul": "İstanbul, Boğaz ile iki kıtayı birleştiren Türkiye'nin en kalabalık şehridir.",
    "mars": "Mars, Güneş Sistemi'nin dördüncü gezegenidir; kızıl rengi demir oksitten gelir.",
    "sinir agi": "Sinir ağı, birbirine bağlı katmanlardan oluşan bir öğrenme modelidir. Jarvis niyetleri böyle anlar.",
    "makine ogrenmesi": "Makine öğrenmesi, örneklerden örüntü çıkarmaktır. Benim ağırlıklarım Türkçe örneklerle sıfırdan ayarlandı.",
}

DICT_TR_EN: dict[str, str] = {
    "merhaba": "hello",
    "selam": "hi",
    "güle güle": "goodbye",
    "teşekkürler": "thank you",
    "lütfen": "please",
    "evet": "yes",
    "hayır": "no",
    "su": "water",
    "ekmek": "bread",
    "kitap": "book",
    "bilgisayar": "computer",
    "yapay zeka": "artificial intelligence",
    "saat": "hour / clock",
    "gün": "day",
    "gece": "night",
    "arkadaş": "friend",
    "sevgi": "love",
    "dünya": "world",
    "güneş": "sun",
    "ay": "moon",
    "yıldız": "star",
    "kod": "code",
    "öğrenmek": "to learn",
    "yardım": "help",
}

DICT_EN_TR = {v.split(" / ")[0]: k for k, v in DICT_TR_EN.items()}

# Net anahtar kelimeler — sinir ağından önce kesin yönlendirme
KEYWORD_ROUTES: list[tuple[list[str], str]] = [
    (["yeniden eğit", "tekrar eğit", "modeli eğit", "sıfırdan eğit", "retrain"], "yeniden_egit"),
    (["şifre üret", "parola oluştur", "güçlü şifre", "password üret", "güvenli parola"], "sifre"),
    (["yazı tura", "tura mı", "zar at", "rastgele sayı"], "rastgele"),
    (["çevir ", "çeviri", "tercüme", "ingilizcesi", "türkçesi", "translate"], "ceviri"),
    (["km", "mil", "santigrat", "fahrenhayt", "pound", "inch", "birim"], "birim"),
    (["hatırla", "not et", "aklında tut", "hafızana yaz", "not al"], "hatirla"),
    (["ne hatırlıyorsun", "notlarım", "notları göster", "hafızanı", "hatırlat"], "hatirlat"),
    (["sistem durumu", "durum raporu", "sağlık kontrolü", "diagnostik"], "sistem"),
    (["benim adım", "ismim", "adım ", "beni şöyle çağır", "bana şöyle hitap"], "ad_kaydet"),
    (["büyük harf", "küçük harf", "ters çevir", "kelime sayısı", "karakter sayısı"], "yazi"),
    (["saat kaç", "saati söyle", "şu an saat"], "saat"),
    (["bugün günlerden", "tarih ne", "bugünün tarihi", "hangi gündeyiz"], "tarih"),
]


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

    def _keyword_route(self, text: str) -> str | None:
        low = normalize(text)
        for keys, tag in KEYWORD_ROUTES:
            for k in keys:
                if normalize(k) in low:
                    return tag
        # matematik ifadesi
        if re.search(r"\d+\s*([+\-*/x×]|arti|artı|eksi|çarpı|carpi|bölü|bolu)\s*\d+", low):
            return "hesap"
        return None

    def _ask_llm(self, text: str) -> dict[str, Any] | None:
        result = ollama_client.chat(text, self.chat_history)
        if not result.get("ok") or not result.get("reply"):
            return {
                "reply": self._llm_fail_message(result),
                "intent": "llm_offline",
                "confidence": 0.0,
                "model": "ollama-offline",
                "error": result.get("error"),
            }
        reply = result["reply"]
        self.chat_history.append({"role": "user", "content": text})
        self.chat_history.append({"role": "assistant", "content": reply})
        if len(self.chat_history) > 24:
            self.chat_history = self.chat_history[-24:]
        return {
            "reply": reply,
            "intent": "genel_soru",
            "confidence": 0.95,
            "model": f"ollama:{result.get('model')}",
        }

    def _llm_fail_message(self, result: dict[str, Any]) -> str:
        err = result.get("error") or "bilinmeyen hata"
        return (
            "Genel soru motoruna (Ollama) bağlanamadım. "
            "VPS'te şunları çalıştırın:\n"
            "  ollama serve\n"
            "  ollama pull llama3.2\n"
            f"Detay: {err}"
        )

    def _should_use_llm(self, tag: str, confidence: float, text: str) -> bool:
        if tag in {"bilinmeyen", "bilgi"}:
            return True
        # Soru cümleleri / uzun serbest sohbet
        low = text.lower().strip()
        if tag not in SKILL_TAGS and confidence < 0.55:
            return True
        if any(w in low for w in ("nedir", "nasıl", "neden", "kimdir", "anlat", "açıkla", "?")):
            if tag not in {"saat", "tarih", "hesap", "sifre", "birim", "ceviri", "hatirla", "hatirlat", "yeniden_egit", "sistem"}:
                return True
        return False

    def handle(self, text: str) -> dict[str, Any]:
        # Doğrudan öğret komutu (niyet beklemeden)
        taught = self._try_inline_teach(text)
        if taught:
            return taught

        # Öğretilmiş bilgi bankası (yüksek öncelik)
        self._refresh_knowledge()
        kb = self._knowledge_lookup(text)
        if kb:
            return {
                "reply": kb,
                "intent": "bilgi_bankasi",
                "confidence": 1.0,
                "model": "jarvis-numpy-mlp-v2",
            }

        tag = self._keyword_route(text)
        confidence = 0.99
        if not tag:
            tag, confidence = self.brain.classify(text)

        # Genel sorular → Ollama
        if self._should_use_llm(tag, confidence, text):
            llm = self._ask_llm(text)
            if llm:
                return llm

        reply = self._dispatch(tag, text)
        if self.user_name and tag in {"selamlama", "espri_durum"} and self.user_name not in reply:
            reply = f"{self.user_name}, {reply[0].lower() + reply[1:]}" if reply else reply

        # Kısa sohbet geçmişine beceri yanıtlarını da ekle (bağlam için)
        if tag in {"selamlama", "espri_durum", "kimlik", "yardim"}:
            self.chat_history.append({"role": "user", "content": text})
            self.chat_history.append({"role": "assistant", "content": reply})

        return {
            "reply": reply,
            "intent": tag,
            "confidence": round(confidence, 3),
            "model": "jarvis-numpy-mlp-v2-from-scratch",
        }

    def _try_inline_teach(self, text: str) -> dict[str, Any] | None:
        # Formats: "öğret soru | cevap" or "öğret: soru => cevap"
        m = re.match(
            r"^\s*(?:öğret|ogret)\s*[:\-]?\s*(.+?)\s*(?:\||=>|->)\s*(.+)\s*$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        q, a = m.group(1).strip(), m.group(2).strip()
        info = teach_qa(q, a)
        self._refresh_knowledge()
        return {
            "reply": (
                f"Öğrendim. «{info['question']}» → «{info['answer']}». "
                "Kalıcı model güncellemesi için «yeniden eğit» deyin."
            ),
            "intent": "ogret",
            "confidence": 1.0,
            "model": "teacher",
            "taught": info,
        }

    def _knowledge_lookup(self, text: str) -> str | None:
        low = normalize(text)
        bank = {**BASE_KNOWLEDGE, **self.brain.knowledge}
        # tam / kısmi anahtar
        for key, val in sorted(bank.items(), key=lambda kv: -len(kv[0])):
            if len(key) >= 3 and key in low:
                return val
        m = re.search(r"(.+?)\s+nedir\??$", low)
        if m:
            topic = m.group(1).strip()
            for key, val in bank.items():
                if key in topic or topic in key:
                    return val
        return None

    def _dispatch(self, tag: str, text: str) -> str:
        handlers = {
            "saat": self._saat,
            "tarih": self._tarih,
            "hesap": self._hesap,
            "sistem": self._sistem,
            "hatirla": self._hatirla,
            "hatirlat": self._hatirlat,
            "bilgi": self._bilgi,
            "yeniden_egit": self._yeniden_egit,
            "ceviri": self._ceviri,
            "birim": self._birim,
            "sifre": self._sifre,
            "yazi": self._yazi,
            "rastgele": self._rastgele,
            "ad_kaydet": self._ad_kaydet,
            "ogretilen": self._ogretilen,
        }
        if tag in handlers:
            return handlers[tag](text)
        if tag == "bilinmeyen":
            return self._fallback(text)
        canned = self.brain.pick_response(tag)
        return canned or self._fallback(text)

    def _saat(self, _t: str) -> str:
        return f"Şu an saat {datetime.now().strftime('%H:%M')}, efendim."

    def _tarih(self, _t: str) -> str:
        gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        now = datetime.now()
        return f"Bugün {gunler[now.weekday()]}, {now.strftime('%d.%m.%Y')}."

    def _safe_eval(self, expr: str) -> float:
        node = ast.parse(expr, mode="eval")

        def _eval(n: ast.AST) -> float:
            if isinstance(n, ast.Expression):
                return _eval(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return float(n.value)
            if isinstance(n, ast.BinOp):
                op = _OPS.get(type(n.op))
                if not op:
                    raise ValueError("op")
                return float(op(_eval(n.left), _eval(n.right)))
            if isinstance(n, ast.UnaryOp):
                op = _OPS.get(type(n.op))
                if not op:
                    raise ValueError("op")
                return float(op(_eval(n.operand)))
            raise ValueError("bad")

        return _eval(node)

    def _hesap(self, text: str) -> str:
        expr = text.lower()
        for pat, rep in [
            (r"\barti\b|\bartı\b", "+"),
            (r"\beksi\b", "-"),
            (r"\bçarpı\b|\bcarpi\b|\bx\b", "*"),
            (r"\bbölü\b|\bbolu\b", "/"),
            (r"\büzeri\b|\buzeri\b", "**"),
        ]:
            expr = re.sub(pat, rep, expr)
        match = re.search(r"[\d\.\s\+\-\*\/\(\)%]+", expr)
        if not match:
            return "Örnek: 12 çarpı 8 veya (45 + 15) / 3"
        raw = match.group(0).replace("%", "/100")
        raw = re.sub(r"[^0-9\.\+\-\*\/\(\)\s]", "", raw)
        raw = re.sub(r"\s+", "", raw)
        try:
            result = self._safe_eval(raw)
            s = str(int(result)) if result == int(result) else f"{result:.4f}".rstrip("0").rstrip(".")
            return f"Hesap tamam. Sonuç: {s}"
        except Exception:
            return "Bu işlemi güvenli şekilde hesaplayamadım."

    def _sistem(self, _t: str) -> str:
        m = self.brain.meta
        oll = ollama_client.status()
        oll_line = (
            f"Ollama: açık · model {oll.get('active_model')}"
            if oll.get("available")
            else "Ollama: kapalı (genel sorular için ollama pull llama3.2)"
        )
        return (
            "Durum raporu: birimler çevrimiçi. "
            f"Niyet modeli sıfırdan (doğruluk {m.get('accuracy', 0):.0%}). "
            f"{m.get('samples', '?')} örnek · {len(self.brain.tags)} niyet. "
            f"Not: {len(self.memory)} · öğreti: {len(self.brain.knowledge)}. "
            f"{oll_line}."
        )

    def _bilgi(self, text: str) -> str:
        hit = self._knowledge_lookup(text)
        if hit:
            return hit
        llm = self._ask_llm(text)
        if llm and llm.get("intent") == "genel_soru":
            return llm["reply"]
        return llm["reply"] if llm else (
            "Bilgi bankamda kayıt yok. Ollama ile genel cevap için modeli kurun."
        )

    def _fallback(self, text: str) -> str:
        llm = self._ask_llm(text)
        if llm:
            return llm["reply"]
        return random.choice(
            [
                "Tam anlayamadım. 'yardım' yazın veya Ollama modelini kurun.",
                "Düşük güven. Örnekler: saat kaç, 12 çarpı 7, veya herhangi bir genel soru (Ollama ile).",
            ]
        )

    def _hatirla(self, text: str) -> str:
        cleaned = re.sub(
            r"\b(hatırla|hatirla|bunu not et|aklında tut|aklinda tut|kaydet|not al|unutma|"
            r"bunu hatırla|hafızana yaz|hafizana yaz|not tut|sakla bunu|not ekle|belleğine yaz|kayda al)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" .,:;-")
        if not cleaned:
            return "Ne hatırlayayım? Örnek: hatırla yarın toplantı var"
        self.memory.append(cleaned)
        return f"Kaydedildi: «{cleaned}»."

    def _hatirlat(self, _t: str) -> str:
        if not self.memory:
            return "Henüz not yok. 'Hatırla ...' diyerek ekleyin."
        return "Hafızamdaki notlar:\n" + "\n".join(f"• {m}" for m in self.memory[-12:])

    def _yeniden_egit(self, _t: str) -> str:
        if not self._retrain_fn:
            meta = train(epochs=1200)
            self.brain.reload()
        else:
            meta = self._retrain_fn()
        return (
            "Sıfırdan yeniden eğitim tamamlandı. "
            f"Doğruluk {meta.get('accuracy', 0):.0%}, "
            f"örnek {meta.get('samples')}, niyet {len(meta.get('tags', []))}."
        )

    def _ceviri(self, text: str) -> str:
        low = normalize(text)
        low = re.sub(r"\b(çevir|cevir|tercüme et|translate|ingilizceye çevir|türkçeye çevir|"
                     r"ne demek ingilizce|ingilizcesi ne|türkçesi ne|bu kelimeyi çevir|çeviri yap)\b",
                     " ", low)
        word = " ".join(tokenize(low)).strip()
        if not word:
            return "Örnek: çevir merhaba  veya  book türkçesi ne"
        if word in DICT_TR_EN:
            return f"«{word}» → {DICT_TR_EN[word]}"
        if word in DICT_EN_TR:
            return f"«{word}» → {DICT_EN_TR[word]}"
        for k, v in DICT_TR_EN.items():
            if k in word:
                return f"«{k}» → {v}"
        for k, v in DICT_EN_TR.items():
            if k in word:
                return f"«{k}» → {v}"
        return f"«{word}» sözlüğümde yok. 'öğret {word} | anlamı' ile ekleyebilirsiniz."

    def _birim(self, text: str) -> str:
        low = text.lower().replace(",", ".")
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*(km|mil|c|f|kg|pound|lb|m|cm|inch|in)\b", low)
        if not m:
            return "Örnek: 10 km mil, 25 c f, 70 kg pound, 180 cm inch"
        val = float(m.group(1))
        unit = m.group(2)
        if unit == "km":
            return f"{val} km = {val * 0.621371:.3f} mil"
        if unit == "mil":
            return f"{val} mil = {val * 1.60934:.3f} km"
        if unit == "c":
            return f"{val}°C = {val * 9/5 + 32:.1f}°F"
        if unit == "f":
            return f"{val}°F = {(val - 32) * 5/9:.1f}°C"
        if unit == "kg":
            return f"{val} kg = {val * 2.20462:.2f} pound"
        if unit in {"pound", "lb"}:
            return f"{val} pound = {val / 2.20462:.2f} kg"
        if unit == "cm":
            return f"{val} cm = {val / 2.54:.2f} inch"
        if unit in {"inch", "in"}:
            return f"{val} inch = {val * 2.54:.2f} cm"
        if unit == "m":
            return f"{val} m = {val * 3.28084:.2f} feet"
        return "Birimi çözemedim."

    def _sifre(self, text: str) -> str:
        m = re.search(r"(\d{1,2})", text)
        n = int(m.group(1)) if m else 16
        n = max(8, min(n, 32))
        alphabet = string.ascii_letters + string.digits + "!@#$%*?-"
        pwd = "".join(secrets.choice(alphabet) for _ in range(n))
        return f"Güçlü parola ({n} karakter): {pwd}"

    def _yazi(self, text: str) -> str:
        low = text.lower()
        # metni ayıkla
        body = re.sub(
            r"\b(büyük harf yap|küçük harf yap|ters çevir|kaç kelime|kaç harf|"
            r"metni ters çevir|yazıyı büyüt|yazıyı küçült|kelime sayısı|karakter sayısı|metin analizi)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" :")
        if "kelime" in low or "harf" in low or "karakter" in low or "analiz" in low:
            src = body or text
            words = tokenize(src)
            chars = len(re.sub(r"\s+", "", src))
            return f"Kelime: {len(words)} · karakter (boşluksuz): {chars}"
        if not body:
            return "Metni komutla birlikte yazın. Örnek: büyük harf yap merhaba dünya"
        if "büyük" in low or "büyüt" in low:
            return body.upper()
        if "küçük" in low or "küçült" in low:
            return body.lower()
        if "ters" in low:
            return body[::-1]
        return body

    def _rastgele(self, text: str) -> str:
        low = text.lower()
        if "yazı" in low or "tura" in low:
            return "Yazı tura: " + random.choice(["Yazı", "Tura"])
        if "zar" in low:
            return f"Zar: {random.randint(1, 6)}"
        opts = re.split(r"\s+veya\s+|\s+mı\s+|\s*,\s*", text)
        opts = [o.strip() for o in opts if len(o.strip()) > 1]
        # "seç a veya b"
        if "veya" in low and len(opts) >= 2:
            clean = [re.sub(r"^(seç|hangisi|rastgele seç)\s*", "", o, flags=re.I).strip() for o in opts]
            clean = [c for c in clean if c]
            if len(clean) >= 2:
                return f"Seçimim: {random.choice(clean)}"
        return f"Rastgele sayı (1-100): {random.randint(1, 100)}"

    def _ad_kaydet(self, text: str) -> str:
        m = re.search(
            r"(?:adım|ismim|benim adım|beni şöyle çağır|bana şöyle hitap et)\s*[:\-]?\s*(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if not m:
            return "Adınızı söyleyin: 'Benim adım Ali'"
        name = m.group(1).strip(" .!")
        name = re.sub(r"\b(adımı kaydet|ismimi hatırla|adımı unutma)\b", "", name, flags=re.I).strip()
        if not name:
            return "Adı netleştiremedim."
        self.user_name = name.title()
        teach_qa(f"kullanıcı adı nedir", self.user_name)
        return f"Memnun oldum, {self.user_name}. Bundan sonra size böyle hitap edeceğim."

    def _ogretilen(self, text: str) -> str:
        hit = self._knowledge_lookup(text)
        if hit:
            return hit
        resp = self.brain.pick_response("ogretilen")
        return resp or "Bu konuda öğrettiğiniz bir yanıt var ama eşleşme zayıf. 'yeniden eğit' deneyin."
