const logEl = document.getElementById("log");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const micBtn = document.getElementById("micBtn");
const talkMain = document.getElementById("talkMain");
const talkLabel = document.getElementById("talkLabel");
const speakToggle = document.getElementById("speakToggle");
const convBtn = document.getElementById("convBtn");
const clearBtn = document.getElementById("clearBtn");
const voiceState = document.getElementById("voiceState");
const feedList = document.getElementById("feedList");

let voiceOn = true;
let continuous = false;
let recognizing = false;
let busy = false;
let recognition = null;
let jarvisVoice = null;
let audioCtx = null;
let analyser = null;
let levelLoop = null;

function setOrb(mode) {
  window.JarvisOrb?.setMode(mode);
  window.JarvisWaves?.setMode(mode);
}
function feed(text) {
  if (!feedList) return;
  const el = document.createElement("div");
  el.className = "feed-item";
  el.textContent = `${new Date().toLocaleTimeString("tr-TR")} · ${text}`;
  feedList.prepend(el);
  while (feedList.children.length > 8) feedList.lastChild.remove();
}

function addMessage(role, text, meta = "") {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "OPERATOR" : "J.A.R.V.I.S.";
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

function tickClock() {
  const now = new Date();
  document.getElementById("clock").textContent = now.toLocaleTimeString("en-GB");
  document.getElementById("dateLine").textContent = now.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  // sahte gauge animasyonu
  const cpu = 12 + Math.round(8 * Math.abs(Math.sin(Date.now() / 3000)));
  const ram = 40 + Math.round(6 * Math.abs(Math.sin(Date.now() / 4000)));
  const disk = 35;
  document.getElementById("gCpu").textContent = `${cpu}%`;
  document.getElementById("gRam").textContent = `${ram}%`;
  document.getElementById("gDisk").textContent = `${disk}%`;
  document.querySelectorAll(".gauge").forEach((g, i) => {
    const v = [cpu, ram, disk][i];
    g.style.setProperty("--p", v);
  });
}
setInterval(tickClock, 1000);
tickClock();

function pickVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) return null;
  const score = (v) => {
    const n = `${v.name} ${v.lang}`.toLowerCase();
    let s = 0;
    if (v.lang?.toLowerCase().startsWith("tr")) s += 50;
    if (v.lang?.toLowerCase().startsWith("en-gb")) s += 35;
    if (/male|david|daniel|george|thomas|james|brian/.test(n)) s += 20;
    if (/female|zira|susan|linda/.test(n)) s -= 15;
    return s;
  };
  return [...voices].sort((a, b) => score(b) - score(a))[0];
}
function refreshVoice() {
  jarvisVoice = pickVoice();
  document.getElementById("voiceTag") && (document.getElementById("stVoice").textContent = "Online");
}

function speak(text) {
  return new Promise((resolve) => {
    if (!voiceOn || !window.speechSynthesis) {
      setOrb("idle");
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    refreshVoice();
    const parts = (text.match(/[^.!?…]+[.!?…]*/g) || [text]).map((x) => x.trim()).filter(Boolean).slice(0, 14);
    let i = 0;
    const next = () => {
      if (i >= parts.length) {
        setOrb(continuous ? "listening" : "idle");
        voiceState.textContent = continuous ? "Listening…" : "Standby";
        resolve();
        return;
      }
      const u = new SpeechSynthesisUtterance(parts[i++]);
      if (jarvisVoice) {
        u.voice = jarvisVoice;
        u.lang = jarvisVoice.lang || "tr-TR";
      } else u.lang = "tr-TR";
      u.rate = 0.9;
      u.pitch = 0.75;
      setOrb("speaking");
      voiceState.textContent = "Speaking…";
      const pulse = setInterval(() => {
        window.JarvisOrb?.pulse(0.55 + Math.random() * 0.4);
        window.JarvisWaves?.setEnergy(0.5 + Math.random() * 0.5);
      }, 80);
      u.onend = () => { clearInterval(pulse); next(); };
      u.onerror = () => { clearInterval(pulse); next(); };
      window.speechSynthesis.speak(u);
    };
    next();
  });
}

async function ensureMic() {
  if (analyser) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
  } catch (_) {
    analyser = null;
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
    const avg = sum / data.length / 255;
    window.JarvisOrb?.setLevel(0.2 + avg * 1.5);
    window.JarvisWaves?.setEnergy(avg);
  }, 40);
}
function stopLevels() {
  if (levelLoop) clearInterval(levelLoop);
  levelLoop = null;
}

