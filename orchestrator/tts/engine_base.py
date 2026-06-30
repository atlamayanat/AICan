"""TTS motorlari icin ortak arayuz.

Yeni bir motor eklemek (ornegin Chatterbox/ElevenLabs) bu sinifi uygulamak +
config'te tts_engine'i degistirmekten ibarettir. Geri kalan (endpoint, onbellek,
frontend) ayni kalir.
"""
from __future__ import annotations

import abc
import logging

_log = logging.getLogger("tts.fallback")


class TTSEngine(abc.ABC):
    """Metni duyguya gore tonlanmis WAV sesine ceviren motor."""

    name: str = "base"

    @abc.abstractmethod
    def synthesize(self, text: str, jest_id: str | None = None,
                   yogunluk: float = 0.7) -> bytes:
        """text -> WAV bytes. jest_id duygu tonunu, yogunluk siddetini belirler."""
        raise NotImplementedError

    @property
    def sample_rate(self) -> int:
        return 22050


class FallbackEngine(TTSEngine):
    """Birincil motoru dener; hata firlatir ya da bos donerse yedege duser.

    Kullanim: edge (cevrimici, yuksek kalite) birincil, Piper (cevrimdisi) yedek.
    Internet kesilirse sergi susmaz — otomatik Piper'a gecer.
    """

    name = "fallback"

    def __init__(self, primary: TTSEngine, fallback: TTSEngine) -> None:
        self.primary = primary
        self.fallback = fallback

    @property
    def sample_rate(self) -> int:
        return self.primary.sample_rate

    @property
    def voice_name(self) -> str:
        return getattr(self.primary, "voice_name", self.primary.name)

    def synthesize(self, text: str, jest_id: str | None = None,
                   yogunluk: float = 0.7) -> bytes:
        try:
            out = self.primary.synthesize(text, jest_id, yogunluk)
            if out:
                return out
            _log.warning("Birincil TTS (%s) bos dondu, yedege (%s) dusuluyor.",
                         self.primary.name, self.fallback.name)
        except Exception as e:  # noqa: BLE001 — ag/baska hata -> yedek
            _log.warning("Birincil TTS (%s) hata: %s — yedege (%s) dusuluyor.",
                         self.primary.name, e, self.fallback.name)
        return self.fallback.synthesize(text, jest_id, yogunluk)
