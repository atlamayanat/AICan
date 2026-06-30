"""edge-tts (Microsoft, UCRETSIZ, cevrimici) kalite demosu — Emel + Ahmet.

Ayni cumleyi/duygulari Piper demosuyla KARSILASTIRMAK icin uretir. Duygu->prosodi
ayni emotion_voice_map'ten gelir; edge-tts'in rate/pitch/volume parametrelerine cevrilir.

Calistir:  python orchestrator/tts/gen_demo_edge.py
Cikti:     aican/seslendirme_demo/edge_<ses>_<NN>_<duygu>.mp3
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import edge_tts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from emotion_voice_map import prosody_for, prosody_for_va  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[2] / "seslendirme_demo"
SENTENCE = "Seni anlıyorum. Bu an ikimiz için de önemli."

VOICES = {"emel": "tr-TR-EmelNeural", "ahmet": "tr-TR-AhmetNeural"}
DEMO = [
    ("00_notr",           None,             0.0,  0.45),
    ("01_mutluluk_yogun", "mutluluk_yogun", None, None),
    ("03_huzur",          "huzur",          None, None),
    ("04_uzgun_derin",    "uzgun_derin",    None, None),
    ("06_ofke",           "ofke",           None, None),
]


def edge_params(p: dict):
    """emotion_voice_map prosodisini edge-tts rate/pitch/volume'una cevir."""
    rate = round((1.0 / p["length_scale"] - 1.0) * 100)   # hizli -> +%, yavas -> -%
    pitch = round(p["pitch_semitones"] * 18)              # ~18 Hz / yari ton
    vol = round((p["volume"] - 1.0) * 50)
    rate = max(-40, min(40, rate))
    pitch = max(-60, min(60, pitch))
    vol = max(-30, min(20, vol))
    return f"{rate:+d}%", f"{pitch:+d}Hz", f"{vol:+d}%"


async def gen() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Cumle : {SENTENCE}\nCikti : {OUT_DIR}\n")
    for tag, voice in VOICES.items():
        for label, jest, V, A in DEMO:
            p = prosody_for_va(V, A, 0.7) if jest is None else prosody_for(jest, 0.8)
            rate, pitch, vol = edge_params(p)
            out = OUT_DIR / f"edge_{tag}_{label}.mp3"
            c = edge_tts.Communicate(SENTENCE, voice, rate=rate, pitch=pitch, volume=vol)
            await c.save(str(out))
            print(f"{tag:6} {label:18} rate={rate:>5} pitch={pitch:>6} vol={vol:>5} -> {out.name}")
    print("\nTamam. 'seslendirme_demo' icinde edge_emel_* ve edge_ahmet_* dosyalarini dinle.")


if __name__ == "__main__":
    asyncio.run(gen())
