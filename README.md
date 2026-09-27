# JARVIS v3

Türkçe kişisel asistan + **Ollama** ile genel soru-cevap.

## Ne yapar?

- Saat / tarih / hesap / not / şifre / çeviri (yerel beceriler)
- Sıfırdan eğitilmiş niyet modeli
- **Her türlü genel soru** → VPS’teki Ollama LLM

## VPS kurulum

```bash
cd ~
rm -rf jarvis-tr
git clone https://github.com/v64zsf2yzh-cpu/jarvis-tr.git
cd jarvis-tr
pip3 install -r requirements.txt

# Genel sorular için model (bir kez)
ollama pull llama3.2
# gerekirse: ollama serve &

python3 app.py
```

Telefonda: `http://SUNUCU_IP:5050`

## Ortam değişkenleri (opsiyonel)

```bash
export OLLAMA_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=llama3.2
python3 app.py
```
