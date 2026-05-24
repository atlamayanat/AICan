// AI Body — Sergi Ekrani (tepki ekrani)
// gestures.json'u backend'den fetch eder; kontrol panelinden BroadcastChannel ile mesaj alir.

(function () {
  const HIZ = {
    cok_yavas: 0.45,
    yavas: 0.7,
    orta: 1.0,
    hizli: 1.4,
    cok_hizli: 1.9,
  };

  const $ = (q) => document.querySelector(q);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const els = {
    userText: $('#user-text'),
    aiText: $('#ai-text'),
    gestureBadge: $('#gesture-badge'),
    statusDot: $('#status-dot'),
    statusText: $('#status-text'),
    canvas: $('#led-canvas'),
    leftPlaceholder: $('#left-placeholder'),
    rightPlaceholder: $('#right-placeholder'),
    testList: $('#test-list'),
    testPanel: $('#test-panel'),
    controls: document.querySelector('.controls'),
  };

  let panel;
  let gestures = [];
  let gestureMap = new Map();
  let activeTypewriter = null;

  // Otonom "canlı göz" idle — etkileşim olmadan X sn geçince devreye girer.
  const EYE_IDLE_TIMEOUT_MS = 30000;
  let eyeIdleTimer = null;
  function noteInteraction() {
    if (panel) panel.setEyeIdle(false);
    if (eyeIdleTimer) clearTimeout(eyeIdleTimer);
    eyeIdleTimer = setTimeout(() => {
      if (panel) panel.setEyeIdle(true);
    }, EYE_IDLE_TIMEOUT_MS);
  }

  // ——— Yardimcilar ———————————————————————————————————————————
  function speedFor(jest) {
    const h = jest && jest.animasyon ? jest.animasyon.hiz : 'orta';
    return HIZ[h] != null ? HIZ[h] : 1.0;
  }
  function primaryFor(jest) {
    return (jest && jest.animasyon && jest.animasyon.ana_renk) || [120, 220, 255];
  }
  function secondaryFor(jest) {
    const a = jest && jest.animasyon;
    return (a && a.ikincil_renk) || (a && a.ana_renk) || [200, 120, 255];
  }
  function durationMsFor(jest) {
    const s = jest && jest.animasyon && jest.animasyon.sure_sn;
    return (typeof s === 'number' ? s : 4.0) * 1000;
  }
  function intensityFor(jest, override) {
    if (typeof override === 'number') return override;
    const v = jest && jest.animasyon && jest.animasyon.yogunluk_varsayilan;
    return typeof v === 'number' ? v : 0.85;
  }
  function humanName(id) {
    if (!id) return '';
    return id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // ——— Typewriter ——————————————————————————————————————————————
  function typeInto(el, text, speed = 22) {
    if (activeTypewriter && activeTypewriter.id) clearInterval(activeTypewriter.id);
    el.textContent = '';
    el.classList.add('typing');
    let i = 0;
    return new Promise((resolve) => {
      const id = setInterval(() => {
        if (i >= text.length) {
          clearInterval(id);
          el.classList.remove('typing');
          resolve();
          return;
        }
        el.textContent += text[i++];
      }, speed);
      activeTypewriter = { el, id };
    });
  }

  // ——— Jesti tetikle ————————————————————————————————————————————
  // Varsayilan duration: Infinity — jest, baska bir jest gelene kadar oynar.
  function triggerGesture(gestureId, opts = {}) {
    const g = gestureMap.get(gestureId);
    if (!g) {
      console.warn('Bilinmeyen jest_id:', gestureId);
      return;
    }
    const primary = opts.primary || primaryFor(g);
    const secondary = opts.secondary || secondaryFor(g);
    const speed = (opts.speed != null) ? opts.speed : speedFor(g);
    const intensity = intensityFor(g, opts.intensity);
    const duration = (opts.duration != null) ? opts.duration : Number.POSITIVE_INFINITY;
    const isEmoji = (g.gorsel_tipi === 'emoji');

    panel.setGesture({
      pattern: g.animasyon.desen,
      primary, secondary,
      speed, intensity,
      duration,
      gestureId: g.id,
      isEmoji,
    });
    panel.setIdle({
      pattern: 'breathe',
      primary,
      secondary,
      speed: 0.6,
      intensity: 0.7,
      gestureId: null,
      isEmoji: false,
    });

    els.gestureBadge.classList.remove('hidden');
    const rgb = 'rgb(' + primary.join(',') + ')';
    els.gestureBadge.innerHTML =
      '<span class="dot" style="background:' + rgb + ';' +
      ' box-shadow: 0 0 12px ' + rgb + '"></span>' + humanName(g.id);

    // Arka plan ve dış halo aktif jestin baskın rengine kaysın.
    // CSS transition'lar yumuşak (1.4s) geçiş yapar.
    const root = document.documentElement.style;
    root.setProperty('--gesture-glow',   primary.join(','));
    root.setProperty('--gesture-glow-2', secondary.join(','));

    // Gözler de jest rengiyle uyumlu olsun (idle moduna döndüğünde bu renkten gelir)
    if (panel && panel.eyes) panel.eyes.setColors(primary, secondary);

    // Jest = etkileşim; eye idle'ı kapat ve sayacı sıfırla.
    noteInteraction();
  }

  // ——— Yildiz tozu ——————————————————————————————————————————
  function initStars() {
    const c = document.getElementById('stars');
    if (!c) return;
    const ctx = c.getContext('2d');
    function resize() {
      c.width = window.innerWidth;
      c.height = window.innerHeight;
    }
    resize(); window.addEventListener('resize', resize);
    const stars = [];
    for (let i = 0; i < 220; i++) {
      stars.push({
        x: Math.random() * 1920,
        y: Math.random() * 1080,
        r: Math.random() * 1.2 + 0.2,
        a: Math.random(),
        speed: 0.2 + Math.random() * 0.6,
      });
    }
    function draw() {
      ctx.clearRect(0, 0, c.width, c.height);
      for (const s of stars) {
        s.a += 0.005 * s.speed;
        const alpha = 0.3 + 0.4 * (0.5 + 0.5 * Math.sin(s.a));
        ctx.fillStyle = 'rgba(200, 220, 255, ' + alpha + ')';
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      requestAnimationFrame(draw);
    }
    draw();
  }

  // ——— Test paneli (T tusu) ——————————————————————————————————
  function buildTestPanel() {
    if (!els.testList) return;
    els.testList.innerHTML = '';
    gestures.forEach((g, idx) => {
      const btn = document.createElement('button');
      btn.className = 'test-item';
      const rgb = 'rgb(' + primaryFor(g).join(',') + ')';
      btn.innerHTML =
        '<span class="num">' + String(idx + 1).padStart(2, '0') + '</span>' +
        '<span class="swatch" style="background:' + rgb + '"></span>' +
        '<span class="name">' + humanName(g.id) + '</span>' +
        '<span class="pat">' + g.animasyon.desen + '</span>';
      btn.addEventListener('click', () => triggerGesture(g.id));
      els.testList.appendChild(btn);
    });
  }

  // ——— Mod (emoji/desen) ————————————————————————————————
  function applyMode(mode) {
    const m = (mode === 'emoji') ? 'emoji' : 'desen';
    if (panel) panel.setMode(m);
    try { localStorage.setItem('aibody.mode', m); } catch (_) {}
  }
  function loadStoredMode() {
    try { return localStorage.getItem('aibody.mode') || 'desen'; } catch (_) { return 'desen'; }
  }

  // ——— Kontrol paneli ile haberlesme ———————————————————————
  function initChannel() {
    let bc;
    try {
      bc = new BroadcastChannel('aibody');
    } catch (e) {
      console.warn('BroadcastChannel desteklenmiyor', e);
      return;
    }
    bc.onmessage = async (e) => {
      const d = e.data || {};
      if (d.type === 'ping') {
        bc.postMessage({ type: 'display_ready', mode: panel ? panel.mode : 'desen' });
      } else if (d.type === 'set_mode') {
        applyMode(d.mode);
      } else if (d.type === 'user_text') {
        // Ziyaretci mesaj yazdi — eye idle'i hemen kapat (jest sonra gelecek)
        noteInteraction();
        if (els.leftPlaceholder) els.leftPlaceholder.style.display = 'none';
        if (els.rightPlaceholder) els.rightPlaceholder.style.display = 'none';
        if (els.aiText) els.aiText.textContent = '';
        els.gestureBadge.classList.add('hidden');
        await typeInto(els.userText, d.text || '', 26);
      } else if (d.type === 'ai_reply') {
        if (d.jest_id) {
          triggerGesture(d.jest_id, { intensity: d.yogunluk });
        }
        await sleep(350);
        if (els.rightPlaceholder) els.rightPlaceholder.style.display = 'none';
        if (d.yanit) await typeInto(els.aiText, d.yanit, 22);
      } else if (d.type === 'manual_gesture') {
        if (els.leftPlaceholder) els.leftPlaceholder.style.display = 'none';
        if (d.jest_id) triggerGesture(d.jest_id);
      } else if (d.type === 'clear') {
        if (els.userText) els.userText.textContent = '';
        if (els.aiText) els.aiText.textContent = '';
        if (els.leftPlaceholder) els.leftPlaceholder.style.display = '';
        if (els.rightPlaceholder) els.rightPlaceholder.style.display = '';
        els.gestureBadge.classList.add('hidden');
      } else if (d.type === 'stop') {
        const idle = gestureMap.has('huzur') ? 'huzur' : 'meditatif';
        if (gestureMap.has(idle)) triggerGesture(idle, { duration: 99999999 });
      }
    };
    bc.postMessage({ type: 'display_ready', mode: panel ? panel.mode : 'desen' });
    setInterval(() => bc.postMessage({
      type: 'display_ready', mode: panel ? panel.mode : 'desen',
    }), 4000);
  }

  async function loadEmojiManifest() {
    try {
      const r = await fetch('/api/emoji_manifest');
      const data = await r.json();
      if (panel) panel.setEmojiManifest(data.frames || {}, data.fps || 12);
    } catch (e) {
      console.warn('emoji manifest yuklenemedi:', e);
    }
  }

  // ——— Klavye kisayollari ——————————————————————————————————
  document.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
    if (e.key === 't' || e.key === 'T') {
      if (els.testPanel) els.testPanel.classList.toggle('open');
    }
    if (e.key === 'f' || e.key === 'F') {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen();
    }
  });

  // ——— Init ————————————————————————————————————————————————
  async function loadGestures() {
    try {
      const r = await fetch('/api/gestures');
      const data = await r.json();
      gestures = data.jestler || [];
      gestureMap = new Map(gestures.map((g) => [g.id, g]));
    } catch (err) {
      console.error('Jest listesi yuklenemedi:', err);
      if (els.statusText) els.statusText.textContent = 'JEST LISTESI YOK';
    }
  }

  async function init() {
    const size = els.canvas && els.canvas.width ? els.canvas.width : 560;
    panel = new LEDPanel(els.canvas, { size });

    initStars();
    await loadGestures();
    await loadEmojiManifest();
    applyMode(loadStoredMode());
    buildTestPanel();
    initChannel();

    if (els.controls) els.controls.style.display = 'none';

    els.statusDot.classList.add('ok');
    els.statusText.textContent = 'BAGLI';

    const opener = gestureMap.has('huzur') ? 'huzur'
                : (gestureMap.has('meditatif') ? 'meditatif' : null);
    if (opener) {
      setTimeout(() => triggerGesture(opener), 200);
    }
    // Acilis sonrasi eye idle sayacini baslat (30 sn etkilesim yoksa gozler cikar)
    noteInteraction();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
