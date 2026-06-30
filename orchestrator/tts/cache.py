"""Basit dosya tabanli WAV onbellegi.

Anahtar = (ses, jest_id, yogunluk, metin) -> sha1. Sik tekrar eden cumleler
(selamlama vb.) bir kez uretilir, sonra aninda servis edilir; boylece hem gecikme
hem CPU yuku duser. Dosya sayisi limiti asilinca en eski (mtime) dosyalar silinir.
"""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path


class WavCache:
    def __init__(self, cache_dir, max_files: int = 500, enabled: bool = True) -> None:
        self.dir = Path(cache_dir)
        self.max_files = int(max_files)
        self.enabled = bool(enabled)
        self._lock = threading.Lock()
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def make_key(self, text: str, jest_id, yogunluk, voice: str) -> str:
        raw = "\x1f".join([
            str(voice),
            str(jest_id or ""),
            f"{float(yogunluk):.2f}",
            (text or "").strip(),
        ])
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def get(self, key: str):
        if not self.enabled:
            return None
        f = self.dir / f"{key}.wav"
        try:
            return f.read_bytes() if f.exists() else None
        except OSError:
            return None

    def put(self, key: str, data: bytes) -> None:
        if not self.enabled or not data:
            return
        f = self.dir / f"{key}.wav"
        try:
            f.write_bytes(data)
        except OSError:
            return
        self._maybe_evict()

    def _maybe_evict(self) -> None:
        with self._lock:
            files = sorted(self.dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
            while len(files) > self.max_files:
                old = files.pop(0)
                try:
                    old.unlink()
                except OSError:
                    pass
