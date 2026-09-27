/**
 * MCU turuncu holografik Jarvis küresi
 */
(function () {
  function createOrb(canvas) {
    if (!canvas) return null;
    const ctx = canvas.getContext("2d");
    const state = { mode: "idle", level: 0, target: 0.1, t: 0, particles: [] };

    const api = {
      setMode(mode) { state.mode = mode || "idle"; },
      setLevel(v) { state.target = Math.max(0, Math.min(1, v)); },
      pulse(a = 0.65) { state.target = Math.max(state.target, a); },
    };

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const css = canvas.clientWidth || 320;
      canvas.width = Math.floor(css * dpr);
      canvas.height = Math.floor(css * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < 220; i++) {
      const u = Math.random();
      const v = Math.random();
      state.particles.push({
        theta: 2 * Math.PI * u,
        phi: Math.acos(2 * v - 1),
        r: 0.68 + Math.random() * 0.3,
        speed: 0.2 + Math.random() * 0.75,
        size: 0.6 + Math.random() * 1.7,
      });
    }

    function project(x, y, z, cx, cy, scale) {
      const persp = 1.45 / (1.45 + z);
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
      const rings = 12, segs = 46;
      for (let i = 1; i < rings; i++) {
        const lat = (i / rings) * Math.PI;
        ctx.beginPath();
        for (let j = 0; j <= segs; j++) {
          const lon = (j / segs) * Math.PI * 2;
          let x = Math.sin(lat) * Math.cos(lon);
          let y = Math.cos(lat);
          let z = Math.sin(lat) * Math.sin(lon);
          x *= 1 + energy * 0.05 * Math.sin(lon * 4 + state.t * 2.2);
          ;[x, y, z] = rotY(x, y, z, rot);
          ;[x, y, z] = rotX(x, y, z, rot * 0.55);
          const [px, py, p] = project(x, y, z, cx, cy, radius);
          if (j === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
          ctx.strokeStyle = `rgba(255, ${150 + p * 40}, 40, ${0.12 + 0.5 * p * (0.35 + energy)})`;
        }
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      for (let i = 0; i < 14; i++) {
        const lon = (i / 14) * Math.PI * 2;
        ctx.beginPath();
        for (let j = 0; j <= segs; j++) {
          const lat = (j / segs) * Math.PI;
          let x = Math.sin(lat) * Math.cos(lon);
          let y = Math.cos(lat);
          let z = Math.sin(lat) * Math.sin(lon);
          ;[x, y, z] = rotY(x, y, z, rot * 1.1);
          ;[x, y, z] = rotX(x, y, z, -rot * 0.35);
          const [px, py, p] = project(x, y, z, cx, cy, radius);
          if (j === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
          ctx.strokeStyle = `rgba(255, 170, 60, ${0.1 + 0.25 * p * energy})`;
        }
        ctx.stroke();
      }
    }

    function frame(ts) {
      state.t = ts * 0.001;
      if (state.mode === "speaking") {
        state.target = 0.4 + 0.55 * Math.abs(Math.sin(state.t * 11)) * (0.5 + 0.5 * Math.sin(state.t * 3));
      } else if (state.mode === "listening") {
        state.target = Math.max(state.target * 0.9, 0.22 + 0.15 * Math.abs(Math.sin(state.t * 3.2)));
      } else if (state.mode === "thinking") {
        state.target = 0.2 + 0.14 * Math.abs(Math.sin(state.t * 2.4));
      } else {
        state.target = 0.1 + 0.05 * Math.sin(state.t);
      }
      state.level += (state.target - state.level) * 0.14;

      const w = canvas.clientWidth || 320;
      const h = canvas.clientHeight || 320;
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2;
      const e = state.level;
      const R = Math.min(w, h) * (0.3 + e * 0.07);

      const glow = ctx.createRadialGradient(cx, cy, R * 0.15, cx, cy, R * 2.2);
      glow.addColorStop(0, `rgba(255, 160, 50, ${0.22 + e * 0.28})`);
      glow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, w, h);

      for (let i = 0; i < 4; i++) {
        ctx.beginPath();
        ctx.ellipse(
          cx, cy,
          R * (1.15 + i * 0.18),
          R * (0.32 + i * 0.05),
          state.t * (0.45 + i * 0.18) * (i % 2 ? -1 : 1),
          0, Math.PI * 2
        );
        ctx.strokeStyle = `rgba(255, 150, 40, ${0.16 + e * 0.22})`;
        ctx.lineWidth = 1 + e;
        ctx.stroke();
      }

      drawSphere(cx, cy, R * 1.05, state.t * (0.55 + e * 0.7), e);

      const core = ctx.createRadialGradient(cx, cy, R * 0.04, cx, cy, R * 0.72);
      core.addColorStop(0, "#fff7e8");
      core.addColorStop(0.2, `rgba(255, 210, 120, 0.95)`);
      core.addColorStop(0.55, `rgba(255, 130, 30, ${0.5 + e * 0.3})`);
      core.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(cx, cy, R * (0.62 + e * 0.1), 0, Math.PI * 2);
      ctx.fill();

      for (const p of state.particles) {
        p.theta += 0.004 * p.speed * (1 + e * 2.2);
        let x = p.r * Math.sin(p.phi) * Math.cos(p.theta);
        let y = p.r * Math.cos(p.phi);
        let z = p.r * Math.sin(p.phi) * Math.sin(p.theta);
        ;[x, y, z] = rotY(x, y, z, state.t * 0.38);
        const [px, py, persp] = project(x, y, z, cx, cy, R * 1.28);
        ctx.fillStyle = `rgba(255, ${180 + persp * 50}, 90, ${(0.2 + 0.75 * persp) * (0.35 + e)})`;
        ctx.beginPath();
        ctx.arc(px, py, p.size * persp * (0.85 + e), 0, Math.PI * 2);
        ctx.fill();
      }

      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    return api;
  }

  const main = createOrb(document.getElementById("orb"));
  const preview = createOrb(document.getElementById("orbPreview"));
  window.JarvisOrb = main || preview || {
    setMode() {},
    setLevel() {},
    pulse() {},
  };
  // preview idle pulse
  if (preview && !main) preview.setMode("idle");
  if (preview) preview.setMode("idle");
})();
