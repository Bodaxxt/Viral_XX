/**
 * galaxy.js -- Viral-X Hero Galaxy Background Animation
 */
(function () {
  "use strict";
  const canvas = document.getElementById("galaxyCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const CONFIG = {
    starCount: 260,
    shootingStarInterval: 2400,
    maxShootingStars: 3,
    nebulaOrbs: 5,
  };

  let W, H, dpr;
  let stars = [], shootingStars = [], nebulaOrbs = [];
  let animId, lastShoot = 0;

  function resize() {
    dpr = window.devicePixelRatio || 1;
    const section = canvas.parentElement;
    W = section.offsetWidth;
    H = section.offsetHeight;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width  = W + "px";
    canvas.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    init();
  }

  function rand(a, b) { return a + Math.random() * (b - a); }

  function createStar() {
    return {
      x: rand(0, W), y: rand(0, H),
      r: rand(0.3, 2.2),
      baseAlpha: rand(0.25, 0.9),
      alpha: rand(0.25, 0.9),
      twinklePhase: rand(0, Math.PI * 2),
      twinkleSpeed: rand(0.005, 0.025),
      vx: rand(-0.03, 0.03), vy: rand(-0.015, 0.015),
      hue: Math.random() < 0.15 ? rand(230, 280) : null,
    };
  }

  function createShootingStar() {
    const angle = rand(-0.3, 0.5);
    const speed = rand(8, 18);
    return {
      x: rand(W * 0.1, W * 0.9), y: rand(0, H * 0.5),
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      length: rand(80, 200),
      alpha: 1, life: 1,
      decay: rand(0.012, 0.025),
      width: rand(0.8, 2),
    };
  }

  const palettes = [
    [108,53,217],[139,92,246],[59,130,246],[192,80,220],[30,100,200]
  ];
  function createNebulaOrb(i) {
    const [r,g,b] = palettes[i % palettes.length];
    return {
      x: rand(W*0.05, W*0.95), y: rand(H*0.05, H*0.95),
      radius: rand(120, 280), r, g, b,
      alpha: rand(0.04, 0.12),
      phase: rand(0, Math.PI * 2),
      speed: rand(0.003, 0.008),
      driftX: rand(-0.15, 0.15), driftY: rand(-0.08, 0.08),
    };
  }

  function init() {
    stars = Array.from({length: CONFIG.starCount}, createStar);
    shootingStars = [];
    nebulaOrbs = Array.from({length: CONFIG.nebulaOrbs}, (_, i) => createNebulaOrb(i));
  }

  function drawNebulae() {
    nebulaOrbs.forEach(orb => {
      orb.phase += orb.speed;
      const pulse = 0.85 + 0.15 * Math.sin(orb.phase);
      orb.x += orb.driftX; orb.y += orb.driftY;
      if (orb.x < -orb.radius) orb.x = W + orb.radius;
      if (orb.x > W + orb.radius) orb.x = -orb.radius;
      if (orb.y < -orb.radius) orb.y = H + orb.radius;
      if (orb.y > H + orb.radius) orb.y = -orb.radius;
      const g = ctx.createRadialGradient(orb.x, orb.y, 0, orb.x, orb.y, orb.radius * pulse);
      g.addColorStop(0,   "rgba("+orb.r+","+orb.g+","+orb.b+","+(orb.alpha*pulse)+")");
      g.addColorStop(0.5, "rgba("+orb.r+","+orb.g+","+orb.b+","+(orb.alpha*0.3*pulse)+")");
      g.addColorStop(1,   "rgba("+orb.r+","+orb.g+","+orb.b+",0)");
      ctx.beginPath();
      ctx.arc(orb.x, orb.y, orb.radius * pulse, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
    });
  }

  function drawStars() {
    stars.forEach(s => {
      s.twinklePhase += s.twinkleSpeed;
      s.alpha = s.baseAlpha * (0.6 + 0.4 * Math.sin(s.twinklePhase));
      s.x += s.vx; s.y += s.vy;
      if (s.x < 0) s.x = W; if (s.x > W) s.x = 0;
      if (s.y < 0) s.y = H; if (s.y > H) s.y = 0;
      ctx.save();
      ctx.fillStyle = s.hue
        ? "hsla("+s.hue+",80%,90%,"+s.alpha+")"
        : "rgba(255,255,255,"+s.alpha+")";
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
      if (s.r > 1.5) {
        const glow = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, s.r * 4);
        glow.addColorStop(0, "rgba(200,184,240,"+(s.alpha*0.35)+")");
        glow.addColorStop(1, "rgba(200,184,240,0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r * 4, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    });
  }

  function drawShootingStars() {
    shootingStars = shootingStars.filter(ss => ss.life > 0);
    shootingStars.forEach(ss => {
      ss.life -= ss.decay; ss.alpha = ss.life;
      ss.x += ss.vx; ss.y += ss.vy;
      const spd = Math.hypot(ss.vx, ss.vy);
      const tailX = ss.x - ss.vx * (ss.length / spd);
      const tailY = ss.y - ss.vy * (ss.length / spd);
      const g = ctx.createLinearGradient(tailX, tailY, ss.x, ss.y);
      g.addColorStop(0,   "rgba(255,255,255,0)");
      g.addColorStop(0.7, "rgba(200,184,240,"+(ss.alpha*0.6)+")");
      g.addColorStop(1,   "rgba(255,255,255,"+ss.alpha+")");
      ctx.save();
      ctx.strokeStyle = g;
      ctx.lineWidth = ss.width;
      ctx.lineCap = "round";
      ctx.shadowBlur = 8;
      ctx.shadowColor = "rgba(200,184,240,"+(ss.alpha*0.8)+")";
      ctx.beginPath();
      ctx.moveTo(tailX, tailY);
      ctx.lineTo(ss.x, ss.y);
      ctx.stroke();
      ctx.restore();
    });
  }

  function loop(t) {
    ctx.clearRect(0, 0, W, H);
    drawNebulae();
    drawStars();
    if (t - lastShoot > CONFIG.shootingStarInterval && shootingStars.length < CONFIG.maxShootingStars) {
      shootingStars.push(createShootingStar());
      lastShoot = t;
    }
    drawShootingStars();
    animId = requestAnimationFrame(loop);
  }

  resize();
  animId = requestAnimationFrame(loop);
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 150);
  });
})();
