#!/usr/bin/env bash
# Ubuntu / Termux / VPS üzerinde Jarvis UI başlat
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install -q -r requirements.txt
if [[ ! -f model/jarvis_brain.npz ]]; then
  echo "Model yok — ilk eğitim başlıyor..."
  python3 train.py
fi

echo "Jarvis UI başlatılıyor..."
python3 app.py
