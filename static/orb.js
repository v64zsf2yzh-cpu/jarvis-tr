/**
 * Cyan/blue Jarvis AI Core hologram (Command Center)
 */
(function () {
  const canvas = document.getElementById("orb");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const state = { mode: "idle", level: 0, target: 0.08, t: 0, particles: [] };

  window.JarvisOrb = {
    setMode(mode) {
      state.mode = mode || "idle";
    },
    setLevel(v) {
      state.target = Math.max(0, Math.min(1, v));
    },
    pulse(a = 0.6) {
      state.target = Math.max(state.target, a);
    },
  };

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const css = canvas.clientWidth || 260;
    canvas.width = Math.floor(css * dpr);
    canvas.height = Math.floor(css * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  for (let i = 0; i < 180; i++) {
    const u = Math.random();
    const v = Math.random();
    state.particles.push({
      theta: 2 * Math.PI * u,
      phi: Math.acos(2 * v - 1),
      r: 0.7 + Math.random() * 0.28,
      speed: 0.25 + Math.random() * 0.7,
      size: 0.7 + Math.random() * 1.6,
    });
  }

  function project(x, y, z, cx, cy, scale) {
    const persp = 1.4 / (1.4 + z);
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

  function drawSphere(cx, cy, radius, rot, energy) {
    const rings = 11, segs = 42;
    for (let i = 1; i < rings; i++) {
      const lat = (i / rings) * Math.PI;
      ctx.beginPath();
      for (let j = 0; j <= segs; j++) {
        const lon = (j / segs) * Math.PI * 2;
        let x = Math.sin(lat) * Math.cos(lon);
        let y = Math.cos(lat);
        let z = Math.sin(lat) * Math.sin(lon);
        x *= 1 + energy * 0.05 * Math.sin(lon * 4 + state.t * 2);
        ;[x, y, z] = rotY(x, y, z, rot);
        ;[x, y, z] = rotX(x, y, z, rot * 0.55);
        const [px, py, p] = project(x, y, z, cx, cy, radius);
        if (j === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
        ctx.strokeStyle = `rgba(125, 211, 252, ${0.15 + 0.45 * p * (0.4 + energy)})`;
      }
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  function frame(ts) {
    state.t = ts * 0.001;
    if (state.mode === "speaking") {
      state.target = 0.4 + 0.55 * Math.abs(Math.sin(state.t * 11)) * (0.5 + 0.5 * Math.sin(state.t * 3));
    } else if (state.mode === "listening") {
      state.target = Math.max(state.target * 0.92, 0.22 + 0.15 * Math.abs(Math.sin(state.t * 3.5)));
    } else if (state.mode === "thinking") {
      state.target = 0.22 + 0.12 * Math.abs(Math.sin(state.t * 2.2));
    } else {
      state.target = 0.08 + 0.04 * Math.sin(state.t);
    }
    state.level += (state.target - state.level) * 0.14;

    const w = canvas.clientWidth || 260;
    const h = canvas.clientHeight || 260;
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2;
    const e = state.level;
    const R = Math.min(w, h) * (0.28 + e * 0.07);

    const glow = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, R * 2.1);
    glow.addColorStop(0, `rgba(56, 189, 248, ${0.2 + e * 0.25})`);
    glow.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, w, h);

    for (let i = 0; i < 3; i++) {
      ctx.beginPath();
      ctx.ellipse(cx, cy, R * (1.2 + i * 0.2), R * (0.32 + i * 0.06), state.t * (0.5 + i * 0.2) * (i % 2 ? -1 : 1), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(56, 189, 248, ${0.2 + e * 0.25})`;
      ctx.lineWidth = 1 + e;
      ctx.stroke();
    }

    drawSphere(cx, cy, R * 1.05, state.t * (0.6 + e), e);

    const core = ctx.createRadialGradient(cx, cy, R * 0.05, cx, cy, R * 0.7);
    core.addColorStop(0, "#f0f9ff");
    core.addColorStop(0.25, `rgba(125, 211, 252, ${0.9})`);
    core.addColorStop(0.6, `rgba(14, 165, 233, ${0.4 + e * 0.3})`);
    core.addColorStop(1, "rgba(2, 6, 23, 0)");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx, cy, R * (0.62 + e * 0.1), 0, Math.PI * 2);
    ctx.fill();

    for (const p of state.particles) {
      p.theta += 0.004 * p.speed * (1 + e * 2);
      let x = p.r * Math.sin(p.phi) * Math.cos(p.theta);
      let y = p.r * Math.cos(p.phi);
      let z = p.r * Math.sin(p.phi) * Math.sin(p.theta);
      ;[x, y, z] = rotY(x, y, z, state.t * 0.4);
      const [px, py, persp] = project(x, y, z, cx, cy, R * 1.25);
      ctx.fillStyle = `rgba(186, 230, 253, ${(0.2 + 0.7 * persp) * (0.35 + e)})`;
      ctx.beginPath();
      ctx.arc(px, py, p.size * persp * (0.8 + e), 0, Math.PI * 2);
      ctx.fill();
    }

    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
