"""Ollama HTTP köprüsü — config'deki modele (ollama_model) sistem promptu + kullanıcı
metni gönderir, format-schema ile JSON jest cevabını çözümler.
Aktif model config.json'dan gelir; jest davranışı ai/system_prompt.txt ile belirlenir."""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

# Mirror override: model bu jestlerden birini secince ve kullanici 1. tekil
# olumsuz duygu paylasiyorsa sicaklik'a override edilir.
_MIRROR_TARGET_JESTS = {
    "uzgun_yavas", "uzgun_derin", "ofke", "korku", "panik",
    "yalniz", "hayal_kirikligi", "sikilma",
}

# Kullanicinin kendi olumsuz duygu sinyali (1. tekil sahis)
_MIRROR_NEG_PATTERNS = [
    r"\bk[oö]t[uü]y[uü]m\b", r"\b[uü]z[uü]nl?[uü]y[uü]m\b", r"\b[uü]zg[uü]n[uü]m\b",
    r"\bsinirliyim\b", r"\bk[ıi]zg[ıi]n[ıi]m\b", r"\bgerginim\b", r"\bstresliyim\b",
    r"\bkorkuyorum\b", r"\bend[ıi]şeliyim\b", r"\btedirginim\b",
    r"\byaln[ıi]z[ıi]m\b", r"\byorgunum\b", r"\bbunald[ıi]m\b",
    r"\bmoralim bozuk\b", r"\bmoralim k[oö]t[uü]\b",
    r"\b[ıi]yi de[gğ]ilim\b", r"\b[ıi]yi hissetmiyorum\b",
    r"\bk[oö]t[uü] hissediyorum\b", r"\bberbat hissediyorum\b",
]

# Override yapma istisnalari: kullanici bir KAYIP/OLAY anlatiyor (gercek empati uygun)
_MIRROR_LOSS_PATTERNS = [
    r"\b[oö]ld[uü]\b", r"\bkaybettim\b", r"\bvefat\b",
    r"\bayr[ıi]ld[ıi]k\b", r"\bboşand[ıi]k?\b",
    r"\bhastaland[ıi]\b", r"\b[ıi]şten at[ıi]ld[ıi]m\b",
]

# Sanitize: yanit metninde bu kelimeler varsa nazik sablonla degistir
_BANNED_FEELING_WORDS = [
    "üzüldü", "üzülüyor", "üzgün", "üzdü",
    "öfkelend", "sinirlend",
    "korkma", "korktu",
    "kızdı", "kızgın",
]

# jest_id'ye gore nazik sablon yanit
_SAFE_RESPONSE_TEMPLATES = {
    "sicaklik": "Yanındayım, anlatır mısın?",
    "dinliyorum": "Buradayım, dinliyorum.",
    "uzgun_yavas": "Bu hissi anlıyorum, yanındayım.",
    "uzgun_derin": "Çok ağır bir şey, yanındayım.",
    "yalniz": "Yalnız değilsin, buradayım.",
    "hayal_kirikligi": "Bu beklediğin gibi olmamış, anlatır mısın?",
    "korku": "Güvendesin, derin nefes al.",
    "panik": "Birlikte nefes alalım, yavaş.",
    "ofke": "Bunun ağır geldiğini görüyorum.",
    "sikilma": "Anlatmak ister misin?",
    "sevgi": "Sıcak sözlerin için teşekkür ederim.",
    "sicaklik_default": "Seni dinliyorum.",
}


