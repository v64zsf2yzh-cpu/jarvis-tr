"""Uyanıkken kendi dosyalarına güvenli yama yazar."""

from __future__ import annotations

import ast
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import gemini_client
import memory
import ollama_client

ROOT = Path(__file__).resolve().parent
LEARNED = ROOT / "learned_skills.py"
INTENTS = ROOT / "data" / "intents.json"
PATCH_LOG = ROOT / "data" / "patches.jsonl"
BACKUP = ROOT / "data" / "backups"

ALLOWED = {
    "learned_skills.py": LEARNED,
    "data/intents.json": INTENTS,
}

BANNED = (
    "os.system", "subprocess", "shutil.rmtree", "eval(", "exec(",
    "socket", "__import__", "open(", "Path(", "gemini_key", "GEMINI_API_KEY", "rm -",
)

_lock = threading.Lock()
_state: dict[str, Any] = {"last_patch": None, "last_error": None, "applied": 0, "rejected": 0}


def status() -> dict[str, Any]:
    return dict(_state)


def cycle_now(reason: str = "manual") -> dict[str, Any]:
    result = cycle(force=True, reason=reason)
    reply = result.get("reply") or "Bu turda yeni kod yazmadım."
    return {"reply": reply, "intent": "selfcode", "confidence": 1.0, "model": "selfcode", "patch": result}


def cycle(force: bool = False, reason: str = "idle") -> dict[str, Any]:
    journal = _tail_journal(24)
    if not force and len(journal) < 4:
        return {"ok": False, "reason": "az konuşma"}
    proposal = _propose(journal, reason)
    if not proposal:
        return {"ok": False, "reason": "öneri yok", "reply": "Şimdilik dosyalarıma dokunacak net bir iyileştirme görmedim."}
    return _apply(proposal)


def _tail_journal(n: int) -> list[dict[str, Any]]:
    path = ROOT / "data" / "journal.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _propose(journal: list[dict[str, Any]], reason: str) -> dict[str, Any] | None:
    convo = "\n".join(f"{r.get('role')}: {(r.get('text') or '')[:180]}" for r in journal[-16:])
    prompt = (
        "Sen Jarvis kod yazarısın. Sadece JSON döndür.\n"
        "Konuşma günlüğüne bakıp KÜÇÜK ve GÜVENLİ bir iyileştirme öner.\n"
        "İzinli: learned_skills.py try_handle veya data/intents.json pattern.\n"
        "YASAK: os, subprocess, eval, exec, silme, ağ, anahtar, skills.py/app.py/brain.py.\n"
        "{\"target\": \"learned_skills.py\"|\"data/intents.json\", \"kind\": \"skill\"|\"intent\", "
        "\"summary\": \"...\", \"skill_python\": \"def try_handle(text, low): ...\", "
        "\"intent\": {\"tag\": \"...\", \"patterns\": [], \"responses\": []}}\n"
        "İyileştirme yoksa {\"target\": null}\n\n"
        f"Sebep: {reason}\nGünlük:\n{convo}"
    )
    raw = _ask_llm(prompt)
    if not raw:
        return None
    data = _extract_json(raw)
    if not data or not data.get("target"):
        return None
    if data["target"] not in ALLOWED:
        return None
    return data


def _ask_llm(prompt: str) -> str | None:
    if gemini_client.is_configured():
        res = gemini_client.chat(prompt, [])
        if res.get("ok") and res.get("reply"):
            return res["reply"]
    res = ollama_client.chat(prompt, [])
    if res.get("ok") and res.get("reply"):
        return res["reply"]
    return None


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    blob = fence.group(1) if fence else text
    start, end = blob.find("{"), blob.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(blob[start:end + 1])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _apply(proposal: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        target = proposal.get("target")
        path = ALLOWED.get(target)
        if path is None:
            _state["rejected"] += 1
            return {"ok": False, "reason": "hedef yasak"}
        BACKUP.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = BACKUP / f"{path.name}.{stamp}.bak"
        if path.exists():
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            if proposal.get("kind") == "intent" or str(target).endswith("intents.json"):
                _merge_intent(proposal.get("intent") or {})
            else:
                _write_skill(proposal.get("skill_python") or "")
            import importlib
            import learned_skills
            importlib.reload(learned_skills)
        except Exception as e:
            if bak.exists():
                path.write_text(bak.read_text(encoding="utf-8"), encoding="utf-8")
            _state["rejected"] += 1
            _state["last_error"] = str(e)
            return {"ok": False, "reason": str(e), "reply": f"Kodu yazdım ama bozuktu, geri aldım: {e}"}
        summary = proposal.get("summary") or "küçük yama"
        _log_patch(str(target), summary)
        _state["applied"] += 1
        _state["last_patch"] = {"target": target, "summary": summary, "at": stamp}
        memory.mark_evolve({"last_patch": summary})
        return {"ok": True, "target": target, "summary": summary, "reply": f"Kendi dosyama yazdım ({target}): {summary}. Yedek: {bak.name}"}


def _merge_intent(intent: dict[str, Any]) -> None:
    tag = re.sub(r"[^a-z0-9_]", "", (intent.get("tag") or "").lower())[:32]
    patterns = [str(p).strip() for p in (intent.get("patterns") or []) if str(p).strip()]
    responses = [str(p).strip() for p in (intent.get("responses") or []) if str(p).strip()]
    if not tag or not patterns:
        raise ValueError("intent eksik")
    data = json.loads(INTENTS.read_text(encoding="utf-8"))
    intents = data.setdefault("intents", [])
    found = None
    for item in intents:
        if item.get("tag") == tag:
            found = item
            break
    if found is None:
        found = {"tag": tag, "patterns": [], "responses": []}
        intents.append(found)
    found["patterns"] = sorted(set(found.get("patterns", []) + patterns))[:40]
    found["responses"] = list(dict.fromkeys(found.get("responses", []) + responses))[:12]
    INTENTS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_skill(fn_src: str) -> None:
    fn_src = (fn_src or "").strip()
    if "def try_handle" not in fn_src:
        raise ValueError("try_handle yok")
    header = '"""Jarvis uyanıkken yazdı."""\n\nfrom __future__ import annotations\n\nfrom typing import Any\n\n'
    source = header + fn_src + ("" if fn_src.endswith("\n") else "\n")
    _validate_python(source)
    LEARNED.write_text(source, encoding="utf-8")


def _validate_python(source: str) -> None:
    low = source.lower()
    for bad in BANNED:
        if bad.lower() in low:
            raise ValueError(f"yasaklı ifade: {bad}")
    tree = ast.parse(source)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    if "try_handle" not in names:
        raise ValueError("try_handle yok")
    if len(source) > 12000:
        raise ValueError("çok uzun yama")


def _log_patch(target: str, summary: str) -> None:
    PATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now().isoformat(timespec="seconds"), "target": target, "summary": summary}
    with open(PATCH_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
