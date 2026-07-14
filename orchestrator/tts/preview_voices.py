"""ElevenLabs SES SECIM yardimcisi — adaylari Turkce ornek repliklerle dinlet.

Her aday ses icin sergideki gercek duygu araligini (selamlama / heyecan / merak /
uzgun) temsil eden 4 replik sentezlenir ve TEK bir .wav'da birlestirilip
tts/voice_previews/ altina yazilir. Boylece her ses icin bir dosya dinleyip
karar verirsin. Sectigin voice_id'yi config.json tts_voice'a yazariz.

ELEVENLABS_API_KEY gerekli (env ya da config.tts_elevenlabs_api_key).

Kullanim (orchestrator/ dizininden):
  python -m tts.preview_voices                 # hesabindaki TUM sesleri dinlet
  python -m tts.preview_voices <voice_id> ...  # yalnizca verilen voice_id'leri dinlet
"""
from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # orchestrator/ path'e

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import os

import requests

from web_server import SESSION_GREETING_TEXT, load_config  # noqa: E402
from tts.engine_elevenlabs import ElevenLabsEngine, _API_BASE  # noqa: E402

# Sergideki gercek duygu araligini temsil eden ornek replikler (metin, jest, yogunluk).
SAMPLES = [
    (SESSION_GREETING_TEXT, "selamlama", 0.8),
    ("Süper kelime! Çok iyi düşündün, böyle devam!", "hayranlik", 0.9),
    ("'Büyük' kelimesinin zıt anlamlısı ne dersin?", "merak", 0.85),
    ("Off, pes! Bu turu sen aldın, helal olsun sana.", "hayal_kirikligi", 0.85),
]


def _concat_wavs(wavs):
    """Ayni format (44100 mono int16) WAV bytes listesini tek WAV'a birlestir; aralara
    kisa sessizlik koy."""
    frames = b""
    sr = 44100
    gap = b"\x00\x00" * int(sr * 0.4)   # 0.4 sn sessizlik
    for w in wavs:
        if not w:
            continue
        with wave.open(io.BytesIO(w), "rb") as rf:
            sr = rf.getframerate()
            frames += rf.readframes(rf.getnframes()) + gap
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(frames)
    return buf.getvalue()


def _list_account_voices(api_key):
    r = requests.get(f"{_API_BASE}/voices", headers={"xi-api-key": api_key}, timeout=30)
    r.raise_for_status()
    return [(v["voice_id"], v.get("name", "?")) for v in r.json().get("voices", [])]


def _safe(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]


def main():
    cfg = load_config()
    api_key = cfg.get("tts_elevenlabs_api_key") or os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print("HATA: ELEVENLABS_API_KEY yok (env ya da config.tts_elevenlabs_api_key). Iptal.")
        return
    model = cfg.get("tts_elevenlabs_model", "eleven_flash_v2_5")
    language = cfg.get("tts_elevenlabs_language", "tr")

    ids = sys.argv[1:]
    if ids:
        voices = [(vid, vid) for vid in ids]
    else:
        try:
            voices = _list_account_voices(api_key)
        except Exception as e:  # noqa: BLE001
            print(f"Ses listesi alinamadi: {e}\nBir voice_id vererek dene: "
                  f"python -m tts.preview_voices <voice_id>")
            return
    if not voices:
        print("Hesapta ses bulunamadi.")
        return

    out_dir = Path(__file__).resolve().parent / "voice_previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{len(voices)} ses icin {len(SAMPLES)} replik sentezleniyor -> {out_dir}\n")

    for vid, vname in voices:
        # monthly_cap=0 -> onizleme guard'a takilmasin (kucuk metin)
        eng = ElevenLabsEngine(voice=vid, api_key=api_key, model=model,
                               language=language, monthly_cap=0,
                               usage_path=out_dir / "_preview_usage.json")
        wavs = []
        for text, jest, yog in SAMPLES:
            try:
                wavs.append(eng.synthesize(text, jest, yog))
            except Exception as e:  # noqa: BLE001
                print(f"  {vname}: '{text[:20]}...' hata: {e}")
        combined = _concat_wavs(wavs)
        if not combined:
            print(f"  {vname} ({vid}): ses uretilemedi (anahtar/kota?)")
            continue
        fpath = out_dir / f"{_safe(vname)}__{vid}.wav"
        fpath.write_bytes(combined)
        print(f"  ✔ {vname:24} -> {fpath.name}")

    print(f"\nBitti. {out_dir} icindeki dosyalari dinle, begendigin sesin dosya adindaki "
          f"voice_id'sini (…__<voice_id>.wav) bana soyle; config'e yazarim.\n")


if __name__ == "__main__":
    main()
