/**
 * MCU tarzı turuncu holografik Jarvis küresi — konuşma/dinleme ile tepkili.
 */
(function () {
  const canvas = document.getElementById("orb");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const state = {
    mode: "idle", // idle | listening | thinking | speaking
    level: 0,
    target: 0,
    t: 0,
    particles: [],
  };

  // Dışarıdan kontrol
  window.JarvisOrb = {
    setMode(mode) {
      state.mode = mode || "idle";
      if (mode === "speaking") state.target = Math.max(state.target, 0.45);
      if (mode === "listening") state.target = Math.max(state.target, 0.35);
      if (mode === "thinking") state.target = 0.25;
      if (mode === "idle") state.target = 0.08;
    },
    setLevel(v) {
      state.target = Math.max(0, Math.min(1, v));
    },
    pulse(amount = 0.6) {
      state.target = Math.max(state.target, amount);
    },
  };

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const css = Math.min(canvas.clientWidth || 320, 640);
    canvas.width = Math.floor(css * dpr);
    canvas.height = Math.floor(css * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  // Parçacık ağı
  const N = 160;
  for (let i = 0; i < N; i++) {
    const u = Math.random();
    const v = Math.random();
    const theta = 2 * Math.PI * u;
    const phi = Math.acos(2 * v - 1);
    state.particles.push({
      theta,
      phi,
      r: 0.72 + Math.random() * 0.22,
      speed: 0.2 + Math.random() * 0.6,
      size: 0.8 + Math.random() * 1.8,
    });
  }

  function project(x, y, z, cx, cy, scale) {
    const persp = 1.35 / (1.35 + z);
    return [cx + x * scale * persp, cy + y * scale * persp, persp, z];
  }

  function rotY(x, y, z, a) {
    const c = Math.cos(a), s = Math.sin(a);
    return [x * c + z * s, y, -x * s + z * c];
  }
  function rotX(x, y, z, a) {
    const c = Math.cos(a), s = Math.sin(a);
    return [x, y * c - z * s, y * s + z * c];
  }

  function drawWireSphere(cx, cy, radius, rot, wobble, alpha) {
    const rings = 10;
    const segs = 48;
    ctx.lineWidth = 1;
    for (let i = 1; i < rings; i++) {
      const lat = (i / rings) * Math.PI;
      ctx.beginPath();
      for (let j = 0; j <= segs; j++) {
        const lon = (j / segs) * Math.PI * 2;
        let x = Math.sin(lat) * Math.cos(lon);
        let y = Math.cos(lat);
        let z = Math.sin(lat) * Math.sin(lon);
        x *= 1 + wobble * 0.04 * Math.sin(lon * 3 + state.t * 2);
        ;[x, y, z] = rotY(x, y, z, rot);
        ;[x, y, z] = rotX(x, y, z, rot * 0.6);
        const [px, py, p, depth] = project(x, y, z, cx, cy, radius);
        const a = alpha * (0.25 + 0.75 * p) * (0.35 + 0.65 * ((depth + 1) / 2));
        ctx.strokeStyle = `rgba(255, ${140 + depth * 40}, 40, ${a})`;
        if (j === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
    // meridyenler
    for (let i = 0; i < 12; i++) {
      const lon = (i / 12) * Math.PI * 2;
      ctx.beginPath();
      for (let j = 0; j <= segs; j++) {
        const lat = (j / segs) * Math.PI;
        let x = Math.sin(lat) * Math.cos(lon);
        let y = Math.cos(lat);
        let z = Math.sin(lat) * Math.sin(lon);
        ;[x, y, z] = rotY(x, y, z, rot * 1.15);
        ;[x, y, z] = rotX(x, y, z, -rot * 0.4);
        const [px, py, p] = project(x, y, z, cx, cy, radius);
        if (j === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
        ctx.strokeStyle = `rgba(255, 170, 70, ${alpha * 0.22 * p})`;
      }
      ctx.stroke();
    }
  }

  function drawCore(cx, cy, radius, energy) {
    const g = ctx.createRadialGradient(cx, cy, radius * 0.05, cx, cy, radius);
    g.addColorStop(0, `rgba(255, 245, 210, ${0.95})`);
    g.addColorStop(0.18, `rgba(255, 200, 100, ${0.85})`);
    g.addColorStop(0.45, `rgba(255, 120, 30, ${0.45 + energy * 0.25})`);
    g.addColorStop(1, "rgba(255, 80, 10, 0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  function frame(ts) {
    state.t = ts * 0.001;
    // yumuşak enerji
    state.level += (state.target - state.level) * 0.12;
    if (state.mode === "speaking") {
      // konuşma simülasyonu — akıcı dalga
      state.target = 0.35 + 0.55 * Math.abs(Math.sin(state.t * 10.5)) * (0.5 + 0.5 * Math.sin(state.t * 3.2));
    } else if (state.mode === "listening") {
      state.target = 0.25 + 0.2 * Math.abs(Math.sin(state.t * 4));
    } else if (state.mode === "thinking") {
      state.target = 0.2 + 0.15 * Math.abs(Math.sin(state.t * 2.5));
    } else {
      state.target = 0.08 + 0.04 * Math.sin(state.t * 1.2);
    }

    const w = canvas.clientWidth || 320;
    const h = canvas.clientHeight || 320;
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2;
    const cy = h / 2;
    const energy = state.level;
    const baseR = Math.min(w, h) * (0.28 + energy * 0.06);

    // dış halo
    const halo = ctx.createRadialGradient(cx, cy, baseR * 0.8, cx, cy, baseR * 2.2);
    halo.addColorStop(0, `rgba(255, 140, 40, ${0.12 + energy * 0.18})`);
    halo.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, w, h);

    // dönen halkalar
    for (let i = 0; i < 4; i++) {
      const rr = baseR * (1.15 + i * 0.18 + energy * 0.05);
      ctx.beginPath();
      ctx.ellipse(cx, cy, rr, rr * (0.35 + i * 0.05), state.t * (0.4 + i * 0.15) * (i % 2 ? -1 : 1), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255, ${150 + i * 15}, 50, ${0.18 + energy * 0.2})`;
      ctx.lineWidth = 1 + energy;
      ctx.stroke();
    }

    drawWireSphere(cx, cy, baseR * 1.05, state.t * (0.55 + energy * 0.8), energy, 0.55 + energy * 0.35);
    drawCore(cx, cy, baseR * (0.55 + energy * 0.12), energy);

    // parçacıklar
    for (const p of state.particles) {
      p.theta += 0.004 * p.speed * (1 + energy * 2);
      let x = p.r * Math.sin(p.phi) * Math.cos(p.theta);
      let y = p.r * Math.cos(p.phi);
      let z = p.r * Math.sin(p.phi) * Math.sin(p.theta);
      ;[x, y, z] = rotY(x, y, z, state.t * 0.35);
      const [px, py, persp] = project(x, y, z, cx, cy, baseR * 1.25);
      const a = (0.25 + 0.75 * persp) * (0.4 + energy * 0.6);
      ctx.fillStyle = `rgba(255, ${180 + persp * 50}, 90, ${a})`;
      ctx.beginPath();
      ctx.arc(px, py, p.size * persp * (0.8 + energy), 0, Math.PI * 2);
      ctx.fill();
    }

    // HUD barları güncelle
    const bars = [document.getElementById("barA"), document.getElementById("barB"), document.getElementById("barC")];
    bars.forEach((el, i) => {
      if (!el) return;
      const hgt = 20 + energy * 75 * Math.abs(Math.sin(state.t * (6 + i * 2) + i));
      el.style.height = `${hgt}%`;
    });

    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
