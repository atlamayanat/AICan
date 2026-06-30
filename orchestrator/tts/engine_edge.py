"""edge-tts motoru — Microsoft Edge'in UCRETSIZ (anahtarsiz) neural seslendirmesi.

Yuksek kaliteli Turkce neural sesler: tr-TR-EmelNeural (kadin), tr-TR-AhmetNeural (erkek).
- Duygu emotion_voice_map ile prosodiye, oradan edge'in rate/pitch/volume'una cevrilir.
- Cikti mp3 -> ffmpeg ile WAV'a normalize edilir (Piper ile AYNI format; onbellek/servis
  uniform kalir).
- CEVRIMICI: Microsoft sunucusuna baglanir. Internet yoksa synthesize hata verir ve
  FallbackEngine devreye girip Piper'a (cevrimdisi) duser.
"""
from __future__ import annotations

import asyncio
import io
import subprocess
import wave

import edge_tts
import imageio_ffmpeg

from .engine_base import TTSEngine
from .emotion_voice_map import prosody_for, prosody_for_va


class EdgeEngine(TTSEngine):
    name = "edge"

    def __init__(self, voice: str = "tr-TR-EmelNeural", out_rate: int = 24000) -> None:
        self.voice_name = voice
        self._sr = int(out_rate)
        self._ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    @property
    def sample_rate(self) -> int:
        return self._sr

    def synthesize(self, text: str, jest_id: str | None = None,
                   yogunluk: float = 0.7) -> bytes:
        text = (text or "").strip()
        if not text:
            return b""
        p = prosody_for(jest_id, yogunluk) if jest_id else prosody_for_va(0.0, 0.45, yogunluk)
        rate, pitch, vol = self._edge_params(p)
        mp3 = self._fetch_mp3(text, rate, pitch, vol)   # ag hatasi -> exception (Fallback yakalar)
        if not mp3:
            return b""
        return self._mp3_to_wav(mp3)

    # ——— ic yardimcilar ————————————————————————————————————————————
    @staticmethod
    def _edge_params(p: dict):
        """emotion_voice_map prosodisini edge-tts rate/pitch/volume string'lerine cevir."""
        rate = max(-40, min(40, round((1.0 / p["length_scale"] - 1.0) * 100)))
        pitch = max(-60, min(60, round(p["pitch_semitones"] * 18)))   # ~18 Hz / yari ton
        vol = max(-30, min(20, round((p["volume"] - 1.0) * 50)))
        return f"{rate:+d}%", f"{pitch:+d}Hz", f"{vol:+d}%"

    def _fetch_mp3(self, text: str, rate: str, pitch: str, vol: str) -> bytes:
        async def _run() -> bytes:
            data = bytearray()
            comm = edge_tts.Communicate(text, self.voice_name,
                                        rate=rate, pitch=pitch, volume=vol)
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    data += chunk["data"]
            return bytes(data)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()

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
