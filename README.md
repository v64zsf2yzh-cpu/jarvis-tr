# JARVIS v3.6 — Gemini + Komuta Merkezi

## VPS’te Gemini bağlama

```bash
cd ~/jarvis-tr
git pull

# Anahtarı kaydet (GitHub'a gitmez)
echo 'SENIN_GEMINI_ANAHTARIN' > .gemini_key

# veya:
# export GEMINI_API_KEY='SENIN_GEMINI_ANAHTARIN'

python3 app.py
```

Telefonda: `http://SUNUCU_IP:5050` → **JARVIS’İ BAŞLAT**

## Öncelik sırası

1. **Gemini** (varsa)
2. Ollama (yedek)
3. Yerel araçlar (saat/hesap/not)

Model: `gemini-3.8-flash` (`GEMINI_MODEL` ile değiştirilebilir)
