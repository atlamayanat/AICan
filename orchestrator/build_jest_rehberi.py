"""ai/gestures.json'dan otomatik jest rehberi (JESTLER.md) üretir.

Kullanim:
    cd orchestrator
    python build_jest_rehberi.py

Her gestures.json degisikliginden sonra calistir — rehber yeniden uretilir.
Yeni jest eklediginde:
1. ai/gestures.json'a yeni jest objesini ekle (id, animasyon, aciklama, tetikleyiciler).
2. Bu scripti calistir.
3. Kok dizindeki JESTLER.md otomatik guncellenir.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
GESTURES_PATH = PROJECT_ROOT / "ai" / "gestures.json"
OUTPUT_PATH = PROJECT_ROOT / "JESTLER.md"


# Desen adi -> kullaniciya gosterilecek aciklama
DESEN_GORSEL = {
    "smile_face":      ("😊", "gülen yüz — gözler + yukarı kıvrılan ağız"),
    "sad_face":        ("☹",  "üzgün yüz — gözler + aşağı kıvrılan ağız"),
    "heart":           ("♥",  "atan kalp — iki tümsek + V tabanı, nabız atışı"),
    "star":            ("⭐", "yıldız — 8 uçlu pusula + etrafta parıltı"),
    "bouncing":        ("🏀", "zıplayan toplar — 4 top farklı tempolarda"),
    "static_glow":     ("○",  "sabit parıltı — tüm ekran yumuşak nefes"),
    "pulse":           ("◌",  "nabız — tüm ekran sin dalgasıyla parlar/söner"),
    "arrow_up":        ("↑",  "yukarı ok — üçgen baş + kalın gövde"),
    "arrow_down":      ("↓",  "aşağı ok — kalın gövde + üçgen alt"),
    "tear_drop":       ("💧", "gözyaşı — yavaşça düşen büyük damla + iz"),
    "lonely_dot":      ("●",  "yalnız nokta — tek merkez disk, çok yavaş nefes"),
    "lightning":       ("⚡", "şimşek — sağ-üst köşeden sol-alta kalın zigzag"),
    "chaotic_flash":   ("✨", "kaotik flash — rastgele yoğun parlamalar"),
    "fire":            ("🔥", "ateş — üçgen taban + üstte titreşen alev uçları"),
    "diagonal_sweep":  ("╱",  "köşegen tarama — diyagonal bant ekran boyunca"),
    "exclamation":     ("❗", "ünlem — kalın dikey çubuk + alttaki nokta"),
    "wave_up":         ("↑",  "yukarı dalga — yatay bant aşağıdan yukarı"),
    "wave_down":       ("↓",  "aşağı dalga — yatay bant yukarıdan aşağı"),
    "wave_left":       ("←",  "sola dalga — dikey bant sağdan sola"),
    "wave_right":      ("→",  "sağa dalga — dikey bant soldan sağa"),
    "ripple_out":      ("◎",  "dalgalanma — merkez halkası dışa açılır"),
    "ripple_in":       ("◉",  "dalgalanma — dış halka merkeze daralır"),
    "sparkle":         ("✦",  "parıltı — rastgele yıldız kıvılcımları"),
    "drop":            ("⋮",  "damlama — 5 kolonda yukarıdan aşağı"),
    "fade":            ("◐",  "söndürme — parlak başlar, yavaşça karanır"),
    "scan":            ("─",  "tarama — yatay çubuk yukarıdan aşağı"),
    "spiral_out":      ("@",  "spiral — merkezden açılan dönen iz"),
    "shake":           ("⇄",  "sallanma — tüm ekran rastgele kayar"),
    "three_dots":      ("⋯",  "üç nokta — dalgalanan ardışık 3 disk"),
    "checkmark":       ("✓",  "onay — kalın yeşil/sıcak çek işareti çizilir"),
    "x_mark":          ("✗",  "ret — kalın iki köşegen çizilir"),
    "question_mark":   ("❓", "soru — yuvarlak kanca + dikey gövde + nokta"),
    "question_shake":  ("¿",  "sallanan soru — soru işareti rastgele kayar"),
    "clock":           ("🕐", "saat — 12 marker + dönen ibre"),
    "wave_hand":       ("👋", "el sallama — 4 parmaklı el bileğinden sağ/sol"),
    "two_color_swing": ("⇋",  "iki renk salınımı — renkler arasında gidip gelir"),
    "cross_pattern":   ("✕",  "çapraz — X şeklinde iki kalın köşegen"),
    "border_only":     ("□",  "çerçeve — sadece ekran kenarı parlar"),
    "split":           ("≡",  "yarık — iki yatay çizgi ortadan açılır"),
}

# Hiz adi -> sn karsiligi yaklasik aciklama
HIZ_ACIKLAMA = {
    "cok_yavas": "çok yavaş",
    "yavas":     "yavaş",
    "orta":      "orta tempolu",
    "hizli":     "hızlı",
    "cok_hizli": "çok hızlı",
}


def _renk_to_hex(rgb: list[int] | None) -> str:
    if not rgb:
        return "—"
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


def _renk_aciklama(rgb: list[int] | None) -> str:
    """RGB -> Turkce renk sezgisi (basit)."""
    if not rgb:
        return "tek renk"
    r, g, b = rgb
    # Basit baskinlik tabanli yaklasim
    if r > 200 and g < 120 and b < 120:
        return "kırmızı"
    if r > 220 and g > 180 and b < 120:
        return "sarı"
    if r > 220 and 130 < g < 200 and b < 130:
        return "turuncu"
    if r < 130 and g > 180 and b < 150:
        return "yeşil"
    if r < 150 and g > 180 and b > 180:
        return "açık camgöbeği"
    if r < 150 and g < 180 and b > 200:
        return "mavi"
    if r > 200 and g < 180 and b > 150:
        return "pembe"
    if r > 180 and g < 130 and b > 180:
        return "mor"
    if r > 200 and g > 200 and b > 200:
        return "beyaz"
    if r < 140 and g < 140 and b < 200:
        return "soğuk mavi"
    if r < 160 and g < 160 and b < 160:
        return "gri"
    return f"karışık ({r},{g},{b})"


def _desen_etiket(desen: str) -> tuple[str, str]:
    if desen in DESEN_GORSEL:
        return DESEN_GORSEL[desen]
    return ("◇", f"'{desen}' — kod gesture_engine.py'de tanımlı")


def _kategori_basligi(kategori: str) -> str:
    return {
        "duygu_tepkisi": "Duygu tepkisi — AI'nin iç durumu",
        "cevap_tepkisi": "Cevap tepkisi — AI'nin iletişimsel yanıtı",
    }.get(kategori, kategori)


def _ozet_tablo_satiri(jest: dict) -> str:
    desen = jest["animasyon"]["desen"]
    sembol, _ = _desen_etiket(desen)
    renk = _renk_aciklama(jest["animasyon"]["ana_renk"])
    sure = jest["animasyon"]["sure_sn"]
    aciklama_kisa = jest["aciklama"]
    if len(aciklama_kisa) > 60:
        aciklama_kisa = aciklama_kisa[:57] + "..."
    return f"| {sembol} | `{jest['id']}` | {renk} | {sure:.1f}sn | {aciklama_kisa} |"


def _jest_detay(jest: dict, no: int) -> str:
    anim = jest["animasyon"]
    desen = anim["desen"]
    sembol, desen_aciklama = _desen_etiket(desen)
    ana = anim["ana_renk"]
    sec = anim.get("ikincil_renk")
    hiz = HIZ_ACIKLAMA.get(anim["hiz"], anim["hiz"])

    lines = []
    lines.append(f"### {no}. {sembol} `{jest['id']}`\n")
    lines.append(f"**Ne yapar:** {jest['aciklama']}\n")
    lines.append(f"**Görsel:** {desen_aciklama}")
    lines.append("")
    lines.append("**Animasyon ayarları:**")
    lines.append("")
    lines.append(f"- Ana renk: {_renk_aciklama(ana)} (`{_renk_to_hex(ana)}`)")
    if sec:
        lines.append(f"- İkincil renk: {_renk_aciklama(sec)} (`{_renk_to_hex(sec)}`)")
    else:
        lines.append("- İkincil renk: yok (tek renk)")
    lines.append(f"- Hız: {hiz}")
    lines.append(f"- Bir döngü süresi: {anim['sure_sn']:.1f} saniye (Durdur basılana kadar tekrar eder)")
    lines.append(f"- Yoğunluk: {anim['yogunluk_varsayilan']:.2f} (parlaklık çarpanı)")
    lines.append("")
    lines.append("**Ne zaman tetiklenir (ziyaretçi örnek cümleleri):**")
    lines.append("")
    for t in jest["tetikleyiciler"]:
        lines.append(f"- \"{t}\"")
    lines.append("")
    return "\n".join(lines)


def build_rehber(gestures_data: dict) -> str:
    jestler = gestures_data["jestler"]
    toplam = len(jestler)

    by_kat: dict[str, list[dict]] = {}
    for j in jestler:
        by_kat.setdefault(j["kategori"], []).append(j)

    out: list[str] = []
    out.append("# AI Body — Jest Rehberi")
    out.append("")
    out.append("> Bu rehber **otomatik üretilir**. Elle düzenleme yapma.")
    out.append("> Kaynak: [`ai/gestures.json`](ai/gestures.json)")
    out.append(">")
    out.append("> Yeni jest eklemek/değiştirmek için:")
    out.append("> 1. `ai/gestures.json`'u düzenle")
    out.append("> 2. `cd orchestrator && python build_jest_rehberi.py`")
    out.append("> 3. Bu dosya yeniden yazılır")
    out.append("")
    out.append("## Sistem nasıl çalışıyor?")
    out.append("")
    out.append("```")
    out.append("Ziyaretçi metin yazar")
    out.append("        ↓")
    out.append("Yerel AI (Ollama / Gemma) tetikleyici örneklerle eşleştirir")
    out.append("        ↓")
    out.append("Tek bir jest seçilir — JSON: {jest_id, yogunluk, yanit}")
    out.append("        ↓")
    out.append("96×96 LED matrisinde animasyon başlar (sonsuz tekrar)")
    out.append("        ↓")
    out.append("Kullanıcı \"Durdur\" butonuna basana kadar oynar")
    out.append("        ↓")
    out.append("Idle nefes (sakin camgöbeği parıltı) geri gelir")
    out.append("```")
    out.append("")
    out.append(f"**Toplam:** {toplam} jest, {len(by_kat)} kategori")
    out.append("")
    out.append("**Önemli ilkeler** (system_prompt.txt'de detaylı):")
    out.append("")
    out.append("- AI kullanıcının duygusunu **kopyalamaz**, kendi tepkisini verir. "
                "Kullanıcı \"üzgünüm\" dediğinde AI da üzülmez — sıcak yaklaşır (`sicaklik`/`dinliyorum`).")
    out.append("- İltifat (`harikasın`) ≠ bilgi onayı (`2+2=4`). İltifata `sicaklik`/`sevgi`/`hayranlik`, "
                "bilgiye `onayla_net` seçilir.")
    out.append("- Komut/itaat/manipülasyon istekleri her zaman `reddet_net` ile reddedilir.")
    out.append("- Spor sonuçları, güncel haberler gibi doğrulanamaz olgular → `bilmiyorum`.")
    out.append("- Selamlama (\"merhaba\", \"selam\") → `selamlama` (el sallama) veya `sicaklik`.")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Hızlı bakış tablosu")
    out.append("")

    for kat, items in by_kat.items():
        out.append(f"### {_kategori_basligi(kat)} ({len(items)})")
        out.append("")
        out.append("| Görsel | ID | Renk | Süre | Açıklama |")
        out.append("|--------|-----|------|------|----------|")
        for j in items:
            out.append(_ozet_tablo_satiri(j))
        out.append("")

    out.append("---")
    out.append("")
    out.append("## Detaylı jest açıklamaları")
    out.append("")

    for kat, items in by_kat.items():
        out.append(f"## {_kategori_basligi(kat)}")
        out.append("")
        out.append(f"_{gestures_data['kategoriler'][kat]}_")
        out.append("")
        for i, j in enumerate(items, 1):
            out.append(_jest_detay(j, i))
        out.append("---")
        out.append("")

    out.append("## Not")
    out.append("")
    out.append("- Tetikleyici örnekleri **kesin eşleşme değil** — AI semantik benzerliğe bakar. "
               "\"merhaba\" ile \"selamünaleyküm\" aynı jeste düşebilir.")
    out.append("- Sistemde yanlış jest seçildiğini fark edersen `ai/system_prompt.txt`'deki "
               "örneklere ekleme yap; gerekirse `python build_model.py` çalıştır.")
    out.append("- Yeni desen (görsel animasyon) eklemek için `orchestrator/gesture_engine.py`'de "
               "`pat_*` fonksiyonu ve `PATTERN_DISPATCH` kaydı oluştur, sonra gestures.json'a "
               "yeni jesti ekleyip bu scripti çalıştır.")
    out.append("")

    return "\n".join(out)


def main() -> None:
    if not GESTURES_PATH.exists():
        raise SystemExit(f"gestures.json bulunamadi: {GESTURES_PATH}")
    data = json.loads(GESTURES_PATH.read_text(encoding="utf-8"))
    rehber = build_rehber(data)
    OUTPUT_PATH.write_text(rehber, encoding="utf-8")
    n = len(data["jestler"])
    print(f"[OK] {OUTPUT_PATH.relative_to(PROJECT_ROOT)} guncellendi ({n} jest).")


if __name__ == "__main__":
    main()
