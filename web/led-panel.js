// 96x96 LED Panel — canvas tabanlı, glow/bloom efektli
// Her desen: (x, y, t, primary, secondary, speed, intensity) -> [r, g, b, a]

(function () {
  const GRID = 96;

  // ——— Utility ————————————————————————————————————————————————
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const mixRgb = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
  const dist = (x, y, cx, cy) => Math.hypot(x - cx, y - cy);
  const CENTER = (GRID - 1) / 2;

  // hash for stable random
  function hash(x, y, seed) {
    let h = Math.sin(x * 374.123 + y * 91.7 + seed * 13.7) * 43758.5453;
    return h - Math.floor(h);
  }

  // ——— Desenler ——————————————————————————————————————————————
  const patterns = {
    // 01 — Merkez parlama / nefes
    pulse(x, y, t, p, s, spd, intensity) {
      const d = dist(x, y, CENTER, CENTER);
      const wave = 0.5 + 0.5 * Math.sin(t * spd * 2.0 - d * 0.18);
      const falloff = clamp(1 - d / 55, 0, 1);
      const v = wave * falloff * intensity;
      const c = mixRgb(s, p, wave);
      return [c[0], c[1], c[2], v];
    },

    // 02 — Yukarı dalga
    wave_up(x, y, t, p, s, spd, intensity) {
      const phase = (GRID - y) * 0.22 - t * spd * 3;
      const v = (0.5 + 0.5 * Math.sin(phase)) * intensity;
      const c = mixRgb(s, p, v);
      return [c[0], c[1], c[2], v * 0.95];
    },
    wave_down(x, y, t, p, s, spd, intensity) {
      const phase = y * 0.22 - t * spd * 3;
      const v = (0.5 + 0.5 * Math.sin(phase)) * intensity;
      const c = mixRgb(s, p, v);
      return [c[0], c[1], c[2], v * 0.95];
    },
    wave_left(x, y, t, p, s, spd, intensity) {
      const phase = (GRID - x) * 0.22 - t * spd * 3;
      const v = (0.5 + 0.5 * Math.sin(phase)) * intensity;
      const c = mixRgb(s, p, v);
      return [c[0], c[1], c[2], v * 0.95];
    },
    wave_right(x, y, t, p, s, spd, intensity) {
      const phase = x * 0.22 - t * spd * 3;
      const v = (0.5 + 0.5 * Math.sin(phase)) * intensity;
      const c = mixRgb(s, p, v);
      return [c[0], c[1], c[2], v * 0.95];
    },

    // 06 — Merkezden halka
    ripple_out(x, y, t, p, s, spd, intensity) {
      const d = dist(x, y, CENTER, CENTER);
      const phase = d - t * spd * 22;
      const ring = Math.exp(-Math.pow(((phase % 18) + 18) % 18 - 9, 2) / 6);
      const v = ring * intensity;
      const c = mixRgb(s, p, ring);
      return [c[0], c[1], c[2], v];
    },
    ripple_in(x, y, t, p, s, spd, intensity) {
      const d = dist(x, y, CENTER, CENTER);
      const phase = d + t * spd * 22;
      const ring = Math.exp(-Math.pow(((phase % 18) + 18) % 18 - 9, 2) / 6);
      const v = ring * intensity;
      const c = mixRgb(s, p, ring);
      return [c[0], c[1], c[2], v];
    },

    // 08 — Parıltı
    sparkle(x, y, t, p, s, spd, intensity) {
      const seed = Math.floor(t * spd * 6);
      const r1 = hash(x, y, seed);
      const r2 = hash(x, y, seed + 1);
      const sub = (t * spd * 6) % 1;
      const v = (r1 > 0.985 ? (1 - sub) : 0) + (r2 > 0.985 ? sub : 0);
      const c = mixRgb(s, p, Math.min(1, v));
      return [c[0], c[1], c[2], clamp(v, 0, 1) * intensity];
    },

    // 09 — Akma / damla
    drop(x, y, t, p, s, spd, intensity) {
      const seed = Math.floor(x / 4);
      const offset = hash(seed, 0, 1) * 96;
      const head = ((t * spd * 28 + offset) % 130) - 17;
      const d = y - head;
      let v = 0;
      if (d > -2 && d < 22) {
        v = Math.exp(-d * d / 14) + (d > 0 ? Math.exp(-d / 8) * 0.6 : 0);
      }
      v *= intensity;
      const c = mixRgb(s, p, clamp(v, 0, 1));
      return [c[0], c[1], c[2], clamp(v, 0, 1)];
    },

    // 10 — Yavaş sönme
    fade(x, y, t, p, s, spd, intensity) {
      const v = (0.4 + 0.6 * Math.sin(t * spd * 0.7)) * intensity;
      const d = dist(x, y, CENTER, CENTER);
      const falloff = clamp(1 - d / 60, 0, 1);
      return [p[0], p[1], p[2], v * falloff];
    },

    // 11 — Tarayıcı çizgi
    scan(x, y, t, p, s, spd, intensity) {
      const headY = ((t * spd * 28) % (GRID + 30)) - 15;
      const d = Math.abs(y - headY);
      const v = Math.exp(-d * d / 5) * intensity;
      const trail = y < headY ? Math.exp(-(headY - y) / 12) * 0.4 : 0;
      const total = clamp(v + trail, 0, 1);
      const c = mixRgb(s, p, total);
      return [c[0], c[1], c[2], total];
    },

    // 12 — Sabit titreşen parlama
    static_glow(x, y, t, p, s, spd, intensity) {
      const d = dist(x, y, CENTER, CENTER);
      const falloff = clamp(1 - d / 55, 0, 1);
      const flicker = 0.85 + 0.15 * Math.sin(t * spd * 9 + d * 0.5);
      const v = falloff * flicker * intensity;
      return [p[0], p[1], p[2], v];
    },

    // 13 — Üç nokta (düşünme)
    three_dots(x, y, t, p, s, spd, intensity) {
      const dots = [
        [CENTER - 22, CENTER],
        [CENTER, CENTER],
        [CENTER + 22, CENTER],
      ];
      let v = 0;
      const phase = (t * spd * 2) % 3;
      for (let i = 0; i < 3; i++) {
        const active = phase > i && phase < i + 1.4;
        const intensity2 = active ? Math.sin((phase - i) * Math.PI / 1.4) : 0;
        const d = dist(x, y, dots[i][0], dots[i][1]);
        v += Math.exp(-d * d / 22) * intensity2;
      }
      v *= intensity;
      const c = mixRgb(s, p, clamp(v, 0, 1));
      return [c[0], c[1], c[2], clamp(v, 0, 1)];
    },

    // 14 — Spiral
    spiral_out(x, y, t, p, s, spd, intensity) {
      const dx = x - CENTER, dy = y - CENTER;
      const r = Math.hypot(dx, dy);
      const ang = Math.atan2(dy, dx);
      const phase = ang * 2 - r * 0.35 + t * spd * 4;
      const v = Math.pow(0.5 + 0.5 * Math.sin(phase), 2);
      const falloff = clamp(1 - r / 60, 0, 1);
      const total = v * falloff * intensity;
      const c = mixRgb(s, p, v);
      return [c[0], c[1], c[2], total];
    },

    // 15 — Titreşim
    shake(x, y, t, p, s, spd, intensity) {
      const ox = Math.sin(t * spd * 30) * 3;
      const oy = Math.cos(t * spd * 27) * 3;
      const d = dist(x + ox, y + oy, CENTER, CENTER);
      const falloff = clamp(1 - d / 40, 0, 1);
      const v = falloff * intensity;
      const c = mixRgb(s, p, falloff);
      return [c[0], c[1], c[2], v];
    },

    // 16 — Çapraz tarama
    diagonal_sweep(x, y, t, p, s, spd, intensity) {
      const phase = ((x + y) - t * spd * 40) % 50;
      const v = Math.exp(-Math.pow(phase - 25, 2) / 80) * intensity;
      const c = mixRgb(s, p, clamp(v, 0, 1));
      return [c[0], c[1], c[2], v];
    },

    // 17 — İki renk salınımı
    two_color_swing(x, y, t, p, s, spd, intensity) {
      const w = 0.5 + 0.5 * Math.sin(t * spd * 2 + x * 0.08);
      const c = mixRgb(s, p, w);
      const d = dist(x, y, CENTER, CENTER);
      const falloff = clamp(1 - d / 58, 0, 1);
      return [c[0], c[1], c[2], falloff * intensity];
    },

    // 18 — X deseni
    cross_pattern(x, y, t, p, s, spd, intensity) {
      const d1 = Math.abs((x - CENTER) - (y - CENTER));
      const d2 = Math.abs((x - CENTER) + (y - CENTER));
      const arm = Math.min(d1, d2);
      const pulse = 0.6 + 0.4 * Math.sin(t * spd * 3);
      const v = Math.exp(-arm * arm / 10) * pulse * intensity;
      const c = mixRgb(s, p, pulse);
      return [c[0], c[1], c[2], v];
    },

    // 19 — Sadece kenar
    border_only(x, y, t, p, s, spd, intensity) {
      const edge = Math.min(x, y, GRID - 1 - x, GRID - 1 - y);
      if (edge > 4) return [0, 0, 0, 0];
      const pulse = 0.6 + 0.4 * Math.sin(t * spd * 3 + (x + y) * 0.08);
      const v = (1 - edge / 5) * pulse * intensity;
      const c = mixRgb(s, p, pulse);
      return [c[0], c[1], c[2], v];
    },

    // 20 — Ortadan ayrılma
    split(x, y, t, p, s, spd, intensity) {
      const phase = (t * spd) % 2;
      const opening = Math.min(phase, 2 - phase) * 40;
      const d = Math.abs(x - CENTER);
      let v;
      if (d < opening) {
        v = 0.9 * Math.exp(-(opening - d) / 10);
      } else {
        v = Math.exp(-Math.pow(d - opening, 2) / 30);
      }
      const dy = Math.abs(y - CENTER);
      const falloff = clamp(1 - dy / 50, 0, 1);
      const total = v * falloff * intensity;
      const c = mixRgb(s, p, v);
      return [c[0], c[1], c[2], total];
    },

    // 21 — Onay (V)
    checkmark(x, y, t, p, s, spd, intensity) {
      // V şekli: (20,52)->(42,72)->(76,28)
      const progress = clamp(t * spd * 0.8, 0, 1.2);
      const segs = [
        [[20, 52], [42, 72]],
        [[42, 72], [76, 28]],
      ];
      const lens = segs.map(([a, b]) => Math.hypot(b[0] - a[0], b[1] - a[1]));
      const total = lens[0] + lens[1];
      const drawn = progress * total;
      let v = 0;
      let acc = 0;
      for (let i = 0; i < segs.length; i++) {
        const [a, b] = segs[i];
        const segLen = lens[i];
        const segStart = acc;
        const segEnd = acc + segLen;
        const segDrawn = clamp(drawn - segStart, 0, segLen);
        if (segDrawn > 0) {
          const t1 = segDrawn / segLen;
          // distance from (x,y) to segment a->[a + (b-a)*t1]
          const ex = a[0] + (b[0] - a[0]) * t1;
          const ey = a[1] + (b[1] - a[1]) * t1;
          const d = pointSegDist(x, y, a[0], a[1], ex, ey);
          v = Math.max(v, Math.exp(-d * d / 4));
        }
        acc = segEnd;
      }
      const green = [60, 240, 140];
      return [green[0], green[1], green[2], v * intensity];
    },

    // 22 — Ret (X)
    x_mark(x, y, t, p, s, spd, intensity) {
      const progress = clamp(t * spd * 0.8, 0, 1.2);
      const segs = [
        [[24, 24], [72, 72]],
        [[72, 24], [24, 72]],
      ];
      const lens = segs.map(([a, b]) => Math.hypot(b[0] - a[0], b[1] - a[1]));
      const total = lens[0] + lens[1];
      const drawn = progress * total;
      let v = 0;
      let acc = 0;
      for (let i = 0; i < segs.length; i++) {
        const [a, b] = segs[i];
        const segLen = lens[i];
        const segDrawn = clamp(drawn - acc, 0, segLen);
        if (segDrawn > 0) {
          const t1 = segDrawn / segLen;
          const ex = a[0] + (b[0] - a[0]) * t1;
          const ey = a[1] + (b[1] - a[1]) * t1;
          const d = pointSegDist(x, y, a[0], a[1], ex, ey);
          v = Math.max(v, Math.exp(-d * d / 4));
        }
        acc += segLen;
      }
      const red = [255, 80, 90];
      return [red[0], red[1], red[2], v * intensity];
    },

    // 23 — Kalp atışı
    heartbeat(x, y, t, p, s, spd, intensity) {
      const beat = (t * spd) % 1.2;
      let pulse = 0;
      if (beat < 0.12) pulse = Math.sin(beat / 0.12 * Math.PI);
      else if (beat < 0.32) pulse = Math.sin((beat - 0.20) / 0.12 * Math.PI) * 0.7;
      const d = dist(x, y, CENTER, CENTER);
      const falloff = clamp(1 - d / 36, 0, 1);
      const v = pulse * falloff * intensity;
      return [p[0], p[1], p[2], v];
    },

    // 24 — Halo / yörünge
    orbit(x, y, t, p, s, spd, intensity) {
      const dx = x - CENTER, dy = y - CENTER;
      const r = Math.hypot(dx, dy);
      const ang = Math.atan2(dy, dx);
      const ringWidth = Math.exp(-Math.pow(r - 30, 2) / 24);
      const arc = 0.5 + 0.5 * Math.cos(ang - t * spd * 3);
      const v = ringWidth * Math.pow(arc, 3) * intensity;
      const c = mixRgb(s, p, arc);
      return [c[0], c[1], c[2], v];
    },

    // 25 — Flaş
    flash(x, y, t, p, s, spd, intensity) {
      const phase = (t * spd * 1.4) % 1;
      const v = phase < 0.18 ? (1 - phase / 0.18) : 0;
      const d = dist(x, y, CENTER, CENTER);
      const falloff = clamp(1 - d / 60, 0, 1);
      return [p[0], p[1], p[2], v * falloff * intensity];
    },

    // 26 — Kuyruklu yıldız
    comet(x, y, t, p, s, spd, intensity) {
      const phase = (t * spd * 0.7) % 1;
      const headX = phase * (GRID + 30) - 15;
      const headY = CENTER + Math.sin(phase * Math.PI * 2) * 18;
      const dx = x - headX, dy = y - headY;
      const along = -dx; // tail trails left
      const perp = Math.abs(dy + dx * 0.3);
      let v = 0;
      if (along > -2) v = Math.exp(-along * along / 12 - perp * perp / 5);
      if (along > 0) v += Math.exp(-along / 9) * Math.exp(-perp * perp / 8) * 0.5;
      const c = mixRgb(s, p, clamp(v, 0, 1));
      return [c[0], c[1], c[2], clamp(v, 0, 1) * intensity];
    },

    // 27 — Yağmur
    rain(x, y, t, p, s, spd, intensity) {
      const col = x;
      const offset = hash(col, 0, 7) * 96;
      const speedMul = 0.7 + hash(col, 0, 11) * 0.6;
      const head = ((t * spd * 30 * speedMul + offset) % 110) - 7;
      const d = y - head;
      let v = 0;
      if (d > -1 && d < 14) v = Math.exp(-d * d / 6) + (d > 0 ? Math.exp(-d / 5) * 0.5 : 0);
      v *= intensity * (0.4 + hash(col, 0, 17) * 0.6);
      const c = mixRgb(s, p, clamp(v, 0, 1));
      return [c[0], c[1], c[2], clamp(v, 0, 1)];
    },

    // 28 — Girdap
    vortex(x, y, t, p, s, spd, intensity) {
      const dx = x - CENTER, dy = y - CENTER;
      const r = Math.hypot(dx, dy);
      const ang = Math.atan2(dy, dx);
      const phase = ang * 3 + r * 0.4 - t * spd * 5;
      const v = Math.pow(0.5 + 0.5 * Math.sin(phase), 3);
      const falloff = clamp(1 - r / 60, 0, 1);
      const c = mixRgb(s, p, v);
      return [c[0], c[1], c[2], v * falloff * intensity];
    },

    // 29 — Konfeti
    confetti(x, y, t, p, s, spd, intensity) {
      const cell = 4;
      const cx = Math.floor(x / cell);
      const cy = Math.floor(y / cell);
      const seed = Math.floor(t * spd * 4) + cx * 13 + cy * 7;
      const r = hash(cx, cy, seed);
      let v = 0;
      let c = p;
      if (r > 0.85) {
        v = (r - 0.85) / 0.15;
        c = hash(cx, cy, seed + 99) > 0.5 ? p : s;
      }
      return [c[0], c[1], c[2], v * intensity];
    },

    // 30 — Idle / nefes (default)
    breathe(x, y, t, p, s, spd, intensity) {
      const d = dist(x, y, CENTER, CENTER);
      const breath = 0.35 + 0.35 * Math.sin(t * 1.1);
      const falloff = clamp(1 - d / 48, 0, 1);
      const v = Math.pow(falloff, 1.6) * breath * intensity;
      return [p[0], p[1], p[2], v];
    },
  };

  function pointSegDist(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy;
    if (len2 < 0.0001) return Math.hypot(px - ax, py - ay);
    const t = clamp(((px - ax) * dx + (py - ay) * dy) / len2, 0, 1);
    return Math.hypot(px - (ax + dx * t), py - (ay + dy * t));
  }

  // gestures.json desen adlari -> patterns objesindeki mevcut desenlere alias.
  // Eksik LED matematigi olan desenleri en yakin mevcut desene yonlendirir.
  const patternAlias = {
    smile_face:    'sparkle',
    heart:         'heartbeat',
    star:          'sparkle',
    bouncing:      'confetti',
    arrow_up:      'wave_up',
    arrow_down:    'wave_down',
    tear_drop:     'drop',
    sad_face:      'fade',
    lonely_dot:    'breathe',
    lightning:     'flash',
    chaotic_flash: 'shake',
    fire:          'spiral_out',
    exclamation:   'flash',
    question_mark: 'three_dots',
    clock:         'orbit',
    wave_hand:     'wave_right',
    question_shake:'shake',
  };

  function resolvePattern(name) {
    if (!name) return 'breathe';
    if (patterns[name]) return name;
    if (patternAlias[name] && patterns[patternAlias[name]]) return patternAlias[name];
    return 'breathe';
  }

  // ——— Otonom "canlı göz" idle sistemi —————————————————————
  // Referans: FluxGarage/RoboEyes (parametrik göz + autoblinker + curiosity/tired)
  // ve sidikalamini/eyes-animation (akışkan pupil + state geçişleri).
  // Mantık referans alındı, kod tamamen kendi implementasyon (96x96 Canvas).
  // Sevimli/çizgi film estetiği; LLM/jest sisteminden bağımsız.
  class EyeSystem {
    constructor(bufCtx, grid) {
      this.ctx = bufCtx;
      this.G = grid;
      // göz geometrisi (taban) — sergi temasıyla uyumlu cyan/açık mavi
      this.eyeW = 22;
      this.eyeH = 26;
      this.radius = 8;
      this.spacing = 32;       // iki göz merkezi arası
      // dinamik durum
      this.target = { x: 0, y: 0 };  // pupil hedef offseti
      this.pupil = { x: 0, y: 0 };   // pupil mevcut offseti (lerp'lenir)
      this.topLid = 0;          // 0=acik, 1=tam kapali
      this.bottomLid = 0;
      this.scale = 1.0;         // yawn/stretch icin gov genel olcek
      this.bob = { x: 0, y: 0 };// dance icin offset
      // state machine
      this.state = 'LOOK';
      this.stateEnd = performance.now() + 1800;
      this.subPhase = 0;
      this.lastInteract = performance.now();
      this.sleeping = false;
      this._lastTick = performance.now();
      // renk paleti — aktif jestin renginden türetilir, yumuşak geçer
      this.targetPrimary = [110, 230, 255];   // varsayılan cyan
      this.targetSecondary = [170, 100, 255]; // varsayılan mor
      this.currentPrimary = [110, 230, 255];
      this.currentSecondary = [170, 100, 255];
    }

    /** Aktif jest renklerini al — iris/göz gövdesi/pupil tonu bu paletten türer. */
    setColors(primary, secondary) {
      if (Array.isArray(primary) && primary.length >= 3) {
        this.targetPrimary = [primary[0] | 0, primary[1] | 0, primary[2] | 0];
      }
      if (Array.isArray(secondary) && secondary.length >= 3) {
        this.targetSecondary = [secondary[0] | 0, secondary[1] | 0, secondary[2] | 0];
      }
    }

    _lerpColor(cur, tgt, t) {
      cur[0] += (tgt[0] - cur[0]) * t;
      cur[1] += (tgt[1] - cur[1]) * t;
      cur[2] += (tgt[2] - cur[2]) * t;
    }

    _tone(rgb, target, t) {
      return [
        Math.round(rgb[0] * (1 - t) + target[0] * t),
        Math.round(rgb[1] * (1 - t) + target[1] * t),
        Math.round(rgb[2] * (1 - t) + target[2] * t),
      ];
    }
    _rgbStr(rgb) { return 'rgb(' + (rgb[0]|0) + ',' + (rgb[1]|0) + ',' + (rgb[2]|0) + ')'; }

    /** Etkilesim oldu — uyu durumundaysa uyandir, sleep sayacini sifirla. */
    markInteraction() {
      this.lastInteract = performance.now();
      if (this.sleeping || this.state === 'SLEEP') {
        this.sleeping = false;
        this.state = 'WAKE';
        this.stateEnd = performance.now() + 700;
      }
    }

    _pickNextState() {
      const now = performance.now();
      const sinceInteract = (now - this.lastInteract) / 1000;

      // 120 sn uzerinde hic etkilesim yoksa uyu
      if (sinceInteract > 120 && !this.sleeping) {
        this.sleeping = true;
        this.state = 'SLEEP';
        this.stateEnd = Infinity;
        this.target = { x: 0, y: 2 };
        return;
      }

      const r = Math.random();
      if (r < 0.14) {                       // tek kirpma
        this.state = 'BLINK';
        this.stateEnd = now + 130 + Math.random() * 80;
      } else if (r < 0.18) {                // cift kirpma
        this.state = 'DOUBLE_BLINK';
        this.stateEnd = now + 460;
      } else if (r < 0.22) {                // dans
        this.state = 'DANCE';
        this.stateEnd = now + 2500 + Math.random() * 2000;
      } else if (r < 0.25) {                // esneme
        this.state = 'YAWN';
        this.stateEnd = now + 1100 + Math.random() * 600;
      } else {                              // bakinma (cogu zaman)
        this.state = 'LOOK';
        this.stateEnd = now + 1400 + Math.random() * 2200;
        // yeni rastgele bakis hedefi (organik dagilim)
        const maxX = 5, maxY = 4;
        this.target = {
          x: (Math.random() * 2 - 1) * maxX,
          y: (Math.random() * 2 - 1) * maxY,
        };
      }
    }

    update() {
      const now = performance.now();
      const dt = Math.min(0.05, (now - this._lastTick) / 1000);
      this._lastTick = now;

      if (now > this.stateEnd) this._pickNextState();

      // Pupil yumusak lerp (akiskan goz hareketi)
      const lerp = Math.min(1, dt * 5.5);
      this.pupil.x += (this.target.x - this.pupil.x) * lerp;
      this.pupil.y += (this.target.y - this.pupil.y) * lerp;

      // Renkleri hedefe doğru yumuşak çek (~1.5 sn geçiş)
      const colorLerp = Math.min(1, dt * 2.2);
      this._lerpColor(this.currentPrimary, this.targetPrimary, colorLerp);
      this._lerpColor(this.currentSecondary, this.targetSecondary, colorLerp);

      switch (this.state) {
        case 'BLINK': {
          const total = 200;
          const phase = 1 - Math.max(0, Math.min(1, (this.stateEnd - now) / total));
          const v = Math.sin(phase * Math.PI);
          this.topLid = v;
          this.bottomLid = v * 0.55;
          this.scale += (1 - this.scale) * 0.2;
          break;
        }
        case 'DOUBLE_BLINK': {
          // iki ardi sira kirpma
          const elapsed = 460 - (this.stateEnd - now);
          const cycle = (elapsed % 230) / 230;
          const v = Math.sin(cycle * Math.PI);
          this.topLid = v;
          this.bottomLid = v * 0.55;
          break;
        }
        case 'DANCE': {
          const t = now / 1000;
          this.bob.x = Math.sin(t * 4.5) * 4.5;
          this.bob.y = -Math.abs(Math.sin(t * 9)) * 2.2;
          this.topLid *= 0.7;
          this.bottomLid *= 0.7;
          break;
        }
        case 'YAWN': {
          const total = 1300;
          const phase = 1 - Math.max(0, Math.min(1, (this.stateEnd - now) / total));
          if (phase < 0.45) {
            const k = phase / 0.45;
            this.scale = 1 + 0.28 * k;
            this.topLid = 0;
            this.bottomLid = 0;
          } else {
            const k = (phase - 0.45) / 0.55;
            this.scale = 1.28 - 0.28 * k;
            this.topLid = k * 0.45;
            this.bottomLid = k * 0.25;
          }
          this.bob.x *= 0.85;
          this.bob.y *= 0.85;
          break;
        }
        case 'WAKE': {
          // uyudan uyanma: kapaklar acilir, hafif esneme
          const total = 700;
          const phase = 1 - Math.max(0, Math.min(1, (this.stateEnd - now) / total));
          this.topLid = (1 - phase) * 0.6;
          this.bottomLid = (1 - phase) * 0.15;
          this.scale = 1 + 0.12 * Math.sin(phase * Math.PI);
          this.target = { x: 0, y: 0 };
          this.bob.x *= 0.7;
          this.bob.y *= 0.7;
          break;
        }
        case 'SLEEP': {
          this.topLid = 0.86;
          this.bottomLid = 0.12;
          this.bob.y = Math.sin(now / 1500) * 0.7;
          this.bob.x *= 0.9;
          this.scale += (1 - this.scale) * 0.1;
          break;
        }
        case 'LOOK':
        default: {
          // sakin durumda kapaklar acil, bob soner, scale normallesir
          this.topLid *= 0.82;
          this.bottomLid *= 0.82;
          this.bob.x *= 0.82;
          this.bob.y *= 0.82;
          this.scale += (1 - this.scale) * 0.1;
          break;
        }
      }
    }

    render() {
      const ctx = this.ctx;
      const G = this.G;
      ctx.save();
      // zemin temizle (LED panelin koyu arkasi)
      ctx.fillStyle = '#04060d';
      ctx.fillRect(0, 0, G, G);

      // sevimli/yumusak ton paleti — aktif jest renginden türetilir
      // göz beyazı: primary'nin %62 beyaza karışmış açık tonu (uyumlu ama göze rahat)
      // iris: primary'nin orijinali
      // pupil: primary'nin %85 siyaha karışmış koyu tonu (sergi koyu temasında durur)
      const p = this.currentPrimary;
      const eyeFill = this._rgbStr(this._tone(p, [255, 255, 255], 0.62));
      const irisColor = this._rgbStr(p);
      const pupilColor = this._rgbStr(this._tone(p, [0, 0, 0], 0.85));
      const highlight = '#ffffff';
      const lidColor = '#04060d';

      const eyeW = this.eyeW * this.scale;
      const eyeH = this.eyeH * this.scale;
      const r = Math.max(2, this.radius * this.scale);
      const cy = 48 + this.bob.y;
      const centers = [
        { cx: 48 - this.spacing / 2 + this.bob.x, cy },
        { cx: 48 + this.spacing / 2 + this.bob.x, cy },
      ];

      for (const e of centers) {
        // 1) göz govdesi (rounded rect)
        this._roundRect(ctx, e.cx - eyeW / 2, e.cy - eyeH / 2, eyeW, eyeH, r, eyeFill);

        // 2) iris + pupil
        const px = e.cx + this.pupil.x;
        const py = e.cy + this.pupil.y;
        ctx.fillStyle = irisColor;
        ctx.beginPath(); ctx.arc(px, py, 4.6, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = pupilColor;
        ctx.beginPath(); ctx.arc(px, py, 2.8, 0, Math.PI * 2); ctx.fill();
        // canlilik parlamasi
        ctx.fillStyle = highlight;
        ctx.beginPath(); ctx.arc(px - 1.2, py - 1.4, 1.0, 0, Math.PI * 2); ctx.fill();

        // 3) kapaklar — koyu zemin renkli dikdortgen, göz govdesinin üstüne biner
        const topLidH = this.topLid * eyeH;
        if (topLidH > 0.3) {
          this._roundRect(
            ctx,
            e.cx - eyeW / 2 - 1, e.cy - eyeH / 2 - 1,
            eyeW + 2, topLidH + 1,
            r, lidColor,
          );
        }
        const botLidH = this.bottomLid * eyeH;
        if (botLidH > 0.3) {
          this._roundRect(
            ctx,
            e.cx - eyeW / 2 - 1, e.cy + eyeH / 2 - botLidH,
            eyeW + 2, botLidH + 1,
            r, lidColor,
          );
        }
      }

      // SLEEP'te kucuk "z" hissi: sag uste hafif parlak nokta (iris renginde)
      if (this.state === 'SLEEP') {
        const t = (performance.now() / 1000) % 3;
        const a = Math.max(0, Math.min(1, 1 - t / 3));
        ctx.fillStyle = 'rgba(' + (p[0]|0) + ',' + (p[1]|0) + ',' + (p[2]|0) + ',' + (0.45 * a) + ')';
        ctx.fillRect(80, 18 - t * 4, 2, 2);
      }

      ctx.restore();
    }

    _roundRect(ctx, x, y, w, h, r, fill) {
      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.arcTo(x + w, y, x + w, y + r, r);
      ctx.lineTo(x + w, y + h - r);
      ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
      ctx.lineTo(x + r, y + h);
      ctx.arcTo(x, y + h, x, y + h - r, r);
      ctx.lineTo(x, y + r);
      ctx.arcTo(x, y, x + r, y, r);
      ctx.closePath();
      ctx.fill();
    }
  }

  // ——— Renderer ——————————————————————————————————————————————
  class LEDPanel {
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.glowCanvas = document.createElement('canvas');
      this.glowCtx = this.glowCanvas.getContext('2d');
      this.bufCanvas = document.createElement('canvas');
      this.bufCanvas.width = GRID;
      this.bufCanvas.height = GRID;
      this.bufCtx = this.bufCanvas.getContext('2d');
      this.bufImg = this.bufCtx.createImageData(GRID, GRID);

      this.size = opts.size || 560;
      this.resize(this.size);

      this.startT = performance.now();
      this.current = {
        pattern: 'breathe',
        primary: [120, 220, 255],
        secondary: [200, 120, 255],
        speed: 1.0,
        intensity: 0.9,
        endsAt: Infinity,
        gestureId: null,
        isEmoji: false,
      };
      this.idle = {
        pattern: 'breathe',
        primary: [120, 220, 255],
        secondary: [200, 120, 255],
        speed: 1.0,
        intensity: 0.9,
        gestureId: null,
        isEmoji: false,
      };

      // Emoji modu: gestures.json'da gorsel_tipi=emoji olan jestler icin
      // assets/emojis/<id>/frame_*.png kareleri oynatir.
      this.mode = 'desen';            // 'desen' | 'emoji'
      this.emojiFps = 12;
      this.emojiManifest = null;       // { jest_id: frame_count }
      this.emojiCache = new Map();     // jest_id -> Image[]

      // Otonom "canlı göz" idle sistemi (varsayilan kapali; app.js timer ile aktive eder)
      this.eyes = new EyeSystem(this.bufCtx, GRID);
      this.eyeIdleActive = false;

      this.tick = this.tick.bind(this);
      requestAnimationFrame(this.tick);
    }

    setEyeIdle(active) {
      const wasActive = this.eyeIdleActive;
      this.eyeIdleActive = !!active;
      if (this.eyeIdleActive && !wasActive && this.eyes) {
        // taze başla — son etkileşim şimdi sayılır, uyku sayacı sıfırlanır
        this.eyes.lastInteract = performance.now();
        this.eyes._lastTick = performance.now();
      }
      if (!this.eyeIdleActive && this.eyes) {
        // etkileşim geri geldi — sayacı sıfırla, uyuyorsa uyandır
        this.eyes.markInteraction();
      }
    }

    setMode(mode) {
      this.mode = (mode === 'emoji') ? 'emoji' : 'desen';
    }

    setEmojiManifest(manifest, fps) {
      this.emojiManifest = manifest || null;
      if (fps && fps > 0) this.emojiFps = fps;
    }

    hasEmojiFor(gestureId) {
      return !!(this.emojiManifest && this.emojiManifest[gestureId] > 0);
    }

    _loadEmojiFrames(gestureId) {
      if (!gestureId || !this.emojiManifest) return null;
      if (this.emojiCache.has(gestureId)) return this.emojiCache.get(gestureId);
      const count = this.emojiManifest[gestureId];
      if (!count) return null;
      const frames = [];
      for (let i = 0; i < count; i++) {
        const img = new Image();
        img.src = '/assets/emojis/' + gestureId + '/frame_' + String(i).padStart(2, '0') + '.png';
        frames.push(img);
      }
      this.emojiCache.set(gestureId, frames);
      return frames;
    }

    resize(size) {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.canvas.width = size * dpr;
      this.canvas.height = size * dpr;
      this.canvas.style.width = size + 'px';
      this.canvas.style.height = size + 'px';
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.glowCanvas.width = size * dpr;
      this.glowCanvas.height = size * dpr;
      this.glowCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.size = size;
    }

    setGesture(opts) {
      const gestureId = opts.gestureId || null;
      const isEmoji = !!opts.isEmoji;
      this.current = {
        pattern: resolvePattern(opts.pattern),
        primary: opts.primary || [120, 220, 255],
        secondary: opts.secondary || opts.primary || [200, 120, 255],
        speed: opts.speed || 1,
        intensity: opts.intensity != null ? opts.intensity : 0.9,
        startedAt: performance.now(),
        endsAt: performance.now() + (opts.duration || 4500),
        gestureId,
        isEmoji,
      };
      // emoji frame'leri arkaplanda yukle (lazy)
      if (isEmoji && gestureId) this._loadEmojiFrames(gestureId);
    }

    setIdle(opts) {
      const merged = Object.assign({}, this.idle, opts);
      if (opts && opts.pattern) merged.pattern = resolvePattern(opts.pattern);
      if (opts && 'gestureId' in opts) merged.gestureId = opts.gestureId;
      if (opts && 'isEmoji' in opts) merged.isEmoji = !!opts.isEmoji;
      this.idle = merged;
    }

    tick() {
      const now = performance.now();
      // jest süresi bittiyse idle'a dön
      const active = now < this.current.endsAt ? this.current : this.idle;
      const t = (now - (active.startedAt || this.startT)) / 1000;

      // Otonom göz idle modu — etkin ise patterns/emoji tamamen devre dışı.
      let drewEye = false;
      if (this.eyeIdleActive && this.eyes) {
        this.eyes.update();
        this.eyes.render();
        // bufCanvas zaten gözler ile dolu; bufImg'i refresh et (glow + dot katmanı için)
        this.bufImg = this.bufCtx.getImageData(0, 0, GRID, GRID);
        drewEye = true;
      }

      // Emoji modu: gorsel_tipi=emoji ve frame'leri yuklenebilmis ise PNG kareleri oynat.
      // Aksi halde matematik desene dus.
      let drewEmoji = false;
      if (drewEye) { /* gözler çizildi, pattern/emoji atlanır */ } else
      if (this.mode === 'emoji' && active.isEmoji && active.gestureId
          && this.hasEmojiFor(active.gestureId)) {
        const frames = this._loadEmojiFrames(active.gestureId);
        if (frames && frames.length > 0) {
          const idx = Math.floor(t * this.emojiFps) % frames.length;
          const img = frames[idx];
          if (img && img.complete && img.naturalWidth > 0) {
            this.bufCtx.clearRect(0, 0, GRID, GRID);
            this.bufCtx.drawImage(img, 0, 0, GRID, GRID);
            // yogunluk override: intensity < 1 ise karartma uygula
            if (active.intensity != null && active.intensity < 0.99) {
              const k = active.intensity;
              this.bufImg = this.bufCtx.getImageData(0, 0, GRID, GRID);
              const dd = this.bufImg.data;
              for (let i = 0; i < dd.length; i += 4) {
                dd[i]     = dd[i]     * k;
                dd[i + 1] = dd[i + 1] * k;
                dd[i + 2] = dd[i + 2] * k;
              }
              this.bufCtx.putImageData(this.bufImg, 0, 0);
            } else {
              this.bufImg = this.bufCtx.getImageData(0, 0, GRID, GRID);
            }
            drewEmoji = true;
          }
        }
      }

      if (!drewEye && !drewEmoji) {
        const fn = patterns[active.pattern] || patterns.pulse;
        const data = this.bufImg.data;
        const p = active.primary;
        const s = active.secondary;
        const spd = active.speed;
        const intensity = active.intensity;

        for (let y = 0; y < GRID; y++) {
          for (let x = 0; x < GRID; x++) {
            const rgba = fn(x, y, t, p, s, spd, intensity);
            const idx = (y * GRID + x) * 4;
            const a = clamp(rgba[3], 0, 1);
            data[idx]     = clamp(rgba[0] * a, 0, 255);
            data[idx + 1] = clamp(rgba[1] * a, 0, 255);
            data[idx + 2] = clamp(rgba[2] * a, 0, 255);
            data[idx + 3] = 255;
          }
        }
        this.bufCtx.putImageData(this.bufImg, 0, 0);
      }

      const W = this.size;
      const cell = W / GRID;

      // 1) Glow katmanı — büyütülmüş + blur
      this.glowCtx.clearRect(0, 0, W, W);
      this.glowCtx.filter = 'blur(' + (cell * 1.6) + 'px)';
      this.glowCtx.globalCompositeOperation = 'lighter';
      this.glowCtx.imageSmoothingEnabled = true;
      this.glowCtx.drawImage(this.bufCanvas, 0, 0, W, W);
      this.glowCtx.filter = 'none';

      // 2) Ana çizim — koyu zemin + LED dotları
      this.ctx.fillStyle = '#04060d';
      this.ctx.fillRect(0, 0, W, W);

      // hafif iç grid
      this.ctx.strokeStyle = 'rgba(80,120,200,0.04)';
      this.ctx.lineWidth = 1;
      for (let i = 0; i <= 8; i++) {
        const p = i * (W / 8);
        this.ctx.beginPath();
        this.ctx.moveTo(p, 0); this.ctx.lineTo(p, W);
        this.ctx.moveTo(0, p); this.ctx.lineTo(W, p);
        this.ctx.stroke();
      }

      // glow alta
      this.ctx.globalCompositeOperation = 'lighter';
      this.ctx.globalAlpha = 0.85;
      this.ctx.drawImage(this.glowCanvas, 0, 0, W, W);
      this.ctx.globalAlpha = 1;

      // LED noktaları üstte (yuvarlak)
      this.ctx.globalCompositeOperation = 'lighter';
      const data2 = this.bufImg.data;
      const r0 = cell * 0.34;
      for (let y = 0; y < GRID; y++) {
        for (let x = 0; x < GRID; x++) {
          const idx = (y * GRID + x) * 4;
          const r = data2[idx], g = data2[idx + 1], b = data2[idx + 2];
          const lum = (r + g + b) / 3;
          // dark base dot
          const cx = (x + 0.5) * cell;
          const cy = (y + 0.5) * cell;
          if (lum < 4) {
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.fillStyle = 'rgba(18,22,38,0.55)';
            this.ctx.beginPath();
            this.ctx.arc(cx, cy, r0 * 0.55, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalCompositeOperation = 'lighter';
          } else {
            this.ctx.fillStyle = 'rgb(' + Math.round(r) + ',' + Math.round(g) + ',' + Math.round(b) + ')';
            this.ctx.beginPath();
            this.ctx.arc(cx, cy, r0, 0, Math.PI * 2);
            this.ctx.fill();
          }
        }
      }
      this.ctx.globalCompositeOperation = 'source-over';

      requestAnimationFrame(this.tick);
    }
  }

  window.LEDPanel = LEDPanel;
  window.LED_PATTERNS = Object.keys(patterns);
})();
