"""ElevenLabs TTS motoru — bulut tabanli, yuksek kaliteli cok dilli seslendirme.

- Duygu emotion_voice_map ile prosodiye, oradan ElevenLabs voice_settings
  (stability/style/speed/similarity_boost) alanlarina cevrilir.
- Cikti mp3 -> ffmpeg ile WAV'a normalize edilir (edge/Piper ile AYNI format;
  onbellek/servis uniform kalir).
- CEVRIMICI + KOTALI: her sentez kredi harcar. CreditGuard aylik tavan koyar;
  tavan dolunca ya da anahtar/ag yoksa synthesize b"" doner -> FallbackEngine
  otomatik ucretsiz edge-tts'e (ordan Piper'a) duser. Sergi asla susmaz, butce asilmaz.

Anahtar GUVENLIGI: config.json'a yazma; ELEVENLABS_API_KEY ortam degiskenini kullan.
Yeni motor eklemek icin bkz tts/engine_base.py (yalnizca synthesize gerekli).
"""
from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import threading
import wave
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg
import requests

from .engine_base import TTSEngine
from .emotion_voice_map import prosody_for, prosody_for_va

_log = logging.getLogger("tts.elevenlabs")

_API_BASE = "https://api.elevenlabs.io/v1"
# Nötr çapa: emotion_voice_map._NEUTRAL ile tutarlı (length_scale/noise_scale).
_NEUTRAL_LENGTH = 1.05
_NEUTRAL_NOISE = 0.667


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _credits_per_char(model_id: str) -> float:
    """API'de Flash/Turbo modelleri 0.5 kredi/karakter; digerleri 1.0."""
    m = (model_id or "").lower()
    return 0.5 if ("flash" in m or "turbo" in m) else 1.0


def compute_voice_settings(p: dict, stability=None, style=None,
                           similarity_boost: float = 0.8,
                           use_speaker_boost: bool = True) -> dict:
    """emotion_voice_map prosodisini ElevenLabs voice_settings'e cevir.

    arousal noise_scale'den geri cikarilir (map formulunun tersi). Yuksek arousal
    -> daha dusuk stability (daha anlatimli) + daha yuksek style. Hiz length_scale'den.
    ElevenLabs'te dogrudan pitch yok; duygu stability/style + metin icerigiyle verilir.
    """
    arousal = _clamp((p["noise_scale"] - _NEUTRAL_NOISE) / 0.35 + 0.45, 0.0, 1.0)
    a = (arousal - 0.45) / 0.55            # ~ -0.82 .. +1.0
    speed = _clamp(_NEUTRAL_LENGTH / p["length_scale"], 0.7, 1.2)
    if stability is None:
        stability = _clamp(0.55 - 0.45 * a, 0.30, 0.75)
    if style is None:
        style = _clamp(0.30 + 0.50 * a, 0.0, 0.65)
    return {
        "stability": round(float(stability), 3),
        "similarity_boost": round(float(similarity_boost), 3),
        "style": round(float(style), 3),
        "use_speaker_boost": bool(use_speaker_boost),
        "speed": round(speed, 3),
    }


def emotion_signature(jest_id, yogunluk, stability=None, style=None) -> str:
    """Onbellek anahtari icin KABA duygu imzasi — ayni voice_settings ureten (benzer)
    jest'ler ayni imzayi paylasir, tek kez uretilir. Oyunun rastgele-jest secimini
    ON-URETIM ile uyumlu kilar (emoji/jest_id oyunda aynen kalir, yalnizca SES anahtari
    kanoniklesir). 1 ondalik yuvarlama duygu kumeleri icinde tek sese indirger."""
    p = prosody_for(jest_id, yogunluk) if jest_id else prosody_for_va(0.0, 0.45, yogunluk)
    vs = compute_voice_settings(p, stability, style)
    return f"el:{vs['stability']:.1f}:{vs['style']:.1f}:{vs['speed']:.1f}"


class CreditGuard:
    """Aylik kredi tavani — dosyaya yazan kalici sayac.

    allow(text) tavani asacaksa False doner (motor bos ses -> fallback). charge(text)
    yalnizca BASARILI sentezden sonra cagrilir. Ay degisince sayac sifirlanir
    (ElevenLabs kredileri de aylik yenilenir). cap<=0 => sinirsiz (guard kapali).
    """

    def __init__(self, monthly_cap, usage_path, credits_per_char: float) -> None:
        self.cap = float(monthly_cap or 0)
        self.path = Path(usage_path)
        self.cpc = float(credits_per_char)
        self._lock = threading.Lock()
        self._month = ""
        self._spent = 0.0
        self._load()

    @staticmethod
    def _now_month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self._month = str(d.get("month", ""))
            self._spent = float(d.get("spent_credits", 0.0))
        except (OSError, json.JSONDecodeError, ValueError):
            self._month, self._spent = "", 0.0
        if self._month != self._now_month():          # ay degistiyse sifirla
            self._month, self._spent = self._now_month(), 0.0
            self._save()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"month": self._month, "spent_credits": round(self._spent, 1)},
                           ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass

    def _rollover(self) -> None:
        cur = self._now_month()
        if self._month != cur:
            self._month, self._spent = cur, 0.0

    def est_credits(self, text: str) -> float:
        return len(text or "") * self.cpc

    def allow(self, text: str) -> bool:
        if self.cap <= 0:
            return True
        with self._lock:
            self._rollover()
            return self._spent + self.est_credits(text) <= self.cap

    def charge(self, text: str) -> None:
        with self._lock:
            self._rollover()
            self._spent += self.est_credits(text)
            self._save()

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def remaining(self) -> float:
        return max(0.0, self.cap - self._spent) if self.cap > 0 else float("inf")


