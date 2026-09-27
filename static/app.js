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
const liveCaption = document.getElementById("liveCaption");
const feedList = document.getElementById("feedList");
const bootGate = document.getElementById("bootGate");
const bootBtn = document.getElementById("bootBtn");

const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

let voiceOn = true;
let continuous = true; // varsayılan açık
let recognizing = false;
let busy = false;
let started = false;
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

function tickClock() {
  const now = new Date();
  document.getElementById("clock").textContent = now.toLocaleTimeString("tr-TR");
  document.getElementById("dateLine").textContent = now.toLocaleDateString("tr-TR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  const cpu = 12 + Math.round(8 * Math.abs(Math.sin(Date.now() / 3000)));
  const ram = 40 + Math.round(6 * Math.abs(Math.sin(Date.now() / 4000)));
  const disk = 35;
  document.getElementById("gCpu").textContent = `${cpu}%`;
  document.getElementById("gRam").textContent = `${ram}%`;
  document.getElementById("gDisk").textContent = `${disk}%`;
  document.querySelectorAll(".gauge").forEach((g, i) => {
    g.style.setProperty("--p", [cpu, ram, disk][i]);
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
    if (v.lang?.toLowerCase().startsWith("tr")) s += 80;
    if (v.lang?.toLowerCase().startsWith("en-gb")) s += 25;
    if (/male|yuri|cem|tolga|ahmet|emre|daniel|thomas|james|david/.test(n)) s += 20;
    if (/female|filiz|yelda|zira|susan/.test(n)) s -= 10;
    return s;
  };
  return [...voices].sort((a, b) => score(b) - score(a))[0];
}

function refreshVoice() {
  jarvisVoice = pickVoice();
}

function unlockAudio() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    // iOS speech unlock: sessiz utterance
    if (window.speechSynthesis) {
      const warm = new SpeechSynthesisUtterance(" ");
      warm.volume = 0;
      window.speechSynthesis.speak(warm);
      window.speechSynthesis.cancel();
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
    window.speechSynthesis.cancel();
    refreshVoice();
    const parts = (text.match(/[^.!?…]+[.!?…]*/g) || [text])
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 16);
    let i = 0;
    const next = () => {
      if (i >= parts.length) {
        setOrb(continuous ? "listening" : "idle");
        voiceState.textContent = continuous ? "Dinliyorum…" : "Beklemede";
        liveCaption.textContent = continuous ? "Dinliyorum" : "Hazır";
        resolve();
        return;
      }
      const u = new SpeechSynthesisUtterance(parts[i++]);
      if (jarvisVoice) {
        u.voice = jarvisVoice;
        u.lang = jarvisVoice.lang || "tr-TR";
      } else {
        u.lang = "tr-TR";
      }
      u.rate = isIOS ? 0.95 : 0.9;
      u.pitch = 0.78;
      u.volume = 1;
      setOrb("speaking");
      voiceState.textContent = "Konuşuyor…";
      liveCaption.textContent = "Jarvis konuşuyor";
      const pulse = setInterval(() => {
        window.JarvisOrb?.pulse(0.55 + Math.random() * 0.4);
        window.JarvisWaves?.setEnergy(0.55 + Math.random() * 0.4);
      }, 80);
      u.onend = () => { clearInterval(pulse); next(); };
      u.onerror = () => { clearInterval(pulse); next(); };
      window.speechSynthesis.speak(u);
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
    feed("Mikrofon izni yok — yazarak kullanabilirsiniz");
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
    const gem = s.gemini || {};
    const oll = s.ollama || {};
    const card = document.getElementById("cardOllama");
    document.getElementById("stMem").textContent = `${s.memory_count || 0} kayıt`;
    document.getElementById("memBadge").textContent = s.knowledge_count || 0;
    document.getElementById("stNlu").textContent = `%${Math.round((s.accuracy || 0) * 100)}`;
    if (gem.configured) {
      document.getElementById("stLlm").textContent = gem.model || "Gemini";
      document.getElementById("stLlm").classList.add("ok");
      card.classList.add("on");
      card.querySelector("span").textContent = "Gemini";
      card.querySelector("b").textContent = "Bağlı";
      document.getElementById("sysPill").textContent = "OPTİMAL";
    } else if (oll.available && oll.active_model) {
      document.getElementById("stLlm").textContent = oll.active_model;
      document.getElementById("stLlm").classList.add("ok");
      card.classList.add("on");
      card.querySelector("span").textContent = "Ollama";
      card.querySelector("b").textContent = "Bağlı";
      document.getElementById("sysPill").textContent = "OPTİMAL";
    } else {
      document.getElementById("stLlm").textContent = "Kapalı";
      card.querySelector("b").textContent = "Yok";
      document.getElementById("sysPill").textContent = "SINIRLI";
    }
  } catch (_) {
    document.getElementById("sysPill").textContent = "BAĞLANTI YOK";
  }
}

async function askJarvis(message) {
  if (busy || !message) return;
  busy = true;
  setOrb("thinking");
  voiceState.textContent = "İşleniyor…";
  liveCaption.textContent = "Analiz";
  feed(`Sorgu: ${message.slice(0, 42)}`);

  const row = addMessage("bot", "");
  const bubble = row.querySelector(".bubble");
  bubble.textContent = "";
  let metaEl = null;
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
    voiceState.textContent = "Yanıt geliyor…";
    liveCaption.textContent = "Canlı yanıt";

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
          window.JarvisWaves?.setEnergy(0.4 + Math.random() * 0.4);
        }
        if (ev.type === "done") {
          full = ev.reply || full;
          bubble.textContent = full;
          model = ev.model || model;
          intent = ev.intent || intent;
        }
      }
    }

    if (!full.trim()) {
      bubble.textContent = "Yanıt alınamadı.";
    } else {
      metaEl = document.createElement("div");
      metaEl.className = "meta";
      metaEl.textContent = `${intent} · ${model}`;
      row.append(metaEl);
      feed(`Yanıt: ${model || "çekirdek"}`);
      await speak(full);
    }
    await refreshStatus();
    if (continuous) setTimeout(() => startListening(), 250);
    else {
      setOrb("idle");
      voiceState.textContent = "Beklemede";
      liveCaption.textContent = "Hazır";
    }
  } catch (_) {
    // stream yoksa klasik API
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
      bubble.textContent = "Bağlantı hatası. VPS’te python3 app.py çalışıyor mu?";
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
  setTimeout(() => bootGate?.remove(), 500);

  continuous = true;
  convBtn?.setAttribute("aria-pressed", "true");
  if (convBtn) convBtn.textContent = "Sürekli sohbet açık";

  addMessage("bot", "J.A.R.V.I.S. çevrimiçi. Sürekli sohbet aktif.");
  feed("Sistem açıldı");
  await refreshStatus();

  const greet = "Jarvis komuta merkezi çevrimiçi. Emrinizi bekliyorum.";
  await speak(greet);

  const micOk = await ensureMic();
  if (micOk && recognition) {
    startLevels();
    startListening();
    liveCaption.textContent = "Dinliyorum";
    voiceState.textContent = "Dinliyorum…";
    feed("Mikrofon aktif");
  } else {
    liveCaption.textContent = "Yazarak konuşun";
    voiceState.textContent = "Mikrofon yok — yazın";
    feed("Mikrofon kullanılamıyor (iOS/izin)");
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

async function toggleMic() {
  if (!started) {
    await bootJarvis();
    return;
  }
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
  speakToggle.textContent = voiceOn ? "Jarvis sesi açık" : "Ses kapalı";
  if (!voiceOn) window.speechSynthesis?.cancel();
});

convBtn?.addEventListener("click", async () => {
  if (!started) await bootJarvis();
  continuous = !continuous;
  convBtn.setAttribute("aria-pressed", String(continuous));
  convBtn.textContent = continuous ? "Sürekli sohbet açık" : "Sürekli sohbet kapalı";
  if (continuous) {
    await ensureMic();
    startLevels();
    startListening();
  } else {
    stopListening();
    stopLevels();
    setOrb("idle");
  }
});

clearBtn?.addEventListener("click", () => {
  logEl.innerHTML = "";
  addMessage("bot", "Sohbet temizlendi.");
});

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!started) await bootJarvis();
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const act = btn.dataset.act;
    if (act === "sohbet") document.getElementById("chatPanel")?.scrollIntoView({ behavior: "smooth" });
    if (act === "hafiza") askJarvis("ne hatırlıyorsun");
    if (act === "durum") askJarvis("sistem durumu");
    if (act === "yardim") askJarvis("ne yapabilirsin");
    if (act === "selam") askJarvis("merhaba jarvis");
  });
});

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    talkLabel.textContent = "Bu tarayıcıda mikrofon tanıma yok";
    return;
  }
  recognition = new SR();
  recognition.lang = "tr-TR";
  recognition.interimResults = false;
  recognition.continuous = false;

  recognition.onstart = async () => {
    recognizing = true;
    micBtn?.setAttribute("aria-pressed", "true");
    talkLabel.textContent = "Dinliyorum…";
    setOrb("listening");
    voiceState.textContent = "Dinliyorum…";
    liveCaption.textContent = "Dinliyorum";
    window.speechSynthesis?.cancel();
    await ensureMic();
    startLevels();
  };

  recognition.onend = () => {
    recognizing = false;
    micBtn?.setAttribute("aria-pressed", "false");
    talkLabel.textContent = "Konuşmak için dokun";
    stopLevels();
    if (continuous && !busy) {
      setTimeout(() => {
        if (continuous && !busy && !recognizing) startListening();
      }, 400);
    } else if (!busy) setOrb("idle");
  };

  recognition.onerror = (e) => {
    if (e.error === "not-allowed") {
      talkLabel.textContent = "Mikrofon izni gerekli";
      feed("Mikrofon izni reddedildi");
    }
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
liveCaption.textContent = "Başlatmayı bekliyor";

// Boot gate — iOS için zorunlu dokunuş; masaüstünde de güvenli
bootBtn?.addEventListener("click", bootJarvis);
bootGate?.addEventListener("click", (e) => {
  if (e.target === bootGate) bootJarvis();
});

// Otomatik deneme (Android/Chrome bazen izin verir)
window.addEventListener("load", async () => {
  await refreshStatus();
  if (!isIOS) {
    // iOS değilse sessizce başlatmayı dene
    setTimeout(async () => {
      try {
        unlockAudio();
        // Konuşma denemesi
        if (window.speechSynthesis) {
          await bootJarvis();
        }
      } catch (_) {
        // gate açık kalsın
      }
    }, 400);
  }
});
