#!/usr/bin/env python3
"""Jarvis beynini sıfırdan (veya öğretilerle birlikte) eğit."""

from build_dataset import INTENTS  # noqa: F401 — dataset dosyasını güncel tut
import build_dataset
from brain import train

if __name__ == "__main__":
    build_dataset  # dataset yazımı import sırasında olur
    # build_dataset script as module already wrote? Need to call main logic
    import json
    from pathlib import Path

    # regenerate base intents
    out = Path(__file__).parent / "data" / "intents.json"
    from build_dataset import INTENTS, OUT

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"intents": INTENTS}, f, ensure_ascii=False, indent=2)
    print(f"Veri seti: {len(INTENTS)} niyet")
    meta = train(epochs=2200, lr=0.08, hidden=[160, 96, 48])
    print("Model kaydedildi.")
    print(
        f"doğruluk={meta['accuracy']:.3f} val={meta['val_accuracy']:.3f} "
        f"örnek={meta['samples']} özellik={len(meta['vocab'])}"
    )
