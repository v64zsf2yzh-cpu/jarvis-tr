const bootGate = document.getElementById("bootGate");
const bootBtn = document.getElementById("bootBtn");
const textBtn = document.getElementById("textBtn");
const callUi = document.getElementById("callUi");
const userCam = document.getElementById("userCam");
const stateLine = document.getElementById("stateLine");
const subs = document.getElementById("subs");
const muteBtn = document.getElementById("muteBtn");
const camBtn = document.getElementById("camBtn");
const endBtn = document.getElementById("endBtn");
const panelBtn = document.getElementById("panelBtn");
const sidePanel = document.getElementById("sidePanel");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatLog = document.getElementById("chatLog");
const gateStatus = document.getElementById("gateStatus");
const hudClock = document.getElementById("hudClock");
const hudBrain = document.getElementById("hudBrain");
const hudLearn = document.getElementById("hudLearn");

const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

let voiceOn = true, camOn = true, continuous = true, recognizing = false, busy = false, started = false, textOnly = false;
let recognition = null, jarvisVoice = null, audioCtx = null, analyser = null, levelLoop = null, mediaStream = null;
let lastReply = "", nudgeTimer = null, knownName = "";

function setOrb(mode) { window.JarvisOrb?.setMode(mode); }
function setState(t) { if (stateLine) stateLine.textContent = t; }
function setSubs(t) { if (subs) subs.textContent = t || ""; }
function addLog(who, text) {
  if (!chatLog || !text) return;
  const p = document.createElement("p");
  p.className = who === "u" ? "u" : "j";
  p.textContent = (who === "u" ? "Siz: " : "Jarvis: ") + text;
  chatLog.appendChild(p);
  chatLog.scrollTop = chatLog.scrollHeight;
}
function cleanSpeak(t) {
  return String(t || "").replace(/```[\s\S]*?```/g, " ").replace(/[*_`#]+/g, " ").replace(/^\s*[-•]\s*/gm, " ").replace(/\s+/g, " ").trim();
}
function dayPart() {
  const h = new Date().getHours();
  if (h < 6) return "İyi geceler";
  if (h < 12) return "Günaydın";
  if (h < 18) return "İyi günler";
  return "İyi akşamlar";
}
function tickClock() {
  const n = new Date();
  const pad = (x) => String(x).padStart(2, "0");
  if (hudClock) hudClock.textContent = pad(n.getHours()) + ":" + pad(n.getMinutes());
}
async function refreshStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    if (s.user_name) knownName = s.user_name;
    const brain = s.gemini?.configured ? ("Gemini " + (s.gemini.model || "")) :
      (s.ollama?.available ? ("Ollama " + (s.ollama.active_model || "")) : "yerel");
    if (hudBrain) hudBrain.textContent = brain;
    const ev = s.evolve || {};
    if (hudLearn) hudLearn.textContent = "öğreti " + (ev.learned || 0) + " · görev " + (s.tasks || 0);
    if (gateStatus) gateStatus.textContent = "v" + (s.version || "4.3") + " · " + brain;
    return s;
  } catch {
    if (gateStatus) gateStatus.textContent = "Sunucu bekleniyor";
    return null;
  }
}
async function pollNudge() {
  if (!started || busy || textOnly || !voiceOn) return;
  try {
    const data = await (await fetch("/api/nudge")).json();
    if (data.speak) {
      lastReply = data.speak;
      addLog("j", data.speak);
      stopListening();
      await speak(data.speak);
      if (continuous) setTimeout(() => startListening(), 250);
    }
  } catch (_) {}
}
function startNudge() {
  if (nudgeTimer) clearInterval(nudgeTimer);
  nudgeTimer = setInterval(pollNudge, 20000);
}
function pickVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) return null;
  const score = (v) => {
    const n = (v.name + " " + v.lang).toLowerCase();
    let s = 0;
    if (/google uk english male|daniel|arthur|george|thomas|james|ryan|malcolm|oliver|ravi/.test(n)) s += 120;
    if (v.lang?.toLowerCase().startsWith("en-gb")) s += 70;
    if (v.lang?.toLowerCase().startsWith("en-us") && /male|david|mark|guy/.test(n)) s += 40;
    if (/male|baritone/.test(n)) s += 25;
    if (v.lang?.toLowerCase().startsWith("tr")) s += 8;
    if (/female|filiz|yelda|zira|samantha|siri|karen|moira|tessa|fiona/.test(n)) s -= 80;
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
      w.volume = 0; speechSynthesis.speak(w); speechSynthesis.cancel();
    }
  } catch (_) {}
}
function protocolChime() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const t0 = audioCtx.currentTime;
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(880, t0);
    o.frequency.exponentialRampToValueAtTime(440, t0 + 0.18);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(0.12, t0 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.28);
    o.connect(g); g.connect(audioCtx.destination);
    o.start(t0); o.stop(t0 + 0.3);
  } catch (_) {}
}
function speak(text) {
  return new Promise((resolve) => {
    text = cleanSpeak(text);
    if (!voiceOn || !window.speechSynthesis || textOnly) {
      setOrb(continuous && !textOnly ? "listening" : "idle"); resolve(); return;
    }
    speechSynthesis.cancel(); jarvisVoice = pickVoice(); setSubs(text);
    protocolChime();
    const parts = (text.match(/[^.!?...]+[.!?...]*/g) || [text]).map((x) => x.trim()).filter(Boolean).slice(0, 8);
    let i = 0;
    const next = () => {
      if (i >= parts.length) {
        setOrb(continuous && !textOnly ? "listening" : "idle");
        setState(continuous && !textOnly ? "Dinliyor — konuşun" : "Hazır"); resolve(); return;
      }
      const u = new SpeechSynthesisUtterance(parts[i++]);
      if (jarvisVoice) { u.voice = jarvisVoice; u.lang = jarvisVoice.lang || "en-GB"; }
      else u.lang = "en-GB";
      u.rate = isIOS ? 0.88 : 0.82;
      u.pitch = 0.62;
      u.volume = 1;
      setOrb("speaking"); setState("Konuşuyor");
      const pulse = setInterval(() => window.JarvisOrb?.pulse(0.55 + Math.random() * 0.4), 80);
      u.onend = () => { clearInterval(pulse); next(); };
      u.onerror = () => { clearInterval(pulse); next(); };
      setTimeout(() => speechSynthesis.speak(u), i === 1 ? 220 : 40);
    };
    next();
  });
}
async function openMedia() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 860 } } });
    userCam.srcObject = mediaStream;
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") await audioCtx.resume();
    analyser = audioCtx.createAnalyser(); analyser.fftSize = 256;
    const audioTracks = mediaStream.getAudioTracks();
    if (audioTracks.length) audioCtx.createMediaStreamSource(new MediaStream(audioTracks)).connect(analyser);
    return true;
  } catch (_) {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser(); analyser.fftSize = 256;
      audioCtx.createMediaStreamSource(mediaStream).connect(analyser);
      if (userCam) userCam.style.display = "none"; camOn = false; camBtn?.setAttribute("aria-pressed", "false");
      return true;
    } catch {
      setState("Mikrofon izni gerekli"); if (userCam) userCam.style.display = "none"; return false;
    }
  }
}
function startLevels() {
  stopLevels(); if (!analyser) return;
  const data = new Uint8Array(analyser.frequencyBinCount);
  levelLoop = setInterval(() => {
    if (!recognizing) return;
    analyser.getByteFrequencyData(data);
    let sum = 0; for (const v of data) sum += v;
    window.JarvisOrb?.setLevel(0.2 + (sum / data.length / 255) * 1.5);
  }, 40);
}
function stopLevels() { if (levelLoop) clearInterval(levelLoop); levelLoop = null; }
async function askJarvis(message) {
  if (!message) return;
  const low = message.toLocaleLowerCase("tr-TR");
  if (/\b(sus|kes sesi|sessiz ol|dur konuş)\b/.test(low) && message.split(/\s+/).length <= 6) {
    speechSynthesis.cancel(); setState("Sessiz"); setOrb("idle"); return;
  }
  if (/\b(tekrar et|tekrar söyle|ne dedin|bir daha söyle)\b/.test(low) && lastReply) {
    await speak(lastReply); return;
  }
  if (busy) return;
  busy = true; setOrb("thinking"); setState("Düşünüyor"); setSubs(message); addLog("u", message);
  let full = "";
  try {
    const res = await fetch("/api/chat/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) });
    if (!res.ok || !res.body) throw new Error("stream");
    const reader = res.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n"); buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let ev; try { ev = JSON.parse(line); } catch { continue; }
        if (ev.type === "token" && ev.token) { full += ev.token; setSubs(full); window.JarvisOrb?.pulse(0.4 + Math.random() * 0.4); }
        if (ev.type === "done") full = ev.reply || full;
      }
    }
    if (!full.trim()) full = "Yanıt alamadım, efendim.";
    full = cleanSpeak(full); lastReply = full;
    addLog("j", full); await speak(full); refreshStatus();
    if (continuous && !textOnly) setTimeout(() => startListening(), 220); else setState("Hazır");
  } catch (_) {
    try {
      const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) });
      const data = await res.json();
      const reply = cleanSpeak(data.reply || "Bağlantı hatası."); lastReply = reply;
      addLog("j", reply); await speak(reply);
    } catch { await speak("Bağlantı hatası, efendim."); }
  } finally { busy = false; }
}
function startListening() {
  if (textOnly || !recognition || recognizing || busy || !voiceOn) return;
  try { recognition.start(); } catch (_) {}
}
function stopListening() { try { recognition?.stop(); } catch (_) {} }
function setupSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { setState("Bu tarayıcıda ses tanıma yok — Chrome/Edge kullanın"); return; }
  recognition = new SR(); recognition.lang = "tr-TR"; recognition.interimResults = true; recognition.continuous = false;
  recognition.onstart = () => { recognizing = true; setOrb("listening"); setState("Dinliyor — konuşun"); startLevels(); };
  recognition.onend = () => {
    recognizing = false; stopLevels();
    if (continuous && voiceOn && !busy && !textOnly) setTimeout(() => { if (continuous && !busy && !recognizing && !textOnly) startListening(); }, 280);
  };
  recognition.onresult = async (ev) => {
    let interim = "", finalText = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalText += t; else interim += t;
    }
    if (interim) setSubs(interim);
    if (finalText.trim()) { setSubs(finalText.trim()); stopListening(); await askJarvis(finalText.trim()); }
  };
}
async function startCall(opts = {}) {
  if (started) return; started = true; textOnly = !!opts.textOnly;
  document.body.classList.toggle("voice-mode", !textOnly);
  document.body.classList.toggle("text-mode", textOnly);
  if (textOnly) {
    voiceOn = false; camOn = false; continuous = false;
    muteBtn?.setAttribute("aria-pressed", "false"); if (muteBtn) muteBtn.textContent = "Sessiz";
    camBtn?.setAttribute("aria-pressed", "false"); if (userCam) userCam.style.display = "none";
    sidePanel?.classList.remove("collapsed"); panelBtn?.setAttribute("aria-pressed", "true");
  } else {
    voiceOn = true; continuous = true;
    sidePanel?.classList.add("collapsed"); panelBtn?.setAttribute("aria-pressed", "false");
  }
  unlockAudio(); callUi.hidden = false; bootGate.classList.add("hide"); setTimeout(() => bootGate.remove(), 500);
  setOrb("thinking"); setState(textOnly ? "Yazılı sohbet" : "Bağlanıyor");
  let ok = false; if (!textOnly) ok = await openMedia();
  jarvisVoice = pickVoice();
  const s = await refreshStatus();
  const name = (s && s.user_name) || knownName || "efendim";
  const tasks = (s && s.tasks) || 0;
  let hello = textOnly
    ? `Jarvis çevrimiçi. ${dayPart()} ${name}.`
    : `Defense protocol standing by. ${dayPart()} ${name}. Jarvis çevrimiçi.`;
  if (tasks) hello += ` ${tasks} açık görevin var.`;
  lastReply = hello; addLog("j", hello); await speak(hello);
  startNudge();
  if (!textOnly && ok && recognition && voiceOn) startListening();
  else if (!textOnly) setState("Mikrofon yok — Chrome'dan açın");
  else { setState("Hazır"); setOrb("idle"); chatInput?.focus(); }
}
function endCall() {
  continuous = false; stopListening(); speechSynthesis?.cancel();
  if (nudgeTimer) { clearInterval(nudgeTimer); nudgeTimer = null; }
  mediaStream?.getTracks()?.forEach((t) => t.stop());
  setOrb("idle"); setState("Görüşme bitti"); setSubs("Yenilemek için sayfayı yenileyin");
  if (userCam) userCam.srcObject = null;
}
muteBtn?.addEventListener("click", () => {
  voiceOn = !voiceOn; muteBtn.setAttribute("aria-pressed", String(voiceOn)); muteBtn.textContent = voiceOn ? "Ses" : "Sessiz";
  if (!voiceOn) { stopListening(); speechSynthesis?.cancel(); setState("Sessiz"); }
  else { textOnly = false; continuous = true; document.body.classList.add("voice-mode"); startListening(); }
});
camBtn?.addEventListener("click", () => {
  camOn = !camOn; camBtn.setAttribute("aria-pressed", String(camOn));
  const v = mediaStream?.getVideoTracks?.()?.[0]; if (v) v.enabled = camOn;
  if (userCam) userCam.style.opacity = camOn ? "1" : "0.2";
});
panelBtn?.addEventListener("click", () => {
  const collapsed = sidePanel?.classList.toggle("collapsed");
  panelBtn.setAttribute("aria-pressed", String(!collapsed));
});
document.getElementById("chips")?.addEventListener("click", (e) => {
  const q = e.target?.getAttribute?.("data-q"); if (q) askJarvis(q);
});
chatForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = (chatInput.value || "").trim(); if (!msg) return;
  chatInput.value = ""; stopListening(); await askJarvis(msg);
});
endBtn?.addEventListener("click", endCall);
bootBtn?.addEventListener("click", () => startCall({ textOnly: false }));
textBtn?.addEventListener("click", () => startCall({ textOnly: true }));
if (window.speechSynthesis) speechSynthesis.onvoiceschanged = () => { jarvisVoice = pickVoice(); };
setupSpeech(); setOrb("idle"); tickClock(); setInterval(tickClock, 15000); refreshStatus(); setInterval(refreshStatus, 20000);
