"""Ollama HTTP köprüsü — Qwen 2.5 7B'ye sistem promptu + kullanıcı metni gönderir,
JSON formatında jest cevabını çözümler."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)


class LLMBridge:
    def __init__(self, config: dict, base_dir: Path):
        self.url = config["ollama_url"].rstrip("/")
        self.model = config["ollama_model"]
        self.timeout = float(config.get("request_timeout_sec", 20))
        self.use_baked_prompt = bool(config.get("use_baked_prompt", False))

        prompt_path = (base_dir / config["system_prompt_path"]).resolve()
        gestures_path = (base_dir / config["gestures_path"]).resolve()
        self.system_prompt = prompt_path.read_text(encoding="utf-8")

        gdata = json.loads(gestures_path.read_text(encoding="utf-8"))
        self.valid_ids = {g["id"] for g in gdata["jestler"]}
        mode = "baked (modele gömülü)" if self.use_baked_prompt else "her istek (api üzerinden)"
        log.info("LLMBridge hazır — %d jest, model=%s, sistem promptu=%s",
                 len(self.valid_ids), self.model, mode)

    def is_alive(self) -> bool:
        # Iki defaya kadar dene; ilk istek bazen geç gelir (Ollama henuz hazirlanir)
        for attempt in range(2):
            try:
                r = requests.get(f"{self.url}/api/tags", timeout=5)
                if r.status_code == 200:
                    return True
            except requests.RequestException as e:
                if attempt == 1:
                    log.warning("Ollama erişilemiyor (2 deneme): %s", e)
        return False

    def request(self, user_text: str) -> Optional[dict]:
        """Başarılı: {jest_id, yogunluk, yanit, meta}. Başarısız: {error: ..., meta?}"""
        t0 = time.monotonic()
        # Baked modda sistem promptu modele gömülü olduğundan tekrar göndermeyiz —
        # bu ~2300 token prompt eval süresi tasarrufu sağlar.
        messages: list[dict] = []
        if not self.use_baked_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_text})

        try:
            r = requests.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_predict": 120,
                        "repeat_penalty": 1.15,
                    },
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            log.error("Ollama çağrısı hata verdi: %s", e)
            return {"error": f"ollama_request_failed: {e}",
                    "meta": {"wall_s": time.monotonic() - t0}}

        wall_s = time.monotonic() - t0

        meta = {
            "wall_s": wall_s,
            "total_ms": data.get("total_duration", 0) / 1e6,
            "load_ms": data.get("load_duration", 0) / 1e6,
            "prompt_tokens": int(data.get("prompt_eval_count", 0)),
            "prompt_eval_ms": data.get("prompt_eval_duration", 0) / 1e6,
            "eval_tokens": int(data.get("eval_count", 0)),
            "eval_ms": data.get("eval_duration", 0) / 1e6,
        }
        meta["tok_per_s"] = (
            meta["eval_tokens"] * 1000.0 / meta["eval_ms"]
            if meta["eval_ms"] > 0 else 0.0
        )

        content = data.get("message", {}).get("content", "")
        if not content:
            log.error("Ollama boş cevap döndü: %s", data)
            return {"error": "empty_content", "meta": meta}

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            log.error("Model JSON çözülemedi: %s\nİçerik: %s", e, content)
            return {"error": "invalid_json", "raw": content, "meta": meta}

        jest_id = parsed.get("jest_id")
        if jest_id not in self.valid_ids:
            log.warning("Bilinmeyen jest_id: %r", jest_id)
            return {"error": "unknown_jest_id", "jest_id": jest_id,
                    "raw": parsed, "meta": meta}

        try:
            yog = float(parsed.get("yogunluk", 0.7))
        except (TypeError, ValueError):
            yog = 0.7
        yog = max(0.0, min(1.0, yog))

        yanit = str(parsed.get("yanit", "")).strip()
        return {"jest_id": jest_id, "yogunluk": yog, "yanit": yanit, "meta": meta}