"""Yazılım simülatörü — 22 desen ve idle nefes.

Mantık `src/main.cpp` içindeki firmware ile birebir aynı (XY haritalama, renk
ölçekleme, hız çarpanları, idle animasyonu). Donanım yerine bir 16×16 piksel
buffer'a yazıyor; UI tarafı bu buffer'ı renderler.
"""
from __future__ import annotations

import math
import random
import time
from typing import Optional

W, H = 32, 32
CX, CY = 15.5, 15.5

SPEED_MULTS = (0.4, 0.7, 1.0, 1.5, 2.5)
SPEED_NAME_TO_ID = {
    "cok_yavas": 0, "yavas": 1, "orta": 2, "hizli": 3, "cok_hizli": 4,
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _scale(r: int, g: int, b: int, k: float) -> tuple[int, int, int]:
    k = _clamp(k, 0.0, 1.0)
    return (int(r * k), int(g * k), int(b * k))


def _scale8(c: tuple[int, int, int], factor: int) -> tuple[int, int, int]:
    r, g, b = c
    return (r * factor // 256, g * factor // 256, b * factor // 256)


class Buffer:
    """16×16 piksel buffer'ı (firmware'deki CRGB leds[] eşdeğeri)."""

    def __init__(self) -> None:
        self.pixels: list[tuple[int, int, int]] = [(0, 0, 0)] * (W * H)

    def clear(self) -> None:
        for i in range(W * H):
            self.pixels[i] = (0, 0, 0)

    def fill(self, color: tuple[int, int, int]) -> None:
        for i in range(W * H):
            self.pixels[i] = color

    def set(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < W and 0 <= y < H:
            self.pixels[y * W + x] = color

    def fade_all(self, factor: int) -> None:
        for i in range(W * H):
            self.pixels[i] = _scale8(self.pixels[i], factor)


# ============== Desen fonksiyonlari ==============
# Tum imza: (buf, t_sec, r,g,b, r2,g2,b2, intensity, speed_mult)


def pat_pulse(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    w = (math.sin(2 * math.pi * t * 0.7 * speed_mult) + 1) * 0.5
    k = intensity * (0.20 + 0.80 * w)
    buf.fill(_scale(r, g, b, k))


def _wave(buf, t, r, g, b, intensity, speed_mult, vertical, reverse):
    pos = (t * 0.6 * speed_mult) % 1.0
    bound = H if vertical else W
    band = 6
    head = (1 - pos) * (bound + band) - 1 if reverse else pos * (bound + band) - band + 1
    buf.clear()
    for d in range(band):
        p = int(head + d)
        if p < 0 or p >= bound:
            continue
        k = intensity * (1 - d / band * 0.6)
        c = _scale(r, g, b, k)
        if vertical:
            for x in range(W):
                buf.set(x, p, c)
        else:
            for y in range(H):
                buf.set(p, y, c)


def pat_wave_up(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    _wave(buf, t, r, g, b, intensity, speed_mult, True, True)


def pat_wave_down(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    _wave(buf, t, r, g, b, intensity, speed_mult, True, False)


def pat_wave_left(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    _wave(buf, t, r, g, b, intensity, speed_mult, False, True)


def pat_wave_right(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    _wave(buf, t, r, g, b, intensity, speed_mult, False, False)


def _ripple(buf, t, r, g, b, intensity, speed_mult, out):
    pos = (t * 1.0 * speed_mult) % 1.0
    if not out:
        pos = 1.0 - pos
    radius = pos * 22.0
    buf.clear()
    band_w = 2.5
    for y in range(H):
        for x in range(W):
            d = math.sqrt((x - CX) ** 2 + (y - CY) ** 2)
            diff = abs(d - radius)
            if diff < band_w:
                k = intensity * (1 - diff / band_w)
                buf.set(x, y, _scale(r, g, b, k))


def pat_ripple_out(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    _ripple(buf, t, r, g, b, intensity, speed_mult, True)


def pat_ripple_in(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    _ripple(buf, t, r, g, b, intensity, speed_mult, False)


def pat_sparkle(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.fade_all(220)
    has_second = (r2 + g2 + b2) > 0
    n = int(8 + 18 * speed_mult)
    for _ in range(n):
        if random.randint(0, 99) >= 50:
            continue
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        if has_second and random.randint(0, 1) == 0:
            cr, cg, cb = r2, g2, b2
        else:
            cr, cg, cb = r, g, b
        k = intensity * (0.55 + random.random() * 0.45)
        buf.set(x, y, _scale(cr, cg, cb, k))


def pat_drop(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.fade_all(200)
    xs = (5, 11, 16, 21, 27)
    for k_idx, x in enumerate(xs):
        phase = (t * 0.45 * speed_mult + k_idx * 0.2) % 1.0
        y = int(phase * (H + 3)) - 1
        if 0 <= y < H:
            buf.set(x, y, _scale(r, g, b, intensity))
            if y + 1 < H:
                buf.set(x, y + 1, _scale(r, g, b, intensity * 0.6))


def pat_fade(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    cycle_len = 2.5
    c_pos = ((t * speed_mult) % cycle_len) / cycle_len
    k = intensity * (1 - c_pos)
    buf.fill(_scale(r, g, b, k))


def pat_scan(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    pos = (t * 0.7 * speed_mult) % 1.0
    y = int(pos * H)
    buf.clear()
    if 0 <= y < H:
        c = _scale(r, g, b, intensity)
        for x in range(W):
            buf.set(x, y, c)


def pat_static_glow(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    w = (math.sin(2 * math.pi * t * 0.3 * speed_mult) + 1) * 0.5
    k = intensity * (0.55 + 0.15 * w)
    buf.fill(_scale(r, g, b, k))


def pat_three_dots(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.clear()
    dots = (8, 16, 24)
    y = 16
    radius = 2  # 32x32 icin daha buyuk nokta (5x5 alan)
    for i, dx in enumerate(dots):
        phase = t * 1.2 * speed_mult - i * 0.33
        w = (math.sin(2 * math.pi * phase) + 1) * 0.5
        if w < 0.25:
            w = 0
        k = intensity * w
        c = _scale(r, g, b, k)
        for ddy in range(-radius, radius + 1):
            for ddx in range(-radius, radius + 1):
                if ddx * ddx + ddy * ddy <= radius * radius:
                    buf.set(dx + ddx, y + ddy, c)


def pat_spiral_out(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.fade_all(220)
    angle = t * 4.0 * speed_mult
    radius = ((t * speed_mult) % 1.0) * 18.0
    # Daha kalin iz - 2x2 piksel
    cx = CX + radius * math.cos(angle)
    cy = CY + radius * math.sin(angle)
    c = _scale(r, g, b, intensity)
    for dx in (0, 1):
        for dy in (0, 1):
            buf.set(int(cx + dx), int(cy + dy), c)


def pat_shake(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.clear()
    ox = random.randint(-2, 2)
    oy = random.randint(-2, 2)
    c = _scale(r, g, b, intensity * 0.85)
    for y in range(H):
        for x in range(W):
            buf.set(x + ox, y + oy, c)


def pat_diagonal_sweep(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.clear()
    pos = (t * 0.4 * speed_mult) % 1.0
    offset = pos * 62.0 - 4.0  # 32x32 icin (2*W+offset)
    band = 4.0
    for y in range(H):
        for x in range(W):
            d = abs((x + y) - offset)
            if d < band:
                k = intensity * (1 - d / band)
                buf.set(x, y, _scale(r, g, b, k))


def pat_two_color_swing(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    w = (math.sin(2 * math.pi * t * 0.6 * speed_mult) + 1) * 0.5
    has_second = (r2 + g2 + b2) > 0
    if has_second:
        cr = int(r * (1 - w) + r2 * w)
        cg = int(g * (1 - w) + g2 * w)
        cb = int(b * (1 - w) + b2 * w)
    else:
        cr, cg, cb = r, g, b
    buf.fill(_scale(cr, cg, cb, intensity))


def pat_cross(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.clear()
    w = (math.sin(2 * math.pi * t * 0.7 * speed_mult) + 1) * 0.5
    k = intensity * (0.5 + 0.5 * w)
    c = _scale(r, g, b, k)
    for i in range(W):
        buf.set(i, i, c)
        buf.set(i, H - 1 - i, c)


def pat_border_only(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.clear()
    w = (math.sin(2 * math.pi * t * 0.5 * speed_mult) + 1) * 0.5
    k = intensity * (0.55 + 0.45 * w)
    c = _scale(r, g, b, k)
    for x in range(W):
        buf.set(x, 0, c)
        buf.set(x, H - 1, c)
    for y in range(1, H - 1):
        buf.set(0, y, c)
        buf.set(W - 1, y, c)


def pat_split(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    buf.clear()
    pos = (t * 0.5 * speed_mult) % 1.0
    gap = int(pos * 15)
    top, bot = 15 - gap, 16 + gap
    c = _scale(r, g, b, intensity)
    if top >= 0:
        for x in range(W):
            buf.set(x, top, c)
            buf.set(x, max(0, top - 1), c)
    if bot < H:
        for x in range(W):
            buf.set(x, bot, c)
            buf.set(x, min(H - 1, bot + 1), c)


def _plot_seg(buf, x0, y0, x1, y1, prog, c, thickness=1):
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        buf.set(x0, y0, c)
        return
    n = min(int(prog * steps + 0.5), steps)
    for i in range(n + 1):
        x = int(x0 + dx * i / steps + 0.5)
        y = int(y0 + dy * i / steps + 0.5)
        buf.set(x, y, c)
        # Thicker line for 32x32 visibility
        if thickness >= 2:
            buf.set(x + 1, y, c)
            buf.set(x, y + 1, c)
        if thickness >= 3:
            buf.set(x - 1, y, c)
            buf.set(x, y - 1, c)


def pat_checkmark(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    cycle = (t * 0.4 * speed_mult) % 1.0
    if cycle < 0.4:
        p1, p2 = cycle / 0.4, 0.0
    elif cycle < 0.85:
        p1, p2 = 1.0, (cycle - 0.4) / 0.45
    else:
        p1, p2 = 1.0, 1.0
    buf.clear()
    c = _scale(r, g, b, intensity)
    # 32x32 olceginde ✓ : (6,18) -> (14,26) -> (26,8)
    _plot_seg(buf, 6, 18, 14, 26, p1, c, thickness=3)
    _plot_seg(buf, 14, 26, 26, 8, p2, c, thickness=3)


def pat_x_mark(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    cycle = (t * 0.4 * speed_mult) % 1.0
    if cycle < 0.4:
        p1, p2 = cycle / 0.4, 0.0
    elif cycle < 0.85:
        p1, p2 = 1.0, (cycle - 0.4) / 0.45
    else:
        p1, p2 = 1.0, 1.0
    buf.clear()
    c = _scale(r, g, b, intensity)
    # 32x32 olceginde ✗ : kosegenler (6,6)-(25,25) ve (25,6)-(6,25)
    _plot_seg(buf, 6, 6, 25, 25, p1, c, thickness=3)
    _plot_seg(buf, 25, 6, 6, 25, p2, c, thickness=3)


# --- Sembolik şekil pikselleri ---

def _build_heart() -> tuple[tuple[int, int], ...]:
    """32x32 olceginde dolu kalp sekli."""
    pts: set[tuple[int, int]] = set()
    # Iki ust tumsek (rows 3-5, ayri ayri)
    for x in range(5, 11):
        pts.add((x, 3))
    for x in range(21, 27):
        pts.add((x, 3))
    for x in range(4, 13):
        pts.add((x, 4))
    for x in range(19, 28):
        pts.add((x, 4))
    for x in range(3, 14):
        pts.add((x, 5))
    for x in range(18, 29):
        pts.add((x, 5))
    # Birlesme noktasi
    for x in range(3, 29):
        pts.add((x, 6))
    # Tam genislik (rows 7-9)
    for y in (7, 8, 9):
        for x in range(2, 30):
            pts.add((x, y))
    # Asagiya dogru daralma (rows 10-22)
    narrow = [
        (3, 28), (4, 27), (5, 26), (6, 25), (7, 24), (8, 23),
        (9, 22), (10, 21), (11, 20), (12, 19), (13, 18), (14, 17), (15, 16),
    ]
    for i, (left, right) in enumerate(narrow):
        y = 10 + i
        for x in range(left, right + 1):
            pts.add((x, y))
    return tuple(sorted(pts))


HEART_PIXELS = _build_heart()

def _build_question_body() -> tuple[tuple[int, int], ...]:
    """32x32 olceginde soru isareti govdesi."""
    pts: set[tuple[int, int]] = set()
    # Ust kavis (rows 4-7)
    for x in range(10, 22):
        pts.add((x, 4))
        pts.add((x, 5))
    for y in range(6, 9):
        pts.add((9, y)); pts.add((10, y))
        pts.add((21, y)); pts.add((22, y))
    # Sag kenar asagiya egilim
    for y, (a, b) in zip(range(9, 16), [(20, 22), (19, 21), (18, 20), (17, 19), (16, 18), (15, 17), (15, 16)]):
        for x in range(a, b + 1):
            pts.add((x, y))
    # Dikey govde (rows 16-22)
    for y in range(16, 22):
        for x in range(14, 18):
            pts.add((x, y))
    return tuple(sorted(pts))


def _build_question_dot() -> tuple[tuple[int, int], ...]:
    return tuple((x, y) for y in range(25, 29) for x in range(14, 18))


QUESTION_BODY = _build_question_body()
QUESTION_DOT = _build_question_dot()


def pat_heart(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Kalp atışı — iki hızlı vuruş, sonra dinlenme."""
    buf.clear()
    cycle = (t * 0.8 * speed_mult) % 1.0
    if cycle < 0.15:
        beat = math.sin(math.pi * cycle / 0.15)
    elif cycle < 0.30:
        beat = 0.25
    elif cycle < 0.45:
        beat = math.sin(math.pi * (cycle - 0.30) / 0.15) * 0.75
    else:
        beat = max(0.25 - (cycle - 0.45) * 0.4, 0.0)
    k = intensity * (0.40 + 0.60 * beat)
    has_second = (r2 + g2 + b2) > 0
    if has_second:
        cr = int(r * (1 - beat * 0.4) + r2 * beat * 0.4)
        cg = int(g * (1 - beat * 0.4) + g2 * beat * 0.4)
        cb = int(b * (1 - beat * 0.4) + b2 * beat * 0.4)
    else:
        cr, cg, cb = r, g, b
    c = _scale(cr, cg, cb, k)
    for (x, y) in HEART_PIXELS:
        buf.set(x, y, c)


def pat_question_mark(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Soru işareti — gövde yumuşak nefes alır, alttaki nokta ayrı blink yapar."""
    buf.clear()
    body_w = (math.sin(2 * math.pi * t * 0.5 * speed_mult) + 1) * 0.5
    k_body = intensity * (0.55 + 0.30 * body_w)
    c_body = _scale(r, g, b, k_body)
    for (x, y) in QUESTION_BODY:
        buf.set(x, y, c_body)

    dot_phase = (t * 0.7 * speed_mult) % 1.0
    if dot_phase < 0.55:
        k_dot = intensity * (0.85 + 0.15 * math.sin(math.pi * dot_phase / 0.55))
    else:
        k_dot = intensity * 0.30
    c_dot = _scale(r, g, b, k_dot)
    for (x, y) in QUESTION_DOT:
        buf.set(x, y, c_dot)


def pat_question_shake(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Sallanan soru işareti — kafası karışmış 'anlamadım' hissi."""
    buf.clear()
    ox = random.randint(-1, 1)
    oy = random.randint(-1, 1)
    body_w = (math.sin(2 * math.pi * t * 0.7 * speed_mult) + 1) * 0.5
    k_body = intensity * (0.50 + 0.30 * body_w)
    c_body = _scale(r, g, b, k_body)
    for (x, y) in QUESTION_BODY:
        buf.set(x + ox, y + oy, c_body)
    dot_phase = (t * 1.0 * speed_mult) % 1.0
    if dot_phase < 0.55:
        k_dot = intensity * (0.80 + 0.20 * math.sin(math.pi * dot_phase / 0.55))
    else:
        k_dot = intensity * 0.30
    c_dot = _scale(r, g, b, k_dot)
    for (x, y) in QUESTION_DOT:
        buf.set(x + ox, y + oy, c_dot)


# --- Yıldız (compass rose / 8-point starburst) ---

def _build_star() -> tuple[tuple[int, int], ...]:
    """32x32 olceginde 8-uclu yildiz: dikey + yatay cubuk + iki capraz."""
    pts: set[tuple[int, int]] = set()
    for y in range(H):
        pts.add((15, y)); pts.add((16, y))
    for x in range(W):
        pts.add((x, 15)); pts.add((x, 16))
    for i in range(H):
        pts.add((i, i))
        pts.add((H - 1 - i, i))
    return tuple(sorted(pts))


STAR_PIXELS = _build_star()


def pat_star(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Yıldız — gövde nefes alır, etrafa rastgele ikincil renkte parıltı saçar."""
    buf.clear()
    pulse = (math.sin(2 * math.pi * t * 0.5 * speed_mult) + 1) * 0.5
    k = intensity * (0.55 + 0.45 * pulse)
    c = _scale(r, g, b, k)
    for (x, y) in STAR_PIXELS:
        buf.set(x, y, c)
    has_second = (r2 + g2 + b2) > 0
    if has_second:
        n = int(2 + 4 * speed_mult)
        for _ in range(n):
            if random.randint(0, 99) >= 35:
                continue
            x = random.randint(0, W - 1)
            y = random.randint(0, H - 1)
            k_sp = intensity * (0.6 + random.random() * 0.4)
            buf.set(x, y, _scale(r2, g2, b2, k_sp))


# --- Ünlem işareti ---

EXCLAMATION_BODY = tuple((x, y) for y in range(3, 21) for x in range(13, 19))
EXCLAMATION_DOT = tuple((x, y) for y in range(24, 29) for x in range(13, 19))


def pat_exclamation(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Ünlem — başlangıçta keskin flash, sonra hızlı pulse."""
    buf.clear()
    cycle = (t * 1.0 * speed_mult) % 1.0
    if cycle < 0.10:
        k_main = intensity
    else:
        w = (math.sin(2 * math.pi * t * 1.0 * speed_mult) + 1) * 0.5
        k_main = intensity * (0.55 + 0.40 * w)
    c = _scale(r, g, b, k_main)
    for (x, y) in EXCLAMATION_BODY:
        buf.set(x, y, c)
    dot_pulse = (math.sin(2 * math.pi * t * 1.6 * speed_mult) + 1) * 0.5
    k_dot = intensity * (0.70 + 0.30 * dot_pulse)
    c_dot = _scale(r, g, b, k_dot)
    for (x, y) in EXCLAMATION_DOT:
        buf.set(x, y, c_dot)


# --- Yüz şekilleri (smile / sad) ---

# 32x32 yuz: gozler 4x4 blok, agiz egrisi
SMILE_EYES = tuple(
    (x, y) for x in range(8, 12) for y in range(9, 13)
) + tuple(
    (x, y) for x in range(20, 24) for y in range(9, 13)
)

SMILE_MOUTH = (
    # Iki dis kose (rows 18)
    (7, 18), (8, 18), (23, 18), (24, 18),
    # Egim (rows 19-20)
    (8, 19), (9, 19), (10, 19), (21, 19), (22, 19), (23, 19),
    (10, 20), (11, 20), (12, 20), (19, 20), (20, 20), (21, 20),
    # Agiz tabani (rows 21-22)
    (12, 21), (13, 21), (14, 21), (15, 21), (16, 21), (17, 21), (18, 21), (19, 21),
    (13, 22), (14, 22), (15, 22), (16, 22), (17, 22), (18, 22),
)
SMILE_PIXELS = SMILE_EYES + SMILE_MOUTH

# Uzgun yuz: ayni gozler, ters agiz (cember asagiya)
SAD_MOUTH = (
    # Agiz tepesi (rows 19-20)
    (13, 19), (14, 19), (15, 19), (16, 19), (17, 19), (18, 19),
    (12, 20), (13, 20), (14, 20), (15, 20), (16, 20), (17, 20), (18, 20), (19, 20),
    # Egim asagidan yukariya (rows 21-22)
    (10, 21), (11, 21), (12, 21), (19, 21), (20, 21), (21, 21),
    (8, 22), (9, 22), (10, 22), (21, 22), (22, 22), (23, 22),
    # Dis koseler (rows 23)
    (7, 23), (8, 23), (23, 23), (24, 23),
)
SAD_PIXELS = SMILE_EYES + SAD_MOUTH


def pat_smile_face(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Gülen yüz — yumuşak nefes pulsu."""
    buf.clear()
    pulse = (math.sin(2 * math.pi * t * 0.4 * speed_mult) + 1) * 0.5
    k = intensity * (0.60 + 0.35 * pulse)
    c = _scale(r, g, b, k)
    for (x, y) in SMILE_PIXELS:
        buf.set(x, y, c)


def pat_sad_face(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Üzgün yüz — yavaş, ağır pulse."""
    buf.clear()
    pulse = (math.sin(2 * math.pi * t * 0.25 * speed_mult) + 1) * 0.5
    k = intensity * (0.50 + 0.30 * pulse)
    c = _scale(r, g, b, k)
    for (x, y) in SAD_PIXELS:
        buf.set(x, y, c)


# --- Damla (gözyaşı) ---

def pat_tear_drop(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Yavaşça düşen tek bir gözyaşı (32x32 olceginde buyuk damla)."""
    buf.clear()
    cycle = (t * 0.25 * speed_mult) % 1.0
    head_y = int(cycle * 36) - 4  # y=-4..32 arasi
    cx = 15  # merkez kolon
    c_main = _scale(r, g, b, intensity)
    c_dim = _scale(r, g, b, intensity * 0.55)
    c_trail = _scale(r, g, b, intensity * 0.25)
    # Iz (yukaridan asagiya hafif gradyan)
    for off in range(-4, -1):
        py = head_y + off
        if 0 <= py < H:
            buf.set(cx, py, c_trail)
    # Ust sivri
    if 0 <= head_y - 1 < H:
        buf.set(cx, head_y - 1, c_dim)
    # Govde - 3 piksel genis 2 piksel uzun
    if 0 <= head_y < H:
        buf.set(cx - 1, head_y, c_main)
        buf.set(cx, head_y, c_main)
        buf.set(cx + 1, head_y, c_main)
    if 0 <= head_y + 1 < H:
        buf.set(cx - 1, head_y + 1, c_main)
        buf.set(cx, head_y + 1, c_main)
        buf.set(cx + 1, head_y + 1, c_main)
    # Alt yuvarlama
    if 0 <= head_y + 2 < H:
        buf.set(cx, head_y + 2, c_dim)


# --- Ateş (alev) ---

def _build_fire_base() -> tuple[tuple[int, int], ...]:
    """32x32 olceginde alev tabani - asagidan yukariya daralan ucgen."""
    pts: set[tuple[int, int]] = set()
    # Genislik tabandan tepeye azaliyor
    widths = [
        (8, 23, 31),    # row 31: cols 8-23
        (8, 23, 30),
        (9, 22, 29),
        (9, 22, 28),
        (10, 21, 27),
        (10, 21, 26),
        (11, 20, 25),
        (12, 19, 24),
        (12, 19, 23),
        (13, 18, 22),
        (13, 18, 21),
        (14, 17, 20),
        (14, 17, 19),
        (15, 16, 18),
    ]
    for left, right, y in widths:
        for x in range(left, right + 1):
            pts.add((x, y))
    return tuple(sorted(pts))


FIRE_BASE = _build_fire_base()


def pat_fire(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Alev — taban sabit, ustler kipirdar (32x32 buyuk alev)."""
    buf.clear()
    flicker = (math.sin(2 * math.pi * t * 4.0 * speed_mult) + 1) * 0.5
    base_k = intensity * (0.65 + 0.30 * flicker)
    c_base = _scale(r, g, b, base_k)
    for (x, y) in FIRE_BASE:
        buf.set(x, y, c_base)
    has_second = (r2 + g2 + b2) > 0
    n_tips = int(10 + 18 * speed_mult)
    for _ in range(n_tips):
        if random.randint(0, 99) >= 60:
            continue
        x = 10 + random.randint(0, 11)
        y = 10 + random.randint(0, 12)
        use_second = has_second and random.randint(0, 1) == 0
        cr, cg, cb = (r2, g2, b2) if use_second else (r, g, b)
        k = intensity * (0.45 + random.random() * 0.45)
        buf.set(x, y, _scale(cr, cg, cb, k))


# --- Şimşek ---

def _build_lightning() -> tuple[tuple[int, int], ...]:
    """32x32 olceginde kalin zigzag simsek — sag-ust koseden sol-alta."""
    pts: set[tuple[int, int]] = set()
    # Ust kisim: (20,2) -> (12,12), kalinlik 3
    for i in range(0, 11):
        x = 20 - i + i // 2
        y = 2 + i
        for dx in (-1, 0, 1):
            pts.add((x + dx, y))
    # Genisleme noktasi (rows 11-13)
    for x in range(8, 24):
        pts.add((x, 12))
    for x in range(10, 22):
        pts.add((x, 13))
    # Alt kisim: (12,13) -> (4,28), kalinlik 3
    for i in range(0, 16):
        x = 12 - i // 2
        y = 14 + i
        for dx in (-1, 0, 1):
            pts.add((x + dx, y))
    return tuple(sorted(pts))


LIGHTNING_PIXELS = _build_lightning()


def pat_lightning(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Şimşek — ani parlak çakma, ardından karanlık."""
    buf.clear()
    cycle = (t * 0.9 * speed_mult) % 1.0
    if cycle < 0.05:
        c = _scale(255, 255, 255, intensity)
    elif cycle < 0.18:
        fade = 1.0 - (cycle - 0.05) / 0.13
        c = _scale(r, g, b, intensity * fade)
    else:
        return
    for (x, y) in LIGHTNING_PIXELS:
        buf.set(x, y, c)


# --- Oklar (yukarı / aşağı) ---

def _build_arrow_up() -> tuple[tuple[int, int], ...]:
    """32x32 olceginde yukari ok: ucgen ust + genis govde."""
    pts: set[tuple[int, int]] = set()
    # Ucgen ust (rows 4-9, genisleyerek)
    triangle = [
        (15, 16, 4),
        (14, 17, 5),
        (13, 18, 6),
        (12, 19, 7),
        (11, 20, 8),
        (10, 21, 9),
    ]
    for left, right, y in triangle:
        for x in range(left, right + 1):
            pts.add((x, y))
    # Govde 4 piksel genis (cols 14-17, rows 10-27)
    for y in range(10, 28):
        for x in range(14, 18):
            pts.add((x, y))
    return tuple(sorted(pts))


def _build_arrow_down() -> tuple[tuple[int, int], ...]:
    """32x32 olceginde asagi ok: govde + ucgen alt."""
    pts: set[tuple[int, int]] = set()
    # Govde 4 piksel genis (cols 14-17, rows 4-21)
    for y in range(4, 22):
        for x in range(14, 18):
            pts.add((x, y))
    # Ucgen alt (rows 22-27, genisleyip daralarak)
    triangle = [
        (10, 21, 22),
        (11, 20, 23),
        (12, 19, 24),
        (13, 18, 25),
        (14, 17, 26),
        (15, 16, 27),
    ]
    for left, right, y in triangle:
        for x in range(left, right + 1):
            pts.add((x, y))
    return tuple(sorted(pts))


ARROW_UP_PIXELS = _build_arrow_up()
ARROW_DOWN_PIXELS = _build_arrow_down()


def pat_arrow_up(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Yukari ok — uca dogru parlaklik gradyani."""
    buf.clear()
    pulse = (math.sin(2 * math.pi * t * 0.5 * speed_mult) + 1) * 0.5
    k_top = intensity * (0.70 + 0.30 * pulse)
    k_bottom = intensity * (0.40 + 0.20 * pulse)
    for (x, y) in ARROW_UP_PIXELS:
        ratio = 1 - (y - 4) / 24
        k = k_bottom + (k_top - k_bottom) * ratio
        buf.set(x, y, _scale(r, g, b, k))


def pat_arrow_down(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Asagi ok — asagiya dogru parlaklik gradyani."""
    buf.clear()
    pulse = (math.sin(2 * math.pi * t * 0.4 * speed_mult) + 1) * 0.5
    k_top = intensity * (0.30 + 0.15 * pulse)
    k_bottom = intensity * (0.65 + 0.30 * pulse)
    for (x, y) in ARROW_DOWN_PIXELS:
        ratio = (y - 4) / 24
        k = k_top + (k_bottom - k_top) * ratio
        buf.set(x, y, _scale(r, g, b, k))


# --- Yalnız tek nokta ---

def pat_lonely_dot(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Tek bir kucuk nokta merkezde, cok yavas nefes alir (32x32 buyuk nokta)."""
    buf.clear()
    pulse = (math.sin(2 * math.pi * t * 0.20 * speed_mult) + 1) * 0.5
    k = intensity * (0.40 + 0.45 * pulse)
    c = _scale(r, g, b, k)
    # 4x4 merkez nokta
    for dx in range(-2, 2):
        for dy in range(-2, 2):
            buf.set(15 + dx + 1, 15 + dy + 1, c)


# --- Zıplayan toplar ---

def pat_bouncing(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """4 top farkli tempolarda ziplar — 32x32 olceginde 3x3 toplar."""
    buf.clear()
    has_second = (r2 + g2 + b2) > 0
    balls = [(5, 0.0), (12, 0.25), (20, 0.50), (27, 0.75)]
    for cx, phase in balls:
        cycle = (t * 0.7 * speed_mult + phase) % 1.0
        bounce = abs(math.sin(math.pi * cycle))
        cy = 28 - int(bounce * 24)
        if not (0 <= cy < H):
            continue
        use_second = has_second and (int(t * 2 * speed_mult + phase * 3) % 2 == 0)
        cr, cg, cb = (r2, g2, b2) if use_second else (r, g, b)
        c = _scale(cr, cg, cb, intensity)
        # 3x3 top
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx * dx + dy * dy <= 2:
                    buf.set(cx + dx, cy + dy, c)


# --- Saat ---

def pat_clock(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Donen saat ibresi — bekleme hissi (32x32 buyuk saat)."""
    buf.clear()
    cx, cy = CX, CY
    radius_marks = 13.5
    # 12 saat isareti — 2x2 sonuk blok
    c_marks = _scale(r, g, b, intensity * 0.35)
    for h in range(12):
        angle = 2 * math.pi * h / 12 - math.pi / 2
        mx = cx + radius_marks * math.cos(angle)
        my = cy + radius_marks * math.sin(angle)
        for dx in (0, 1):
            for dy in (0, 1):
                buf.set(int(mx + dx), int(my + dy), c_marks)
    # Ibre — 12 piksel uzunlukta, 2 piksel kalin
    hand_angle = 2 * math.pi * (t * 0.25 * speed_mult) - math.pi / 2
    c_hand = _scale(r, g, b, intensity)
    cosA = math.cos(hand_angle)
    sinA = math.sin(hand_angle)
    for r_step in range(1, 12):
        for thick in (-1, 0, 1):
            # ibreyi cogalt - dik yonde 1 piksel kalinlastir
            px = cx + r_step * cosA - thick * sinA
            py = cy + r_step * sinA + thick * cosA
            buf.set(int(px), int(py), c_hand)
    # Merkez 4x4
    for dx in range(-2, 2):
        for dy in range(-2, 2):
            buf.set(15 + dx + 1, 15 + dy + 1, c_hand)


# --- Kaotik flaş ---

def pat_chaotic_flash(buf, t, r, g, b, r2, g2, b2, intensity, speed_mult):
    """Panik icin kaotik rastgele flaslar (32x32 yogun)."""
    buf.fade_all(170)
    has_second = (r2 + g2 + b2) > 0
    n = int(25 + 40 * speed_mult)
    for _ in range(n):
        if random.randint(0, 99) >= 65:
            continue
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        use_second = has_second and random.randint(0, 1) == 0
        cr, cg, cb = (r2, g2, b2) if use_second else (r, g, b)
        k = intensity * (0.7 + random.random() * 0.3)
        buf.set(x, y, _scale(cr, cg, cb, k))


PATTERN_DISPATCH = {
    "pulse": pat_pulse,
    "wave_up": pat_wave_up,
    "wave_down": pat_wave_down,
    "wave_left": pat_wave_left,
    "wave_right": pat_wave_right,
    "ripple_out": pat_ripple_out,
    "ripple_in": pat_ripple_in,
    "sparkle": pat_sparkle,
    "drop": pat_drop,
    "fade": pat_fade,
    "scan": pat_scan,
    "static_glow": pat_static_glow,
    "three_dots": pat_three_dots,
    "spiral_out": pat_spiral_out,
    "shake": pat_shake,
    "diagonal_sweep": pat_diagonal_sweep,
    "two_color_swing": pat_two_color_swing,
    "cross_pattern": pat_cross,
    "border_only": pat_border_only,
    "split": pat_split,
    "checkmark": pat_checkmark,
    "x_mark": pat_x_mark,
    "heart": pat_heart,
    "question_mark": pat_question_mark,
    "question_shake": pat_question_shake,
    "star": pat_star,
    "exclamation": pat_exclamation,
    "smile_face": pat_smile_face,
    "sad_face": pat_sad_face,
    "tear_drop": pat_tear_drop,
    "fire": pat_fire,
    "lightning": pat_lightning,
    "arrow_up": pat_arrow_up,
    "arrow_down": pat_arrow_down,
    "lonely_dot": pat_lonely_dot,
    "bouncing": pat_bouncing,
    "clock": pat_clock,
    "chaotic_flash": pat_chaotic_flash,
}


# ============== Engine ==============


class GestureEngine:
    """Aktif jest durumunu tutar, her frame için buffer'ı günceller."""

    def __init__(self, gestures_data: dict) -> None:
        self.gestures = {g["id"]: g for g in gestures_data["jestler"]}
        self.buf = Buffer()
        self.active: Optional[dict] = None
        self.start: float = 0.0
        self.duration: float = 0.0
        self.intensity: float = 1.0
        self._t0 = time.monotonic()

    def trigger(self, jest_id: str, yogunluk: Optional[float] = None,
                sure_sn: Optional[float] = None) -> bool:
        """sure_sn=None ise jest sonsuza kadar oynar (stop() ile durdurulur)."""
        g = self.gestures.get(jest_id)
        if not g:
            return False
        anim = g["animasyon"]
        self.active = g
        self.start = time.monotonic()
        self.duration = float("inf") if sure_sn is None else float(sure_sn)
        self.intensity = float(yogunluk if yogunluk is not None else anim["yogunluk_varsayilan"])
        return True

    def stop(self) -> Optional[str]:
        """Aktif jesti durdur, idle'a don. Durdurulan jestin id'sini doner."""
        if not self.active:
            return None
        jid = self.active["id"]
        self.active = None
        return jid

    def render(self) -> list[tuple[int, int, int]]:
        now = time.monotonic()
        if self.active and (self.duration == float("inf") or (now - self.start) < self.duration):
            self._render_active(now)
        else:
            self.active = None
            self._render_idle(now)
        return self.buf.pixels

    def _render_active(self, now: float) -> None:
        g = self.active
        anim = g["animasyon"]
        spd = SPEED_MULTS[SPEED_NAME_TO_ID[anim["hiz"]]]
        elapsed = now - self.start
        r, gg, b = anim["ana_renk"]
        sec = anim.get("ikincil_renk")
        r2, g2, b2 = (sec[0], sec[1], sec[2]) if sec else (0, 0, 0)
        fn = PATTERN_DISPATCH.get(anim["desen"])
        if fn is None:
            self.buf.clear()
            return
        fn(self.buf, elapsed, r, gg, b, r2, g2, b2, self.intensity, spd)

    def _render_idle(self, now: float) -> None:
        t = now - self._t0
        w = (math.sin(2 * math.pi * t / 4.0) + 1) * 0.5
        k = 0.18 + 0.22 * w
        self.buf.fill(_scale(60, 130, 150, k))

    def is_active(self) -> bool:
        if not self.active:
            return False
        if self.duration == float("inf"):
            return True
        return (time.monotonic() - self.start) < self.duration

    def active_id(self) -> Optional[str]:
        return self.active["id"] if self.active else None
