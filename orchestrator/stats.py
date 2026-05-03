"""Sistem istatistikleri — psutil varsa Ollama ve Python RAM kullanımını döndürür."""
from __future__ import annotations

from typing import Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def ram_usage() -> Optional[dict]:
    """{'python_mb': float, 'ollama_mb': float} ya da psutil yoksa None."""
    if not HAS_PSUTIL:
        return None
    me = psutil.Process()
    py_mb = me.memory_info().rss / (1024 * 1024)
    ollama_mb = 0.0
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (p.info["name"] or "").lower()
            if "ollama" in name:
                ollama_mb += p.info["memory_info"].rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"python_mb": py_mb, "ollama_mb": ollama_mb}


def fmt_mb(mb: float) -> str:
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.0f} MB"
