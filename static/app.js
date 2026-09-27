const logEl = document.getElementById("log");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const micBtn = document.getElementById("micBtn");
const talkLabel = document.getElementById("talkLabel");
const statusLine = document.getElementById("statusLine");
const liveCaption = document.getElementById("liveCaption");
const bootGate = document.getElementById("bootGate");
const bootBtn = document.getElementById("bootBtn");

const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

let voiceOn = true;
let continuous = true;
let recognizing = false;
let busy = false;
let started = false;
let recognition = null;
let jarvisVoice = null;
let audioCtx = null;
let analyser = null;
let levelLoop = null;

function setOrb(mode) { window.JarvisOrb?.setMode(mode); }

function addMessage(role, text, meta = "") {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "SİZ" : "JARVIS";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.append(who, bubble);
  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    row.append(m);
  }
  logEl.append(row);
  logEl.scrollTop = logEl.scrollHeight;
  return row;
}

function setStatus(t) { statusLine.textContent = t; }

function pickVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) return null;
  const score = (v) => {
    const n = `${v.name} ${v.lang}`.toLowerCase();
    let s = 0;
    if (v.lang?.toLowerCase().startsWith("tr")) s += 80;
    if (v.lang?.toLowerCase().startsWith("en-gb")) s += 25;
    if (/male|daniel|thomas|james|david|cem|tolga/.test(n)) s += 20;
    if (/female|filiz|yelda|zira/.test(n)) s -= 10;
    return s;
  };
  return [...voices].sort((a, b) => score(b) - score(a))[0];
}

function unlockAudio() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    if (window.speechSynthesis) {
      const w = new SpeechSynthesisUtterance(" ");
      w.volume = 0;
      speechSynthesis.speak(w);
      speechSynthesis.cancel();
    }
  } catch (_) {}
}

function speak(text) {
  return new Promise((resolve) => {
    if (!voiceOn || !window.speechSynthesis) {
      setOrb(continuous ? "listening" : "idle");
      resolve();
      return;
    }
    speechSynthesis.cancel();
    jarvisVoice = pickVoice();
    const parts = (text.match(/[^.!?…]+[.!?…]*/g) || [text]).map((x) => x.trim()).filter(Boolean).slice(0, 14);
    let i = 0;
    const next = () => {
      if (i >= parts.length) {
        setOrb(continuous ? "listening" : "idle");
        setStatus(continuous ? "Dinliyor" : "Hazır");
        liveCaption.textContent = continuous ? "Dinliyorum" : "Dinlemek için bas";
        resolve();
        return;
      }
      const u = new SpeechSynthesisUtterance(parts[i++]);
      if (jarvisVoice) {
        u.voice = jarvisVoice;
        u.lang = jarvisVoice.lang || "tr-TR";
      } else u.lang = "tr-TR";
      u.rate = isIOS ? 0.95 : 0.9;
      u.pitch = 0.78;
      setOrb("speaking");
      setStatus("Konuşuyor");
      liveCaption.textContent = "Jarvis konuşuyor";
      const pulse = setInterval(() => window.JarvisOrb?.pulse(0.55 + Math.random() * 0.4), 80);
      u.onend = () => { clearInterval(pulse); next(); };
      u.onerror = () => { clearInterval(pulse); next(); };
      speechSynthesis.speak(u);
    };
    next();
  });
}

async function ensureMic() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") await audioCtx.resume();
    if (analyser) return true;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    return true;
  } catch (_) {
    return false;
  }
}

function startLevels() {
  stopLevels();
  if (!analyser) return;
  const data = new Uint8Array(analyser.frequencyBinCount);
  levelLoop = setInterval(() => {
    if (!recognizing) return;
    analyser.getByteFrequencyData(data);
    let sum = 0;
    for (const v of data) sum += v;
    window.JarvisOrb?.setLevel(0.2 + (sum / data.length / 255) * 1.5);
  }, 40);
}
function stopLevels() {
  if (levelLoop) clearInterval(levelLoop);
  levelLoop = null;
}

async function refreshStatus() {
  try {
    const s = await fetch("/api/status").then((r) => r.json());
    if (s.gemini?.configured) setStatus(`Gemini · ${s.gemini.model || "açık"}`);
    else if (s.ollama?.available) setStatus(`Ollama · ${s.ollama.active_model || "açık"}`);
    else setStatus("Sınırlı mod");
  } catch (_) {
    setStatus("Bağlantı yok");
  }
}

