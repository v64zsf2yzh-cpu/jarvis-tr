const bootGate = document.getElementById("bootGate");
const bootBtn = document.getElementById("bootBtn");
const callUi = document.getElementById("callUi");
const userCam = document.getElementById("userCam");
const stateLine = document.getElementById("stateLine");
const subs = document.getElementById("subs");
const muteBtn = document.getElementById("muteBtn");
const camBtn = document.getElementById("camBtn");
const endBtn = document.getElementById("endBtn");

const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

let voiceOn = true;
let camOn = true;
let continuous = true;
let recognizing = false;
let busy = false;
let started = false;
let recognition = null;
let jarvisVoice = null;
let audioCtx = null;
let analyser = null;
let levelLoop = null;
let mediaStream = null;

function setOrb(mode) { window.JarvisOrb?.setMode(mode); }
function setState(t) { stateLine.textContent = t; }
function setSubs(t) { subs.textContent = t || ""; }

function pickVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) return null;
  const score = (v) => {
    const n = `${v.name} ${v.lang}`.toLowerCase();
    let s = 0;
    if (v.lang?.toLowerCase().startsWith("tr")) s += 80;
    if (v.lang?.toLowerCase().startsWith("en-gb")) s += 30;
    if (/male|daniel|thomas|james|david|arthur/.test(n)) s += 20;
    if (/female|filiz|yelda|zira/.test(n)) s -= 12;
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
    setSubs(text);
    const parts = (text.match(/[^.!?…]+[.!?…]*/g) || [text]).map((x) => x.trim()).filter(Boolean).slice(0, 14);
    let i = 0;
    const next = () => {
      if (i >= parts.length) {
        setOrb(continuous ? "listening" : "idle");
        setState(continuous ? "Dinliyor" : "Hazır");
        resolve();
        return;
      }
      const u = new SpeechSynthesisUtterance(parts[i++]);
      if (jarvisVoice) {
        u.voice = jarvisVoice;
        u.lang = jarvisVoice.lang || "tr-TR";
      } else u.lang = "tr-TR";
      u.rate = isIOS ? 0.95 : 0.9;
      u.pitch = 0.76;
      setOrb("speaking");
      setState("Konuşuyor");
      const pulse = setInterval(() => window.JarvisOrb?.pulse(0.55 + Math.random() * 0.4), 80);
      u.onend = () => { clearInterval(pulse); next(); };
      u.onerror = () => { clearInterval(pulse); next(); };
      speechSynthesis.speak(u);
    };
    next();
  });
}

async function openMedia() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 860 } },
    });
    userCam.srcObject = mediaStream;
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") await audioCtx.resume();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    // sadece ses kanalını analize bağla
    const audioTracks = mediaStream.getAudioTracks();
    if (audioTracks.length) {
      const audioOnly = new MediaStream(audioTracks);
      audioCtx.createMediaStreamSource(audioOnly).connect(analyser);
    }
    return true;
  } catch (_) {
    // sadece mikrofon dene
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      audioCtx.createMediaStreamSource(mediaStream).connect(analyser);
      userCam.style.display = "none";
      camOn = false;
      camBtn.setAttribute("aria-pressed", "false");
      return true;
    } catch {
      setState("İzin gerekli");
      return false;
    }
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

async function askJarvis(message) {
  if (busy || !message) return;
  busy = true;
  setOrb("thinking");
  setState("Düşünüyor");
  setSubs(message);

  let full = "";
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
        if (ev.type === "token" && ev.token) {
          full += ev.token;
          setSubs(full);
          window.JarvisOrb?.pulse(0.4 + Math.random() * 0.4);
        }
        if (ev.type === "done") full = ev.reply || full;
      }
    }
    if (!full.trim()) full = "Yanıt alamadım efendim.";
    await speak(full);
    if (continuous) setTimeout(() => startListening(), 280);
    else setState("Hazır");
  } catch (_) {
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      await speak(data.reply || "Bağlantı hatası.");
    } catch {
      await speak("Bağlantı hatası.");
    }
  } finally {
    busy = false;
  }
}

function startListening() {
  if (!recognition || recognizing || busy || !voiceOn) return;
  try { recognition.start(); } catch (_) {}
}
function stopListening() {
  try { recognition?.stop(); } catch (_) {}
}

function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    setState("Ses tanıma yok");
    return;
  }
  recognition = new SR();
  recognition.lang = "tr-TR";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.onstart = () => {
    recognizing = true;
    setOrb("listening");
    setState("Dinliyor");
    speechSynthesis?.cancel();
    startLevels();
  };
  recognition.onend = () => {
    recognizing = false;
    stopLevels();
    if (continuous && voiceOn && !busy) {
      setTimeout(() => {
        if (continuous && !busy && !recognizing) startListening();
      }, 350);
    }
  };
  recognition.onresult = async (ev) => {
    let interim = "";
    let finalText = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalText += t;
      else interim += t;
    }
    if (interim) setSubs(interim);
    if (finalText.trim()) {
      setSubs(finalText.trim());
      await askJarvis(finalText.trim());
    }
  };
}

async function startCall() {
  if (started) return;
  started = true;
  unlockAudio();
  callUi.hidden = false;
  bootGate.classList.add("hide");
  setTimeout(() => bootGate.remove(), 500);

  // Ana orb'u yeniden bağla (gate preview kalktıktan sonra)
  // orb.js zaten #orb için oluşturdu
  setOrb("thinking");
  setState("Bağlanıyor");

  const ok = await openMedia();
  jarvisVoice = pickVoice();
  await speak("Jarvis çevrimiçi. Görüntülü görüşme hazır. Emrinizi bekliyorum.");

  if (ok && recognition && voiceOn) {
    startListening();
  } else {
    setState("Mikrofon / kamera izni gerekli");
  }
}

function endCall() {
  continuous = false;
  stopListening();
  speechSynthesis?.cancel();
  mediaStream?.getTracks()?.forEach((t) => t.stop());
  setOrb("idle");
  setState("Görüşme bitti");
  setSubs("Yenilemek için sayfayı yenileyin");
  userCam.srcObject = null;
}

muteBtn.addEventListener("click", () => {
  voiceOn = !voiceOn;
  muteBtn.setAttribute("aria-pressed", String(voiceOn));
  muteBtn.textContent = voiceOn ? "Ses" : "Sessiz";
  if (!voiceOn) {
    stopListening();
    speechSynthesis?.cancel();
    setState("Sessiz");
  } else {
    continuous = true;
    startListening();
  }
});

camBtn.addEventListener("click", () => {
  camOn = !camOn;
  camBtn.setAttribute("aria-pressed", String(camOn));
  const v = mediaStream?.getVideoTracks?.()?.[0];
  if (v) v.enabled = camOn;
  userCam.style.opacity = camOn ? "1" : "0.2";
});

endBtn.addEventListener("click", endCall);
bootBtn.addEventListener("click", startCall);

if (window.speechSynthesis) {
  speechSynthesis.onvoiceschanged = () => { jarvisVoice = pickVoice(); };
}
setupSpeech();
setOrb("idle");
