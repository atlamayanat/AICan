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
    gameOptions: $('#game-options'),
    aiThinking: $('#ai-thinking'),
    stateBadge: $('#state-badge'),
    attractBox: $('#attract'),
    attractMsg: $('#attract-msg'),
    attractCount: $('#attract-count'),
    attractNum: $('#ac-num'),
  };

  let panel;
  let gestures = [];
  let gestureMap = new Map();
  let activeTypewriter = null;
  let bc = null;                 // BroadcastChannel — kontrol paneli ile iki yonlu

  // ——— Aşamalı durum rozeti (Dinliyorum/Düşünüyorum/Konuşuyor/Yazıyor) ———
  // Öncelik: dinleme > düşünme > konuşma (TTS) > yazma (daktilo); boşta gizli.
  let stListening = false;
  let stThinking = false;
  let stTyping = false;
  let stSpeaking = false;
  function updateStateBadge() {
    const b = els.stateBadge;
    if (!b) return;
    let label = null;
    if (stListening) label = 'Dinliyorum…';
    else if (stThinking) label = 'Düşünüyorum…';
    else if (stSpeaking) label = 'Konuşuyor…';
    else if (stTyping) label = 'Yazıyor…';
    if (!label) { b.classList.add('hidden'); return; }
    const span = b.querySelector('.sb-label');
    if (span) span.textContent = label;
    b.classList.remove('hidden');
  }

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
  // Daktilo hızı metin uzunluğuna adaptif: kısa metin ~22ms/harf, uzun ~12ms/harf
  // (uzun cevaplar sıkmadan akar; arada doğrusal geçiş).
  function adaptiveTypeSpeed(text) {
    const n = String(text || '').length;
    if (n <= 60) return 22;
    if (n >= 200) return 12;
    return Math.round(22 - ((n - 60) / 140) * 10);
  }
  // ——— Metni kutuya sigdir (kaydirma cubugu cikmasin) ——————————————————
  // Konusma balonunun sabit bir max-height'i var. Kaydirma yerine, TAM metni
  // gecici olcup scrollHeight kutuyu asiyorsa font boyutunu 34px'den ~18px'e
  // kademeli kucultur. Olcum daktilo BASLAMADAN once yapilir; boylece yazarken
  // boyut sabit kalir ve zipplama olmaz. Kisa mesajlar 34px'de kalir.
  const FIT_MAX_FS = 34, FIT_MIN_FS = 18;
  function fitSpeechText(el, fullText) {
    if (!el) return;
    const prev = el.textContent;
    el.style.fontSize = FIT_MAX_FS + 'px';
    el.textContent = fullText || '';
    let fs = FIT_MAX_FS;
    // scrollHeight (tam icerik) > clientHeight (max-height ile sinirli) => tasma
    while (fs > FIT_MIN_FS && el.scrollHeight > el.clientHeight) {
      fs -= 1;
      el.style.fontSize = fs + 'px';
    }
    el.textContent = prev;   // typeInto zaten '' ile bastan yazacak
  }

  function typeInto(el, text, speed) {
    if (activeTypewriter && activeTypewriter.id) {
      clearInterval(activeTypewriter.id);
      if (activeTypewriter.el === els.aiText) { stTyping = false; updateStateBadge(); }
    }
    const ms = (typeof speed === 'number') ? speed : adaptiveTypeSpeed(text);
    el.textContent = '';
    el.classList.add('typing');
    if (el === els.aiText) { stTyping = true; updateStateBadge(); }
    let i = 0;
    return new Promise((resolve) => {
      const id = setInterval(() => {
        if (i >= text.length) {
          clearInterval(id);
          el.classList.remove('typing');
          if (el === els.aiText) { stTyping = false; updateStateBadge(); }
          resolve();
          return;
        }
        el.textContent += text[i++];
      }, ms);
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

  // ——— Cumle-bazli akis: metin cumle parcalarina bolunur, parcalar SIRAYLA
  // POST edilir ve gelen sesler kuyrukta kesintisiz arka arkaya calinir.
  // Ilk parca gelir gelmez ses baslar; tek cumlelik kisa metin = tek istek.
  let speakToken = 0;          // artan sayac: her yeni konusma eskisini iptal eder
  let audioQueue = [];         // sirada bekleyen blob URL'leri
  let queuePlaying = false;

  // Cumle sinirlari: .!?… + bosluk. orchestrator/web_server.py _split_sentences_tr
  // ile BIREBIR ayni mantik (on-isitma onbellek anahtarlari isabet etsin diye).
  const SENT_MIN_LEN = 10;
  function splitSentences(text) {
    const parts = String(text || '').trim().split(/(?<=[.!?…])\s+/)
      .map((s) => s.trim()).filter(Boolean);
    const out = [];
    let buf = '';
    for (const p of parts) {
      buf = buf ? buf + ' ' + p : p;
      if (buf.length >= SENT_MIN_LEN) { out.push(buf); buf = ''; }
    }
    if (buf) {
      if (out.length) out[out.length - 1] += ' ' + buf;
      else out.push(buf);
    }
    return out;
  }

  // Aktif konusmayi tamamen durdur: calan ses + bekleyen kuyruk + suren fetch'ler.
  function stopSpeech() {
    speakToken++;              // eski uretici dongu/kuyruk zincirleri gecersiz olsun
    queuePlaying = false;
    if (currentAudio) {
      try { currentAudio.pause(); URL.revokeObjectURL(currentAudio.src); } catch (_) {}
      currentAudio = null;
    }
    for (const u of audioQueue) { try { URL.revokeObjectURL(u); } catch (_) {} }
    audioQueue = [];
    if (stSpeaking) { stSpeaking = false; updateStateBadge(); }
  }

  async function fetchSpeechUrl(text, jestId, yogunluk) {
    const r = await fetch('/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, jest_id: jestId || '', yogunluk: yogunluk }),
    });
    if (!r.ok) { if (r.status !== 503) console.warn('TTS HTTP', r.status); return null; }
    const blob = await r.blob();
    return URL.createObjectURL(blob);
  }

  function playQueue(token) {
    if (token !== speakToken || queuePlaying) return;
    const url = audioQueue.shift();
    if (!url) return;
    queuePlaying = true;
    stSpeaking = true;                     // "Konuşuyor…" rozeti
    updateStateBadge();
    const a = new Audio(url);
    currentAudio = a;
    let bitti = false;
    const done = () => {
      if (bitti) return;
      bitti = true;
      try { URL.revokeObjectURL(url); } catch (_) {}
      if (token !== speakToken) return;   // stopSpeech geldi: kuyruga dokunma
      queuePlaying = false;
      if (currentAudio === a) currentAudio = null;
      playQueue(token);                    // siradaki parca — kesintisiz devam
      if (!queuePlaying && stSpeaking) { stSpeaking = false; updateStateBadge(); }
    };
    a.onended = done;
    a.onerror = done;
    a.play().catch((e) => { console.warn('Ses oynatilamadi (autoplay kilidi?)', e); done(); });
  }

  // Imza SABIT: speak(text, jestId, yogunluk) — ayni jest/yogunluk tum parcalara.
  async function speak(text, jestId, yogunluk) {
    if (!ttsEnabled || !text) return;
    stopSpeech();
    const token = speakToken;
    const yog = (typeof yogunluk === 'number' ? yogunluk : 0.7);
    try {
      const parcalar = splitSentences(text);
      for (const parca of parcalar) {
        if (token !== speakToken || !ttsEnabled) return;
        const url = await fetchSpeechUrl(parca, jestId, yog);
        if (token !== speakToken) {          // bu arada iptal geldi
          if (url) { try { URL.revokeObjectURL(url); } catch (_) {} }
          return;
        }
        if (!url) return;                    // backend hatasi: kalan parcalari zorlama
        audioQueue.push(url);
        playQueue(token);
      }
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
    // Jest rozeti değişiminde ~300ms cross-fade (yalnız opacity animasyonu)
    els.gestureBadge.classList.remove('swap');
    void els.gestureBadge.offsetWidth;      // reflow — animasyonu baştan başlat
    els.gestureBadge.classList.add('swap');

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

  // ——— "Düşünüyorum…" göstergesi ————————————————————————————
  // Kontrol paneli 'thinking' yayınlar; ai_reply gelince temizlenir.
  // 45 sn güvenlik zaman aşımı, backend cevap veremezse takılı kalmayı önler.
  let thinkingSafetyId = null;
  function thinkingGestureId() {
    if (gestureMap.has('bekle')) return 'bekle';
    for (const g of gestures) {
      if (g.animasyon && g.animasyon.desen === 'three_dots') return g.id;
    }
    return null;
  }
  function setThinking(on, label, jest) {
    stThinking = !!on;
    if (thinkingSafetyId) { clearTimeout(thinkingSafetyId); thinkingSafetyId = null; }
    if (els.aiThinking) {
      if (on) {
        els.aiThinking.textContent = label || 'Düşünüyorum…';
        els.aiThinking.classList.remove('hidden');
        if (els.rightPlaceholder) els.rightPlaceholder.style.display = 'none';
      } else {
        els.aiThinking.classList.add('hidden');
      }
    }
    if (on) {
      thinkingSafetyId = setTimeout(() => setThinking(false), 45000);
      // jest=false: hızlı yerel oyun yanıtlarında jest titremesin (yalnız gösterge)
      if (jest !== false) {
        const gid = thinkingGestureId();
        if (gid) triggerGesture(gid, { intensity: 0.6 });
      }
      noteInteraction();
    }
    updateStateBadge();
  }

  // ——— Attract / boşta modu (zamanlayıcı otoritesi control.js'te) ————
  // attract_on: gözler LED panelde sürer; davet metinleri yumuşak fade ile döner.
  // attract_countdown: "Hâlâ orada mısın?" + görünür geri sayım.
  // Herhangi bir gerçek etkileşim mesajı attract'ı anında kapatır.
  const ATTRACT_MSGS = ['Bana bir soru sor!', 'Benimle oyun oyna!', 'Sana uzayı anlatayım mı?'];
  const ATTRACT_CYCLE_MS = 6000;
  const ATTRACT_FADE_MS = 800;
  const ATTRACT_CANCEL = new Set([
    'user_text', 'thinking', 'ai_reply', 'manual_gesture', 'listening',
    'game_score', 'game_options', 'game_option_select', 'timer_start', 'game_exit',
  ]);
  let attractActive = false;
  let attractIdx = 0;
  let attractCycleId = null;
  let attractFadeId = null;

  function attractShow() {
    if (!els.attractBox || attractActive) return;
    attractActive = true;
    attractIdx = 0;
    if (els.attractCount) els.attractCount.classList.add('hidden');
    if (els.attractMsg) {
      els.attractMsg.classList.remove('out');
      els.attractMsg.textContent = ATTRACT_MSGS[0];
    }
    els.attractBox.classList.remove('hidden');
    attractCycleId = setInterval(() => {
      if (!els.attractMsg) return;
      els.attractMsg.classList.add('out');               // yumuşak fade-out
      attractFadeId = setTimeout(() => {
        attractIdx = (attractIdx + 1) % ATTRACT_MSGS.length;
        els.attractMsg.textContent = ATTRACT_MSGS[attractIdx];
        els.attractMsg.classList.remove('out');           // fade-in
      }, ATTRACT_FADE_MS);
    }, ATTRACT_CYCLE_MS);
  }
  function attractHide() {
    if (attractCycleId) { clearInterval(attractCycleId); attractCycleId = null; }
    if (attractFadeId) { clearTimeout(attractFadeId); attractFadeId = null; }
    attractActive = false;
    if (els.attractBox) els.attractBox.classList.add('hidden');
    if (els.attractCount) els.attractCount.classList.add('hidden');
  }
  function attractCountdownTick(seconds) {
    if (!attractActive) attractShow();
    if (els.attractCount) els.attractCount.classList.remove('hidden');
    if (els.attractNum) els.attractNum.textContent = String(seconds);
  }

  // ——— Yildiz tozu ——————————————————————————————————————————
  // Performans: 2 karede 1 çizim (parıltı dt-tabanlı — algılanan hız değişmez),
  // sekme gizliyken tamamen durur.
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
    let frameNo = 0;
    let lastDraw = performance.now();
    function draw(now) {
      requestAnimationFrame(draw);
      if (document.hidden) { lastDraw = now; return; }   // gizliyken dur
      frameNo++;
      if (frameNo % 2 === 1) return;                     // 2 karede 1 çiz
      const dt = Math.min(100, now - lastDraw) / 16.7;   // ~kare cinsinden süre
      lastDraw = now;
      ctx.clearRect(0, 0, c.width, c.height);
      for (const s of stars) {
        s.a += 0.005 * s.speed * dt;
        const alpha = 0.3 + 0.4 * (0.5 + 0.5 * Math.sin(s.a));
        ctx.fillStyle = 'rgba(200, 220, 255, ' + alpha + ')';
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    requestAnimationFrame(draw);
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

  function optionKeyLabel(button, index) {
    const key = String((button && button.key) || '').trim();
    const readable = {
      tas: 'taş',
      kagit: 'kağıt',
      makas: 'makas',
      cikis: 'çıkış',
      basla: 'başla',
      edebiyat: 'edebiyat',
      tarih: 'tarih',
      bilim: 'bilim',
      genel: 'genel',
      eszit: 'eş/zıt',
      atasozu: 'atasözü',
      dogruyanlis: 'doğru/yanlış',
      kelime: 'kelime',
      bilgi: 'bilgi',
    };
    if (readable[key]) return readable[key];
    if (/^[0-9]+$/.test(key)) return key;
    return key || String(index + 1);
  }

  function optionTextLabel(button, index) {
    const raw = (button && button.label) ? String(button.label) : optionKeyLabel(button, index);
    const clean = raw.replace(/^[^\p{L}\p{N}]+/u, '').replace(/\s+/g, ' ').trim();
    return clean || raw;
  }

  function normChoice(text) {
    return String(text || '')
      .replace(/[İI]/g, 'i').replace(/Ç/g, 'c').replace(/Ğ/g, 'g')
      .replace(/Ö/g, 'o').replace(/Ş/g, 's').replace(/Ü/g, 'u')
      .toLowerCase()
      .replace(/[çğıöşüâîû]/g, (c) => (
        { 'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u', 'â': 'a', 'î': 'i', 'û': 'u' }[c] || c
      ))
      .replace(/[^a-z0-9 ]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function renderGameOptions(payload) {
    const box = els.gameOptions;
    if (!box) return;
    const buttons = Array.isArray(payload && payload.buttons) ? payload.buttons : [];
    box.innerHTML = '';
    box.classList.remove('count-2', 'count-3', 'count-4', 'count-5');
    if (!payload || !payload.visible || buttons.length === 0) {
      box.classList.add('hidden');
      return;
    }
    box.classList.add('count-' + Math.min(Math.max(buttons.length, 2), 5));
    buttons.forEach((button, index) => {
      const row = document.createElement('div');
      row.className = 'game-option';
      row.style.animationDelay = Math.min(index * 45, 180) + 'ms';
      row.dataset.key = String((button && button.key) || '');
      row.dataset.choice = normChoice(
        row.dataset.key + ' ' + optionKeyLabel(button, index) + ' ' + optionTextLabel(button, index)
      );

      const key = document.createElement('span');
      key.className = 'go-key';
      key.textContent = optionKeyLabel(button, index);

      const label = document.createElement('span');
      label.className = 'go-label';
      label.textContent = optionTextLabel(button, index);

      row.appendChild(key);
      row.appendChild(label);
      box.appendChild(row);
    });
    box.classList.remove('hidden');
    noteInteraction();
  }

  function selectGameOption(payload) {
    const box = els.gameOptions;
    if (!box || box.classList.contains('hidden')) return;
    const key = String((payload && payload.key) || '');
    const text = normChoice((payload && (payload.text || payload.label)) || key);
    let selected = null;
    for (const row of box.querySelectorAll('.game-option')) {
      row.classList.remove('selected', 'pulse');
      const rowKey = row.dataset.key || '';
      const rowChoice = row.dataset.choice || '';
      if (!selected && (
        (key && rowKey === key) ||
        (text && (rowChoice === text || rowChoice.includes(text) || text.includes(rowChoice)))
      )) {
        selected = row;
      }
    }
    if (!selected) return;
    selected.classList.add('selected');
    void selected.offsetWidth;
    selected.classList.add('pulse');
    setTimeout(() => selected && selected.classList.remove('pulse'), 1200);
  }

  function hideGameOptions() {
    if (!els.gameOptions) return;
    els.gameOptions.innerHTML = '';
    els.gameOptions.className = 'game-options hidden';
  }

  function resetSpeechPanels() {
    if (activeTypewriter && activeTypewriter.id) {
      clearInterval(activeTypewriter.id);
      if (activeTypewriter.el) activeTypewriter.el.classList.remove('typing');
      activeTypewriter = null;
    }
    stTyping = false;
    if (els.aiThinking) els.aiThinking.classList.add('hidden');
    updateStateBadge();
    if (els.userText) els.userText.textContent = '';
    if (els.aiText) {
      els.aiText.textContent = '';
      els.aiText.classList.remove('insist', 'typing');
    }
    if (els.leftPlaceholder) els.leftPlaceholder.style.display = '';
    if (els.rightPlaceholder) els.rightPlaceholder.style.display = '';
    if (els.gestureBadge) els.gestureBadge.classList.add('hidden');
  }

  // ——— Sürekli sesli giriş (ekran mikrofonu + VAD) ————————————————————
  // Sergi ekranında mikrofon sürekli açık kalır: AI KONUŞMUYOR/DÜŞÜNMÜYOR/
  // YAZMIYORken dinler; kişi cümlesini bitirip sustuğunda (sessizlik eşiği)
  // segmenti otomatik Whisper'a (/api/transcribe) yollar, çıkan metni kontrol
  // paneline BroadcastChannel ile iletir ('voice_input') — orada tıpkı yazılıp
  // gönderilmiş gibi işlenir. Bas-tut sistemi kontrol panelinde fallback kalır.
  //
  // Yankı koruması: TTS bu ekranın hoparlöründen çaldığı için, AI çıktı
  // verirken (stThinking/stSpeaking/stTyping) kayıt tamamen durur; mikrofon
  // AI'nın kendi sesini yakalayamaz. Ayrıca echoCancellation açık.
  const VI = {
    enabled: true,          // özellik açık mı (config.voice_input.enabled)
    autostart: true,        // ilk dokunuşta kendiliğinden başlasın mı
    silenceMs: 1000,        // sustuktan sonra "cümle bitti" sayma süresi
    minSpeechMs: 350,       // bundan kısa ses = gürültü, gönderme
    maxUtteranceMs: 12000,  // güvenlik tavanı — tek konuşma bu kadar sürer
    onsetMult: 2.2,         // konuşma eşiği = gürültü_tabanı * mult
    absMinRms: 0.012,       // mutlak alt eşik (sessiz odada bile bu kadar gerek)
    cooldownMs: 400,        // AI sustuktan sonra tekrar dinlemeye geçme gecikmesi
  };
  let viActive = false;          // dinleme fiilen açık mı (mic akışı var)
  let viStream = null;
  let viCtx = null;
  let viAnalyser = null;
  let viData = null;             // zaman-alanı örnek tamponu (Float32Array)
  let viRec = null;              // o anki konuşma için MediaRecorder
  let viChunks = [];
  let viMime = '';
  let viMonitorId = null;        // RMS izleme interval
  let viRecStartAt = 0;
  let viLastLoudAt = 0;
  let viHadSpeech = false;
  let viNoiseFloor = 0.01;       // ortam gürültüsü (EMA ile güncellenir)
  let viPendingAction = null;    // 'send' | 'discard' — onstop ne yapsın
  let viStopping = false;        // stop() çağrıldı, onstop bekleniyor (yarış engeli)
  let viBusyTranscribe = false;  // aynı anda tek transkripsiyon
  let viHoldUntil = 0;           // bu ana kadar yeni kayıt başlatma (cooldown)
  let viWasGated = false;
  let viShowListening = false;   // rozet durumu takibi (spam engelle)

  // AI çıktı veriyorsa dinleme (yankı + sıra karışması engeli). Attract'ta
  // dinlemeye DEVAM ederiz ki gelen ziyaretçi konuşunca uyansın.
  function viGated() {
    return stThinking || stSpeaking || stTyping;
  }

  function viSetListeningBadge(on) {
    if (on === viShowListening) return;
    viShowListening = on;
    stListening = on;
    updateStateBadge();
  }

  function viStopRecorder(action) {
    if (!viRec || viRec.state !== 'recording' || viStopping) return;
    viPendingAction = action;
    viStopping = true;   // onstop işleyene kadar yeni kayıt açma
    // Gönderimden sonra kısa nefes: kontrol paneli 'thinking' yayıp mikrofonu
    // kapatana kadar tekrar tetiklenmesin.
    if (action === 'send') viHoldUntil = performance.now() + 800;
    try { viRec.stop(); } catch (_) {}
  }

  function viStartRecorder() {
    if (!viStream) return;
    try {
      viRec = viMime ? new MediaRecorder(viStream, { mimeType: viMime })
                     : new MediaRecorder(viStream);
    } catch (e) {
      console.warn('VI: MediaRecorder açılamadı', e);
      viRec = null;
      return;
    }
    viChunks = [];
    viHadSpeech = false;
    viPendingAction = null;
    viStopping = false;
    viRecStartAt = performance.now();
    viLastLoudAt = viRecStartAt;
    viRec.ondataavailable = (ev) => { if (ev.data && ev.data.size > 0) viChunks.push(ev.data); };
    viRec.onstop = viOnRecStop;
    try { viRec.start(); } catch (e) { console.warn('VI: kayıt başlamadı', e); viRec = null; }
  }

  function viOnRecStop() {
    const action = viPendingAction; viPendingAction = null;
    const chunks = viChunks; viChunks = [];
    const hadSpeech = viHadSpeech;
    const durMs = performance.now() - viRecStartAt;
    viRec = null;       // sonraki tick yeni kayıt açar (cooldown'a göre)
    viStopping = false; // artık güvenle yeniden başlatılabilir
    if (action === 'send' && hadSpeech && chunks.length && durMs >= VI.minSpeechMs) {
      const blob = new Blob(chunks, { type: viMime || 'audio/webm' });
      viTranscribeAndSend(blob);
    }
  }

  async function viTranscribeAndSend(blob) {
    if (viBusyTranscribe) return;
    viBusyTranscribe = true;   // viHoldUntil zaten viStopRecorder('send')'de ayarlandı
    try {
      const fd = new FormData();
      fd.append('audio', blob, 'utt.webm');
      const r = await fetch('/api/transcribe', { method: 'POST', body: fd });
      const data = await r.json();
      const txt = ((data && data.text) || '').trim();
      if (txt && bc) {
        bc.postMessage({ type: 'voice_input', text: txt });
      }
    } catch (e) {
      console.warn('VI: transkripsiyon hatası', e);
    } finally {
      viBusyTranscribe = false;
    }
  }

  function viMonitorTick() {
    if (!viActive || !viAnalyser) return;
    const now = performance.now();

    // Gate: AI çıktı veriyorsa kaydı at ve dinlemeyi askıya al
    if (viGated()) {
      if (viRec && viRec.state === 'recording') viStopRecorder('discard');
      viWasGated = true;
      viSetListeningBadge(false);
      return;
    }
    // Gate yeni kalktıysa: AI'nın son hecesini yakalamamak için kısa bekle
    if (viWasGated) { viWasGated = false; viHoldUntil = now + VI.cooldownMs; }

    // RMS (ses seviyesi) ölç
    viAnalyser.getFloatTimeDomainData(viData);
    let sum = 0;
    for (let i = 0; i < viData.length; i++) sum += viData[i] * viData[i];
    const rms = Math.sqrt(sum / viData.length);
    const thr = Math.max(VI.absMinRms, viNoiseFloor * VI.onsetMult);
    const loud = rms > thr;

    // Kayıt yoksa (ve bir stop işlenmiyorsa, cooldown bittiyse) başlat;
    // bu arada rozeti "dinliyor" yap.
    if (!viRec || viRec.state !== 'recording') {
      viSetListeningBadge(true);
      if (!viStopping && now >= viHoldUntil) viStartRecorder();
      if (!loud) viNoiseFloor = viNoiseFloor * 0.95 + rms * 0.05;  // gürültü tabanı
      return;
    }

    if (loud) {
      viLastLoudAt = now;
      viHadSpeech = true;
    } else if (!viHadSpeech) {
      viNoiseFloor = viNoiseFloor * 0.95 + rms * 0.05;             // hâlâ sessizken taban
    }

    const sinceStart = now - viRecStartAt;
    const sinceLoud = now - viLastLoudAt;

    if (viHadSpeech && sinceLoud >= VI.silenceMs && sinceStart >= VI.minSpeechMs) {
      viStopRecorder('send');        // kişi sustu → gönder
    } else if (viHadSpeech && sinceStart >= VI.maxUtteranceMs) {
      viStopRecorder('send');        // güvenlik tavanı
    } else if (!viHadSpeech && sinceStart >= VI.silenceMs * 4) {
      viStopRecorder('discard');     // sadece sessizlik birikti → tazele (taban güncel kalsın)
    }
  }

  async function viEnable() {
    if (viActive || !VI.enabled) return;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia
        || typeof MediaRecorder === 'undefined' || !AudioCtx) {
      console.warn('VI: tarayıcı mikrofon/AudioContext API desteklemiyor');
      return;
    }
    try {
      viStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (e) {
      console.warn('VI: mikrofon reddedildi/yok —', e.name);
      return;
    }
    viMime = '';
    for (const m of ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']) {
      if (MediaRecorder.isTypeSupported(m)) { viMime = m; break; }
    }
    try {
      viCtx = new AudioCtx();
      const src = viCtx.createMediaStreamSource(viStream);
      viAnalyser = viCtx.createAnalyser();
      viAnalyser.fftSize = 1024;
      viData = new Float32Array(viAnalyser.fftSize);
      src.connect(viAnalyser);       // destination'a BAĞLAMA → geri besleme yok
      if (viCtx.state === 'suspended') viCtx.resume().catch(() => {});
    } catch (e) {
      console.warn('VI: AudioContext kurulamadı', e);
      viDisable();
      return;
    }
    viActive = true;
    viNoiseFloor = 0.01;
    viWasGated = false;
    viHoldUntil = performance.now() + 500;
    if (viMonitorId) clearInterval(viMonitorId);
    viMonitorId = setInterval(viMonitorTick, 50);
    console.info('VI: sürekli sesli giriş AÇIK');
  }

  function viDisable() {
    viActive = false;
    if (viMonitorId) { clearInterval(viMonitorId); viMonitorId = null; }
    if (viRec && viRec.state === 'recording') { try { viRec.stop(); } catch (_) {} }
    viRec = null;
    if (viStream) { for (const t of viStream.getTracks()) { try { t.stop(); } catch (_) {} } viStream = null; }
    if (viCtx) { try { viCtx.close(); } catch (_) {} viCtx = null; }
    viAnalyser = null; viData = null;
    viSetListeningBadge(false);
    console.info('VI: sürekli sesli giriş KAPALI');
  }

  function viToggle() { if (viActive) viDisable(); else viEnable(); }

  async function loadVoiceInputConfig() {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      const v = d && d.voice_input;
      if (!v) return;
      VI.enabled = v.enabled !== false;
      VI.autostart = v.autostart !== false;
      if (typeof v.silence_ms === 'number') VI.silenceMs = v.silence_ms;
      if (typeof v.min_speech_ms === 'number') VI.minSpeechMs = v.min_speech_ms;
      if (typeof v.max_utterance_ms === 'number') VI.maxUtteranceMs = v.max_utterance_ms;
      if (typeof v.onset_mult === 'number') VI.onsetMult = v.onset_mult;
      if (typeof v.abs_min_rms === 'number') VI.absMinRms = v.abs_min_rms;
      if (typeof v.cooldown_ms === 'number') VI.cooldownMs = v.cooldown_ms;
    } catch (e) {
      console.warn('VI: config alınamadı, varsayılanlar kullanılıyor', e);
    }
  }

  // ——— Kontrol paneli ile haberlesme ———————————————————————
  function initChannel() {
    try {
      bc = new BroadcastChannel('aibody');
    } catch (e) {
      console.warn('BroadcastChannel desteklenmiyor', e);
      return;
    }
    bc.onmessage = async (e) => {
      const d = e.data || {};
      // Herhangi bir gerçek etkileşim mesajı attract modunu anında kapatır.
      if (ATTRACT_CANCEL.has(d.type)) attractHide();
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
        fitSpeechText(els.userText, d.text || '');  // uzun mesaj: kaydirma yerine kucult
        await typeInto(els.userText, d.text || '', 26);
      } else if (d.type === 'ai_reply') {
        setThinking(false);                        // "Düşünüyorum…" göstergesini kapat
        if (d.jest_id) {
          triggerGesture(d.jest_id, { intensity: d.yogunluk });
        }
        // AI tur kazandıysa ekranı sarıya boğ (triggerGesture'dan SONRA override).
        if (d.outcome === 'ai_win') triggerWinFlash();
        // Kullanıcı metni typewriter'ı bitsin diye kısa tampon (Faz 3'te 350→180 ms).
        await sleep(180);
        if (els.rightPlaceholder) els.rightPlaceholder.style.display = 'none';
        if (d.yanit) {
          // Cevap balonu girişi: fade + translateY (yalnız transform/opacity)
          els.aiText.classList.remove('reply-in');
          void els.aiText.offsetWidth;
          els.aiText.classList.add('reply-in');
          speak(d.yanit, d.jest_id, d.yogunluk);   // sesi yaziyla paralel baslat
          fitSpeechText(els.aiText, d.yanit);      // uzun cevap: kaydirma yerine kucult
          await typeInto(els.aiText, d.yanit);     // hız: metin uzunluğuna adaptif
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
        stopSpeech();            // ses kuyrugu da temizlensin
        setThinking(false);
        resetSpeechPanels();
        hideGameOptions();
      } else if (d.type === 'session_reset') {
        stopSpeech();
        if (d.reload) {
          // Boşta-sıfırlama (attract zaman aşımı): sayfa oturum-tabanlı olduğundan
          // reload ziyaretçiye görünmez; bellek sızıntısı sigortasıdır.
          location.reload();
          return;
        }
        setThinking(false);
        updateGameHud(false, null);
        stopDisplayTimer();
        hideGameOptions();
        resetSpeechPanels();
      } else if (d.type === 'stop') {
        stopSpeech();            // calan ses + bekleyen parcalar iptal
        setThinking(false);
        const idle = gestureMap.has('huzur') ? 'huzur' : 'meditatif';
        if (gestureMap.has(idle)) triggerGesture(idle, { duration: 99999999 });
      } else if (d.type === 'thinking') {
        setThinking(d.on !== false, d.label, d.jest);
      } else if (d.type === 'listening') {
        stListening = (d.on !== false);
        if (stListening) noteInteraction();
        updateStateBadge();
      } else if (d.type === 'attract_on') {
        attractShow();
      } else if (d.type === 'attract_off') {
        attractHide();
      } else if (d.type === 'attract_countdown') {
        attractCountdownTick(d.seconds);
      } else if (d.type === 'game_score') {
        updateGameHud(d.active, d.score);
      } else if (d.type === 'game_options') {
        renderGameOptions(d);
      } else if (d.type === 'game_option_select') {
        selectGameOption(d);
      } else if (d.type === 'timer_start') {
        startDisplayTimer(d.seconds, d.who);
      } else if (d.type === 'timer_stop') {
        stopDisplayTimer();
      } else if (d.type === 'game_exit') {
        setThinking(false);
        updateGameHud(false, null);
        stopDisplayTimer();
        hideGameOptions();
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
    if (e.key === 'd' || e.key === 'D') {
      viToggle();   // sürekli sesli giriş (dinleme) aç/kapa
    }
    if (e.key === 's' || e.key === 'S') {
      ttsEnabled = !ttsEnabled;
      if (!ttsEnabled) stopSpeech();   // calan ses + kuyruk + bekleyen parcalar
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
    await loadVoiceInputConfig();
    // Autoplay kilidini ilk etkilesimde ac (kiosk: gorevli bir kez tiklar/tusa basar)
    window.addEventListener('pointerdown', primeAudio, { once: true });
    window.addEventListener('keydown', primeAudio, { once: true });
    // Surekli sesli giris: mic izni bir kullanici jesti ister. Ilk dokunusta
    // (gorevlinin ekrana ilk tiklamasi) kendiliginden baslat. 'd' ile ac/kapa.
    if (VI.enabled && VI.autostart) {
      window.addEventListener('pointerdown', () => viEnable(), { once: true });
    }

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
