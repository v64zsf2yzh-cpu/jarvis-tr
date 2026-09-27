"""
Jarvis beyni — sıfırdan eğitilmiş Türkçe niyet sınıflandırıcı.

Özellikler:
- unigram + bigram bag-of-features
- 3 gizli katmanlı MLP (NumPy, rastgele başlatma)
- eğitim / doğrulama ayrımı
- kullanıcı öğretileri (data/taught.json) ile yeniden eğitim
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "intents.json"
TAUGHT_PATH = ROOT / "data" / "taught.json"
KNOWLEDGE_PATH = ROOT / "data" / "knowledge.json"
MODEL_PATH = ROOT / "model" / "jarvis_brain.npz"
META_PATH = ROOT / "model" / "jarvis_meta.json"
HISTORY_PATH = ROOT / "model" / "train_history.json"


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ı", "i").replace("İ", "i")
    text = text.replace("â", "a").replace("û", "u").replace("î", "i")
    return text


def tokenize(text: str) -> list[str]:
    text = normalize(text)
    text = re.sub(r"[^\w\sçğıöşü]", " ", text, flags=re.UNICODE)
    return [t for t in text.split() if t]


def ngrams(tokens: list[str]) -> list[str]:
    feats = list(tokens)
    for a, b in zip(tokens, tokens[1:]):
        feats.append(f"{a}_{b}")
    return feats


def fold_tr(token: str) -> str:
    return (
        token.replace("ğ", "g")
        .replace("ş", "s")
        .replace("ç", "c")
        .replace("ö", "o")
        .replace("ü", "u")
    )


def build_vocab(patterns: list[str], min_count: int = 1) -> list[str]:
    counts: Counter[str] = Counter()
    for p in patterns:
        counts.update(ngrams(tokenize(p)))
    return sorted([w for w, c in counts.items() if c >= min_count])


def vectorize(tokens: list[str], word_to_idx: dict[str, int]) -> np.ndarray:
    vec = np.zeros(len(word_to_idx), dtype=np.float64)
    for feat in ngrams(tokens):
        if feat in word_to_idx:
            vec[word_to_idx[feat]] += 1.0
        else:
            alt = fold_tr(feat)
            if alt in word_to_idx:
                vec[word_to_idx[alt]] += 1.0
    # L2 normalize — uzun cümleleri dengele
    n = np.linalg.norm(vec)
    if n > 0:
        vec /= n
    return vec


class NeuralNet:
    """Üç gizli katmanlı MLP — tüm ağırlıklar sıfırdan."""

    def __init__(
        self,
        sizes: list[int],
        seed: int = 42,
    ) -> None:
        self.sizes = sizes
        rng = np.random.default_rng(seed)
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        for i in range(len(sizes) - 1):
            fan_in, fan_out = sizes[i], sizes[i + 1]
            self.weights.append(rng.normal(0, math.sqrt(2 / fan_in), (fan_in, fan_out)))
            self.biases.append(np.zeros((1, fan_out)))

    @staticmethod
    def relu(x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)

    @staticmethod
    def relu_grad(x: np.ndarray) -> np.ndarray:
        return (x > 0).astype(np.float64)

    @staticmethod
    def softmax(x: np.ndarray) -> np.ndarray:
        shifted = x - np.max(x, axis=1, keepdims=True)
        exp = np.exp(shifted)
        return exp / np.sum(exp, axis=1, keepdims=True)

    def forward(
        self,
        X: np.ndarray,
        dropout: float = 0.0,
        rng: np.random.Generator | None = None,
    ) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray], list[np.ndarray | None]]:
        activations = [X]
        preacts: list[np.ndarray] = []
        masks: list[np.ndarray | None] = []
        a = X
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            z = a @ W + b
            preacts.append(z)
            if i < len(self.weights) - 1:
                a = self.relu(z)
                if dropout > 0 and rng is not None:
                    mask = (rng.random(a.shape) >= dropout).astype(np.float64) / (1.0 - dropout)
                    a = a * mask
                    masks.append(mask)
                else:
                    masks.append(None)
            else:
                a = self.softmax(z)
                masks.append(None)
            activations.append(a)
        return a, activations, preacts, masks

    def backward(
        self,
        activations: list[np.ndarray],
        preacts: list[np.ndarray],
        masks: list[np.ndarray | None],
        y_onehot: np.ndarray,
        lr: float,
        l2: float = 5e-5,
    ) -> float:
        m = y_onehot.shape[0]
        probs = activations[-1]
        # label smoothing
        smooth = 0.05
        y_s = y_onehot * (1 - smooth) + smooth / y_onehot.shape[1]
        loss = float(-np.sum(y_s * np.log(probs + 1e-12)) / m)
        for W in self.weights:
            loss += 0.5 * l2 * float(np.sum(W * W))

        delta = (probs - y_s) / m
        for i in reversed(range(len(self.weights))):
            a_prev = activations[i]
            dW = a_prev.T @ delta + l2 * self.weights[i]
            db = np.sum(delta, axis=0, keepdims=True)
            if i > 0:
                da = delta @ self.weights[i].T
                mask = masks[i - 1]
                if mask is not None:
                    da = da * mask
                delta = da * self.relu_grad(preacts[i - 1])
            self.weights[i] -= lr * dW
            self.biases[i] -= lr * db
        return loss

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        probs, _, _, _ = self.forward(X)
        return np.argmax(probs, axis=1), probs


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_training_intents() -> dict[str, Any]:
    base = load_json(DATA_PATH, {"intents": []})
    taught = load_json(TAUGHT_PATH, {"intents": [], "knowledge": {}})
    by_tag: dict[str, dict[str, Any]] = {}
    for intent in base.get("intents", []):
        by_tag[intent["tag"]] = {
            "tag": intent["tag"],
            "patterns": list(intent.get("patterns", [])),
            "responses": list(intent.get("responses", [])),
        }
    for intent in taught.get("intents", []):
        tag = intent["tag"]
        if tag not in by_tag:
            by_tag[tag] = {"tag": tag, "patterns": [], "responses": []}
        by_tag[tag]["patterns"].extend(intent.get("patterns", []))
        by_tag[tag]["responses"].extend(intent.get("responses", []))
        # tekilleştir
        by_tag[tag]["patterns"] = sorted(set(by_tag[tag]["patterns"]))
        by_tag[tag]["responses"] = list(dict.fromkeys(by_tag[tag]["responses"]))
    return {"intents": list(by_tag.values())}


def augment_pattern(pattern: str) -> list[str]:
    """Basit Türkçe veri çoğaltma — model daha iyi genellesin."""
    variants = {pattern, pattern.lower(), pattern.strip()}
    variants.add(f"jarvis {pattern}")
    variants.add(f"{pattern} lütfen")
    variants.add(f"bakar mısın {pattern}")
    variants.add(f"hemen {pattern}")
    # noktalama / soru
    variants.add(f"{pattern}?")
    variants.add(f"{pattern}!")
    return [v for v in variants if v.strip()]


def prepare_dataset(
    intents_data: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    tags: list[str] = []
    all_patterns: list[str] = []
    xy: list[tuple[str, str]] = []

    for intent in intents_data["intents"]:
        tag = intent["tag"]
        if tag not in tags:
            tags.append(tag)
        for pattern in intent["patterns"]:
            for variant in augment_pattern(pattern):
                all_patterns.append(variant)
                xy.append((variant, tag))

    vocab = build_vocab(all_patterns)
    word_to_idx = {w: i for i, w in enumerate(vocab)}
    tag_to_idx = {t: i for i, t in enumerate(tags)}

    X = np.zeros((len(xy), len(vocab)), dtype=np.float64)
    y = np.zeros((len(xy), len(tags)), dtype=np.float64)
    for i, (pattern, tag) in enumerate(xy):
        X[i] = vectorize(tokenize(pattern), word_to_idx)
        y[i, tag_to_idx[tag]] = 1.0
    return X, y, vocab, tags


def stratified_split(
    X: np.ndarray, y: np.ndarray, val_ratio: float, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    labels = np.argmax(y, axis=1)
    tr_idx: list[int] = []
    va_idx: list[int] = []
    for lab in np.unique(labels):
        ind = np.where(labels == lab)[0]
        ind = rng.permutation(ind)
        n_val = max(1, int(len(ind) * val_ratio)) if len(ind) >= 5 else 0
        if n_val:
            va_idx.extend(ind[:n_val].tolist())
            tr_idx.extend(ind[n_val:].tolist())
        else:
            tr_idx.extend(ind.tolist())
    return X[tr_idx], y[tr_idx], X[va_idx], y[va_idx]


def train(
    epochs: int = 2200,
    lr: float = 0.08,
    hidden: list[int] | None = None,
    seed: int = 42,
    val_ratio: float = 0.12,
) -> dict[str, Any]:
    if hidden is None:
        hidden = [160, 96, 48]

    intents_data = merge_training_intents()
    X, y, vocab, tags = prepare_dataset(intents_data)
    if len(X) < 2:
        raise RuntimeError("Eğitim için yeterli örnek yok.")

    rng = np.random.default_rng(seed)
    X_tr, y_tr, X_val, y_val = stratified_split(X, y, val_ratio, rng)
    if len(X_val) == 0:
        X_val, y_val = X_tr[:1], y_tr[:1]

    sizes = [len(vocab), *hidden, len(tags)]
    net = NeuralNet(sizes, seed=seed)
    history: list[dict[str, float]] = []
    best_val = -1.0
    best_weights = None
    base_lr = lr

    for epoch in range(1, epochs + 1):
        # kosinüs öğrenme oranı
        lr = base_lr * 0.5 * (1 + math.cos(math.pi * (epoch - 1) / epochs))
        probs, acts, pre, masks = net.forward(X_tr, dropout=0.08, rng=rng)
        loss = net.backward(acts, pre, masks, y_tr, lr)

        train_acc = float(np.mean(np.argmax(probs, axis=1) == np.argmax(y_tr, axis=1)))
        vp, _ = net.predict(X_val)
        val_acc = float(np.mean(vp == np.argmax(y_val, axis=1)))

        history.append({"epoch": epoch, "loss": loss, "train_acc": train_acc, "val_acc": val_acc})

        if val_acc >= best_val:
            best_val = val_acc
            best_weights = [(W.copy(), b.copy()) for W, b in zip(net.weights, net.biases)]

        if epoch % 400 == 0 or epoch == 1:
            print(
                f"Epoch {epoch:4d} | loss={loss:.4f} | train={train_acc:.3f} | val={val_acc:.3f} | lr={lr:.4f}"
            )

    if best_weights:
        for i, (W, b) in enumerate(best_weights):
            net.weights[i] = W
            net.biases[i] = b

    preds, _ = net.predict(X)
    final_acc = float(np.mean(preds == np.argmax(y, axis=1)))
    print(f"Eğitim tamam. Genel doğruluk: {final_acc:.3f} | en iyi val: {best_val:.3f}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {f"W{i}": W for i, W in enumerate(net.weights)}
    payload.update({f"b{i}": b for i, b in enumerate(net.biases)})
    np.savez_compressed(MODEL_PATH, **payload)

    meta = {
        "vocab": vocab,
        "tags": tags,
        "sizes": sizes,
        "accuracy": final_acc,
        "val_accuracy": best_val,
        "epochs": epochs,
        "samples": int(len(X)),
        "trained_from_scratch": True,
        "framework": "numpy-mlp-v2",
        "features": "unigram+bigram+augment",
    }
    save_json(META_PATH, meta)
    save_json(HISTORY_PATH, history[:: max(1, len(history) // 200)])
    return meta


class JarvisBrain:
    def __init__(self) -> None:
        if not MODEL_PATH.exists() or not META_PATH.exists():
            raise FileNotFoundError("Model yok. `python train.py` çalıştırın.")
        meta = load_json(META_PATH, {})
        self.vocab: list[str] = meta["vocab"]
        self.tags: list[str] = meta["tags"]
        self.sizes: list[int] = meta["sizes"]
        self.word_to_idx = {w: i for i, w in enumerate(self.vocab)}
        self.intents = merge_training_intents()
        self.tag_responses = {
            i["tag"]: i.get("responses", []) for i in self.intents["intents"]
        }
        self.knowledge = {
            **load_json(KNOWLEDGE_PATH, {}),
            **load_json(TAUGHT_PATH, {"knowledge": {}}).get("knowledge", {}),
        }
        weights = np.load(MODEL_PATH)
        self.net = NeuralNet(self.sizes)
        for i in range(len(self.sizes) - 1):
            self.net.weights[i] = weights[f"W{i}"]
            self.net.biases[i] = weights[f"b{i}"]
        self.meta = meta

    def classify(self, text: str, threshold: float = 0.18) -> tuple[str, float]:
        tokens = tokenize(text)
        if not tokens:
            return "bilinmeyen", 0.0
        x = vectorize(tokens, self.word_to_idx).reshape(1, -1)
        if float(np.sum(np.abs(x))) == 0:
            return "bilinmeyen", 0.0
        _, probs = self.net.predict(x)
        idx = int(np.argmax(probs[0]))
        conf = float(probs[0][idx])
        if conf < threshold:
            return "bilinmeyen", conf
        return self.tags[idx], conf

    def pick_response(self, tag: str) -> str | None:
        responses = self.tag_responses.get(tag) or []
        if not responses:
            return None
        return random.choice(responses)

    def reload(self) -> None:
        self.__init__()  # type: ignore[misc]


def teach_qa(question: str, answer: str, tag: str = "ogretilen") -> dict[str, Any]:
    """Kullanıcıdan gelen soru-cevap çiftini kalıcı öğret."""
    question = question.strip()
    answer = answer.strip()
    if not question or not answer:
        raise ValueError("Soru ve cevap gerekli.")

    taught = load_json(TAUGHT_PATH, {"intents": [], "knowledge": {}})
    # bilgi bankası
    key = normalize(question)
    taught.setdefault("knowledge", {})[key] = answer
    # niyet olarak da ekle
    found = None
    for intent in taught.setdefault("intents", []):
        if intent.get("tag") == tag:
            found = intent
            break
    if found is None:
        found = {"tag": tag, "patterns": [], "responses": []}
        taught["intents"].append(found)
    if question not in found["patterns"]:
        found["patterns"].append(question)
    if answer not in found["responses"]:
        found["responses"].append(answer)
    save_json(TAUGHT_PATH, taught)

    # knowledge.json'a da yaz
    knowledge = load_json(KNOWLEDGE_PATH, {})
    knowledge[key] = answer
    # kısa anahtar: ilk 3 kelime
    toks = tokenize(question)
    if toks:
        knowledge[" ".join(toks[:3])] = answer
    save_json(KNOWLEDGE_PATH, knowledge)
    return {"question": question, "answer": answer, "tag": tag}


if __name__ == "__main__":
    train()
