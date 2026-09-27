const logEl = document.getElementById("log");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const micBtn = document.getElementById("micBtn");
const speakToggle = document.getElementById("speakToggle");
const retrainBtn = document.getElementById("retrainBtn");
const teachForm = document.getElementById("teachForm");
const teachQ = document.getElementById("teachQ");
const teachA = document.getElementById("teachA");
const core = document.getElementById("core");
const statusLine = document.getElementById("statusLine");
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
}

function setStatus(text) {
  statusLine.textContent = text;
}

function speak(text) {
  if (!voiceOn || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "tr-TR";
  u.rate = 1.02;
  const voices = window.speechSynthesis.getVoices();
  const tr = voices.find((v) => v.lang?.toLowerCase().startsWith("tr"));
  if (tr) u.voice = tr;
  window.speechSynthesis.speak(u);
}

async function refreshStatus() {
  try {
    const s = await fetch("/api/status").then((r) => r.json());
    setStatus(
      `Çevrimiçi · %${(s.accuracy * 100).toFixed(0)} · ${s.knowledge_count} öğreti`
    );
  } catch (_) {}
}

async function askJarvis(message) {
  core.classList.add("thinking");
  setStatus("İşleniyor");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Hata");
    const meta = `${data.intent} · %${Math.round(data.confidence * 100)}`;
    addMessage("bot", data.reply, meta);
    speak(data.reply);
    await refreshStatus();
  } catch (err) {
    addMessage("bot", "Bağlantı hatası. Sunucu çalışıyor mu?");
    setStatus("Bağlantı kesildi");
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
  input.focus();
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
    addMessage("bot", "Öğrendim. Kalıcı için «Yeniden eğit»e bas.");
    teachQ.value = "";
    teachA.value = "";
    await refreshStatus();
  } catch (_) {
    addMessage("bot", "Öğretme isteği başarısız.");
  }
});

retrainBtn.addEventListener("click", async () => {
  core.classList.add("thinking");
  setStatus("Sıfırdan eğitiliyor…");
  retrainBtn.disabled = true;
  addMessage("bot", "Yeniden eğitim başladı…");
  try {
    const res = await fetch("/api/retrain", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error("retrain");
    const m = data.meta;
    const msg = `Eğitim bitti. Doğruluk %${Math.round(m.accuracy * 100)} · ${m.samples} örnek.`;
    addMessage("bot", msg);
    speak(msg);
    await refreshStatus();
  } catch (_) {
    addMessage("bot", "Eğitim sırasında hata oluştu.");
  } finally {
    retrainBtn.disabled = false;
    core.classList.remove("thinking");
  }
});

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.disabled = true;
    micBtn.title = "Ses tanıma desteklenmiyor";
    return;
  }
  recognition = new SR();
  recognition.lang = "tr-TR";
  recognition.interimResults = false;
  recognition.continuous = false;

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
    setStatus("Sistemler çevrimiçi");
  };

  recognition.onerror = () => setStatus("Mikrofon hatası");

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) return;
    addMessage("user", transcript);
    await askJarvis(transcript);
  };

  micBtn.addEventListener("click", () => {
    if (!recognition) return;
    if (recognizing) {
      recognition.stop();
      return;
    }
    recognition.start();
  });
}

setupSpeech();
addMessage("bot", "Merhaba. Jarvis hazır. Yaz veya mikrofona bas.");
refreshStatus();

// Mobil klavye açılınca sohbeti alta kaydır
input.addEventListener("focus", () => {
  setTimeout(() => {
    logEl.scrollTop = logEl.scrollHeight;
  }, 300);
});
