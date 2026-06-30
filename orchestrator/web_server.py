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
import threading
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


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


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


def _load_tts_async(state: "TTSState", config: dict) -> None:
    """TTS motorunu arka planda yukler — HTTP yanitlarini geciktirmez.
    use_cuda=False: 4GB VRAM aktif LLM (Ollama) ile dolu; TTS CPU'da kalir
    (Piper RTF ~0.05, gercek-zamandan cok hizli)."""
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
            primary = EdgeEngine(voice=config.get("tts_voice", "tr-TR-EmelNeural"))
            if config.get("tts_fallback_enabled", True):
                state.engine = FallbackEngine(primary, _make_piper("tts_fallback_voice"))
                log.info("TTS hazir (edge=%s + cevrimdisi yedek piper=%s).",
                         primary.voice_name, state.engine.fallback.voice_name)
            else:
                state.engine = primary
                log.info("TTS hazir (edge=%s, yedek yok).", primary.voice_name)
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


def create_app(config: dict) -> Flask:
    app = Flask(__name__, static_folder=None)

    bridge = LLMBridge(config, BASE_DIR)
    game = GameEngine(bridge=bridge)  # TKM deterministik; kelime turetme (ileride) LLM kullanir
    # Flask threaded=True; tek GameEngine instance'i paylasiliyor. Sure-doldu ile
    # manuel cevap/AI-turu ayni anda gelirse durum makinesi bozulmasin diye seri kilit.
    game_lock = threading.Lock()
    gestures_path = (BASE_DIR / config["gestures_path"]).resolve()
    log_path = (BASE_DIR / config.get("session_log_path", "../logs/session.log")).resolve()
    logger = SessionLogger(log_path, config["ollama_url"], bridge.model)
    logger.start()
    log.info("Oturum logu: %s", log_path)

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
            args=(tts_state, config),
            daemon=True,
        ).start()

    @app.route("/")
    def index():
        return send_from_directory(str(WEB_DIR), "AI_Body_v2.html")

    @app.route("/control")
    @app.route("/kontrol")
    def control_panel():
        return send_from_directory(str(WEB_DIR), "Kontrol_Paneli.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(str(WEB_DIR), filename)

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
        return jsonify({"ollama": bridge.is_alive(), "model": bridge.model})

    @app.get("/api/config")
    def api_config():
        """Frontend'in bilmesi gereken sergi sınırları."""
        return jsonify({
            "max_user_input_chars": int(config.get("max_user_input_chars", 240)),
            "max_record_seconds": int(config.get("max_record_seconds", 30)),
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
        result = bridge.request(text)
        if result is None or "error" in result:
            err = (result or {}).get("error", "no_response")
            meta = (result or {}).get("meta", {})
            logger.log_error(text, result or {"error": err})
            return jsonify({"error": err, "meta": meta}), 500
        logger.log_request(text, result)
        return jsonify(result)

    @app.post("/api/clear_history")
    def api_clear():
        bridge.clear_history()
        logger.log_event("Konusma gecmisi sifirlandi")
        return jsonify({"ok": True})

    # ——— Oyun modu (deterministik; TKM icin LLM cagrilmaz) ————————
    @app.post("/api/game/start")
    def api_game_start():
        with game_lock:
            result = game.start()
        logger.log_event("Oyun baslatildi (menu)")
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
            "voice": config.get("tts_voice", "tr_TR-dfki-medium"),
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

        voice = config.get("tts_voice", "tr_TR-dfki-medium")
        key = tts_cache.make_key(text, jest_id, yogunluk, voice)
        audio = tts_cache.get(key)
        if audio is None:
            try:
                with tts_state._lock:  # tek model -> seri sentez
                    audio = tts_state.engine.synthesize(text, jest_id, yogunluk)
            except Exception as e:  # noqa: BLE001
                log.warning("TTS sentez hatasi: %s", e)
                return jsonify({"error": "tts_failed", "detail": str(e)}), 500
            if audio:
                tts_cache.put(key, audio)
        if not audio:
            return jsonify({"error": "tts_empty"}), 500
        return Response(audio, mimetype="audio/wav",
                        headers={"Cache-Control": "no-store"})

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
