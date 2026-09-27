/** Ses dalgası canvas animasyonları */
(function () {
  const waves = {};
  let energy = 0.15;
  let mode = "idle";

  window.JarvisWaves = {
    setEnergy(v) { energy = Math.max(0, Math.min(1, v)); },
    setMode(m) { mode = m || "idle"; },
  };

  function boot(id) {
    const c = document.getElementById(id);
    if (!c) return null;
    const ctx = c.getContext("2d");
    return { c, ctx };
  }

  ["waveL", "waveR", "voiceWave", "waveBarL", "waveBarR"].forEach((id) => {
    waves[id] = boot(id);
  });

  function draw(w, mirrored) {
    if (!w) return;
    const { c, ctx } = w;
    const W = c.width, H = c.height;
    ctx.clearRect(0, 0, W, H);
    const mid = H / 2;
    const t = performance.now() * 0.005;
    const amp = (mode === "idle" ? 0.15 : 0.35) + energy * 0.65;
    ctx.beginPath();
    for (let x = 0; x < W; x++) {
      const n = x / W;
      const y =
        mid +
        Math.sin(n * 10 + t * (mirrored ? -1 : 1)) * H * 0.18 * amp +
        Math.sin(n * 22 + t * 1.7) * H * 0.1 * amp;
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = `rgba(56, 189, 248, ${0.45 + energy * 0.4})`;
    ctx.lineWidth = 2;
    ctx.shadowColor = "rgba(56, 189, 248, 0.6)";
    ctx.shadowBlur = 8;
    ctx.stroke();
  }

  function loop() {
    if (mode === "speaking") energy = 0.4 + 0.5 * Math.abs(Math.sin(performance.now() * 0.012));
    else if (mode === "listening") energy = Math.max(energy * 0.9, 0.25);
    else energy += (0.12 - energy) * 0.05;
    draw(waves.waveL, false);
    draw(waves.waveR, true);
    draw(waves.voiceWave, false);
    draw(waves.waveBarL, false);
    draw(waves.waveBarR, true);
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
})();
