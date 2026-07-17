"""AI Body — yeni web arayuzu icin Flask HTTP koprusu.

- Statik: /web/ altindan AI_Body_v2.html ve Kontrol_Paneli.html sunar.
- /api/send  : kullanici metnini LLMBridge ile Ollama'ya gonderir, jest sonucunu doner.
- /api/gestures : ai/gestures.json icerigi.
- /api/models : Ollama lokal model listesi.
- /api/model  : aktif modeli degistir.
- /api/pull   : yeni model indir (basit, blocking).
- /api/health : Ollama canli mi.

Calistirma: python orchestrator/web_server.py (veya run_web.py)
Cekirdek dosyalar (llm_bridge.py, gestures.json, system_prompt.txt) DEGISTIRILMEZ.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from game_engine import GameEngine
from llm_bridge import LLMBridge
from session_logger import SessionLogger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("web_server")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
ROOT_DIR = BASE_DIR.parent
WEB_DIR = ROOT_DIR / "web"
ASSETS_DIR = ROOT_DIR / "assets"
EMOJI_BASE_DIR = ASSETS_DIR / "emojis"
EMOJI_FPS = 12  # gesture_engine.EMOJI_FPS ile esit kalmali

# Whisper (ses-metin) ayarlari — KARAR 1: small, CPU, int8, tr.
# CPU'da kalir cunku 4GB VRAM zaten aktif LLM (config.ollama_model,
# orn. qwen3:4b-instruct-2507) ile dolu.
WHISPER_MODEL_SIZE = "small"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_LANGUAGE = "tr"

# TTS varsayilanlari — QW-5: tek kaynak. Birincil motor edge oldugundan varsayilan
# ses de edge sesi olmali (eski "tr_TR-dfki-medium" fallback'i Piper ses adiydi).
DEFAULT_TTS_VOICE = "tr-TR-EmelNeural"

# Acilis edge erisilebilirlik probu: motor yuklendikten sonra BIR KEZ kucuk bir
# sentez denenir; basarisizsa motor bastan Piper'a sabitlenir (FallbackEngine'in
# her istekte edge deneyip timeout beklemesi yerine).
EDGE_PROBE_TEXT = "merhaba"
EDGE_PROBE_TIMEOUT_S = 5.0

# /api/session/new sabit selamlamasi — on-isitma ayni metin/jest/yogunluk kullanir
# ki onbellek anahtarlari birebir isabet etsin.
SESSION_GREETING_TEXT = 'Merhaba. Sohbet edebiliriz. Oyun için "oyun oynayalım" de.'
SESSION_GREETING_JEST = "selamlama"
SESSION_GREETING_YOGUNLUK = 0.8

# ——— TEST MODU (sergi test gunu) ———————————————————————————————
# 'g' tusu / POST /api/test_mode ile acilip kapanir; config.json'da kalicidir.
# Acikken: menude yalnizca TEST_OYUNLAR, sohbet (/api/send LLM yolu) kapali,
# "merhaba" selamlamasi dogrudan oyun menusunu acar.
TEST_OYUNLAR = ("eszit", "atasozu")
TEST_GREETING_LEAD = "Merhaba, hoş geldin!"
TEST_SOHBET_KAPALI_TEXT = "Bugün oyun günü! Hangisini oynayalım — dokun ya da söyle."


def _test_greeting_yanit(menu_payload: dict) -> str:
    """Test modunda 'merhaba' yaniti: selamlama + oyun secimi (menu butonlarindan).
    Tek kaynak: /api/session/new, on-isitma ve gen_batch ayni metni uretir."""
    labels = " · ".join(b["label"] for b in menu_payload.get("buttons", []))
    return f"{TEST_GREETING_LEAD} Hangisini oynayalım? Dokun ya da söyle: {labels}"


def _test_mode_texts() -> list:
    """Test modu sabit replikleri (on-isitma icin) — gecici sinirli motorla birebir."""
    from game_engine import GameEngine
    g = GameEngine(bridge=None)
    g.izinli_oyunlar = TEST_OYUNLAR
    menu = g._menu_payload()
    return [_test_greeting_yanit(menu), menu["yanit"],
            g._menu_payload(reprompt=True)["yanit"], TEST_SOHBET_KAPALI_TEXT]

# game_engine icindeki inline kural/hazirlik metinlerinin birebir kopyalari
# (game_engine'e dokunmadan). Metin orada degisirse on-isitma sadece iska gecer — hata olmaz.
KELIME_KURAL_TEXT = ("Kelime türetme oynayalım! Ben bir kelime söylerim. Sen de son "
                     "harfiyle başlayan yeni bir kelime söyle. Sırayla devam ederiz. "
                     "Aynı kelimeyi iki kez kullanamayız. Her tur için 20 saniyen var. "
                     "Hazırsan 'başla' de!")
HAZIR_BEKLE_TEXT = "Hazır olunca 'başla' de ya da butona dokun :)"


def load_config() -> dict:
    # utf-8-sig: elle duzenlenen config Notepad/PowerShell'den BOM'lu kaydedilse de okunur.
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


class WhisperState:
    """Lazy yuklenmis Whisper modeli + durum. Tek instance, tum istekler paylasir."""

    def __init__(self) -> None:
        self.model = None        # faster_whisper.WhisperModel | None
        self.status = "yok"      # "yok" | "yukleniyor" | "hazir" | "hata"
        self.error = ""
        self._lock = threading.Lock()  # transcribe re-entrancy guard

    def is_ready(self) -> bool:
        return self.model is not None and self.status == "hazir"


def _load_whisper_async(state: WhisperState, model_size: str) -> None:
    """Modeli arka planda yukler — HTTP yanit vermeyi gec birakmaz."""
    state.status = "yukleniyor"
    try:
        from faster_whisper import WhisperModel
        log.info("Whisper yukleniyor: %s (%s, %s)", model_size, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
        state.model = WhisperModel(
            model_size,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        state.status = "hazir"
        log.info("Whisper hazir.")
    except Exception as e:  # noqa: BLE001 — model yuklenmedi ama sergi calismaya devam etsin
        state.status = "hata"
        state.error = str(e)
        log.warning("Whisper yuklenemedi: %s", e)


class TTSState:
    """Tembel yuklenmis TTS motoru + durum. Whisper ile ayni desen."""

    def __init__(self) -> None:
        self.engine = None       # tts.engine_base.TTSEngine | None
        self.status = "yok"      # "yok" | "yukleniyor" | "hazir" | "hata"
        self.error = ""
        self._lock = threading.Lock()  # tek model -> seri sentez

    def is_ready(self) -> bool:
        return self.engine is not None and self.status == "hazir"


def _probe_edge_or_pin_fallback(engine):
    """Edge'in erisilebilirligini BIR KEZ dener (kucuk sentez, sinirli sure).

    Basarili -> engine aynen doner (mevcut davranis). Basarisiz/timeout -> yedek
    Piper motoru doner; boylece FallbackEngine her istekte edge'i deneyip timeout
    beklemez. Yalnizca FallbackEngine (edge+piper) icin anlamlidir.
    """
    from tts.engine_base import FallbackEngine
    if not isinstance(engine, FallbackEngine):
        return engine
    result: dict = {}

    def _try():
        try:
            result["audio"] = engine.primary.synthesize(EDGE_PROBE_TEXT, None, 0.7)
        except Exception as e:  # noqa: BLE001 — ag hatasi = prob basarisiz
            result["error"] = e

    t = threading.Thread(target=_try, daemon=True)
    t.start()
    t.join(EDGE_PROBE_TIMEOUT_S)
    if t.is_alive():
        log.warning("TTS edge probu %.0fs icinde donmedi — motor Piper'a sabitlendi.",
                    EDGE_PROBE_TIMEOUT_S)
        return engine.fallback
    if result.get("error") is not None or not result.get("audio"):
        log.warning("TTS edge probu basarisiz (%s) — motor Piper'a sabitlendi.",
                    result.get("error", "bos ses"))
        return engine.fallback
    log.info("TTS edge probu OK (%d bayt).", len(result["audio"]))
    return engine


# Cumle sinirlari: .!?… + bosluk. web/app.js splitSentences ile BIREBIR ayni
# mantik olmali — on-isitma anahtarlari frontend parcalariyla eslessin.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def _split_sentences_tr(text: str, min_len: int = 10) -> list:
    """Metni cumle parcalarina boler; kisa parca (<min_len) sonrakiyle birlesir,
    artan kisa kuyruk son parcaya eklenir. Tek cumlede [metin] doner."""
    parts = [p.strip() for p in _SENT_SPLIT_RE.split((text or "").strip()) if p.strip()]
    out = []
    buf = ""
    for p in parts:
        buf = (buf + " " + p) if buf else p
        if len(buf) >= min_len:
            out.append(buf)
            buf = ""
    if buf:
        if out:
            out[-1] += " " + buf
        else:
            out.append(buf)
    return out


def _cache_jest(engine, jest_id, yogunluk):
    """Onbellek anahtarindaki jest bileseni. ElevenLabs motoru KABA duygu imzasi
    kullanir (benzer jest'ler tek anahtar -> rastgele-jest pre-gen ile uyumlu).
    Diger motorlar (edge/piper) jest_id'yi oldugu gibi kullanir (mevcut davranis)."""
    sig_fn = getattr(engine, "cache_signature", None)
    if sig_fn is None and hasattr(engine, "primary"):   # FallbackEngine -> primary'yi ac
        sig_fn = getattr(engine.primary, "cache_signature", None)
    return sig_fn(jest_id, yogunluk) if sig_fn else jest_id


def _tts_synth_cached(state: "TTSState", cache, config: dict, text: str,
                      jest_id=None, yogunluk: float = 0.7):
    """Onbellek anahtari turetimi + sentez — api_speak ve on-isitma AYNI yolu
    kullanir (varsayilanlar api_speak ile ayni: jest_id=None, yogunluk=0.7)."""
    voice = config.get("tts_voice", DEFAULT_TTS_VOICE)
    key = cache.make_key(text, _cache_jest(state.engine, jest_id, yogunluk), yogunluk, voice)
    audio = cache.get(key)
    if audio is None:
        with state._lock:  # tek model -> seri sentez
            audio = state.engine.synthesize(text, jest_id, yogunluk)
        if audio:
            cache.put(key, audio)
    return audio


def _warm_texts() -> list:
    """On-isitilacak sabit replikler: (metin, jest_id, yogunluk) uclusu.

    jest/yogunluk degerleri metnin GERCEKTE seslendirildigi payload'larla birebir
    ayni tutuldu (anahtar isabeti icin). Bilinmeyenlerde api_speak varsayilanlari.
    """
    items = []
    # 1) Guard guvenli-yanit sablonlari (llm_bridge) — jest = sablon anahtari.
    try:
        from llm_bridge import _SAFE_RESPONSE_TEMPLATES
        for jest_key, metin in _SAFE_RESPONSE_TEMPLATES.items():
            jest = None if jest_key == "sicaklik_default" else jest_key
            items.append((metin, jest, 0.7))  # yogunluk: api_speak varsayilani
    except Exception as e:  # noqa: BLE001 — isitma eksik kalsin, sergi calissin
        log.warning("On-isitma: guvenli sablonlar alinamadi: %s", e)
    # 2) Sergi selamlamasi (/api/session/new sabiti).
    items.append((SESSION_GREETING_TEXT, SESSION_GREETING_JEST, SESSION_GREETING_YOGUNLUK))
    # 2b) Test modu replikleri ('g' ile sinirli menu) — acildiginda beklenmesin.
    try:
        for metin in _test_mode_texts():
            items.append((metin, SESSION_GREETING_JEST, SESSION_GREETING_YOGUNLUK))
    except Exception as e:  # noqa: BLE001
        log.warning("On-isitma: test modu replikleri alinamadi: %s", e)
    # 3) Oyun kural/hazirlik replikleri (game_engine sabitleri — en sik kullanilanlar).
    try:
        from game_engine import _JEST as _GJ, _TXT as _GT
        items.append((_GT["exit"][0], _GJ["exit"], 0.6))
        for jest in _GJ.get("kel_intro", []):                     # random.choice ikisini de secebilir
            items.append((KELIME_KURAL_TEXT, jest, 0.8))          # game.start() = dogrudan kelime kurali
        items.append((HAZIR_BEKLE_TEXT, "bekle", 0.6))
    except Exception as e:  # noqa: BLE001
        log.warning("On-isitma: oyun replikleri alinamadi: %s", e)
    return items


def _warm_tts_cache(state: "TTSState", cache, config: dict) -> None:
    """Sik sabit metinleri cumle parcalari halinde onbellege isit.

    Frontend (app.js speak) metni cumlelere bolup POST ettigi icin isitma da ayni
    bolme ile parca parca yapilir. 3 hatadan sonra birakilir (motor coktu demektir).
    """
    if cache is None or not getattr(cache, "enabled", False) or not state.is_ready():
        return
    hazir = 0
    hata = 0
    for metin, jest, yog in _warm_texts():
        for parca in _split_sentences_tr(metin):
            if hata >= 3:
                log.warning("TTS on-isitma birakildi (ust uste hata; %d parca isindi).", hazir)
                return
            try:
                audio = _tts_synth_cached(state, cache, config, parca, jest, yog)
            except Exception as e:  # noqa: BLE001
                hata += 1
                log.warning("TTS on-isitma parca hatasi (%r): %s", parca[:30], e)
                continue
            if audio:
                hazir += 1
            else:
                hata += 1
    log.info("TTS on-isitma tamam: %d parca onbellekte.", hazir)


def _load_tts_async(state: "TTSState", config: dict, cache=None) -> None:
    """TTS motorunu arka planda yukler — HTTP yanitlarini geciktirmez.
    use_cuda=False: 4GB VRAM aktif LLM (Ollama) ile dolu; TTS CPU'da kalir
    (Piper RTF ~0.05, gercek-zamandan cok hizli).
    Yukleme sonrasi (ayni thread): edge erisilebilirlik probu + onbellek on-isitmasi."""
    state.status = "yukleniyor"
    try:
        def _make_piper(voice_key: str):
            from tts.engine_piper import PiperEngine
            return PiperEngine(
                voice=config.get(voice_key, "tr_TR-dfki-medium"),
                use_cuda=False,
                pitch_enabled=bool(config.get("tts_pitch_enabled", True)),
            )

        engine_name = config.get("tts_engine", "piper")
        if engine_name == "edge":
            # Birincil: edge-tts (cevrimici). Yedek: Piper (cevrimdisi) — internet
            # kesilirse sergi susmasin diye FallbackEngine otomatik gecer.
            from tts.engine_edge import EdgeEngine
            from tts.engine_base import FallbackEngine
            primary = EdgeEngine(voice=config.get("tts_voice", DEFAULT_TTS_VOICE))
            if config.get("tts_fallback_enabled", True):
                engine = FallbackEngine(primary, _make_piper("tts_fallback_voice"))
                # Acilis probu: edge erisilemiyorsa motor BASTAN Piper'a sabitlenir.
                engine = _probe_edge_or_pin_fallback(engine)
                state.engine = engine
                if isinstance(engine, FallbackEngine):
                    log.info("TTS hazir (edge=%s + cevrimdisi yedek piper=%s).",
                             primary.voice_name, engine.fallback.voice_name)
                else:
                    log.info("TTS hazir (Piper, %s — edge probu basarisiz, motor sabitlendi).",
                             engine.voice_name)
            else:
                state.engine = primary
                log.info("TTS hazir (edge=%s, yedek yok).", primary.voice_name)
        elif engine_name == "elevenlabs":
            # Birincil: ElevenLabs (bulut, KOTALI — her sentez kredi harcar).
            # Yedek zinciri: edge (ucretsiz online) -> Piper (offline). Kredi tavani
            # dolar ya da anahtar/ag yoksa ElevenLabs b"" doner; FallbackEngine
            # otomatik ucretsiz yedege gecer (sergi susmaz, butce asilmaz).
            from tts.engine_elevenlabs import ElevenLabsEngine
            from tts.engine_edge import EdgeEngine
            from tts.engine_base import FallbackEngine
            primary = ElevenLabsEngine(
                voice=config.get("tts_voice", ""),
                api_key=(config.get("tts_elevenlabs_api_key")
                         or os.environ.get("ELEVENLABS_API_KEY", "")),
                model=config.get("tts_elevenlabs_model", "eleven_flash_v2_5"),
                language=config.get("tts_elevenlabs_language", "tr"),
                monthly_cap=config.get("tts_elevenlabs_monthly_credit_cap", 32000),
                usage_path=BASE_DIR / "tts" / "elevenlabs_usage.json",
            )
            if config.get("tts_fallback_enabled", True):
                # 3 katman: elevenlabs -> edge -> piper.
                offline = FallbackEngine(
                    EdgeEngine(voice=config.get("tts_elevenlabs_edge_fallback_voice",
                                                DEFAULT_TTS_VOICE)),
                    _make_piper("tts_fallback_voice"))
                state.engine = FallbackEngine(primary, offline)
                log.info("TTS hazir (elevenlabs=%s + yedek: edge -> piper).",
                         primary.voice_name)
            else:
                state.engine = primary
                log.info("TTS hazir (elevenlabs=%s, yedek yok).", primary.voice_name)
        else:
            if engine_name != "piper":
                log.warning("Bilinmeyen tts_engine '%s' — piper'a dusuluyor.", engine_name)
            state.engine = _make_piper("tts_voice")
            log.info("TTS hazir (Piper, %s).", state.engine.voice_name)
        state.status = "hazir"
    except Exception as e:  # noqa: BLE001 — TTS yuklenemese de sergi devam etsin
        state.status = "hata"
        state.error = str(e)
        log.warning("TTS yuklenemedi: %s", e)
        return
    # On-isitma: motor hazir olduktan sonra AYNI arka plan thread'inde —
    # ilk ziyaretci selamlamayi/menu repliklerini sentez beklemeden duysun.
    try:
        _warm_tts_cache(state, cache, config)
    except Exception as e:  # noqa: BLE001 — isitma hatasi sergiyi durdurmaz
        log.warning("TTS on-isitma hatasi: %s", e)


def create_app(config: dict) -> Flask:
    app = Flask(__name__, static_folder=None)
    app_start = time.monotonic()  # /api/health uptime_s icin

    bridge = LLMBridge(config, BASE_DIR)
    game = GameEngine(bridge=bridge)  # TKM deterministik; kelime turetme (ileride) LLM kullanir
    # Test modu durumu (config.json'dan; 'g' tusu / POST /api/test_mode degistirir).
    test_mode = {"on": bool(config.get("test_mode", False))}
    if test_mode["on"]:
        game.izinli_oyunlar = TEST_OYUNLAR
    # Flask threaded=True; tek GameEngine instance'i paylasiliyor. Sure-doldu ile
    # manuel cevap/AI-turu ayni anda gelirse durum makinesi bozulmasin diye seri kilit.
    game_lock = threading.Lock()
    gestures_path = (BASE_DIR / config["gestures_path"]).resolve()
    log_path = (BASE_DIR / config.get("session_log_path", "../logs/session.log")).resolve()
    logger = SessionLogger(log_path, config["ollama_url"], bridge.model)
    logger.start()
    log.info("Oturum logu: %s", log_path)
    # Oyun baslangic/bitis ozetleri de ayni oturum loguna yazilsin (gozlem).
    game.session_logger = logger

    # Tek seferlik warmup arka planda
    if config.get("warmup_on_start", True):
        def _warm():
            ok = bridge.warmup()
            log.info("Warmup: %s", "OK" if ok else "fail")
        threading.Thread(target=_warm, daemon=True).start()

    # Whisper modeli arka planda yuklensin — HTTP istekleri bunu beklemez.
    whisper_state = WhisperState()
    whisper_size = config.get("whisper_model_size", WHISPER_MODEL_SIZE)
    if config.get("whisper_enabled", True):
        threading.Thread(
            target=_load_whisper_async,
            args=(whisper_state, whisper_size),
            daemon=True,
        ).start()

    # TTS motoru arka planda yuklensin — HTTP istekleri bunu beklemez.
    from tts.cache import WavCache
    tts_state = TTSState()
    tts_cache = WavCache(
        BASE_DIR / "tts" / "cache",
        max_files=int(config.get("tts_cache_max", 500)),
        enabled=bool(config.get("tts_cache_enabled", True)),
    )
    if config.get("tts_enabled", True):
        threading.Thread(
            target=_load_tts_async,
            args=(tts_state, config, tts_cache),
            daemon=True,
        ).start()

    @app.route("/")
    def index():
        return send_from_directory(str(WEB_DIR), "AI_Body_v2.html")

    @app.route("/control")
    @app.route("/kontrol")
    def control_panel():
        return send_from_directory(str(WEB_DIR), "Kontrol_Paneli.html")

    @app.get("/api/gestures")
    def api_gestures():
        return send_from_directory(str(gestures_path.parent), gestures_path.name)

    @app.get("/api/emoji_manifest")
    def api_emoji_manifest():
        """Her jest_id icin assets/emojis/<id>/frame_*.png sayisi."""
        manifest = {}
        if EMOJI_BASE_DIR.is_dir():
            for jest_dir in EMOJI_BASE_DIR.iterdir():
                if jest_dir.is_dir():
                    frames = sorted(jest_dir.glob("frame_*.png"))
                    if frames:
                        manifest[jest_dir.name] = len(frames)
        return jsonify({"fps": EMOJI_FPS, "frames": manifest})

    @app.get("/assets/<path:filename>")
    def static_assets(filename):
        return send_from_directory(str(ASSETS_DIR), filename)

    @app.get("/api/health")
    def api_health():
        """Watchdog/izleme icin: Ollama canli mi + TTS hazir mi + sunucu uptime."""
        return jsonify({
            "ollama": bridge.is_alive(),
            "model": bridge.model,
            "tts": tts_state.is_ready(),
            "tts_status": tts_state.status,
            "uptime_s": round(time.monotonic() - app_start, 1),
        })

    @app.get("/api/config")
    def api_config():
        """Frontend'in bilmesi gereken sergi sınırları + sesli giriş ayarları."""
        return jsonify({
            "max_user_input_chars": int(config.get("max_user_input_chars", 240)),
            "max_record_seconds": int(config.get("max_record_seconds", 30)),
            "test_mode": test_mode["on"],
            # Sergi ekranindaki surekli sesli giris (VAD) ayarlari. Sergide JS'e
            # dokunmadan config.json'dan ayarlanabilsin diye burada aciga cikarilir.
            "voice_input": {
                "enabled": bool(config.get("voice_input_enabled", True)),
                "autostart": bool(config.get("voice_input_autostart", True)),
                "silence_ms": int(config.get("voice_input_silence_ms", 1000)),
                "min_speech_ms": int(config.get("voice_input_min_speech_ms", 350)),
                "max_utterance_ms": int(config.get("voice_input_max_utterance_ms", 12000)),
                "onset_mult": float(config.get("voice_input_onset_mult", 2.2)),
                "abs_min_rms": float(config.get("voice_input_abs_min_rms", 0.012)),
                "cooldown_ms": int(config.get("voice_input_cooldown_ms", 400)),
            },
        })

    @app.get("/api/models")
    def api_models():
        return jsonify({"models": bridge.list_local_models(), "active": bridge.model})

    @app.post("/api/model")
    def api_set_model():
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"error": "model adi bos"}), 400
        changed = bridge.set_model(name)
        if changed:
            config["ollama_model"] = name
            try:
                save_config(config)
            except OSError as e:
                log.warning("config.json yazilamadi: %s", e)
            logger.model_name = name
            logger.log_event(f"Aktif model degisti: {name}")
        return jsonify({"changed": changed, "active": bridge.model})

    @app.post("/api/pull")
    def api_pull():
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"error": "model adi bos"}), 400
        last_status = {"status": "baslatildi"}

        def on_progress(data):
            last_status.update(data)

        ok = bridge.pull_model(name, on_progress)
        if not ok:
            return jsonify({"error": last_status.get("error", "indirme basarisiz"),
                            "status": last_status}), 500
        return jsonify({"ok": True, "name": name, "status": last_status})

    @app.post("/api/send")
    def api_send():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return jsonify({"error": "metin bos"}), 400
        max_chars = int(config.get("max_user_input_chars", 240))
        if len(text) > max_chars:
            # Sergi koruma: cok uzun prompt -> Ollama'yi kilitlemeyelim
            return jsonify({
                "error": "too_long",
                "max": max_chars,
                "len": len(text),
            }), 413
        if test_mode["on"]:
            # Test gunu: sohbet kapali — LLM'e gitmeden nazik oyun yonlendirmesi.
            # (Frontend zaten oyuna yonlendirir; bu backend guvencesidir.)
            logger.log_event("Test modu: sohbet istegi oyuna yonlendirildi")
            return jsonify({
                "yanit": TEST_SOHBET_KAPALI_TEXT,
                "jest_id": SESSION_GREETING_JEST,
                "yogunluk": 0.8,
                "meta": {"test_mode": True},
            })
        result = bridge.request(text)
        if result is None or "error" in result:
            err = (result or {}).get("error", "no_response")
            meta = dict((result or {}).get("meta") or {})
            logger.log_error(text, result or {"error": err})
            # Sergi dayanikliligi: 500 yerine HTTP 200 + nazik "bekle" yaniti.
            # Kiosk hata kutusu gostermez; ziyaretci dogal bir cevap duyar/gorur.
            # 'bekle' jesti gestures.json'da mevcut (donen ibre — saat).
            meta.update({"degraded": True, "error": err})
            return jsonify({
                "yanit": "Şu an düşünemiyorum, birazdan tekrar dener misin?",
                "jest_id": "bekle",
                "yogunluk": 0.4,
                "meta": meta,
            })
        logger.log_request(text, result)
        return jsonify(result)

    @app.post("/api/clear_history")
    def api_clear():
        bridge.clear_history()
        logger.log_event("Konusma gecmisi sifirlandi")
        return jsonify({"ok": True})

    @app.post("/api/session/new")
    def api_session_new():
        """Yeni ziyaretci selami: sohbet gecmisini ve oyun durumunu temizle.

        Bu akista LLM'e gidilmez; karsilama sabit kalir ki kiosk her ziyaretciye
        temiz ve hizli bir acilis yapsin.
        """
        bridge.clear_history()
        if test_mode["on"]:
            # Test gunu: "merhaba" -> selamla + dogrudan oyun secimi (sohbet yok).
            with game_lock:
                game.exit()
                menu = game.start()
            menu["yanit"] = _test_greeting_yanit(menu)
            menu["jest_id"] = SESSION_GREETING_JEST
            menu["yogunluk"] = SESSION_GREETING_YOGUNLUK
            logger.log_event("Yeni ziyaretci (test modu): selamlama + oyun menusu")
            return jsonify(menu)
        with game_lock:
            game.exit()
        logger.log_event("Yeni ziyaretci: selamlama ile temiz oturum")
        return jsonify({
            "ok": True,
            "jest_id": SESSION_GREETING_JEST,
            "yogunluk": SESSION_GREETING_YOGUNLUK,
            "yanit": SESSION_GREETING_TEXT,   # on-isitma ile ayni sabit (anahtar isabeti)
            "phase": "idle",
            "buttons": [],
        })

    # ——— Test modu (sergi test gunu: sinirli menu + sohbet kapali) ————————
    @app.get("/api/test_mode")
    def api_test_mode_get():
        return jsonify({"on": test_mode["on"], "games": list(TEST_OYUNLAR)})

    @app.post("/api/test_mode")
    def api_test_mode_set():
        """Test modunu ac/kapa. Body {"on": bool} verilirse o degere, verilmezse
        toggle. Aktif oyun sifirlanir (menude eski butonlar kalmasin)."""
        payload = request.get_json(silent=True) or {}
        on = payload.get("on")
        on = (not test_mode["on"]) if on is None else bool(on)
        test_mode["on"] = on
        with game_lock:
            game.izinli_oyunlar = TEST_OYUNLAR if on else None
            game.exit()
        config["test_mode"] = on
        # Kalicilik: diskteki config tazelenip YALNIZ bu anahtar yazilir
        # (calisma-zamani degisikliklerini diske sizdirmamak icin). Disk bozuksa
        # (JSONDecodeError=ValueError!) bellekteki kopyaya dusulur; kalicilik
        # hatasi HTTP 500 uretmez — bellek durumu zaten degisti, 200 donmeli.
        try:
            disk = load_config()
        except (OSError, ValueError) as e:
            log.warning("config.json okunamadi (%s) — bellekteki kopya yazilacak", e)
            disk = dict(config)
        disk["test_mode"] = on
        try:
            save_config(disk)
        except OSError as e:
            log.warning("config.json yazilamadi: %s", e)
        logger.log_event("Test modu " + ("ACIK (yalniz " + ", ".join(TEST_OYUNLAR) + ")"
                                         if on else "KAPALI"))
        return jsonify({"on": on, "games": list(TEST_OYUNLAR)})

    # ——— Oyun modu (Kelime Türetme; deterministik akis, AI kelimeleri temali havuzdan) ————
    @app.post("/api/game/start")
    def api_game_start():
        with game_lock:
            result = game.start()
        logger.log_event("Oyun baslatildi (kelime turetme)")
        return jsonify(result)

    @app.post("/api/game/input")
    def api_game_input():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        timeout = bool(payload.get("timeout"))
        if not text and not timeout:
            return jsonify({"error": "metin bos"}), 400
        # Sergi koruma: oyun girdileri kisa olmali
        if len(text) > 60:
            text = text[:60]
        with game_lock:
            result = game.handle(text, timeout=timeout)
        if result.get("kind") == "round":
            logger.log_event(
                f"Oyun turu: kullanici={result.get('user_move')} ai={result.get('ai_move')} "
                f"sonuc={result.get('outcome')} skor={result.get('score')} jest={result.get('jest_id')}"
            )
        elif result.get("game") == "kelime":
            logger.log_event(
                f"Kelime: kind={result.get('kind')} kullanici_kelime={result.get('user_word')} "
                f"harf={result.get('required_letter')} outcome={result.get('outcome')} "
                f"skor={result.get('score')}"
            )
        elif result.get("ended"):
            logger.log_event("Oyundan cikildi")
        return jsonify(result)

    @app.post("/api/game/ai_turn")
    def api_game_ai_turn():
        """Kelime oyunu: sira AI'dayken AI'nin kelimesini/pes'ini uretir (LLM burada)."""
        with game_lock:
            result = game.ai_turn()
        if result.get("ai_error"):
            log.warning("Kelime AI turu: Ollama erisilemedi — gercek pes DEGIL (gorevli kontrol etsin)")
            logger.log_event("UYARI: Kelime AI turunda Ollama erisilemedi (gercek pes degil)")
        logger.log_event(
            f"Kelime AI turu: kind={result.get('kind')} kelime={result.get('ai_word')} "
            f"harf={result.get('required_letter')} outcome={result.get('outcome')}"
        )
        return jsonify(result)

    @app.post("/api/game/exit")
    def api_game_exit():
        with game_lock:
            result = game.exit()
        logger.log_event("Oyun kapatildi")
        return jsonify(result)

    @app.get("/api/transcribe/status")
    def api_transcribe_status():
        return jsonify({
            "status": whisper_state.status,
            "ready": whisper_state.is_ready(),
            "error": whisper_state.error,
            "model": whisper_size,
            "language": WHISPER_LANGUAGE,
        })

    @app.post("/api/transcribe")
    def api_transcribe():
        """Tarayicidan gelen ses (multipart 'audio' veya raw body) -> turkce metin.
        faster-whisper PyAV ile WebM/Opus, MP3, WAV vb. format'lari decode eder.
        """
        if not whisper_state.is_ready():
            return jsonify({
                "error": "whisper_not_ready",
                "status": whisper_state.status,
                "detail": whisper_state.error,
            }), 503

        # Audio bytes'i topla: once multipart 'audio' alani, yoksa raw request body
        audio_bytes = b""
        if "audio" in request.files:
            audio_bytes = request.files["audio"].read()
        else:
            audio_bytes = request.get_data() or b""
        if not audio_bytes:
            return jsonify({"error": "audio_empty"}), 400

        # Transcribe — re-entrancy lock (tek model, tek thread guvenli kullanim)
        try:
            with whisper_state._lock:
                segments, info = whisper_state.model.transcribe(
                    io.BytesIO(audio_bytes),
                    language=WHISPER_LANGUAGE,
                    vad_filter=True,
                    beam_size=1,             # CPU'da hizli kalmasi icin
                    condition_on_previous_text=False,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as e:  # noqa: BLE001
            log.warning("Transkripsiyon hatasi: %s", e)
            return jsonify({"error": "transcribe_failed", "detail": str(e)}), 500

        meta = {
            "duration_s": getattr(info, "duration", 0.0),
            "language": getattr(info, "language", WHISPER_LANGUAGE),
            "language_prob": getattr(info, "language_probability", 0.0),
        }
        if not text:
            return jsonify({"text": "", "meta": meta, "warning": "no_speech"})
        # Sergi koruma: cok uzun konusma -> kirp (ses giris akisini kilitlemeyelim)
        max_chars = int(config.get("max_user_input_chars", 240))
        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "…"
            truncated = True
        return jsonify({"text": text, "meta": meta, "truncated": truncated})

    @app.get("/api/speak/status")
    def api_speak_status():
        return jsonify({
            "status": tts_state.status,
            "ready": tts_state.is_ready(),
            "error": tts_state.error,
            "engine": config.get("tts_engine", "piper"),
            "voice": config.get("tts_voice", DEFAULT_TTS_VOICE),  # QW-5: edge varsayilani
            "enabled": bool(config.get("tts_enabled", True)),
            "autoplay": bool(config.get("tts_autoplay", True)),
        })

    @app.post("/api/speak")
    def api_speak():
        """Metin + jest_id + yogunluk -> duyguya gore tonlanmis WAV ses."""
        if not config.get("tts_enabled", True):
            return jsonify({"error": "tts_disabled"}), 503
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        jest_id = (payload.get("jest_id") or "").strip() or None
        try:
            yogunluk = float(payload.get("yogunluk", 0.7))
        except (TypeError, ValueError):
            yogunluk = 0.7
        if not text:
            return jsonify({"error": "metin bos"}), 400
        # Sergi koruma: asiri uzun metni kirp (CPU'yu kilitlemeyelim)
        max_chars = int(config.get("max_user_input_chars", 240)) * 2
        if len(text) > max_chars:
            text = text[:max_chars]
        if not tts_state.is_ready():
            return jsonify({
                "error": "tts_not_ready",
                "status": tts_state.status,
                "detail": tts_state.error,
            }), 503

        # Anahtar turetimi + sentez ortak yardimcida — on-isitma da AYNI yolu kullanir.
        try:
            audio = _tts_synth_cached(tts_state, tts_cache, config, text, jest_id, yogunluk)
        except Exception as e:  # noqa: BLE001
            log.warning("TTS sentez hatasi: %s", e)
            return jsonify({"error": "tts_failed", "detail": str(e)}), 500
        if not audio:
            return jsonify({"error": "tts_empty"}), 500
        return Response(audio, mimetype="audio/wav",
                        headers={"Cache-Control": "no-store"})

    @app.route("/<path:filename>")
    def static_files(filename):
        # API yollari yukaridaki net route'larda kalmali; catch-all sadece web dosyalari icin.
        return send_from_directory(str(WEB_DIR), filename)

    # CORS: sadece localhost; basit acik politika (tek bilgisayar)
    @app.after_request
    def add_cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    app.config["_logger"] = logger
    return app


def open_browsers(host: str, port: int, delay_sec: float = 1.2) -> None:
    """Sunucu kalktiktan sonra iki sekmeyi ayni tarayicida ac."""
    def _open():
        import time
        time.sleep(delay_sec)
        base = f"http://{host}:{port}"
        try:
            webbrowser.open_new(f"{base}/")
            # ikinci sekme ayni pencereye gelsin
            webbrowser.open_new_tab(f"{base}/control")
        except Exception as e:
            log.warning("Tarayici acilamadi: %s — manuel ac: %s", e, base)
    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    config = load_config()
    app = create_app(config)
    host = "127.0.0.1"
    port = int(config.get("web_port", 5057))
    log.info("AI Body web sunucusu: http://%s:%d", host, port)
    log.info("  Sergi:          http://%s:%d/", host, port)
    log.info("  Kontrol paneli: http://%s:%d/control", host, port)
    open_browsers(host, port)
    try:
        # use_reloader=False -> warmup ve iki sekme acmayi tek seferde calistirir
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    finally:
        logger = app.config.get("_logger")
        if logger:
            try:
                logger.end()
            except Exception as e:
                log.warning("Oturum kapanis hatasi: %s", e)


if __name__ == "__main__":
    main()