class LLMBridge:
    def __init__(self, config: dict, base_dir: Path):
        self.url = config["ollama_url"].rstrip("/")
        self.model = config["ollama_model"]
        self.timeout = float(config.get("request_timeout_sec", 20))
        self.use_baked_prompt = bool(config.get("use_baked_prompt", False))
        self.history_max_turns = int(config.get("history_max_turns", 6))
        # Sergi sertlestirme bayraklari
        self.mirror_override_enabled = bool(config.get("mirror_override_enabled", True))
        self.sanitize_responses = bool(config.get("sanitize_responses", True))
        # Ollama keep_alive — model RAM'de kalsin (sergi acilisi gecikmemesi icin)
        self.keep_alive = config.get("keep_alive", "60m")
        # Ollama default num_ctx=4096, sistem promptumuz ~5000 token + tarihce ile
        # kirpiliyor ve model tone/kural tablolarini goremiyor. 8192 rahat sigsin.
        self.num_ctx = int(config.get("num_ctx", 8192))
        # Ornekleme parametreleri (config'ten ayarlanabilir). Varsayilanlar
        # cesitlilik icindir: dusuk deterministiklik + frequency/presence penalty
        # -> ornek cumleleri ezberleyip papaganlamayi azaltir.
        self.temperature = float(config.get("llm_temperature", 0.75))
        self.top_p = float(config.get("llm_top_p", 0.92))
        self.repeat_penalty = float(config.get("llm_repeat_penalty", 1.15))
        self.frequency_penalty = float(config.get("llm_frequency_penalty", 0.6))
        self.presence_penalty = float(config.get("llm_presence_penalty", 0.3))
        self.num_predict = int(config.get("llm_num_predict", 160))
        # Sergi koruma: asiri uzun girdi prompt'u sisirip timeout/donma yapmasin.
        # web_server zaten 413 ile reddeder; bu, Tkinter (main.py) yolunu da korur.
        self.max_user_input_chars = int(config.get("max_user_input_chars", 240))

        prompt_path = (base_dir / config["system_prompt_path"]).resolve()
        gestures_path = (base_dir / config["gestures_path"]).resolve()
        self.system_prompt = prompt_path.read_text(encoding="utf-8")

        gdata = json.loads(gestures_path.read_text(encoding="utf-8"))
        self.valid_ids = {g["id"] for g in gdata["jestler"]}

        # Yapilandirilmis cikti semasi — Ollama'da jest_id'yi enum'a kilitler,
        # gecersiz jest uretme ihtimalini sifirlar.
        self._format_schema = {
            "type": "object",
            "properties": {
                "jest_id": {"type": "string", "enum": sorted(self.valid_ids)},
                "yogunluk": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "yanit": {"type": "string", "maxLength": 200},
            },
            "required": ["jest_id", "yogunluk", "yanit"],
        }

        # Konusma gecmisi — son N turun user/assistant ciftleri tutulur.
        self._history: list[dict] = []

        mode = "baked (modele gömülü)" if self.use_baked_prompt else "her istek (api üzerinden)"
        log.info("LLMBridge hazır — %d jest, model=%s, sistem promptu=%s, history=%d tur",
                 len(self.valid_ids), self.model, mode, self.history_max_turns)

    # ---------- Post-processing katmani ----------
    def _apply_mirror_override(self, user_text: str, jest_id: str, yanit: str) -> tuple[str, str, bool]:
        """Mirror kuralini sertlestir: model uzgun_*/ofke/korku/panik/yalniz/sikilma
        secip kullanici 1. tekil olumsuz duygu paylasiyorsa sicaklik'a override et.
        ISTISNA: kullanici kayip/olay anlatiyorsa override yapma (gercek empati uygun).
        Doner: (yeni_jest_id, yeni_yanit, override_yapildi_mi)
        """
        if not self.mirror_override_enabled:
            return jest_id, yanit, False
        if jest_id not in _MIRROR_TARGET_JESTS:
            return jest_id, yanit, False

        text = user_text.lower()
        # Kayip/olay cumlesi varsa override yapma (uzgun_derin gercek empati)
        if any(re.search(p, text) for p in _MIRROR_LOSS_PATTERNS):
            return jest_id, yanit, False
        # 1. tekil olumsuz duygu sinyali var mi?
        if not any(re.search(p, text) for p in _MIRROR_NEG_PATTERNS):
            return jest_id, yanit, False

        new_yanit = _SAFE_RESPONSE_TEMPLATES.get("sicaklik", "Yanındayım.")
        log.info("Mirror override: %s -> sicaklik (kullanici: %r)", jest_id, user_text[:40])
        return "sicaklik", new_yanit, True

    def _sanitize_yanit(self, jest_id: str, yanit: str) -> tuple[str, bool]:
        """Yanit metni kullanicinin duygu kelimesini tekrar ediyorsa nazik sablona cevir.
        Doner: (yeni_yanit, sanitize_yapildi_mi)
        """
        if not self.sanitize_responses or not yanit:
            return yanit, False
        low = yanit.lower()
        if not any(w in low for w in _BANNED_FEELING_WORDS):
            return yanit, False
        new_yanit = _SAFE_RESPONSE_TEMPLATES.get(jest_id, _SAFE_RESPONSE_TEMPLATES["sicaklik_default"])
        log.info("Sanitize: %r -> %r (jest=%s)", yanit[:50], new_yanit, jest_id)
        return new_yanit, True

    def _fallback_jest(self, yanit: str) -> str:
        """Model gecersiz jest_id urettiginde (cok nadir, schema enum kilidini asarsa)
        yanit metninin valansina gore makul bir jest sec.
        """
        text = (yanit or "").lower()
        if any(w in text for w in ("üzül", "ağır", "kötü", "kayıp", "yanındayım")):
            return "uzgun_yavas"
        if any(w in text for w in ("güzel", "harika", "sevin", "mutlu", "tebrik")):
            return "sicaklik"
        if "?" in text or any(w in text for w in ("kasted", "anlat", "tekrar")):
            return "soru_isareti"
        if any(w in text for w in ("merhaba", "selam", "hoş geldin")):
            return "selamlama"
        return "anlamadim"

    def clear_history(self) -> None:
        """Konusma gecmisini sifirla (yeni oturum/konu icin)."""
        self._history.clear()

    def warmup(self) -> bool:
        """Modeli RAM'e isit — ilk kullanici beklemesin. /api/generate ile kucuk
        bir istek gonderir; cevabin icerigi onemsiz, amac model_load."""
        try:
            r = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "ok",
                    "stream": False,
                    "think": False,
                    "keep_alive": self.keep_alive,
                    "options": {"num_predict": 1, "temperature": 0.0, "num_ctx": self.num_ctx},
                },
                timeout=120,
            )
            ok = r.status_code == 200
            log.info("Warmup %s: %s", self.model, "OK" if ok else f"HTTP {r.status_code}")
            return ok
        except requests.RequestException as e:
            log.warning("Warmup hatasi: %s", e)
            return False

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

    def list_local_models(self) -> list[dict]:
        """Lokal yuklu modelleri donder: [{name, size_gb}]."""
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=5)
            r.raise_for_status()
            out = []
            for m in r.json().get("models", []):
                size_gb = float(m.get("size", 0)) / (1024 ** 3)
                out.append({"name": m.get("name", "?"), "size_gb": size_gb})
            out.sort(key=lambda x: x["name"])
            return out
        except requests.RequestException as e:
            log.warning("Model listesi alinamadi: %s", e)
            return []

    def set_model(self, name: str) -> bool:
        """Aktif modeli degistir; konusma gecmisini sifirla."""
        name = name.strip()
        if not name or name == self.model:
            return False
        log.info("Model degistirildi: %s -> %s", self.model, name)
        self.model = name
        self._history.clear()
        return True

    def pull_model(self, name: str, on_progress) -> bool:
        """Modeli Ollama registry'sinden cek; her durum guncellemesi on_progress'e gonderilir.
        Streaming JSON (her satir bir olay): {status, completed?, total?, error?}.
        """
        name = name.strip()
        if not name:
            on_progress({"error": "model adi bos"})
            return False
        try:
            with requests.post(
                f"{self.url}/api/pull",
                json={"name": name, "stream": True},
                stream=True,
                timeout=None,
            ) as r:
                if r.status_code != 200:
                    on_progress({"error": f"http {r.status_code}: {r.text[:200]}"})
                    return False
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    on_progress(data)
                    if data.get("error"):
                        return False
            return True
        except requests.RequestException as e:
            log.error("Model indirme hatasi: %s", e)
            on_progress({"error": str(e)})
            return False

    def request(self, user_text: str) -> Optional[dict]:
        """Başarılı: {jest_id, yogunluk, yanit, meta}. Başarısız: {error: ..., meta?}"""
        t0 = time.monotonic()
        # Asiri uzun girdiyi kirp (her iki giris yolunu da korur).
        if self.max_user_input_chars > 0 and len(user_text) > self.max_user_input_chars:
            user_text = user_text[: self.max_user_input_chars]
        # Baked modda sistem promptu modele gömülü olduğundan tekrar göndermeyiz —
        # bu ~2300 token prompt eval süresi tasarrufu sağlar.
        messages: list[dict] = []
        if not self.use_baked_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        # Onceki turlar — modelin bagi kaybetmemesi icin son N user/assistant cifti
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_text})

        try:
            r = requests.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "format": self._format_schema,
                    "keep_alive": self.keep_alive,
                    # Qwen3 gibi "thinking" modellerinde dusunce tokenlari content'i
                    # bos birakir ve num_predict limiti dolar -> empty_content hatasi.
                    # think=false dusunceyi kapatir; thinking desteklemeyen modeller
                    # (qwen2.5, gemma3) bu alani gormez.
                    "think": False,
                    "options": {
                        # jest_id format-schema enum'la kilitli oldugu icin sicaklik
                        # artirmak JSON'u BOZMAZ, sadece "yanit" metnini cesitlendirir.
                        # frequency/presence penalty ornek cumlelerin ezberlenip
                        # papaganlanmasini kirar (config'ten ayarlanir).
                        "temperature": self.temperature,
                        "top_p": self.top_p,
                        "num_ctx": self.num_ctx,
                        "num_predict": self.num_predict,
                        # 1.3 Turkce'yi bozuyor (kelime atlama); 1.15 dengeli.
                        "repeat_penalty": self.repeat_penalty,
                        "frequency_penalty": self.frequency_penalty,
                        "presence_penalty": self.presence_penalty,
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
        try:
            yog = float(parsed.get("yogunluk", 0.7))
        except (TypeError, ValueError):
            yog = 0.7
        yog = max(0.0, min(1.0, yog))
        yanit = str(parsed.get("yanit", "")).strip()

        # Schema enum kilidi normalde gecersiz jest_id'yi onler; yine de gelirse
        # hatayla durmak yerine yanitin valansindan makul bir jest sec.
        meta["fallback_used"] = False
        if jest_id not in self.valid_ids:
            log.warning("Bilinmeyen jest_id: %r — fallback uygulandi", jest_id)
            jest_id = self._fallback_jest(yanit)
            meta["fallback_used"] = True

        # Post-processing: mirror override (Sorun 4) + sanitize (Sorun 5)
        jest_id, yanit, mirror_done = self._apply_mirror_override(user_text, jest_id, yanit)
        meta["mirror_override"] = mirror_done
        yanit, sanitize_done = self._sanitize_yanit(jest_id, yanit)
        meta["sanitized"] = sanitize_done

        # Basarili turu gecmise yaz — assistant turunu tam JSON olarak sakliyoruz
        # ki model formati ve onceki kararlarini tutarli sekilde gorsun.
        assistant_payload = json.dumps(
            {"jest_id": jest_id, "yogunluk": yog, "yanit": yanit},
            ensure_ascii=False,
        )
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_payload})
        limit = self.history_max_turns * 2
        if len(self._history) > limit:
            self._history = self._history[-limit:]

        return {"jest_id": jest_id, "yogunluk": yog, "yanit": yanit, "meta": meta}