#!/usr/bin/env python3
"""Jarvis v3.9 — sesli komuta + araçlar + kendini geliştirme."""

from __future__ import annotations

import socket
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import evolve
import hooks
import memory
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
    hooks.install(skills)
    evolve.start(_retrain, interval_sec=180)
    print(
        f"Jarvis v3.9 | acc={brain.meta.get('accuracy', 0):.3f} | "
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


@app.post("/api/chat/stream")
def chat_stream():
    import json as _json
    from flask import Response, stream_with_context
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "Boş mesaj"}), 400

    def generate():
        for ev in skills.stream(text):
            yield _json.dumps(ev, ensure_ascii=False) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/teach")
def teach():
    data = request.get_json(silent=True) or {}
    q = (data.get("question") or "").strip()
    a = (data.get("answer") or "").strip()
    if not q or not a:
        return jsonify({"error": "question ve answer gerekli"}), 400
    info = teach_qa(q, a)
    memory.enqueue_learn(q, a)
    return jsonify({"ok": True, "taught": info, "hint": "Arka planda modele işlenecek."})


@app.post("/api/retrain")
def retrain():
    if evolve.status().get("training"):
        return jsonify({"ok": True, "queued": True, "message": "Eğitim zaten çalışıyor."})
    started = evolve.background_train(skills._retrain_fn or train)
    return jsonify({"ok": True, "background": started})


@app.get("/api/status")
def status():
    import gemini_client
    import ollama_client
    import selfcode
    ev = evolve.status()
    snap = memory.load()
    return jsonify({
        "name": "Jarvis",
        "version": "3.9",
        "language": "tr",
        "trained_from_scratch": True,
        "accuracy": skills.brain.meta.get("accuracy"),
        "val_accuracy": skills.brain.meta.get("val_accuracy"),
        "samples": skills.brain.meta.get("samples"),
        "intents": skills.brain.tags,
        "vocab_size": len(skills.brain.vocab),
        "knowledge_count": len(skills.brain.knowledge),
        "memory_count": len(memory.list_notes(80)),
        "user_name": snap.get("user_name") or skills.user_name,
        "city": snap.get("city"),
        "gemini": gemini_client.status(),
        "ollama": ollama_client.status(),
        "evolve": ev,
        "selfcode": selfcode.status(),
        "features": ["voice", "gemini", "tools", "wiki", "fx", "news", "reminders", "memory", "self-improve"],
    })


@app.get("/manifest.webmanifest")
def manifest():
    return jsonify({
        "name": "JARVIS",
        "short_name": "JARVIS",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#02040a",
        "theme_color": "#02040a",
        "lang": "tr",
        "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    })


if __name__ == "__main__":
    port = 5050
    ip = local_ip()
    print()
    print("=" * 50)
    print("  JARVIS Komuta Merkezi v3.9")
    print(f"  Telefondan aç : http://{ip}:{port}")
    print(f"  Bu cihazda    : http://127.0.0.1:{port}")
    print("=" * 50)
    print()
    app.run(host="0.0.0.0", port=port, debug=False)
