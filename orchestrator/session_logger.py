"""Detayli oturum logu — yapay zeka analizi icin .txt dosyasina yazar.

Her oturum icin:
  1. Baslangicta basligi yazar (model adi/sürümü, tarih/saat, sistem bilgisi)
  2. Her istek/yanit/hatayi detaylica kaydeder (token, RAM, sure)
  3. Pencere kapaninca oturum ozetini yazar
  4. Sonraki oturumlar ayni dosyaya eklenir, aralarinda 3 bos satir bosluk olur
"""
from __future__ import annotations

import platform
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from stats import HAS_PSUTIL, ram_usage


class SessionLogger:
    SEP_THICK = "=" * 80
    SEP_THIN = "-" * 80
    SEP_DOT = "." * 80

    def __init__(self, log_path: Path, ollama_url: str, model_name: str):
        self.log_path = log_path
        self.ollama_url = ollama_url.rstrip("/")
        self.model_name = model_name
        self.session_start = time.monotonic()
        self.session_start_dt = datetime.now()
        self.events: list[dict] = []
        self._closed = False
        self.peak_ollama_mb = 0.0
        self.peak_python_mb = 0.0
        # Dizini olustur
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- Yardimcilar ----------
    def _write(self, text: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(text)

    def _fetch_model_info(self) -> Optional[dict]:
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            if r.status_code != 200:
                return None
            for m in r.json().get("models", []):
                if m.get("name") == self.model_name:
                    return m
        except requests.RequestException:
            pass
        return None

    def _update_peak_ram(self) -> Optional[dict]:
        ram = ram_usage()
        if ram:
            self.peak_ollama_mb = max(self.peak_ollama_mb, ram["ollama_mb"])
            self.peak_python_mb = max(self.peak_python_mb, ram["python_mb"])
        return ram

    # ---------- Yasam dongusu ----------
    def start(self) -> None:
        """Oturum baslangicini yaz."""
        existing_size = self.log_path.stat().st_size if self.log_path.exists() else 0
        # Iki oturum arasinda bosluk
        if existing_size > 0:
            self._write("\n\n\n")

        model_info = self._fetch_model_info()
        ram = self._update_peak_ram()

        lines: list[str] = []
        lines.append(self.SEP_THICK)
        lines.append(f"OTURUM BASLANGICI — {self.session_start_dt:%Y-%m-%d %H:%M:%S}")
        lines.append(self.SEP_THICK)
        lines.append(f"Model adi:           {self.model_name}")
        if model_info:
            size_gb = model_info.get("size", 0) / (1024 ** 3)
            lines.append(f"Model boyutu:        {size_gb:.2f} GB")
            modified = model_info.get("modified_at", "?")
            lines.append(f"Model son guncelleme:{modified}")
            details = model_info.get("details") or {}
            if details:
                lines.append(f"Parent model:        {details.get('parent_model', '-')}")
                lines.append(f"Format:              {details.get('format', '?')}")
                lines.append(f"Family:              {details.get('family', '?')}")
                lines.append(f"Parametre sayisi:    {details.get('parameter_size', '?')}")
                lines.append(f"Quantization:        {details.get('quantization_level', '?')}")
            digest = model_info.get("digest", "")
            if digest:
                lines.append(f"Model hash:          {digest[:16]}…")
        else:
            lines.append("Model bilgisi alinamadi (Ollama yanit vermedi).")
        lines.append("")
        lines.append(f"Python:              {sys.version.split()[0]}")
        lines.append(f"Platform:            {platform.system()} {platform.release()} ({platform.machine()})")
        lines.append(f"psutil mevcut:       {'evet' if HAS_PSUTIL else 'hayir'}")
        if ram:
            lines.append(f"Baslangic RAM:       ollama={ram['ollama_mb']:.0f} MB, python={ram['python_mb']:.0f} MB")
        lines.append("")
        lines.append(self.SEP_THIN)
        lines.append("KONUSMA GECMISI")
        lines.append(self.SEP_THIN)
        lines.append("")

        self._write("\n".join(lines) + "\n")

    def log_request(self, user_text: str, result: dict) -> None:
        """Basarili bir AI cevabini kaydet."""
        ts = datetime.now()
        meta = result.get("meta", {})
        ram = self._update_peak_ram()

        self.events.append({
            "type": "request",
            "ts": ts,
            "text": user_text,
            "jest_id": result.get("jest_id"),
            "yogunluk": result.get("yogunluk"),
            "yanit": result.get("yanit"),
            "meta": dict(meta),
            "ram": dict(ram) if ram else None,
        })

        lines = []
        lines.append(f"[{ts:%H:%M:%S}] >> {user_text!r}")
        lines.append(f"           jest_id:        {result.get('jest_id')}")
        lines.append(f"           yogunluk:       {result.get('yogunluk', 0):.2f}")
        lines.append(f"           yanit:          {result.get('yanit', '')!r}")
        lines.append(f"           wall_time:      {meta.get('wall_s', 0):.2f} s")
        lines.append(f"           load_time:      {meta.get('load_ms', 0):.0f} ms")
        lines.append(f"           prompt_tokens:  {meta.get('prompt_tokens', 0)}")
        lines.append(f"           prompt_eval_ms: {meta.get('prompt_eval_ms', 0):.0f} ms")
        lines.append(f"           eval_tokens:    {meta.get('eval_tokens', 0)}")
        lines.append(f"           eval_ms:        {meta.get('eval_ms', 0):.0f} ms")
        lines.append(f"           tok_per_s:      {meta.get('tok_per_s', 0):.1f}")
        if ram:
            lines.append(f"           ram_ollama:     {ram['ollama_mb']:.0f} MB")
            lines.append(f"           ram_python:     {ram['python_mb']:.0f} MB")
        lines.append("")
        self._write("\n".join(lines) + "\n")

    def log_error(self, user_text: str, detail: dict) -> None:
        ts = datetime.now()
        meta = detail.get("meta", {})
        self.events.append({
            "type": "error",
            "ts": ts,
            "text": user_text,
            "error": detail.get("error"),
            "meta": dict(meta) if meta else {},
        })
        lines = [
            f"[{ts:%H:%M:%S}] >> {user_text!r}",
            f"           HATA:           {detail.get('error')}",
        ]
        if meta.get("wall_s"):
            lines.append(f"           wall_time:      {meta['wall_s']:.2f} s (timeout/fail)")
        lines.append("")
        self._write("\n".join(lines) + "\n")

    def log_event(self, msg: str) -> None:
        """Sistem olayi (durdur, idle, vb.)."""
        ts = datetime.now()
        self.events.append({"type": "event", "ts": ts, "msg": msg})
        self._write(f"[{ts:%H:%M:%S}] -- {msg}\n\n")

    def end(self) -> None:
        if self._closed:
            return
        self._closed = True
        end_dt = datetime.now()
        duration = time.monotonic() - self.session_start

        request_evts = [e for e in self.events if e["type"] == "request"]
        errors = [e for e in self.events if e["type"] == "error"]
        events = [e for e in self.events if e["type"] == "event"]

        wall_times = [e["meta"].get("wall_s", 0) for e in request_evts]
        prompt_tokens = sum(e["meta"].get("prompt_tokens", 0) for e in request_evts)
        eval_tokens = sum(e["meta"].get("eval_tokens", 0) for e in request_evts)
        load_times = [e["meta"].get("load_ms", 0) / 1000 for e in request_evts if e["meta"].get("load_ms", 0) > 100]
        speeds = [e["meta"].get("tok_per_s", 0) for e in request_evts if e["meta"].get("tok_per_s", 0) > 0]
        jest_counter = Counter(e["jest_id"] for e in request_evts if e.get("jest_id"))
        category_counter: Counter = Counter()
        for e in request_evts:
            jid = e.get("jest_id") or ""
            if jid.startswith(("onayla_", "reddet_", "kararsiz", "bilmiyorum",
                               "soru_isareti", "dinliyorum", "bekle", "anlamadim")):
                category_counter["cevap_tepkisi"] += 1
            elif jid:
                category_counter["duygu_tepkisi"] += 1

        mins, secs = divmod(int(duration), 60)
        hrs, mins = divmod(mins, 60)
        sure_str = f"{hrs} sa {mins} dk {secs} sn" if hrs else f"{mins} dk {secs} sn"

        lines: list[str] = ["", self.SEP_THICK, f"OTURUM OZETI — {end_dt:%Y-%m-%d %H:%M:%S}", self.SEP_THICK]
        lines.append(f"Sure:                    {sure_str}")
        lines.append(f"Toplam olay sayisi:      {len(self.events)}")
        lines.append(f"  - Basarili istek:      {len(request_evts)}")
        lines.append(f"  - Hata:                {len(errors)}")
        lines.append(f"  - Sistem olayi:        {len(events)}")

        if wall_times:
            lines.append("")
            lines.append("Performans:")
            lines.append(f"  Toplam dusunme suresi:   {sum(wall_times):.1f} sn")
            lines.append(f"  Ortalama yanit suresi:   {sum(wall_times) / len(wall_times):.2f} sn")
            lines.append(f"  En hizli yanit:          {min(wall_times):.2f} sn")
            lines.append(f"  En yavas yanit:          {max(wall_times):.2f} sn")
            if load_times:
                lines.append(f"  Toplam model yukleme:    {sum(load_times):.1f} sn ({len(load_times)} kez)")
            if speeds:
                lines.append(f"  Ortalama uretim hizi:    {sum(speeds) / len(speeds):.1f} tok/s")
                lines.append(f"  Max uretim hizi:         {max(speeds):.1f} tok/s")
                lines.append(f"  Min uretim hizi:         {min(speeds):.1f} tok/s")

        if prompt_tokens or eval_tokens:
            lines.append("")
            lines.append("Token kullanimi:")
            lines.append(f"  Toplam prompt token:     {prompt_tokens:,}")
            lines.append(f"  Toplam yanit token:      {eval_tokens:,}")
            lines.append(f"  Toplam:                  {prompt_tokens + eval_tokens:,}")
            if request_evts:
                avg_p = prompt_tokens / len(request_evts)
                avg_e = eval_tokens / len(request_evts)
                lines.append(f"  Ortalama prompt/istek:   {avg_p:.0f}")
                lines.append(f"  Ortalama yanit/istek:    {avg_e:.0f}")

        if HAS_PSUTIL:
            lines.append("")
            lines.append("RAM:")
            lines.append(f"  Pik ollama:              {self.peak_ollama_mb:.0f} MB")
            lines.append(f"  Pik python:              {self.peak_python_mb:.0f} MB")

        if category_counter:
            lines.append("")
            lines.append("Kategori dagilimi:")
            for cat, n in category_counter.most_common():
                lines.append(f"  {cat:25s} x {n}")

        if jest_counter:
            lines.append("")
            lines.append("En sik secilen jestler:")
            for jid, n in jest_counter.most_common(15):
                lines.append(f"  {jid:25s} x {n}")

        if errors:
            lines.append("")
            lines.append("Hatalar:")
            for e in errors:
                lines.append(f"  [{e['ts']:%H:%M:%S}] {e['text']!r:30s} -> {e['error']}")

        lines.append("")
        lines.append(self.SEP_THICK)
        lines.append(f"OTURUM KAPANISI — {end_dt:%Y-%m-%d %H:%M:%S}")
        lines.append(self.SEP_THICK)
        self._write("\n".join(lines) + "\n")
