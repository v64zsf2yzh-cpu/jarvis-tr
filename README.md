# JARVIS v3.7 — Gemini + Komuta Merkezi + kendini geliştirme

## VPS’te çalıştırma

```bash
cd ~/jarvis-tr
git pull

# Anahtarı kaydet (GitHub'a gitmez)
echo 'SENIN_GEMINI_ANAHTARIN' > .gemini_key

python3 app.py
```

Telefonda: `http://SUNUCU_IP:5050`

- **ARA** — sesli / görüntülü görüşme
- **YAZ** — yazılı sohbet (kamera/mikrofon şart değil)

## Öncelik sırası

1. Yerel araçlar (saat, tarih, hesap, hava, not, şifre, birim…)
2. Niyet modeli yüksek güvenliyse yerel yanıt
3. **Gemini** (varsa)
4. Ollama (yedek)

## Kendini geliştirme

Jarvis açık kaldıkça konuşmaları kaydeder, öğretileri kuyruğa alır, profili hatırlar ve birikince niyet modelini arka planda yeniden eğitir.

Öğretmek: `öğret soru | cevap`
Yeniden eğit: `yeniden eğit`
