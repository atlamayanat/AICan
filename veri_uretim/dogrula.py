#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AICAN veri doğrulayıcı — AI'ya ürettirilen es_zit_anlam / atasozu JSON
dosyalarını oyun motorunun (orchestrator/game_engine.py) beklediği semantiğe
göre denetler. Amaç: dosya sergiye girmeden önce "ziyaretçinin doğru cevabı
yanlış sayılır" ya da "kayıt sessizce düşer" türü sorunları yakalamak.

Kullanım:
    python veri_uretim/dogrula.py <dosya.json> [--tip es_zit|atasozu] [--yukle]

  --tip    verilmezse yapıdan otomatik anlaşılır (nesne -> es_zit, dizi -> atasozu)
  --yukle  doğrulama HATASIZ ise dosyayı ai/ altına kopyalar (mevcutu yedekler)

Çıkış kodu: 0 = onay (uyarılar olabilir), 1 = hata var, 2 = kullanım/IO hatası.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

_BURASI = Path(__file__).resolve().parent
_PROJE = _BURASI.parent
_AI_DIR = _PROJE / "ai"

# Windows konsolunda Türkçe karakterler bozulmasın.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ——— Motorla BİREBİR aynı metin işleme ————————————————————————
# Önce orchestrator'dan içe aktar (tek doğruluk kaynağı); olmazsa (ör. requests
# kurulu değil) aşağıdaki birebir kopyalara düş.
sys.path.insert(0, str(_PROJE / "orchestrator"))
try:
    from word_llm import temiz_kelime, tr_lower  # noqa: F401
    from game_engine import normalize  # noqa: F401
except Exception:
    _TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})

    def tr_lower(s: str) -> str:
        return (s or "").translate(_TR_LOWER).lower()

    def temiz_kelime(s: str) -> str:
        s = tr_lower(s).strip()
        s = re.sub(r"[^a-zçğıöşü]", " ", s).strip()
        return s.split(" ")[0] if s else ""

    _TR_MAP = str.maketrans({
        "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "I": "i",
        "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
        "â": "a", "î": "i", "û": "u",
    })

    def normalize(s: str) -> str:
        s = (s or "").translate(_TR_MAP).lower()
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()