async function askJarvis(message) {
  if (busy || !message) return;
  busy = true;
  setOrb("thinking");
  setStatus("Düşünüyor");
  liveCaption.textContent = "Analiz…";

  const row = addMessage("bot", "");
  const bubble = row.querySelector(".bubble");
  let full = "";
  let model = "";
  let intent = "sohbet";

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!res.ok || !res.body) throw new Error("stream");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    setOrb("speaking");

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let ev;
        try { ev = JSON.parse(line); } catch { continue; }
        if (ev.type === "meta") {
          intent = ev.intent || intent;
          model = ev.model || model;
        }
        if (ev.type === "token" && ev.token) {
          full += ev.token;
          bubble.textContent = full;
          logEl.scrollTop = logEl.scrollHeight;
          window.JarvisOrb?.pulse(0.45 + Math.random() * 0.35);
        }
        if (ev.type === "done") {
          full = ev.reply || full;
          bubble.textContent = full;
          model = ev.model || model;
          intent = ev.intent || intent;
        }
      }
    }

    if (!full.trim()) bubble.textContent = "Yanıt alınamadı.";
    else {
      const m = document.createElement("div");
      m.className = "meta";
      m.textContent = `${intent} · ${model}`;
      row.append(m);
      await speak(full);
    }
    await refreshStatus();
    if (continuous) setTimeout(() => startListening(), 250);
    else {
      setOrb("idle");
      setStatus("Hazır");
      liveCaption.textContent = "Dinlemek için bas";
    }
  } catch (_) {
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      bubble.textContent = data.reply || "Hata";
      await speak(data.reply || "");
    } catch {
      bubble.textContent = "Bağlantı hatası.";
    }
    setOrb("idle");
  } finally {
    busy = false;
  }
}

function startListening() {
  if (!recognition || recognizing || busy) return;
  try { recognition.start(); } catch (_) {}
}
function stopListening() {
  try { recognition?.stop(); } catch (_) {}
}

async function bootJarvis() {
  if (started) return;
  started = true;
  unlockAudio();
  bootGate?.classList.add("hide");
  setTimeout(() => bootGate?.remove(), 450);

  addMessage("bot", "Merhaba. Jarvis hazır.");
  await refreshStatus();
  await speak("Jarvis çevrimiçi. Emrinizi bekliyorum.");

  const micOk = await ensureMic();
  if (micOk && recognition) {
    startLevels();
    startListening();
    liveCaption.textContent = "Dinliyorum";
    setStatus("Dinliyor");
  } else {
    liveCaption.textContent = "Yazarak sor";
    setStatus("Mikrofon yok");
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!started) await bootJarvis();
  const message = input.value.trim();
  if (!message) return;
  addMessage("user", message);
  input.value = "";
  await askJarvis(message);
});

micBtn.addEventListener("click", async () => {
  if (!started) {
    await bootJarvis();
    return;
  }
  if (busy) return;
  await ensureMic();
  if (recognizing) stopListening();
  else startListening();
});

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    talkLabel.textContent = "YAZ";
    return;
  }
  recognition = new SR();
  recognition.lang = "tr-TR";
  recognition.interimResults = false;
  recognition.continuous = false;

  recognition.onstart = async () => {
    recognizing = true;
    micBtn.setAttribute("aria-pressed", "true");
    talkLabel.textContent = "DİNLE";
    setOrb("listening");
    setStatus("Dinliyor");
    liveCaption.textContent = "Dinliyorum";
    speechSynthesis?.cancel();
    await ensureMic();
    startLevels();
  };
  recognition.onend = () => {
    recognizing = false;
    micBtn.setAttribute("aria-pressed", "false");
    talkLabel.textContent = "KONUŞ";
    stopLevels();
    if (continuous && !busy) {
      setTimeout(() => {
        if (continuous && !busy && !recognizing) startListening();
      }, 400);
    } else if (!busy) setOrb("idle");
  };
  recognition.onresult = async (ev) => {
    const t = ev.results[0][0].transcript.trim();
    if (!t) return;
    addMessage("user", t);
    await askJarvis(t);
  };
}

if (window.speechSynthesis) {
  speechSynthesis.onvoiceschanged = () => { jarvisVoice = pickVoice(); };
}

setupSpeech();
setOrb("idle");
bootBtn?.addEventListener("click", bootJarvis);
bootGate?.addEventListener("click", (e) => {
  if (e.target === bootGate) bootJarvis();
});
window.addEventListener("load", () => {
  refreshStatus();
  if (!isIOS) setTimeout(() => { try { bootJarvis(); } catch (_) {} }, 350);
});
