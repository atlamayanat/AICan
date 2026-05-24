// Kontrol Paneli — operator arayuzu
// Gercek backend (Python/Flask) + sergi ekrani (BroadcastChannel) ile konusur.

(function () {
  const HIZ = {
    cok_yavas: 0.45, yavas: 0.7, orta: 1.0, hizli: 1.4, cok_hizli: 1.9,
  };

  const $ = (q) => document.querySelector(q);

  const els = {
    canvas: $('#led-canvas'),                 // panelde LED canvas yok ama olabilir
    prompt: $('#prompt-input'),
    sendBtn: $('#send-btn'),
    stopBtn: $('#stop-btn'),
    aiResponse: $('#ai-response'),
    eventLog: $('#event-log'),
    activeGesture: $('#active-gesture'),
    modelSelect: $('#model-select'),
    newModelInput: $('#new-model-input'),
    activateBtn: $('#activate-model'),
    refreshBtn: $('#refresh-models'),
    downloadBtn: $('#download-model'),
    activeModel: $('#active-model'),
    activeNote: $('#active-note'),
    lastGesture: $('#last-gesture'),
    lastIntensity: $('#last-intensity'),
    lastDuration: $('#last-duration'),
    statThink: $('#stat-think'),
    statLoad: $('#stat-load'),
    statTokens: $('#stat-tokens'),
    statRate: $('#stat-rate'),
    gestureGrid: $('#gesture-grid'),
    connDot: $('#conn-dot'),
    connText: $('#conn-text'),
    clock: $('#clock'),
    modeToggle: $('#mode-toggle'),
    micBtn: $('#mic-btn'),
    micStatus: $('#mic-status'),
    charCount: $('#char-count'),
  };

  let currentMode = 'desen'; // 'desen' | 'emoji'

  // ——— Sergi koruma sınırları (backend'den /api/config ile gelir)
  let MAX_CHARS = 240;
  let MAX_RECORD_MS = 30000;

  // ——— Mikrofon (Whisper STT) durumu ————————————————————
  let micStream = null;
  let mediaRecorder = null;
  let recChunks = [];
  let recStartedAt = 0;
  let recAutoStopTimer = null;
  let whisperReady = false;
  let micEnabled = false;

  let panel;
  let bc;
  let gestures = [];
  let gestureMap = new Map();
  let lastDisplayPing = 0;

  // ——— Yardimcilar ————————————————————————————————————
  const pad = (n, w = 2) => String(n).padStart(w, '0');
  function nowStamp() {
    const d = new Date();
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }
  function tickClock() { if (els.clock) els.clock.textContent = nowStamp(); }
  setInterval(tickClock, 1000); tickClock();

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
  function humanName(id) {
    if (!id) return '';
    return id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // ——— Olay log ————————————————————————————————————
  function log(type, msg, data) {
    if (!els.eventLog) return;
    const wrap = document.createElement('div');
    wrap.className = 'log-row log-' + type;
    const stamp = '<span class="log-stamp">' + nowStamp() + '</span>';
    const tag = '<span class="log-tag log-tag-' + type + '">[' + type + ']</span>';
    wrap.innerHTML = stamp + tag + '<span class="log-msg"></span>';
    wrap.querySelector('.log-msg').textContent = msg;
    if (data) {
      const detail = document.createElement('div');
      detail.className = 'log-detail';
      detail.textContent = data;
      wrap.appendChild(detail);
    }
    els.eventLog.appendChild(wrap);
    els.eventLog.scrollTop = els.eventLog.scrollHeight;
    while (els.eventLog.children.length > 200) els.eventLog.firstChild.remove();
  }

  // ——— Sergi ekrani kanali ——————————————————————————
  function initChannel() {
    try {
      bc = new BroadcastChannel('aibody');
      bc.onmessage = (e) => {
        if (e.data && e.data.type === 'display_ready') {
          lastDisplayPing = Date.now();
          if (els.connDot && !els.connDot.classList.contains('ok')) {
            els.connDot.classList.add('ok');
            els.connText.textContent = 'SERGI EKRANI BAGLI';
            log('sys', 'sergi ekrani bagli');
          }
        }
      };
      bc.postMessage({ type: 'ping' });
      log('sys', 'kanal acildi (aibody)');
    } catch (e) {
      log('sys', 'BroadcastChannel desteklenmiyor');
    }
    // her 2 sn'de ping at; 6 sn cevapsiz kalirsa kopuk goster
    setInterval(() => {
      if (!bc) return;
      bc.postMessage({ type: 'ping' });
      if (Date.now() - lastDisplayPing > 6000 && els.connDot && els.connDot.classList.contains('ok')) {
        els.connDot.classList.remove('ok');
        els.connText.textContent = 'SERGI EKRANI ARANIYOR';
        log('sys', 'sergi ekrani kopuk');
      }
    }, 2000);
  }
  function sendToDisplay(payload) {
    if (bc) bc.postMessage(payload);
  }

  // ——— Jest tetikle (kontrol panelinde onizleme + sergiye yolla) ——
  // Varsayilan duration: Infinity — jest, yeni bir jest gelene kadar oynar.
  function triggerGesture(gestureId, opts = {}) {
    const g = gestureMap.get(gestureId);
    if (!g) {
      log('sys', 'bilinmeyen jest: ' + gestureId);
      return;
    }
    const primary = primaryFor(g);
    const secondary = secondaryFor(g);
    const speed = (opts.speed != null) ? opts.speed : speedFor(g);
    const intensity = (opts.intensity != null) ? opts.intensity
                    : (g.animasyon.yogunluk_varsayilan != null ? g.animasyon.yogunluk_varsayilan : 0.85);
    const duration = (opts.duration != null) ? opts.duration : Number.POSITIVE_INFINITY;
    const isEmoji = (g.gorsel_tipi === 'emoji');

    if (panel) {
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
        primary, secondary,
        speed: 0.6, intensity: 0.7,
        gestureId: null, isEmoji: false,
      });
    }

    if (els.activeGesture) {
      const rgb = 'rgb(' + primary.join(',') + ')';
      els.activeGesture.innerHTML =
        '<span class="dot" style="background:' + rgb + '; box-shadow: 0 0 12px ' + rgb + '"></span>' + humanName(g.id);
    }
    if (els.lastGesture) els.lastGesture.textContent = g.id;
    if (els.lastIntensity) els.lastIntensity.textContent = intensity.toFixed(2);
    if (els.lastDuration) {
      els.lastDuration.textContent = isFinite(duration) ? (duration / 1000).toFixed(1) + ' sn' : 'süresiz';
    }
  }

  // ——— Mod (emoji/desen) ————————————————————————————————
  function applyMode(mode, broadcast) {
    currentMode = (mode === 'emoji') ? 'emoji' : 'desen';
    if (panel) panel.setMode(currentMode);
    if (els.modeToggle) {
      els.modeToggle.textContent = 'GÖRSEL: ' + (currentMode === 'emoji' ? 'EMOJI' : 'DESEN');
      els.modeToggle.classList.toggle('emoji', currentMode === 'emoji');
    }
    try { localStorage.setItem('aibody.mode', currentMode); } catch (_) {}
    if (broadcast) {
      sendToDisplay({ type: 'set_mode', mode: currentMode });
      log('sys', 'görsel modu: ' + currentMode);
    }
  }
  function loadStoredMode() {
    try { return localStorage.getItem('aibody.mode') || 'desen'; } catch (_) { return 'desen'; }
  }
  function toggleMode() {
    applyMode(currentMode === 'emoji' ? 'desen' : 'emoji', true);
  }

  // ——— Mikrofon (bas-bırak) ————————————————————————————
  function setMicStatus(text, cls) {
    if (!els.micStatus) return;
    els.micStatus.textContent = text;
    els.micStatus.classList.remove('recording', 'busy', 'error', 'ok');
    if (cls) els.micStatus.classList.add(cls);
  }

  async function pollWhisperReady() {
    try {
      const r = await fetch('/api/transcribe/status');
      const d = await r.json();
      if (d.ready) {
        whisperReady = true;
        if (micEnabled) {
          setMicStatus('mikrofon hazır — basılı tut, konuş', 'ok');
        } else {
          setMicStatus('mikrofon erisimi yok', 'error');
        }
        log('sys', 'whisper modeli hazır (' + d.model + ')');
        return true;
      }
      if (d.status === 'hata') {
        setMicStatus('model hatası: ' + (d.detail || '').slice(0, 60), 'error');
        if (els.micBtn) els.micBtn.disabled = true;
        return true; // poll'u kes
      }
      setMicStatus('model yükleniyor...', 'busy');
      return false;
    } catch (e) {
      setMicStatus('whisper durumu alınamadı', 'error');
      return false;
    }
  }

  async function initMic() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia
        || typeof MediaRecorder === 'undefined') {
      setMicStatus('tarayıcı mikrofon API desteklemiyor', 'error');
      if (els.micBtn) els.micBtn.disabled = true;
      return;
    }
    if (els.micBtn) els.micBtn.disabled = true;
    setMicStatus('whisper modeli yükleniyor...', 'busy');

    // Whisper hazir olana kadar yokla (her 2 sn)
    const tick = async () => {
      const done = await pollWhisperReady();
      if (!done) setTimeout(tick, 2000);
    };
    tick();

    // Mikrofon izni butona ilk basısta istenecek (kullanıcı jestiyle).
    // Burada sadece dinleyicileri kur.
    if (!els.micBtn) return;
    els.micBtn.addEventListener('pointerdown', onMicDown);
    els.micBtn.addEventListener('pointerup', onMicUp);
    els.micBtn.addEventListener('pointerleave', onMicUp);
    els.micBtn.addEventListener('pointercancel', onMicUp);
    // Sağ tık veya context menu kaydı bozmasın
    els.micBtn.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  async function ensureMicStream() {
    if (micStream && micStream.active) return micStream;
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      micEnabled = true;
      return micStream;
    } catch (e) {
      micEnabled = false;
      setMicStatus('mikrofon reddedildi / yok', 'error');
      log('sys', 'mikrofon erisimi alınamadı: ' + e.name);
      if (els.micBtn) els.micBtn.disabled = true;
      return null;
    }
  }

  async function onMicDown(e) {
    e.preventDefault();
    if (!whisperReady) {
      setMicStatus('model hazır değil', 'busy');
      return;
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') return;
    const stream = await ensureMicStream();
    if (!stream) return;

    // Tarayıcı destekli en iyi opus mime tipini seç
    let mime = '';
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'];
    for (const m of candidates) {
      if (MediaRecorder.isTypeSupported(m)) { mime = m; break; }
    }
    try {
      mediaRecorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
    } catch (err) {
      setMicStatus('kayıt başlatılamadı', 'error');
      log('sys', 'MediaRecorder hata: ' + err.message);
      return;
    }
    recChunks = [];
    mediaRecorder.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) recChunks.push(ev.data);
    };
    mediaRecorder.onstop = onRecStop;
    mediaRecorder.start();
    recStartedAt = performance.now();
    setMicStatus('dinliyorum... (bırakınca durur, max ' + (MAX_RECORD_MS / 1000) + ' sn)', 'recording');
    if (els.micBtn) els.micBtn.classList.add('recording');
    // Sergi koruma: kayit MAX_RECORD_MS uzerine cikmasin (uzun ses Whisper'i kilitler)
    if (recAutoStopTimer) clearTimeout(recAutoStopTimer);
    recAutoStopTimer = setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        log('sys', 'kayit ' + (MAX_RECORD_MS / 1000) + ' sn sinirinda otomatik durduruldu');
        try { mediaRecorder.stop(); } catch (_) {}
        if (els.micBtn) els.micBtn.classList.remove('recording');
      }
    }, MAX_RECORD_MS);
  }

  function onMicUp(e) {
    if (!mediaRecorder || mediaRecorder.state !== 'recording') return;
    e && e.preventDefault && e.preventDefault();
    if (recAutoStopTimer) { clearTimeout(recAutoStopTimer); recAutoStopTimer = null; }
    try { mediaRecorder.stop(); } catch (_) {}
    if (els.micBtn) els.micBtn.classList.remove('recording');
  }

  async function onRecStop() {
    const dur = (performance.now() - recStartedAt) / 1000;
    if (recChunks.length === 0 || dur < 0.3) {
      setMicStatus('çok kısa — tekrar dene', 'error');
      return;
    }
    const mime = (mediaRecorder && mediaRecorder.mimeType) || 'audio/webm';
    const blob = new Blob(recChunks, { type: mime });
    setMicStatus('çevriliyor... (' + dur.toFixed(1) + ' sn)', 'busy');
    const fd = new FormData();
    fd.append('audio', blob, 'rec.webm');
    try {
      const r = await fetch('/api/transcribe', { method: 'POST', body: fd });
      const data = await r.json();
      if (data.error) {
        setMicStatus('hata: ' + data.error, 'error');
        log('sys', 'transkripsiyon hatasi: ' + data.error);
        return;
      }
      const txt = (data.text || '').trim();
      if (!txt) {
        setMicStatus('anlaşılmadı — tekrar dene', 'error');
        return;
      }
      // Mevcut metnin sonuna ekle (varsa) veya kutuyu doldur — MAX_CHARS sin
      if (els.prompt) {
        const cur = (els.prompt.value || '').trim();
        let combined = cur ? (cur + ' ' + txt) : txt;
        if (combined.length > MAX_CHARS) {
          combined = combined.slice(0, MAX_CHARS);
        }
        els.prompt.value = combined;
        els.prompt.focus();
        updateCharCount();
      }
      const langProb = data.meta && data.meta.language_prob;
      const truncNote = data.truncated ? ' (kırpıldı)' : '';
      setMicStatus(
        'çevrildi' + truncNote + ' (' + (langProb ? Math.round(langProb * 100) + '%) tr' : 'tr') + ' — enter ile gönder',
        data.truncated ? 'busy' : 'ok'
      );
      log('sys', 'STT' + truncNote + ': ' + txt);
    } catch (e) {
      setMicStatus('ag hatasi: ' + e.message, 'error');
    }
  }

  async function loadEmojiManifest() {
    try {
      const r = await fetch('/api/emoji_manifest');
      const data = await r.json();
      if (panel) panel.setEmojiManifest(data.frames || {}, data.fps || 12);
    } catch (e) {
      log('sys', 'emoji manifest yuklenemedi: ' + e.message);
    }
  }

  // ——— Karakter sayacı ————————————————————————————————
  function updateCharCount() {
    if (!els.charCount || !els.prompt) return;
    const n = (els.prompt.value || '').length;
    els.charCount.textContent = n + ' / ' + MAX_CHARS;
    els.charCount.classList.toggle('warn', n > MAX_CHARS * 0.8 && n < MAX_CHARS);
    els.charCount.classList.toggle('full', n >= MAX_CHARS);
  }

  async function loadServerConfig() {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      if (d.max_user_input_chars) {
        MAX_CHARS = d.max_user_input_chars;
        if (els.prompt) els.prompt.maxLength = MAX_CHARS;
      }
      if (d.max_record_seconds) MAX_RECORD_MS = d.max_record_seconds * 1000;
      updateCharCount();
    } catch (_) { /* varsayilanlar kalir */ }
  }

  // ——— Gercek backend cagirisi ——————————————————————
  async function handleSend() {
    const text = (els.prompt.value || '').trim();
    if (!text) return;
    if (text.length > MAX_CHARS) {
      log('sys', 'iptal: prompt ' + text.length + ' / ' + MAX_CHARS + ' karakter sınırını aşıyor');
      return;
    }
    log('user', '> ' + text);
    els.prompt.value = '';
    updateCharCount();
    els.sendBtn.disabled = true;
    if (els.statThink) els.statThink.textContent = 'dusunuyor...';

    // sergiye soruyu yansit (typewriter)
    sendToDisplay({ type: 'user_text', text });

    log('llm', 'prompt baslatildi', 'model: ' + (els.activeModel.textContent || '-'));

    try {
      const res = await fetch('/api/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (data.error) {
        let msg = data.error;
        if (data.error === 'too_long') {
          msg = 'metin çok uzun (' + data.len + ' > ' + data.max + ' karakter)';
        }
        log('sys', 'HATA: ' + msg);
        if (els.statThink) els.statThink.textContent = '— sn';
        if (els.aiResponse) {
          els.aiResponse.textContent = 'Hata: ' + msg;
          els.aiResponse.classList.remove('empty');
        }
        return;
      }

      const meta = data.meta || {};
      const wall = meta.wall_s || 0;
      const promptTok = meta.prompt_tokens || 0;
      const evalTok = meta.eval_tokens || 0;
      const rate = meta.tok_per_s || 0;
      const loadMs = meta.load_ms || 0;

      log('llm', 'prompt ' + wall.toFixed(2) + 's  yanit ' + evalTok + 'tok @ ' + rate.toFixed(1) + ' tok/s');
      log('jest', data.jest_id + ' yog=' + (data.yogunluk || 0).toFixed(2));
      if (meta.mirror_override) log('sys', 'mirror override uygulandi');
      if (meta.sanitized) log('sys', 'yanit metni sanitize edildi');
      if (meta.fallback_used) log('sys', 'fallback jest kullanildi');
      log('yanit', "'" + (data.yanit || '') + "'");

      if (els.statThink) els.statThink.textContent = wall.toFixed(2) + ' sn';
      if (els.statTokens) els.statTokens.textContent = promptTok + ' → ' + evalTok;
      if (els.statRate) els.statRate.textContent = rate.toFixed(1) + ' tok/s';
      if (els.statLoad) els.statLoad.textContent = (loadMs / 1000).toFixed(1) + ' sn';

      // sergiye yaniti yolla
      sendToDisplay({
        type: 'ai_reply',
        jest_id: data.jest_id,
        yanit: data.yanit || '',
        yogunluk: data.yogunluk,
      });
      // kontrol panelinde onizle
      triggerGesture(data.jest_id, { intensity: data.yogunluk });
      if (els.aiResponse) {
        els.aiResponse.textContent = data.yanit || '';
        els.aiResponse.classList.remove('empty');
      }
    } catch (err) {
      log('sys', 'ag hatasi: ' + err.message);
      if (els.statThink) els.statThink.textContent = '— sn';
    } finally {
      els.sendBtn.disabled = false;
      els.prompt.focus();
    }
  }

  function handleStop() {
    sendToDisplay({ type: 'stop' });
    const idle = gestureMap.has('huzur') ? 'huzur'
              : (gestureMap.has('meditatif') ? 'meditatif' : null);
    if (idle) triggerGesture(idle, { duration: 99999999 });
    log('sys', 'durduruldu');
  }

  // ——— Hizli jest grid ——————————————————————————————
  function buildGestureGrid() {
    if (!els.gestureGrid) return;
    els.gestureGrid.innerHTML = '';
    gestures.forEach((g) => {
      const btn = document.createElement('button');
      btn.className = 'gesture-chip';
      const rgb = 'rgb(' + primaryFor(g).join(',') + ')';
      btn.innerHTML =
        '<span class="chip-swatch" style="background:' + rgb +
        '; box-shadow: 0 0 6px ' + rgb + '"></span>' +
        '<span class="chip-name">' + humanName(g.id) + '</span>';
      btn.title = g.id + ' (' + g.animasyon.desen + ')';
      btn.addEventListener('click', () => {
        triggerGesture(g.id);
        sendToDisplay({ type: 'manual_gesture', jest_id: g.id });
        log('sys', 'manuel jest: ' + g.id);
      });
      els.gestureGrid.appendChild(btn);
    });
  }

  // ——— Gercek model yonetimi ————————————————————————
  async function loadGestures() {
    try {
      const r = await fetch('/api/gestures');
      const data = await r.json();
      gestures = data.jestler || [];
      gestureMap = new Map(gestures.map((g) => [g.id, g]));
    } catch (e) {
      log('sys', 'jest listesi yuklenemedi: ' + e.message);
    }
  }

  async function refreshModels() {
    try {
      const r = await fetch('/api/models');
      const data = await r.json();
      const models = data.models || [];
      if (els.modelSelect) {
        els.modelSelect.innerHTML = '';
        models.forEach((m) => {
          const opt = document.createElement('option');
          opt.value = m.name;
          opt.textContent = m.name + '  (' + m.size_gb.toFixed(1) + ' GB)';
          els.modelSelect.appendChild(opt);
        });
        // aktif modeli secili goster
        if (data.active) {
          for (let i = 0; i < els.modelSelect.options.length; i++) {
            if (els.modelSelect.options[i].value === data.active) {
              els.modelSelect.selectedIndex = i;
              break;
            }
          }
        }
      }
      if (data.active && els.activeModel) els.activeModel.textContent = data.active;
      log('sys', 'model listesi yenilendi (' + models.length + ')');
    } catch (e) {
      log('sys', 'model listesi alinamadi: ' + e.message);
    }
  }

  async function activateModel() {
    if (!els.modelSelect || !els.modelSelect.value) return;
    const name = els.modelSelect.value;
    try {
      const r = await fetch('/api/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      const data = await r.json();
      if (data.error) {
        if (els.activeNote) els.activeNote.textContent = 'hata: ' + data.error;
        log('sys', 'model degisim HATA: ' + data.error);
        return;
      }
      if (els.activeModel) els.activeModel.textContent = name;
      if (els.activeNote) els.activeNote.textContent = data.changed ? 'aktif edildi' : 'zaten aktif';
      log('sys', 'aktif model: ' + name);
    } catch (e) {
      if (els.activeNote) els.activeNote.textContent = 'ag hatasi';
      log('sys', 'model degisim ag hatasi: ' + e.message);
    }
  }

  async function downloadModel() {
    const name = (els.newModelInput.value || '').trim();
    if (!name) return;
    log('sys', 'indirme baslatildi: ' + name);
    if (els.activeNote) els.activeNote.textContent = 'indiriliyor...';
    try {
      const r = await fetch('/api/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      const data = await r.json();
      if (data.error) {
        log('sys', 'indirme HATA: ' + data.error);
        if (els.activeNote) els.activeNote.textContent = 'indirme hatasi';
        return;
      }
      log('sys', 'indirme tamam: ' + name);
      if (els.activeNote) els.activeNote.textContent = 'indirildi';
      els.newModelInput.value = '';
      refreshModels();
    } catch (e) {
      log('sys', 'indirme ag hatasi: ' + e.message);
      if (els.activeNote) els.activeNote.textContent = 'ag hatasi';
    }
  }

  // ——— Init ————————————————————————————————————————
  async function init() {
    if (els.canvas && typeof LEDPanel !== 'undefined') {
      panel = new LEDPanel(els.canvas, { size: els.canvas.width });
    }
    await loadGestures();
    await loadEmojiManifest();
    await loadServerConfig();
    applyMode(loadStoredMode(), false);
    buildGestureGrid();
    initChannel();
    refreshModels();

    if (els.prompt) {
      els.prompt.addEventListener('input', updateCharCount);
      updateCharCount();
    }

    if (els.sendBtn) els.sendBtn.addEventListener('click', handleSend);
    if (els.stopBtn) els.stopBtn.addEventListener('click', handleStop);
    if (els.prompt) els.prompt.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });
    if (els.activateBtn) els.activateBtn.addEventListener('click', activateModel);
    if (els.refreshBtn) els.refreshBtn.addEventListener('click', refreshModels);
    if (els.downloadBtn) els.downloadBtn.addEventListener('click', downloadModel);
    if (els.modeToggle) els.modeToggle.addEventListener('click', toggleMode);

    initMic();

    // M tusu: mod toggle (input dışındayken)
    document.addEventListener('keydown', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.key === 'm' || e.key === 'M') toggleMode();
    });

    // Sergi ekranı bağlandığında mevcut modu ona da gönder (geç açılırsa)
    setTimeout(() => sendToDisplay({ type: 'set_mode', mode: currentMode }), 800);

    log('sys', 'kontrol paneli hazir');
    log('sys', 'enter ile gonder · m ile mod degis');

    if (els.statThink) els.statThink.textContent = '— sn';
    if (els.statLoad) els.statLoad.textContent = '— sn';
    if (els.statTokens) els.statTokens.textContent = '0 → 0';
    if (els.statRate) els.statRate.textContent = '— tok/s';
  }

  document.addEventListener('DOMContentLoaded', init);
})();