async function refreshStatus() {
  try {
    const s = await fetch("/api/status").then((r) => r.json());
    const oll = s.ollama || {};
    document.getElementById("stMem").textContent = `${s.memory_count || 0} stored`;
    document.getElementById("memBadge").textContent = s.knowledge_count || 0;
    document.getElementById("stNlu").textContent = `acc ${Math.round((s.accuracy || 0) * 100)}%`;
    const card = document.getElementById("cardOllama");
    if (oll.available && oll.active_model) {
      document.getElementById("stLlm").textContent = oll.active_model;
      document.getElementById("stLlm").classList.add("ok");
      card.classList.add("on");
      card.querySelector("b").textContent = "Connected";
      document.getElementById("sysPill").textContent = "OPTIMAL";
    } else {
      document.getElementById("stLlm").textContent = "Offline";
      card.querySelector("b").textContent = "Not Linked";
      document.getElementById("sysPill").textContent = "DEGRADED";
    }
  } catch (_) {
    document.getElementById("sysPill").textContent = "NO LINK";
  }
}

async function askJarvis(message) {
  if (busy) return;
  busy = true;
  setOrb("thinking");
  voiceState.textContent = "Processing…";
  feed(`Query: ${message.slice(0, 48)}`);
  const typing = addMessage("bot", "Processing request…");
  typing.classList.add("typing");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    typing.remove();
    if (!res.ok) throw new Error("err");
    addMessage("bot", data.reply, `${data.intent} · ${data.model || ""}`);
    feed(`Response via ${data.model || "core"}`);
    await speak(data.reply);
    await refreshStatus();
    if (continuous) startListening();
    else {
      setOrb("idle");
      voiceState.textContent = "Standby";
    }
  } catch (_) {
    typing.remove();
    addMessage("bot", "Link failure. Is python3 app.py running?");
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

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  addMessage("user", message);
  input.value = "";
  await askJarvis(message);
});

async function toggleMic() {
  if (busy) return;
  await ensureMic();
  if (recognizing) stopListening();
  else startListening();
}
micBtn?.addEventListener("click", toggleMic);
talkMain?.addEventListener("click", toggleMic);

speakToggle?.addEventListener("click", () => {
  voiceOn = !voiceOn;
  speakToggle.setAttribute("aria-pressed", String(voiceOn));
  if (!voiceOn) window.speechSynthesis?.cancel();
});

convBtn?.addEventListener("click", async () => {
  continuous = !continuous;
  convBtn.setAttribute("aria-pressed", String(continuous));
  if (continuous) {
    await ensureMic();
    startLevels();
    voiceState.textContent = "Listening…";
    startListening();
    feed("Voice chat engaged");
  } else {
    stopListening();
    stopLevels();
    setOrb("idle");
    voiceState.textContent = "Standby";
  }
});

clearBtn?.addEventListener("click", () => {
  logEl.innerHTML = "";
  addMessage("bot", "Conversation buffer cleared.");
});

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const panel = btn.dataset.panel;
    if (panel === "chat") document.getElementById("chatPanel")?.scrollIntoView({ behavior: "smooth" });
    if (panel === "memory") askJarvis("ne hatırlıyorsun");
    if (panel === "status") askJarvis("sistem durumu");
    if (panel === "tools") askJarvis("ne yapabilirsin");
  });
});

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    talkLabel.textContent = "Mic unsupported";
    return;
  }
  recognition = new SR();
  recognition.lang = "tr-TR";
  recognition.interimResults = false;
  recognition.continuous = false;
  recognition.onstart = async () => {
    recognizing = true;
    micBtn.setAttribute("aria-pressed", "true");
    talkLabel.textContent = "Listening…";
    setOrb("listening");
    voiceState.textContent = "Listening…";
    window.speechSynthesis?.cancel();
    await ensureMic();
    startLevels();
  };
  recognition.onend = () => {
    recognizing = false;
    micBtn.setAttribute("aria-pressed", "false");
    talkLabel.textContent = "Tap to Speak";
    stopLevels();
    if (continuous && !busy) setTimeout(() => { if (continuous && !busy) startListening(); }, 350);
    else if (!busy) setOrb("idle");
  };
  recognition.onresult = async (ev) => {
    const t = ev.results[0][0].transcript.trim();
    if (!t) return;
    addMessage("user", t);
    await askJarvis(t);
  };
}

if (window.speechSynthesis) {
  refreshVoice();
  speechSynthesis.onvoiceschanged = refreshVoice;
}

setupSpeech();
setOrb("idle");
addMessage("bot", "Command Center online. Talk to Jarvis or type a command.");
feed("System boot complete");
refreshStatus();
setTimeout(() => speak("Jarvis command center online. Awaiting your orders."), 700);
