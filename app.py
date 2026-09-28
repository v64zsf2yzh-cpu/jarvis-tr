#!/usr/bin/env python3
"""Jarvis v4.4 — proaktif sesli asistan."""

from __future__ import annotations

import socket
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import doorbell
import evolve
import hello
import hooks
import memory
import nudge
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
        meta = train(epochs=1600, lr=0.08, hidden=[160, 96, 48])
        skills.brain = JarvisBrain()
        return meta

    skills.set_retrain(_retrain)
    hooks.install(skills)
    evolve.start(_retrain, interval_sec=90)
    doorbell.start(interval_sec=12)
    print(f"Jarvis v4.4 | acc={brain.meta.get('accuracy', 0):.3f}")
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

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/teach")
def teach():
    data = request.get_json(silent=True) or {}
    q = (data.get("question") or "").strip()
    a = (data.get("answer") or "").strip()
    if not q or not a:
        return jsonify({"error": "question ve answer gerekli"}), 400
    info = teach_qa(q, a)
    memory.enqueue_learn(q, a)
    return jsonify({"ok": True, "taught": info})


@app.post("/api/retrain")
def retrain():
    if evolve.status().get("training"):
        return jsonify({"ok": True, "queued": True})
    started = evolve.background_train(skills._retrain_fn or train)
    return jsonify({"ok": True, "background": started})


@app.get("/api/nudge")
def api_nudge():
    text = nudge.pop_due()
    return jsonify({"speak": text, "reminders": nudge.status_blob()})


@app.get("/api/hello")
def api_hello():
    text_only = request.args.get("text") == "1"
    return jsonify(hello.compose(text_only=text_only))


@app.get("/api/status")
def status():
    import gemini_client
    import ollama_client
    import selfcode
    ev = evolve.status()
    snap = memory.load()
    prefs = snap.get("prefs") or {}
    return jsonify({
        "name": "Jarvis",
        "version": "4.4",
        "user_name": snap.get("user_name") or skills.user_name,
        "city": snap.get("city"),
        "job": prefs.get("job"),
        "tasks": len(prefs.get("tasks") or []),
        "gemini": gemini_client.status(),
        "ollama": ollama_client.status(),
        "evolve": ev,
        "selfcode": selfcode.status(),
        "nudge": nudge.status_blob(),
        "doorbell": doorbell.status(),
    })


@app.get("/manifest.webmanifest")
def manifest():
    return jsonify({
        "name": "JARVIS", "short_name": "JARVIS", "start_url": "/",
        "display": "standalone", "background_color": "#02040a", "theme_color": "#02040a", "lang": "tr",
        "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    })


if __name__ == "__main__":
    port = 5050
    ip = local_ip()
    print("JARVIS v4.4", f"http://{ip}:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
