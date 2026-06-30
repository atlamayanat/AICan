"""Duygu seslendirme DEMO — ayni Turkce cumleyi farkli duygularda seslendirir.

Amac: tam entegrasyondan once Piper Turkce kalitesini ve duygu farkini kulakla
yargilamak. Piper ile prosodi (hiz/ses/duraklama/cesitlilik) uygulanir, ardindan
ffmpeg ile perde (pitch) kaydirilir.

Calistir:  python orchestrator/tts/gen_demo.py
Cikti:     aican/seslendirme_demo/<NN>_<duygu>.wav
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from emotion_voice_map import prosody_for, prosody_for_va  # noqa: E402

HERE = Path(__file__).resolve().parent
# Ses adi opsiyonel arguman: python gen_demo.py [tr_TR-fahrettin-medium]
VOICE = sys.argv[1] if len(sys.argv) > 1 else "tr_TR-dfki-medium"
TAG = VOICE.split("-")[1] if "-" in VOICE else VOICE   # tr_TR-fahrettin-medium -> fahrettin
MODEL = HERE / "voices" / f"{VOICE}.onnx"
OUT_DIR = HERE.parents[1] / "seslendirme_demo"   # aican/seslendirme_demo
SR = 22050
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Icerigi notr bir cumle: tonu DUYGU tasisin, kelimeler degil.
SENTENCE = "Seni anliyorum. Bu an ikimiz icin de onemli."

# (dosya etiketi, jest_id | None, V, A)  — jest_id None ise V/A dogrudan kullanilir
DEMO = [
    ("00_notr",           None,             0.0,  0.45),
    ("01_mutluluk_yogun", "mutluluk_yogun", None, None),
    ("02_sevgi",          "sevgi",          None, None),
    ("03_huzur",          "huzur",          None, None),
    ("04_uzgun_derin",    "uzgun_derin",    None, None),
    ("05_korku",          "korku",          None, None),
    ("06_ofke",           "ofke",           None, None),
    ("07_saskinlik",      "saskinlik",      None, None),
]


def piper_synth(text: str, out_wav: Path, p: dict) -> None:
    """Piper CLI ile prosodi uygulanmis ham wav uret (metin stdin'den, UTF-8)."""
    cmd = [
        sys.executable, "-m", "piper",
        "-m", str(MODEL),
        "-f", str(out_wav),
        "--length-scale", str(p["length_scale"]),
        "--noise-scale", str(p["noise_scale"]),
        "--noise-w-scale", str(p["noise_w_scale"]),
        "--sentence-silence", str(p["sentence_silence"]),
        "--volume", str(p["volume"]),
    ]
    subprocess.run(cmd, input=text.encode("utf-8"), check=True)


def pitch_shift(in_wav: Path, out_wav: Path, semitones: float) -> None:
    """ffmpeg ile perdeyi yari-ton cinsinden kaydir (sure korunur)."""
    if abs(semitones) < 0.1:
        out_wav.write_bytes(in_wav.read_bytes())
        return
    factor = 2.0 ** (semitones / 12.0)
    af = f"asetrate={SR}*{factor:.6f},atempo={1.0 / factor:.6f},aresample={SR}"
    cmd = [FFMPEG, "-y", "-i", str(in_wav), "-af", af, str(out_wav)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    if not MODEL.exists():
        sys.exit(f"Ses modeli yok: {MODEL}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT_DIR / "_tmp.wav"
    print(f"Ses   : {VOICE}  (etiket: {TAG})")
    print(f"Cumle : {SENTENCE}")
    print(f"Cikti : {OUT_DIR}\n")
    hdr = f"{'dosya':20} {'len':>5} {'pitch':>6} {'vol':>5} {'nsc':>5} {'nw':>5} {'sil':>5}"
    print(hdr)
    print("-" * len(hdr))
    for label, jest, V, A in DEMO:
        p = prosody_for_va(V, A, 0.7) if jest is None else prosody_for(jest, 0.8)
        piper_synth(SENTENCE, tmp, p)
        final = OUT_DIR / f"{TAG}_{label}.wav"
        pitch_shift(tmp, final, p["pitch_semitones"])
        print(f"{label:20} {p['length_scale']:>5} {p['pitch_semitones']:>6} "
              f"{p['volume']:>5} {p['noise_scale']:>5} {p['noise_w_scale']:>5} "
              f"{p['sentence_silence']:>5}")
    if tmp.exists():
        tmp.unlink()
    print(f"\nTamam. '{OUT_DIR.name}' klasorunu acip 00..07 dosyalarini sirayla dinle.")


if __name__ == "__main__":
    main()
