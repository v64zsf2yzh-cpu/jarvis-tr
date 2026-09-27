# JARVIS v3.5 — Komuta Merkezi

Türkçe sesli asistan + Ollama + mobil Command Center.

## VPS kurulum

```bash
cd ~/jarvis-tr
git pull
pip3 install -r requirements.txt

# Genel zekâ (zorunlu — yoksa sorulara cevap zayıf kalır)
ollama pull llama3.2
ollama serve &

python3 app.py
```

Telefonda: `http://SUNUCU_IP:5050`  
iPhone’da bir kez **JARVIS’İ BAŞLAT** → sonra otomatik konuşur/dinler.

## Özellikler

- Canlı yanıt akışı (stream)
- Sürekli sesli sohbet
- Konuşurken hareket eden hologram
- Saat / hesap / not araçları
- Öğretme + yeniden eğitim
- iOS / Android mobil arayüz (Türkçe)

## Ortam

```bash
export OLLAMA_MODEL=llama3.2
export OLLAMA_URL=http://127.0.0.1:11434
```
