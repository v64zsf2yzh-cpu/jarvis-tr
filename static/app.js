const logEl = document.getElementById("log");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const micBtn = document.getElementById("micBtn");
const talkLabel = document.getElementById("talkLabel");
const speakToggle = document.getElementById("speakToggle");
const convBtn = document.getElementById("convBtn");
const clearBtn = document.getElementById("clearBtn");
const teachForm = document.getElementById("teachForm");
const teachQ = document.getElementById("teachQ");
const teachA = document.getElementById("teachA");
const core = document.getElementById("core");
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

function setStatus(text) {
  statusLine.textContent = text;
}

function pickJarvisVoice() {
  if (!window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  // Jarvis hissi: tercihen erkek, sakin, TR varsa TR; yoksa EN erkek
  const score = (v) => {
    const name = `${v.name} ${v.lang}`.toLowerCase();
    let s = 0;
    if (v.lang?.toLowerCase().startsWith("tr")) s += 50;
    if (v.lang?.toLowerCase().startsWith("en-gb")) s += 30;
    if (v.lang?.toLowerCase().startsWith("en")) s += 15;
    if (/male|david|daniel|george|thomas|arthur|james|brian|adam|baris|ahmet|tolga|emre/.test(name)) s += 25;
    if (/female|zira|susan|linda|filiz|yelda|aylin/.test(name)) s -= 20;
    if (/google|premium|enhanced|neural/.test(name)) s += 8;
    return s;
  };

  return [...voices].sort((a, b) => score(b) - score(a))[0] || null;
}

function refreshVoice() {
  jarvisVoice = pickJarvisVoice();
  if (jarvisVoice) {
    voiceTag.textContent = `SES · ${jarvisVoice.name.slice(0, 18)}`;
  }
}

function speak(text) {
  return new Promise((resolve) => {
    if (!voiceOn || !window.speechSynthesis) {
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    refreshVoice();

    // Uzun cevapları cümlelere böl — daha doğal Jarvis ritmi
    const chunks = text
      .replace(/\s+/g, " ")
      .match(/[^.!?…]+[.!?…]*/g) || [text];
    const parts = chunks.map((c) => c.trim()).filter(Boolean).slice(0, 12);

    let i = 0;
    const next = () => {
      if (i >= parts.length) {
        core.classList.remove("speaking");
        resolve();
        return;
      }
      const u = new SpeechSynthesisUtterance(parts[i++]);
      // Jarvis karakteri: sakin, biraz düşük, net
      if (jarvisVoice) {
        u.voice = jarvisVoice;
        u.lang = jarvisVoice.lang || "tr-TR";
      } else {
        u.lang = "tr-TR";
      }
      u.rate = 0.92;
      u.pitch = 0.78;
      u.volume = 1;
      core.classList.add("speaking");
      setStatus("KONUŞUYOR");
      reactorCaption.textContent = "Jarvis yanıtlıyor";
      u.onend = next;
      u.onerror = next;
      window.speechSynthesis.speak(u);
    };
    next();
  });
}

async function refreshStatus() {
  try {
    const s = await fetch("/api/status").then((r) => r.json());
    const oll = s.ollama || {};
    if (oll.available && oll.active_model) {
      modelTag.textContent = `MODEL · ${oll.active_model}`;
      setStatus("SİSTEM ÇEVRİMİÇİ");
    } else {
      modelTag.textContent = "MODEL · YOK";
      setStatus("OLLAMA KAPALI");
    }
  } catch (_) {
    setStatus("BAĞLANTI YOK");
  }
}

async function askJarvis(message) {
  if (busy) return;
  busy = true;
  core.classList.add("thinking");
  setStatus("İŞLENİYOR");
  reactorCaption.textContent = "Analiz ediliyor…";
  const typing = addMessage("bot", "Bir saniye efendim…");
  typing.classList.add("typing");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    typing.remove();
    if (!res.ok) throw new Error(data.error || "Hata");
    addMessage("bot", data.reply, `${data.intent} · ${data.model || ""}`);
    await speak(data.reply);
    await refreshStatus();
    if (continuous) {
      reactorCaption.textContent = "Dinliyorum…";
      startListening();
    } else {
      reactorCaption.textContent = "Dinlemek için KONUŞ’a bas";
      setStatus("SİSTEM HAZIR");
    }
  } catch (_) {
    typing.remove();
    addMessage("bot", "Bağlantı hatası. Sunucu çalışıyor mu?");
    setStatus("HATA");
    reactorCaption.textContent = "Hata";
  } finally {
    core.classList.remove("thinking");
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
  if (!recognition) return;
  try {
    recognition.stop();
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
  voiceTag.textContent = voiceOn ? "SES AKTİF" : "SES KAPALI";
  if (!voiceOn && window.speechSynthesis) window.speechSynthesis.cancel();
});

convBtn.addEventListener("click", () => {
  continuous = !continuous;
  convBtn.setAttribute("aria-pressed", String(continuous));
  if (continuous) {
    setStatus("SÜREKLİ SOHBET");
    reactorCaption.textContent = "Dinliyorum…";
    startListening();
  } else {
    stopListening();
    setStatus("SİSTEM HAZIR");
    reactorCaption.textContent = "Dinlemek için KONUŞ’a bas";
  }
});

clearBtn?.addEventListener("click", () => {
  logEl.innerHTML = "";
  addMessage("bot", "Arayüz temizlendi. Emrinizi bekliyorum.");
});

teachForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = teachQ.value.trim();
  const answer = teachA.value.trim();
  if (!question || !answer) return;
  addMessage("user", `öğret ${question} | ${answer}`);
  try {
    await fetch("/api/teach", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, answer }),
    });
    addMessage("bot", "Öğrendim efendim.");
    teachQ.value = "";
    teachA.value = "";
  } catch (_) {
    addMessage("bot", "Öğretme başarısız.");
  }
});

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.disabled = true;
    talkLabel.textContent = "DESTEK YOK";
    reactorCaption.textContent = "Bu tarayıcı ses tanımayı desteklemiyor";
    return;
  }

  recognition = new SR();
  recognition.lang = "tr-TR";
  recognition.interimResults = false;
  recognition.continuous = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    recognizing = true;
    micBtn.setAttribute("aria-pressed", "true");
    talkLabel.textContent = "DİNLİYOR";
    core.classList.add("listening");
    setStatus("DİNLİYORUM");
    reactorCaption.textContent = "Sizi dinliyorum…";
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  };

  recognition.onend = () => {
    recognizing = false;
    micBtn.setAttribute("aria-pressed", "false");
    talkLabel.textContent = "KONUŞ";
    core.classList.remove("listening");
    if (continuous && !busy) {
      // Kısa bekleme sonra tekrar dinle (konuşma bitince)
      setTimeout(() => {
        if (continuous && !busy && !recognizing) startListening();
      }, 400);
    }
  };

  recognition.onerror = (e) => {
    if (e.error === "no-speech" && continuous) return;
    setStatus("MİKROFON");
    reactorCaption.textContent = "Mikrofon hatası / izin gerekli";
  };

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) return;
    addMessage("user", transcript);
    await askJarvis(transcript);
  };

  // Bas-konuş + tıkla
  const press = () => {
    if (busy) return;
    if (recognizing) stopListening();
    else startListening();
  };
  micBtn.addEventListener("click", press);
  micBtn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    if (!recognizing && !busy) startListening();
  }, { passive: false });
  micBtn.addEventListener("touchend", () => {
    if (recognizing) stopListening();
  });
}

if (window.speechSynthesis) {
  refreshVoice();
  window.speechSynthesis.onvoiceschanged = refreshVoice;
}

setupSpeech();
addMessage("bot", "J.A.R.V.I.S. çevrimiçi. Büyük mavi butona basarak konuşabilirsiniz. Sürekli sohbet de açabilirsiniz.");
refreshStatus();

// İlk açılışta kısa Jarvis selamı
setTimeout(() => {
  speak("Jarvis çevrimiçi. Emrinizi bekliyorum.");
}, 700);
