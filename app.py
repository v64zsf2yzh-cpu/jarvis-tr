#!/usr/bin/env python3
"""Jarvis v2 — Türkçe asistan + öğretme + sıfırdan yeniden eğitim."""

from __future__ import annotations

import socket
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from brain import JarvisBrain, teach_qa, train
from skills import Skills

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model" / "jarvis_brain.npz"

app = Flask(__name__, static_folder="static", template_folder="templates")


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def boot() -> Skills:
    if not MODEL.exists():
        print("Model yok — sıfırdan eğitim...")
        train()
    brain = JarvisBrain()
    skills = Skills(brain)

    def _retrain():
        print("Yeniden eğitim (sıfırdan)...")
        meta = train(epochs=1600, lr=0.08, hidden=[160, 96, 48])
        skills.brain = JarvisBrain()
        return meta

    skills.set_retrain(_retrain)
    print(
        f"Jarvis v2 | acc={brain.meta.get('accuracy', 0):.3f} | "
        f"val={brain.meta.get('val_accuracy', 0):.3f} | "
        f"niyet={len(brain.tags)} | özellik={len(brain.vocab)} | örnek={brain.meta.get('samples')}"
    )
    return skills


skills = boot()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/download")
def download_zip():
    from flask import send_from_directory

    static = ROOT / "static"
    # zip yoksa proje kökündeki yedeği dene
    name = "jarvis.zip"
    if not (static / name).exists():
        return jsonify({"error": "Zip yok"}), 404
    return send_from_directory(static, name, as_attachment=True, download_name="jarvis.zip")


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "Boş mesaj"}), 400
    return jsonify(skills.handle(text))


@app.post("/api/teach")
def teach():
    data = request.get_json(silent=True) or {}
    q = (data.get("question") or "").strip()
    a = (data.get("answer") or "").strip()
    if not q or not a:
        return jsonify({"error": "question ve answer gerekli"}), 400
    info = teach_qa(q, a)
    return jsonify({"ok": True, "taught": info, "hint": "Kalıcı öğrenme için yeniden eğit çağırın."})


@app.post("/api/retrain")
def retrain():
    meta = skills._retrain_fn() if skills._retrain_fn else train()
    if not skills._retrain_fn:
        skills.brain = JarvisBrain()
    return jsonify(
        {
            "ok": True,
            "meta": {
                "accuracy": meta.get("accuracy"),
                "val_accuracy": meta.get("val_accuracy"),
                "samples": meta.get("samples"),
                "intents": len(meta.get("tags", [])),
                "vocab": len(meta.get("vocab", [])),
            },
        }
    )


@app.get("/api/status")
def status():
    return jsonify(
        {
            "name": "Jarvis",
            "version": 2,
            "language": "tr",
            "trained_from_scratch": True,
            "accuracy": skills.brain.meta.get("accuracy"),
            "val_accuracy": skills.brain.meta.get("val_accuracy"),
            "samples": skills.brain.meta.get("samples"),
            "intents": skills.brain.tags,
            "vocab_size": len(skills.brain.vocab),
            "knowledge_count": len(skills.brain.knowledge),
            "memory_count": len(skills.memory),
            "user_name": skills.user_name,
        }
    )


if __name__ == "__main__":
    port = 5050
    ip = local_ip()
    print()
    print("=" * 50)
    print("  JARVIS arayüzü hazır")
    print(f"  Telefondan aç : http://{ip}:{port}")
    print(f"  Bu cihazda    : http://127.0.0.1:{port}")
    print("=" * 50)
    print()
    app.run(host="0.0.0.0", port=port, debug=False)
