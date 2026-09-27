#!/usr/bin/env bash
# Ubuntu VPS: Jarvis UI + Ollama genel soru motoru
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install -q -r requirements.txt
if [[ ! -f model/jarvis_brain.npz ]]; then
  echo "Model yok — ilk eğitim..."
  python3 train.py
fi

echo "Ollama kontrol..."
if command -v ollama >/dev/null 2>&1; then
  if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama kapalı olabilir. Arka planda başlatmayı deneyin: nohup ollama serve >/tmp/ollama.log 2>&1 &"
  fi
  if ! ollama list 2>/dev/null | grep -qiE 'llama|qwen|mistral|gemma|phi'; then
    echo "Model yok. Genel sorular için öneri:"
    echo "  ollama pull llama3.2"
  else
    echo "Ollama modelleri hazır."
  fi
else
  echo "Ollama kurulu değil. Genel soru için: https://ollama.com/download"
fi

echo "Jarvis UI başlıyor..."
# Gemini anahtarı (varsa)
if [[ -f .gemini_key ]]; then
  export GEMINI_API_KEY="$(cat .gemini_key | tr -d '\n')"
  echo "Gemini API anahtarı yüklendi."
elif [[ -n "${GEMINI_API_KEY:-}" ]]; then
  echo "Gemini API ortam değişkeninden yüklendi."
else
  echo "Uyarı: GEMINI_API_KEY yok — Ollama yedek olarak kullanılır."
fi
python3 app.py
