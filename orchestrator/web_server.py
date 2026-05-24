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

from flask import Flask, jsonify, request, send_from_directory

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
# CPU'da kalir cunku 4GB VRAM zaten qwen3:4b ile dolu.
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


def create_app(config: dict) -> Flask:
    app = Flask(__name__, static_folder=None)

    bridge = LLMBridge(config, BASE_DIR)
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
