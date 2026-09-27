const logEl = document.getElementById("log");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const micBtn = document.getElementById("micBtn");
const talkLabel = document.getElementById("talkLabel");
const speakToggle = document.getElementById("speakToggle");
const convBtn = document.getElementById("convBtn");
const clearBtn = document.getElementById("clearBtn");
const statusLine = document.getElementById("statusLine");
const reactorCaption = document.getElementById("reactorCaption");
const modelTag = document.getElementById("modelTag");
const voiceTag = document.getElementById("voiceTag");

let voiceOn = true;
let continuous = false;
let recognizing = false;
let busy = false;
let recognition = null;
let jarvisVoice = null;
let audioCtx = null;
let analyser = null;
let micStream = null;
let levelLoop = null;

function orbMode(mode) {
  window.JarvisOrb?.setMode(mode);
}

function addMessage(role, text, meta = "") {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "SİZ" : "J.A.R.V.I.S.";
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

function setStatus(t) {
  statusLine.textContent = t;
}

function pickJarvisVoice() {
  if (!window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;
  const score = (v) => {
    const name = `${v.name} ${v.lang}`.toLowerCase();
    let s = 0;
    if (v.lang?.toLowerCase().startsWith("tr")) s += 50;
    if (v.lang?.toLowerCase().startsWith("en-gb")) s += 35;
    if (v.lang?.toLowerCase().startsWith("en")) s += 15;
    if (/male|david|daniel|george|thomas|arthur|james|brian|adam/.test(name)) s += 25;
    if (/female|zira|susan|linda|filiz|yelda/.test(name)) s -= 20;
    return s;
  };
  return [...voices].sort((a, b) => score(b) - score(a))[0];
}

function refreshVoice() {
  jarvisVoice = pickJarvisVoice();
  if (jarvisVoice) voiceTag.textContent = `VOICE · ${jarvisVoice.name.slice(0, 16)}`;
}

function speak(text) {
  return new Promise((resolve) => {
    if (!voiceOn || !window.speechSynthesis) {
      orbMode("idle");
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    refreshVoice();
    const parts = (text.match(/[^.!?…]+[.!?…]*/g) || [text])
      .map((c) => c.trim())
      .filter(Boolean)
      .slice(0, 14);

    let i = 0;
    const next = () => {
      if (i >= parts.length) {
        orbMode(continuous ? "listening" : "idle");
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
      u.volume = 1;
      orbMode("speaking");
      setStatus("SPEAKING");
      reactorCaption.textContent = "Jarvis konuşuyor";
      // Konuşurken küreyi ritmik besle
      const pulse = setInterval(() => window.JarvisOrb?.pulse(0.5 + Math.random() * 0.45), 90);
      u.onend = () => {
        clearInterval(pulse);
        next();
      };
      u.onerror = () => {
        clearInterval(pulse);
        next();
      };
      window.speechSynthesis.speak(u);
    };
    next();
  });
}

async function ensureMicAnalyser() {
  if (analyser) return;
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
  } catch (_) {
    analyser = null;
  }
}

function startLevelLoop() {
  stopLevelLoop();
  if (!analyser) return;
  const data = new Uint8Array(analyser.frequencyBinCount);
  levelLoop = setInterval(() => {
    if (!recognizing) return;
    analyser.getByteFrequencyData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i];
    const avg = sum / data.length / 255;
    window.JarvisOrb?.setLevel(0.2 + avg * 1.4);
  }, 40);
}

function stopLevelLoop() {
  if (levelLoop) clearInterval(levelLoop);
  levelLoop = null;
}

async function refreshStatus() {
  try {
    const s = await fetch("/api/status").then((r) => r.json());
    const oll = s.ollama || {};
    if (oll.available && oll.active_model) {
      modelTag.textContent = `MODEL · ${oll.active_model}`;
      setStatus("ONLINE");
    } else {
      modelTag.textContent = "MODEL · OFFLINE";
      setStatus("OLLAMA OFF");
    }
  } catch (_) {
    setStatus("NO LINK");
  }
}

async function askJarvis(message) {
  if (busy) return;
  busy = true;
  orbMode("thinking");
  setStatus("PROCESSING");
  reactorCaption.textContent = "Analiz…";
  const typing = addMessage("bot", "Tabii efendim…");
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
    await speak(data.reply);
    await refreshStatus();
    if (continuous) {
      reactorCaption.textContent = "Dinliyorum…";
      startListening();
    } else {
      reactorCaption.textContent = "Dokunarak konuş";
      setStatus("READY");
      orbMode("idle");
    }
  } catch (_) {
    typing.remove();
    addMessage("bot", "Bağlantı hatası.");
    setStatus("ERROR");
    orbMode("idle");
  } finally {
    busy = false;
  }
}

function startListening() {
  if (!recognition || recognizing || busy) return;
  try {
    recognition.start();
  } catch (_) {}
}
function stopListening() {
  try {
    recognition?.stop();
  } catch (_) {}
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  addMessage("user", message);
  input.value = "";
  await askJarvis(message);
});

speakToggle.addEventListener("click", () => {
  voiceOn = !voiceOn;
  speakToggle.setAttribute("aria-pressed", String(voiceOn));
  speakToggle.textContent = voiceOn ? "Jarvis sesi" : "Ses kapalı";
  if (!voiceOn && window.speechSynthesis) window.speechSynthesis.cancel();
});

convBtn.addEventListener("click", async () => {
  continuous = !continuous;
  convBtn.setAttribute("aria-pressed", String(continuous));
  if (continuous) {
    await ensureMicAnalyser();
    startLevelLoop();
    setStatus("ALWAYS ON");
    reactorCaption.textContent = "Dinliyorum…";
    startListening();
  } else {
    stopListening();
    stopLevelLoop();
    orbMode("idle");
    setStatus("READY");
    reactorCaption.textContent = "Dokunarak konuş";
  }
});

clearBtn?.addEventListener("click", () => {
  logEl.innerHTML = "";
  addMessage("bot", "Arayüz temizlendi.");
});

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.disabled = true;
    talkLabel.textContent = "YOK";
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
    orbMode("listening");
    setStatus("LISTENING");
    reactorCaption.textContent = "Sizi dinliyorum…";
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    await ensureMicAnalyser();
    startLevelLoop();
  };

  recognition.onend = () => {
    recognizing = false;
    micBtn.setAttribute("aria-pressed", "false");
    talkLabel.textContent = "KONUŞ";
    stopLevelLoop();
    if (!busy) orbMode(continuous ? "listening" : "idle");
    if (continuous && !busy) {
      setTimeout(() => {
        if (continuous && !busy && !recognizing) startListening();
      }, 350);
    }
  };

  recognition.onerror = (e) => {
    if (e.error !== "no-speech") {
      setStatus("MIC");
      reactorCaption.textContent = "Mikrofon izni gerekli";
    }
  };

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) return;
    addMessage("user", transcript);
    await askJarvis(transcript);
  };

  micBtn.addEventListener("click", async () => {
    if (busy) return;
    await ensureMicAnalyser();
    if (recognizing) stopListening();
    else startListening();
  });
}

if (window.speechSynthesis) {
  refreshVoice();
  window.speechSynthesis.onvoiceschanged = refreshVoice;
}

setupSpeech();
orbMode("idle");
addMessage("bot", "J.A.R.V.I.S. hologram çevrimiçi. Konuştukça küre hareket eder.");
refreshStatus();
setTimeout(() => speak("Jarvis çevrimiçi. Emrinizi bekliyorum."), 600);