class ElevenLabsEngine(TTSEngine):
    name = "elevenlabs"

    def __init__(self, voice: str, api_key: str = "", model: str = "eleven_flash_v2_5",
                 out_rate: int = 44100, language: str = "tr",
                 monthly_cap=32000, usage_path=None, timeout: float = 30.0,
                 stability=None, similarity_boost: float = 0.8, style=None,
                 use_speaker_boost: bool = True) -> None:
        self.voice_name = voice  # ElevenLabs voice_id; FallbackEngine/loglar okur
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.model = model
        self._sr = int(out_rate)
        self.language = language
        self.timeout = float(timeout)
        self._ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        # Sabit voice_settings override'lari (None -> duygudan turet).
        self._fixed = {"stability": stability, "similarity_boost": float(similarity_boost),
                       "style": style, "use_speaker_boost": bool(use_speaker_boost)}
        up = Path(usage_path) if usage_path else (
            Path(__file__).resolve().parent / "elevenlabs_usage.json")
        self.guard = CreditGuard(monthly_cap, up, _credits_per_char(model))

    @property
    def sample_rate(self) -> int:
        return self._sr

    def synthesize(self, text: str, jest_id: str | None = None,
                   yogunluk: float = 0.7) -> bytes:
        text = (text or "").strip()
        if not text:
            return b""
        if not self.api_key:
            _log.warning("ELEVENLABS_API_KEY yok — bos donuluyor (fallback devrede).")
            return b""
        if not self.guard.allow(text):
            _log.warning("ElevenLabs aylik kredi tavani doldu (%.0f/%.0f kredi) — "
                         "ucretsiz yedege dusuluyor.", self.guard.spent, self.guard.cap)
            return b""
        p = prosody_for(jest_id, yogunluk) if jest_id else prosody_for_va(0.0, 0.45, yogunluk)
        try:
            mp3 = self._convert(text, self._voice_settings(p))
        except Exception as e:  # noqa: BLE001 — ag/istek hatasi -> fallback
            _log.warning("ElevenLabs istek hatasi: %s — yedege dusuluyor.", e)
            return b""
        if not mp3:
            return b""
        self.guard.charge(text)      # yalnizca basarili sentezde krediyi dus
        return self._mp3_to_wav(mp3)

    # ——— duygu -> ElevenLabs voice_settings ————————————————————————
    def _voice_settings(self, p: dict) -> dict:
        return compute_voice_settings(
            p, self._fixed["stability"], self._fixed["style"],
            self._fixed["similarity_boost"], self._fixed["use_speaker_boost"])

    def cache_signature(self, jest_id, yogunluk) -> str:
        """Onbellek anahtarinda jest_id yerine kullanilacak kaba duygu imzasi."""
        return emotion_signature(jest_id, yogunluk,
                                 self._fixed["stability"], self._fixed["style"])

    # ——— ic yardimcilar ————————————————————————————————————————————
    def _convert(self, text: str, voice_settings: dict) -> bytes:
        if not self.voice_name:
            _log.warning("ElevenLabs voice_id (tts_voice) bos — sentez yapilamaz.")
            return b""
        url = f"{_API_BASE}/text-to-speech/{self.voice_name}"
        body = {"text": text, "model_id": self.model, "voice_settings": voice_settings}
        # language_code yalnizca Flash/Turbo modellerinde gecerli (Multilingual v2 otomatik).
        m = self.model.lower()
        if self.language and ("flash" in m or "turbo" in m):
            body["language_code"] = self.language
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json",
                   "Accept": "audio/mpeg"}
        r = requests.post(url, params={"output_format": "mp3_44100_128"},
                          headers=headers, json=body, timeout=self.timeout)
        if r.status_code != 200:
            _log.warning("ElevenLabs HTTP %s: %s", r.status_code, (r.text or "")[:200])
            return b""
        return r.content

    def _mp3_to_wav(self, mp3: bytes) -> bytes:
        proc = subprocess.run(
            [self._ffmpeg, "-loglevel", "error", "-i", "pipe:0",
             "-f", "s16le", "-ar", str(self._sr), "-ac", "1", "pipe:1"],
            input=mp3, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode != 0 or not proc.stdout:
            return b""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sr)
            wf.writeframes(proc.stdout)
        return buf.getvalue()
