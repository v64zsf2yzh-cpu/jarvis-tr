const logEl = document.getElementById("log");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const micBtn = document.getElementById("micBtn");
const speakToggle = document.getElementById("speakToggle");
const clearBtn = document.getElementById("clearBtn");
const retrainBtn = document.getElementById("retrainBtn");
const teachForm = document.getElementById("teachForm");
const teachQ = document.getElementById("teachQ");
const teachA = document.getElementById("teachA");
const core = document.getElementById("core");
const statusLine = document.getElementById("statusLine");
const lede = document.getElementById("lede");
const quickRow = document.getElementById("quickRow");

let voiceOn = true;
let recognizing = false;
let recognition = null;

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

function setStatus(text) {
  statusLine.textContent = text;
}

function speak(text) {
  if (!voiceOn || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.slice(0, 600));
  u.lang = "tr-TR";
  u.rate = 1.02;
  const voices = window.speechSynthesis.getVoices();
  const tr = voices.find((v) => v.lang?.toLowerCase().startsWith("tr"));
  if (tr) u.voice = tr;
  window.speechSynthesis.speak(u);
}

function showTyping() {
  const row = addMessage("bot", "Düşünüyorum…");
  row.classList.add("typing");
  row.querySelector(".bubble").classList.add("typing-dots");
  return row;
}

async function refreshStatus() {
  try {
    const s = await fetch("/api/status").then((r) => r.json());
    const oll = s.ollama || {};
    if (oll.available && oll.active_model) {
      setStatus(`Çevrimiçi · ${oll.active_model}`);
      lede.textContent = `Ollama hazır (${oll.active_model}). Her soruyu sorabilirsin.`;
    } else {
      setStatus("Ollama kapalı — model kur");
      lede.textContent = "Genel cevap için VPS’te: ollama pull llama3.2";
    }
  } catch (_) {
    setStatus("Bağlantı yok");
  }
}

async function askJarvis(message) {
  core.classList.add("thinking");
  setStatus("Düşünüyor…");
  const typing = showTyping();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    typing.remove();
    if (!res.ok) throw new Error(data.error || "Hata");
    const meta = `${data.intent} · ${data.model || ""}`;
    addMessage("bot", data.reply, meta);
    speak(data.reply);
    await refreshStatus();
  } catch (err) {
    typing.remove();
    addMessage("bot", "Bağlantı hatası. python3 app.py çalışıyor mu?");
    setStatus("Hata");
  } finally {
    core.classList.remove("thinking");
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  addMessage("user", message);
  input.value = "";
  await askJarvis(message);
});

quickRow?.addEventListener("click", async (e) => {
  const btn = e.target.closest(".chip");
  if (!btn) return;
  const q = btn.dataset.q;
  addMessage("user", q);
  await askJarvis(q);
});

speakToggle.addEventListener("click", () => {
  voiceOn = !voiceOn;
  speakToggle.setAttribute("aria-pressed", String(voiceOn));
  speakToggle.textContent = voiceOn ? "Ses açık" : "Ses kapalı";
  if (!voiceOn && window.speechSynthesis) window.speechSynthesis.cancel();
});

clearBtn?.addEventListener("click", () => {
  logEl.innerHTML = "";
  addMessage("bot", "Sohbet temizlendi. Buyurun.");
});

teachForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = teachQ.value.trim();
  const answer = teachA.value.trim();
  if (!question || !answer) return;
  addMessage("user", `öğret ${question} | ${answer}`);
  try {
    const res = await fetch("/api/teach", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, answer }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Hata");
    addMessage("bot", "Öğrendim.");
    teachQ.value = "";
    teachA.value = "";
  } catch (_) {
    addMessage("bot", "Öğretme başarısız.");
  }
});

retrainBtn.addEventListener("click", async () => {
  retrainBtn.disabled = true;
  addMessage("bot", "Yeniden eğitiliyor…");
  try {
    const res = await fetch("/api/retrain", { method: "POST" });
    const data = await res.json();
    addMessage("bot", `Eğitim bitti · %${Math.round((data.meta?.accuracy || 0) * 100)}`);
  } catch (_) {
    addMessage("bot", "Eğitim hatası.");
  } finally {
    retrainBtn.disabled = false;
  }
});

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.disabled = true;
    return;
  }
  recognition = new SR();
  recognition.lang = "tr-TR";
  recognition.onstart = () => {
    recognizing = true;
    micBtn.setAttribute("aria-pressed", "true");
    core.classList.add("listening");
    setStatus("Dinliyorum");
  };
  recognition.onend = () => {
    recognizing = false;
    micBtn.setAttribute("aria-pressed", "false");
    core.classList.remove("listening");
  };
  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) return;
    addMessage("user", transcript);
    await askJarvis(transcript);
  };
  micBtn.addEventListener("click", () => {
    if (recognizing) recognition.stop();
    else recognition.start();
  });
}

setupSpeech();
addMessage("bot", "Jarvis v3 hazır. Ollama açıksa her soruna cevap veririm.");
refreshStatus();
