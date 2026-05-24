"""Noto Animated Emoji'den 96x96 piksel kareleri üretir.

Akis:
1. gestures.json'da `gorsel_tipi="emoji"` ve `emoji_kaynak="<codepoint>"` olan jestleri tara.
2. Her biri icin Google CDN'den animated WebP indir.
3. Her frame'i Pillow ile RGBA olarak coz, LANCZOS ile 96x96'ya kucult.
4. Alpha kanalini parlaklik carpani olarak siyah arka plana ezdir (RGB).
5. assets/emojis/<jest_id>/frame_NN.png olarak kaydet + onizleme GIF'leri uret.

Kullanim:
    cd orchestrator
    python prepare_emojis.py                  # tum emojiler
    python prepare_emojis.py selamlama        # tek jest
    python prepare_emojis.py --test           # sadece selamlama + onizleme (kaliteyi gormek icin)
    python prepare_emojis.py --fps 15         # farkli fps (default 12)

Cikti her jest klasorunde:
    frame_00.png ... frame_NN.png   - 96x96 RGB, runtime'da oynatilacak
    preview.gif                     - 96x96 gercek boyut animasyon
    preview_zoom.gif                - 960x960 (10x zoom) gozle inceleme icin

Lisans notu: Noto Emoji - Apache 2.0 + OFL. Atif gerekli.
"""
from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen, Request

from PIL import Image

BASE = Path(__file__).resolve().parent.parent
GESTURES_PATH = BASE / "ai" / "gestures.json"
ASSETS_DIR = BASE / "assets" / "emojis"

NOTO_URL = "https://fonts.gstatic.com/s/e/notoemoji/latest/{cp}/512.webp"
TARGET_SIZE = (96, 96)
DEFAULT_FPS = 12

USER_AGENT = "Mozilla/5.0 (AI-Body-Sergi-Prototipi) Python-urllib"


def fetch_emoji_webp(codepoint: str) -> bytes:
    url = NOTO_URL.format(cp=codepoint)
    print(f"    GET {url}")
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as r:
        return r.read()


def extract_frames(webp_bytes: bytes) -> list[Image.Image]:
    """Animated WebP'den her frame'i RGBA olarak al."""
    img = Image.open(BytesIO(webp_bytes))
    frames: list[Image.Image] = []
    n = getattr(img, "n_frames", 1)
    for i in range(n):
        img.seek(i)
        frames.append(img.convert("RGBA"))
    return frames


def resize_keep_alpha(frame: Image.Image, size: tuple[int, int]) -> Image.Image:
    return frame.resize(size, Image.Resampling.LANCZOS)


def premultiply_onto_black(rgba: Image.Image) -> Image.Image:
    """RGBA -> RGB siyah arka plan uzerine. Alpha parlaklik gibi calisir."""
    bg = Image.new("RGB", rgba.size, (0, 0, 0))
    alpha = rgba.split()[3]
    bg.paste(rgba, mask=alpha)
    return bg


def save_frames(rgb_frames: list[Image.Image], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("frame_*.png"):
        old.unlink()
    for i, f in enumerate(rgb_frames):
        f.save(out_dir / f"frame_{i:02d}.png", optimize=True)
    print(f"    -> {len(rgb_frames)} kare: {out_dir.relative_to(BASE)}")


def save_previews(rgba_frames: list[Image.Image], out_dir: Path, fps: int) -> None:
    """preview.gif (gercek boyut) + preview_zoom.gif (10x zoom) — gozle kontrol icin."""
    duration_ms = int(1000 / fps)
    # GIF saydamlik tek-bit oldugundan, RGB-on-black versiyonunu kullaniyoruz.
    rgb_on_black = [premultiply_onto_black(f) for f in rgba_frames]
    rgb_on_black[0].save(
        out_dir / "preview.gif",
        save_all=True,
        append_images=rgb_on_black[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )
    zoom = (TARGET_SIZE[0] * 10, TARGET_SIZE[1] * 10)
    zoomed = [f.resize(zoom, Image.Resampling.NEAREST) for f in rgb_on_black]
    zoomed[0].save(
        out_dir / "preview_zoom.gif",
        save_all=True,
        append_images=zoomed[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )
    print(f"    -> preview.gif + preview_zoom.gif ({fps} fps, {duration_ms} ms/frame)")


def process_jest(jest_id: str, codepoint: str, fps: int) -> dict:
    print(f"[{jest_id}]  codepoint={codepoint}")
    webp = fetch_emoji_webp(codepoint)
    raw = extract_frames(webp)
    orig_size = raw[0].size
    print(f"    Ham: {len(raw)} kare, orijinal boyut {orig_size}")

    resized = [resize_keep_alpha(f, TARGET_SIZE) for f in raw]
    rgb_frames = [premultiply_onto_black(f) for f in resized]

    out_dir = ASSETS_DIR / jest_id
    save_frames(rgb_frames, out_dir)
    save_previews(resized, out_dir, fps)
    return {"jest_id": jest_id, "frames": len(rgb_frames), "size": orig_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "jest_id", nargs="?",
        help="Tek bir jest_id (ornek: selamlama). Bos birakirsan hepsi islenir."
    )
    parser.add_argument("--test", action="store_true",
                        help="Sadece selamlama + onizlemeleri uret (kalite kontrol)")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS,
                        help=f"Onizleme GIF'i ve runtime hedef FPS (default {DEFAULT_FPS})")
    args = parser.parse_args()

    if not GESTURES_PATH.exists():
        print(f"HATA: {GESTURES_PATH} bulunamadi", file=sys.stderr)
        return 1

    data = json.loads(GESTURES_PATH.read_text(encoding="utf-8"))
    emoji_jests = [
        j for j in data["jestler"]
        if j.get("gorsel_tipi") == "emoji" and j.get("emoji_kaynak")
    ]
    if not emoji_jests:
        print("HATA: gestures.json'da gorsel_tipi='emoji' jest yok", file=sys.stderr)
        return 1

    if args.test:
        targets = [j for j in emoji_jests if j["id"] == "selamlama"]
        if not targets:
            print("HATA: selamlama jesti emoji olarak isaretli degil", file=sys.stderr)
            return 1
    elif args.jest_id:
        targets = [j for j in emoji_jests if j["id"] == args.jest_id]
        if not targets:
            print(f"HATA: '{args.jest_id}' jesti emoji olarak isaretli degil", file=sys.stderr)
            return 1
    else:
        targets = emoji_jests

    print(f"Islenecek: {len(targets)} jest, FPS={args.fps}")
    print()

    results = []
    errors = []
    for j in targets:
        try:
            results.append(process_jest(j["id"], j["emoji_kaynak"], args.fps))
        except Exception as e:
            errors.append((j["id"], str(e)))
            print(f"    HATA: {e}")

    print()
    print(f"Tamamlandi: {len(results)} basarili, {len(errors)} hatali")
    if errors:
        for jid, err in errors:
            print(f"  - {jid}: {err}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
