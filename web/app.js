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
    gameHud: $('#game-hud'),
    winFlash: $('#win-flash'),
    wordTimer: $('#word-timer'),
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

  // ——— Seslendirme (TTS) ————————————————————————————————————————
  // AI cevabi geldiginde /api/speak'ten duyguya gore tonlanmis sesi cek ve cal.
  // Ses, yazi (typewriter) ile PARALEL baslar; ses backend'de CPU'da uretilir.
  let ttsEnabled = true;       // 'S' tusu ile acilip kapanir
  let ttsReady = false;        // backend motoru hazir mi (bilgi amacli)
  let ttsPrimed = false;       // tarayici autoplay kilidi acildi mi
  let currentAudio = null;

  async function checkTtsStatus() {
    try {
      const r = await fetch('/api/speak/status');
      const d = await r.json();
      // autoplay=false veya enabled=false ise sesi hic deneme
      ttsEnabled = (d.enabled !== false) && (d.autoplay !== false);
      ttsReady = !!d.ready;
    } catch (_) { ttsReady = false; }
  }

  // Tarayici autoplay politikasi: ilk kullanici etkilesiminde sesi "ac".
  // (Sergi kiosk'unda gorevli sayfayla bir kez etkilesince ses acilir.)
  function primeAudio() {
    if (ttsPrimed) return;
    ttsPrimed = true;
    try {
      const a = new Audio(
        'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=');
      a.volume = 0;
      a.play().catch(() => {});
    } catch (_) {}
  }

  async function speak(text, jestId, yogunluk) {
    if (!ttsEnabled || !text) return;
    try {
      if (currentAudio) { try { currentAudio.pause(); } catch (_) {} currentAudio = null; }
      const r = await fetch('/api/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          jest_id: jestId || '',
          yogunluk: (typeof yogunluk === 'number' ? yogunluk : 0.7),
        }),
      });
      if (!r.ok) { if (r.status !== 503) console.warn('TTS HTTP', r.status); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = new Audio(url);
      currentAudio = a;
      const cleanup = () => URL.revokeObjectURL(url);
      a.onended = cleanup;
      a.onerror = cleanup;
      a.play().catch((e) => console.warn('Ses oynatilamadi (autoplay kilidi?)', e));
    } catch (e) {
      console.warn('TTS hata:', e);
    }
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

  // ——— Sarı kazanç ışığı (AI tur kazandığında ekran bir kez parlar) ——
  // Aktif jest rengini sıcak altın sarısına çevirir + kısa bir parlama efekti.
  // Bir sonraki jest geldiğinde renk doğal olarak kendi jestine döner.
  const WIN_GLOW = [255, 205, 70];     // sıcak altın sarısı
  const WIN_GLOW_2 = [255, 145, 45];   // turuncu vurgu
  let winFlashTimer = null;
  function triggerWinFlash() {
    const root = document.documentElement.style;
    root.setProperty('--gesture-glow', WIN_GLOW.join(','));
    root.setProperty('--gesture-glow-2', WIN_GLOW_2.join(','));
    const flash = els.winFlash;
    if (!flash) return;
    flash.classList.remove('on');
    void flash.offsetWidth;            // reflow — animasyonu baştan başlat
    flash.classList.add('on');
    if (winFlashTimer) clearTimeout(winFlashTimer);
    winFlashTimer = setTimeout(() => flash.classList.remove('on'), 1600);
  }

  // ——— Kelime oyunu zaman barı (sergi ekranı) ————————————————
  // control.js otorite; burada yalnızca görsel geri sayım gösterilir.
  let dispTimer = { id: null };
  function startDisplayTimer(seconds, who) {
    const bar = els.wordTimer;
    if (!bar) return;
    stopDisplayTimer();
    const fill = bar.querySelector('.wt-fill');
    const label = bar.querySelector('.wt-label');
    const num = bar.querySelector('.wt-num');
    bar.classList.remove('hidden');
    bar.classList.toggle('ai', who === 'ai');
    if (label) label.textContent = (who === 'ai') ? 'AICAN düşünüyor…' : 'SENİN SIRAN';
    const endsAt = Date.now() + seconds * 1000;
    const tick = () => {
      const remain = Math.max(0, (endsAt - Date.now()) / 1000);
      if (num) num.textContent = Math.ceil(remain) + ' sn';
      if (fill) {
        fill.style.width = (remain / seconds) * 100 + '%';
        fill.classList.toggle('low', remain <= 5);
      }
      if (remain <= 0) stopDisplayTimer();
    };
    tick();
    dispTimer.id = setInterval(tick, 100);
    noteInteraction();
  }
  function stopDisplayTimer() {
    if (dispTimer.id) { clearInterval(dispTimer.id); dispTimer.id = null; }
    if (els.wordTimer) els.wordTimer.classList.add('hidden');
  }

  // ——— Oyun skor HUD ————————————————————————————————————
  function updateGameHud(active, score) {
    if (!els.gameHud) return;
    if (active && score) {
      els.gameHud.innerHTML =
        '<span class="ghud-lbl">BEN</span>' +
        '<span class="ghud-num">' + score.ai + '</span>' +
        '<span class="ghud-sep">·</span>' +
        '<span class="ghud-num">' + score.user + '</span>' +
        '<span class="ghud-lbl">SEN</span>';
      els.gameHud.classList.remove('hidden');
    } else {
      els.gameHud.classList.add('hidden');
    }
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
        // AI tur kazandıysa ekranı sarıya boğ (triggerGesture'dan SONRA override).
        if (d.outcome === 'ai_win') triggerWinFlash();
        // Kullanıcı metni typewriter'ı bitsin diye kısa tampon (Faz 3'te 350→180 ms).
        await sleep(180);
        if (els.rightPlaceholder) els.rightPlaceholder.style.display = 'none';
        if (d.yanit) {
          speak(d.yanit, d.jest_id, d.yogunluk);   // sesi yaziyla paralel baslat
          await typeInto(els.aiText, d.yanit, 22);
        }
        // AI "bir daha oynayalım" diye ısrar ediyorsa metni hafifçe nabızlat.
        if (d.insist && els.aiText) {
          els.aiText.classList.remove('insist');
          void els.aiText.offsetWidth;
          els.aiText.classList.add('insist');
          setTimeout(() => els.aiText.classList.remove('insist'), 2400);
        }
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
      } else if (d.type === 'game_score') {
        updateGameHud(d.active, d.score);
      } else if (d.type === 'timer_start') {
        startDisplayTimer(d.seconds, d.who);
      } else if (d.type === 'timer_stop') {
        stopDisplayTimer();
      } else if (d.type === 'game_exit') {
        updateGameHud(false, null);
        stopDisplayTimer();
        if (els.userText) els.userText.textContent = '';
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
    if (e.key === 's' || e.key === 'S') {
      ttsEnabled = !ttsEnabled;
      if (!ttsEnabled && currentAudio) { try { currentAudio.pause(); } catch (_) {} }
      if (els.statusText) els.statusText.textContent = ttsEnabled ? 'BAGLI' : 'BAGLI · SES KAPALI';
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
    checkTtsStatus();
    // Autoplay kilidini ilk etkilesimde ac (kiosk: gorevli bir kez tiklar/tusa basar)
    window.addEventListener('pointerdown', primeAudio, { once: true });
    window.addEventListener('keydown', primeAudio, { once: true });

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