# ——— JSON yükleme (mükerrer anahtar tespitiyle) ————————————————
def _yukle_json(yol: Path):
    """Dosyayı UTF-8(-BOM) olarak oku; mükerrer anahtarları kaydet."""
    mukerrer: list[str] = []

    def hook(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                mukerrer.append(k)
            d[k] = v
        return d

    metin = yol.read_text(encoding="utf-8-sig")
    veri = json.loads(metin, object_pairs_hook=hook)
    return veri, mukerrer, metin


# ——— Eş/Zıt denetimi ————————————————————————————————————————
def dogrula_es_zit(veri, mukerrer):
    hatalar: list[str] = []
    uyarilar: list[str] = []

    if not isinstance(veri, dict):
        return ["Üst düzey yapı JSON nesnesi (sözlük) olmalı."], [], ""

    for k in mukerrer:
        hatalar.append(f"Mükerrer anahtar: '{k}' — ikinci tanım ilkini sessizce ezer.")

    temizlenmis: dict[str, dict[str, list[str]]] = {}

    for ham_k, ham_v in veri.items():
        kk = temiz_kelime(ham_k)
        if not kk:
            hatalar.append(f"'{ham_k}': anahtar temizlenince boş kalıyor — kayıt düşer.")
            continue
        if kk != tr_lower(ham_k).strip():
            hatalar.append(f"'{ham_k}': anahtar tek kelime değil / yasak karakter içeriyor "
                           f"— motor '{kk}' olarak kırpar.")
        if ham_k != tr_lower(ham_k):
            uyarilar.append(f"'{ham_k}': anahtar büyük harf içeriyor — küçük harf yaz.")
        if len(kk) == 1:
            uyarilar.append(f"'{ham_k}': tek harfli anahtar — soru anlamsız olabilir.")
        if kk in temizlenmis:
            hatalar.append(f"'{ham_k}': temizlenince '{kk}' başka bir anahtarla çakışıyor "
                           f"— önceki kayıt sessizce ezilir.")
        if not isinstance(ham_v, dict):
            hatalar.append(f"'{ham_k}': değer nesne değil ({type(ham_v).__name__}) — kayıt düşer.")
            continue
        bilinmeyen = set(ham_v) - {"es", "zit"}
        if bilinmeyen:
            uyarilar.append(f"'{ham_k}': bilinmeyen alan(lar) {sorted(bilinmeyen)} — motor yok sayar.")

        kayit: dict[str, list[str]] = {}
        for tip in ("es", "zit"):
            if tip not in ham_v:
                continue
            liste = ham_v[tip]
            if not isinstance(liste, list):
                hatalar.append(f"'{ham_k}'.{tip}: liste değil — alan düşer.")
                continue
            temiz_liste: list[str] = []
            for oge in liste:
                if not isinstance(oge, str) or not oge.strip():
                    hatalar.append(f"'{ham_k}'.{tip}: boş/metin-olmayan öğe var.")
                    continue
                t = temiz_kelime(oge)
                if not t:
                    hatalar.append(f"'{ham_k}'.{tip}: '{oge}' temizlenince boş kalıyor.")
                    continue
                if t != tr_lower(oge).strip():
                    hatalar.append(f"'{ham_k}'.{tip}: '{oge}' tek kelime değil / yasak karakter "
                                   f"içeriyor — motor '{t}' olarak kırpar (sessiz veri bozulması).")
                if oge != tr_lower(oge):
                    uyarilar.append(f"'{ham_k}'.{tip}: '{oge}' büyük harf içeriyor — küçük harf yaz.")
                if t in temiz_liste:
                    uyarilar.append(f"'{ham_k}'.{tip}: '{t}' listede mükerrer.")
                    continue
                temiz_liste.append(t)
            if temiz_liste:
                kayit[tip] = temiz_liste

        if not kayit:
            hatalar.append(f"'{ham_k}': ne 'es' ne 'zit' dolu — motor kaydı atar.")
            continue
        # Motor cevaplari AKSANSIZ (normalize) karsilastirir: 'sık' ile 'şık'
        # ayni kabul sayilir — kontroller o uzayda da yapilir.
        nk = normalize(kk)
        for tip, liste in kayit.items():
            if kk in liste:
                hatalar.append(f"'{ham_k}'.{tip}: kelimenin kendisi cevap listesinde.")
            elif nk and nk in {normalize(t) for t in liste}:
                hatalar.append(f"'{ham_k}'.{tip}: kelimenin aksansız hali ('{nk}') cevap "
                               f"listesinde — soruyu tekrarlamak doğru sayılır.")
        kes_t = set(kayit.get("es", [])) & set(kayit.get("zit", []))
        if kes_t:
            hatalar.append(f"'{ham_k}': es ve zit kesişiyor: {sorted(kes_t)}.")
        elif kayit.get("es") and kayit.get("zit"):
            kes_n = ({normalize(t) for t in kayit["es"]}
                     & {normalize(t) for t in kayit["zit"]})
            if kes_n:
                hatalar.append(f"'{ham_k}': es ve zit aksansız (normalize) uzayda kesişiyor: "
                               f"{sorted(kes_n)} — motor ikisini aynı cevap sayar.")
        temizlenmis[kk] = kayit

    # Simetri / çaprazlama (uyarı): ziyaretçinin doğru cevabının kabul
    # edilmemesine yol açan tipik eksikler.
    for a, kayit in temizlenmis.items():
        for b in kayit.get("zit", []):
            if b in temizlenmis:
                if a not in temizlenmis[b].get("zit", []):
                    uyarilar.append(f"Simetri eksik: '{a}'.zit içinde '{b}' var ama "
                                    f"'{b}'.zit içinde '{a}' yok.")
                for es_b in temizlenmis[b].get("es", []):
                    if es_b != a and es_b not in kayit["zit"]:
                        uyarilar.append(f"Çaprazlama eksik: '{es_b}' ('{b}' kaydında eş) "
                                        f"'{a}'.zit içinde yok — ziyaretçi '{es_b}' derse yanlış sayılır.")
        for b in kayit.get("es", []):
            if b in temizlenmis and a not in temizlenmis[b].get("es", []):
                uyarilar.append(f"Simetri eksik: '{a}'.es içinde '{b}' var ama "
                                f"'{b}'.es içinde '{a}' yok.")

    n = len(temizlenmis)
    n_es = sum(1 for v in temizlenmis.values() if v.get("es"))
    n_zit = sum(1 for v in temizlenmis.values() if v.get("zit"))
    if n < 60:
        uyarilar.append(f"Havuz küçük ({n} kayıt) — hedef en az 150.")
    ozet = f"Kayıt: {n}  (es'li: {n_es}, zit'li: {n_zit})"
    return hatalar, uyarilar, ozet


# Tek basina "tamam" ogesi olamayacak yaygin fiiller (normalize edilmis):
# cift yonlu substring eslesmesinde her yanlis cevabi dogru saydirirlar.
_YAYGIN_FIIL = frozenset({
    "olur", "olmaz", "gelir", "gider", "eder", "etmez", "yapar", "yemez",
    "olsun", "vardir", "yoktur", "iyidir", "degildir", "bilir", "bilmez",
    "kalir", "kalmaz", "cikar", "cikmaz", "gecer", "gecmez", "yatar", "bakar",
})

# Sesli giriste rakama cevrilebilen sayi kelimeleri (normalize edilmis).
_SAYI_KELIME = frozenset({
    "bir", "iki", "uc", "dort", "bes", "alti", "yedi", "sekiz", "dokuz", "on",
    "yirmi", "otuz", "kirk", "elli", "altmis", "yetmis", "seksen", "doksan",
    "yuz", "bin",
})


# ——— Atasözü denetimi ————————————————————————————————————————
def dogrula_atasozu(veri, mukerrer):
    hatalar: list[str] = []
    uyarilar: list[str] = []

    if not isinstance(veri, list):
        return ["Üst düzey yapı JSON dizisi (liste) olmalı."], [], ""

    for k in mukerrer:
        hatalar.append(f"Mükerrer anahtar: '{k}' — ikinci tanım ilkini sessizce ezer.")

    gecerli = []
    bas_gorulen: dict[str, int] = {}

    for i, oge in enumerate(veri, 1):
        etiket = f"#{i}"
        if not isinstance(oge, dict):
            hatalar.append(f"{etiket}: öğe nesne değil — kayıt düşer.")
            continue
        bas = oge.get("bas")
        tamam = oge.get("tamam")
        bilinmeyen = set(oge) - {"bas", "tamam"}
        if bilinmeyen:
            uyarilar.append(f"{etiket}: bilinmeyen alan(lar) {sorted(bilinmeyen)} — motor yok sayar.")
        if not isinstance(bas, str) or not bas.strip():
            hatalar.append(f"{etiket}: 'bas' boş/eksik — kayıt düşer.")
            continue
        if not isinstance(tamam, list) or not tamam or not all(
                isinstance(t, str) and t.strip() for t in tamam):
            hatalar.append(f"{etiket} ('{bas}'): 'tamam' boş olmayan metin listesi olmalı — kayıt düşer.")
            continue

        etiket = f"#{i} ('{bas}')"
        if re.search(r"[.!?…]\s*$", bas) or bas.rstrip().endswith("..."):
            hatalar.append(f"{etiket}: 'bas' sonunda noktalama var — motor '…' işaretini kendisi ekler.")
        elif bas.rstrip().endswith(","):
            uyarilar.append(f"{etiket}: 'bas' virgülle bitiyor — ekranda garip görünebilir.")
        if bas != bas.strip():
            uyarilar.append(f"{etiket}: 'bas' başında/sonunda boşluk var.")
        if len(bas.split()) < 2:
            uyarilar.append(f"{etiket}: 'bas' tek kelime — ziyaretçi atasözünü tanıyamayabilir.")

        n_bas = normalize(bas)
        for j, t in enumerate(tamam):
            nt = normalize(t)
            if not nt:
                hatalar.append(f"{etiket}: tamam[{j}] ('{t}') normalize edilince boş kalıyor.")
                continue
            if len(nt) < 4:
                uyarilar.append(f"{etiket}: tamam[{j}] ('{t}') çok kısa — esnek eşleşme yanlış "
                                f"kabullere yol açabilir (en az 4 harf önerilir).")
            if len(nt.split()) == 1 and nt in _YAYGIN_FIIL:
                uyarilar.append(f"{etiket}: tamam[{j}] tek başına yaygın bir fiil ('{t}') — "
                                f"içinde bu kelime geçen her yanlış cevap doğru sayılır; "
                                f"bölme noktasını sola kaydır.")
            if re.search(r"[!?…]\s*$", t):
                hatalar.append(f"{etiket}: tamam[{j}] ('{t}') ünlem/soru işaretiyle bitiyor — "
                                f"ekranda 'Cevap: …!.' gibi bozuk görünür.")
            ic = sorted(set(re.findall(r"[^0-9a-zçğıöşüâîû\s.!?…]", tr_lower(t))))
            if ic:
                uyarilar.append(f"{etiket}: tamam[{j}] ('{t}') noktalama içeriyor {ic} — "
                                f"eşleştirmede boşluğa çevrilir; sesli giriş bitişik yazarsa "
                                f"doğru cevap yanlış sayılabilir. Noktalamasız varyantı da ekle.")
            if nt in n_bas:
                if j == 0:
                    hatalar.append(f"{etiket}: cevap ('{t}') zaten 'bas' içinde geçiyor.")
                else:
                    uyarilar.append(f"{etiket}: varyant '{t}' 'bas' içinde geçiyor.")
            if len(t.split()) > 6:
                uyarilar.append(f"{etiket}: tamam[{j}] uzun ({len(t.split())} kelime) — bölme "
                                f"noktasını kaydırmayı düşün.")

        # Sayı kelimesi cevapta ama rakamlı varyant yoksa: sesli giriş 'kırk'ı
        # '40' yazabilir ve doğru cevap yanlış sayılır.
        norm_items = [normalize(t) for t in tamam]
        sayi_iceren = [t for t, n in zip(tamam, norm_items)
                       if any(w in _SAYI_KELIME for w in n.split())]
        if sayi_iceren and not any(re.search(r"\d", n) for n in norm_items):
            uyarilar.append(f"{etiket}: cevapta sayı kelimesi var ('{sayi_iceren[0]}') — sesli "
                            f"giriş rakam yazabilir ('kırk'→'40'); rakamlı varyantı da ekle.")

        if n_bas in bas_gorulen:
            hatalar.append(f"{etiket}: 'bas' #{bas_gorulen[n_bas]} ile mükerrer.")
        else:
            bas_gorulen[n_bas] = i
        gecerli.append((i, bas, tamam))

    # Aynı atasözünün farklı bölünmüş kopyaları: tam metinler iç içe geçiyorsa şüpheli.
    tam_metinler = [(i, normalize(f"{bas} {tamam[0]}")) for i, bas, tamam in gecerli]
    for x in range(len(tam_metinler)):
        for y in range(x + 1, len(tam_metinler)):
            ix, tx = tam_metinler[x]
            iy, ty = tam_metinler[y]
            if tx and ty and (tx in ty or ty in tx):
                uyarilar.append(f"#{ix} ile #{iy}: aynı atasözünün iki farklı hali olabilir "
                                f"('{tx}' ↔ '{ty}').")

    n = len(gecerli)
    if n < 60:
        uyarilar.append(f"Havuz küçük ({n} kayıt) — hedef en az 100.")
    ozet = f"Kayıt: {n}"
    return hatalar, uyarilar, ozet


# ——— Rapor + yükleme ————————————————————————————————————————
_HEDEF = {"es_zit": "es_zit_anlam.json", "atasozu": "atasozu.json"}
_MAKS_GOSTER = 30


def _listele(baslik, ogeler):
    print(f"{baslik} ({len(ogeler)}):")
    for m in ogeler[:_MAKS_GOSTER]:
        print(f"  - {m}")
    if len(ogeler) > _MAKS_GOSTER:
        print(f"  … ve {len(ogeler) - _MAKS_GOSTER} tane daha")


def main() -> int:
    p = argparse.ArgumentParser(description="AICAN oyun verisi doğrulayıcı")
    p.add_argument("dosya", help="denetlenecek JSON dosyası")
    p.add_argument("--tip", choices=("es_zit", "atasozu"),
                   help="veri tipi (verilmezse yapıdan anlaşılır)")
    p.add_argument("--yukle", action="store_true",
                   help="hatasızsa ai/ altına kopyala (mevcutu yedekler)")
    args = p.parse_args()

    yol = Path(args.dosya)
    if not yol.is_file():
        print(f"Dosya bulunamadı: {yol}")
        return 2
    try:
        veri, mukerrer, metin = _yukle_json(yol)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Dosya okunamadı: {e}")
        return 2
    except json.JSONDecodeError as e:
        print(f"JSON HATASI: satır {e.lineno}, sütun {e.colno}: {e.msg}")
        print("Dosya geçerli JSON değil — AI çıktısı kesilmiş ya da kod bloğu "
              "dışı metin karışmış olabilir.")
        return 1

    tip = args.tip or ("es_zit" if isinstance(veri, dict) else "atasozu")
    denetci = dogrula_es_zit if tip == "es_zit" else dogrula_atasozu
    hatalar, uyarilar, ozet = denetci(veri, mukerrer)

    print(f"=== AICAN veri doğrulama · {tip} · {yol.name} ===")
    if ozet:
        print(ozet)
    if hatalar:
        _listele("HATA", hatalar)
    if uyarilar:
        _listele("UYARI", uyarilar)

    if hatalar:
        print(f"SONUÇ: RED — {len(hatalar)} hata. Dosyayı düzeltmeden yükleme.")
        return 1

    print(f"SONUÇ: ONAY — hata yok" + (f", {len(uyarilar)} uyarı." if uyarilar else "."))

    if args.yukle:
        hedef = _AI_DIR / _HEDEF[tip]
        try:
            if yol.resolve() == hedef.resolve():
                print(f"Dosya zaten yerinde ({hedef}) — kopyalama atlandı.")
                return 0
            if hedef.exists():
                yedek = hedef.with_name(
                    f"{hedef.stem}.yedek-{datetime.now():%Y%m%d-%H%M%S}.json")
                shutil.copy2(hedef, yedek)
                print(f"Yedek alındı: {yedek.name}")
            # BOM'suz temiz UTF-8 yaz (utf-8-sig okuma BOM'u zaten soymustur).
            hedef.write_text(metin, encoding="utf-8")
            print(f"Yüklendi: {hedef}")
            print("Değişikliğin etkin olması için sunucuyu yeniden başlat.")
        except OSError as e:
            print(f"Yükleme başarısız: {e}")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
