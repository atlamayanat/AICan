"""Yerel Piper TTS motoru (CPU, ucretsiz, cevrimdisi).

- Piper modeli bir kez yuklenir ve bellekte tutulur (her istekte yeniden yukleme
  yapilmaz -> dusuk gecikme).
- Duygu, emotion_voice_map ile prosodiye cevrilir (hiz/ses/tonlama-cesitliligi/
  cumle-arasi-durak). Perde (pitch) Piper'da olmadigi icin ffmpeg ile son-islemde
  kaydirilir.
- GPU'ya DOKUNMAZ (use_cuda=False) -> ayni 4GB karttaki Ollama ile cakismaz.
"""
from __future__ import annotations

import io
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
from piper import PiperVoice, SynthesisConfig

from .engine_base import TTSEngine
from .emotion_voice_map import prosody_for, prosody_for_va

_VOICES_DIR = Path(__file__).resolve().parent / "voices"


class PiperEngine(TTSEngine):
    name = "piper"

    def __init__(self, voice: str = "tr_TR-dfki-medium", use_cuda: bool = False,
                 pitch_enabled: bool = True) -> None:
        model = _VOICES_DIR / f"{voice}.onnx"
        if not model.exists():
            raise FileNotFoundError(f"Piper ses modeli yok: {model}")
        self.voice_name = voice
        self.pitch_enabled = pitch_enabled
        self._voice = PiperVoice.load(str(model), use_cuda=use_cuda)
        self._sr = int(self._voice.config.sample_rate)
        self._ffmpeg = imageio_ffmpeg.get_ffmpeg_exe() if pitch_enabled else None

    @property
    def sample_rate(self) -> int:
        return self._sr

    def synthesize(self, text: str, jest_id: str | None = None,
                   yogunluk: float = 0.7) -> bytes:
        text = (text or "").strip()
        if not text:
            return b""
        p = prosody_for(jest_id, yogunluk) if jest_id else prosody_for_va(0.0, 0.45, yogunluk)

        syn = SynthesisConfig(
            length_scale=p["length_scale"],
            noise_scale=p["noise_scale"],
            noise_w_scale=p["noise_w_scale"],
            # normalize_audio=True ile hedef tepe = volume*tam-olcek; clip yememesi
            # icin volume <= 1.0 sinirlanir (yuksek-uyarilma duygular tam olcege oturur).
            volume=min(float(p["volume"]), 1.0),
            normalize_audio=True,
        )
        chunks = list(self._voice.synthesize(text, syn_config=syn))
        pcm = self._chunks_to_pcm(chunks, float(p["sentence_silence"]))
        if self.pitch_enabled and abs(p["pitch_semitones"]) >= 0.1 and pcm:
            pcm = self._pitch_shift_pcm(pcm, float(p["pitch_semitones"]))
        return self._pcm_to_wav(pcm)

    # ——— ic yardimcilar ————————————————————————————————————————————
    def _chunks_to_pcm(self, chunks, sentence_silence: float) -> bytes:
        """AudioChunk'lari tek int16 PCM akisina birlestir; cumleler arasina sessizlik koy."""
        if not chunks:
            return b""
        n_sil = int(max(0.0, sentence_silence) * self._sr)
        silence = b"\x00\x00" * n_sil  # mono int16
        parts: list[bytes] = []
        for i, c in enumerate(chunks):
            if i > 0 and silence:
                parts.append(silence)
            parts.append(c.audio_int16_bytes)
        return b"".join(parts)

    def _pitch_shift_pcm(self, pcm: bytes, semitones: float) -> bytes:
        """ffmpeg ile perdeyi yari-ton cinsinden kaydir (sure korunur). Raw PCM giris/cikis."""
        factor = 2.0 ** (semitones / 12.0)
        af = f"asetrate={self._sr}*{factor:.6f},atempo={1.0 / factor:.6f},aresample={self._sr}"
        try:
            proc = subprocess.run(
                [self._ffmpeg, "-loglevel", "error",
                 "-f", "s16le", "-ar", str(self._sr), "-ac", "1", "-i", "pipe:0",
                 "-af", af,
                 "-f", "s16le", "-ar", str(self._sr), "-ac", "1", "pipe:1"],
                input=pcm, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except Exception:
            return pcm
        if proc.returncode != 0 or not proc.stdout:
            return pcm  # pitch basarisizsa ham sesi koru
        return proc.stdout

    def _pcm_to_wav(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sr)
            wf.writeframes(pcm)
        return buf.getvalue()
