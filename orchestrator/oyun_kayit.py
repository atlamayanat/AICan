"""AICAN — Ziyaretci bazli oyun kayit defteri (jsonl).

Sergide gorevli kontrol panelinden "Kayit Baslat" der ve ziyaretcinin adini
girer; o ziyaretcinin oynadigi HER oyun icin tek bir jsonl satiri yazilir:

    logs/oyun_kayitlari/<slug>.jsonl

Satir bicimi (oyun basina 1):
    {"ziyaretci","oyun","tur","baslangic","bitis","sure_sn","skor",
     "tamamlandi","sonuc","kazanan","sebep"}

Tasarim ilkeleri:
  - Yeni bagimlilik YOK (json/pathlib/datetime/threading — hepsi stdlib).
  - Kayit yazimi oyunu ASLA dusurmez: public metotlar hatayi yutar, yalnizca
    log'a uyari yazar (game_engine._log_game ayrica kendi try/except'i ile sarar).
  - Mevcut session.log akisi DEGISMEZ; bu defter ayri dosyalara yazar.
  - Satir kaybi olmaz: yarim kalan oyun YENI OYUN baslarken ya da kayit/oturum
    kapanirken tamamlandi=false ile kapatilir.
  - Kayit panelden baslar/durur; kayit kapaliyken hicbir sey yazilmaz.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# Turkce karakter -> ascii. game_engine._TR_MAP ile ayni desen: kucultmeden
# ONCE cevrilir ('İ'.lower() birlesen nokta uretip dosya adini bolerdi).
_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "I": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
    "â": "a", "î": "i", "û": "u",
})

# Ziyaretci adi bos/gecersiz gelirse kullanilan on ek: "ziyaretci-<n>".
OTOMATIK_ON_EK = "ziyaretci"
# Dosya adi siniri (Windows yol siniri + okunabilirlik).
SLUG_MAX = 48
# Panelde gosterilen "son kayitlar" varsayilan adedi.
SON_KAYIT_ADEDI = 10
# Bitmemis oyunun sonuc alani (ozet/panel bunu arar).
YARIM_SONUC = "yarim_birakildi"


def slugla(ad: str) -> str:
    """Ziyaretci adini guvenli dosya adina cevir: ascii kucuk harf + tire.

    Yol gezinme ('../etc'), surucu harfi ve noktalama tamamen elenir; sonuc
    yalnizca [a-z0-9-] icerir. Hicbir harf kalmazsa "" doner (cagiran otomatik
    ada duser).
    """
    s = (ad or "").translate(_TR_MAP).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:SLUG_MAX].strip("-")


def _detay_coz(detail: str) -> dict:
    """game_engine detay metnini sozluge cevir.

    "kazanan=ai sebep=timeout skor=ai:1" -> {"kazanan":"ai","sebep":"timeout",...}
    """
    out = {}
    for parca in (detail or "").split():
        k, _, v = parca.partition("=")
        if k and v:
            out.setdefault(k, v)
    return out


class OyunKayit:
    """Ziyaretci bazli oyun defteri; kayit panelden baslar/durur.

    Kullanim (web_server):
        kayit = OyunKayit(logs/oyun_kayitlari)
        game.oyun_kayit = kayit          # game_engine._log_game koprusu
        kayit.basla("Ayse") / kayit.bitir() / kayit.durum() / kayit.ozet()

    Flask threaded=True oldugu icin tum durum tek RLock arkasinda.
    """

    def __init__(self, kayit_dir, otomatik_on_ek: str = OTOMATIK_ON_EK):
        self.kayit_dir = Path(kayit_dir)
        self._on_ek = otomatik_on_ek or OTOMATIK_ON_EK
        self._lock = threading.RLock()
        self.aktif = False
        self.ziyaretci = ""
        self.slug = ""
        # O an oynanan oyun (henuz satiri yazilmadi) ya da None.
        self._acik = None
        # Bu kayit oturumunda diske yazilan satir sayisi.
        self._yazilan = 0

    # ——— Dosya yardimcilari ————————————————————————————————
    def _dosya(self, slug: str) -> Path:
        return self.kayit_dir / f"{slug}.jsonl"

    def _satir_yaz(self, slug: str, kayit: dict) -> None:
        """Tek satiri dosyaya ekle. Disk hatasi yutulur (oyun devam eder)."""
        try:
            self.kayit_dir.mkdir(parents=True, exist_ok=True)
            with self._dosya(slug).open("a", encoding="utf-8") as f:
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            self._yazilan += 1
        except (OSError, TypeError, ValueError) as e:
            log.warning("Oyun kaydi yazilamadi (%s): %s", slug, e)

    def _otomatik_ad(self) -> str:
        """Bos ad -> 'ziyaretci-<n>'; n diskteki en buyuk numaranin bir fazlasi
        (sunucu yeniden baslasa da eski dosyanin ustune yazilmaz)."""
        en_buyuk = 0
        try:
            for p in self.kayit_dir.glob(f"{self._on_ek}-*.jsonl"):
                sayi = p.stem[len(self._on_ek) + 1:]
                if sayi.isdigit():
                    en_buyuk = max(en_buyuk, int(sayi))
        except OSError as e:
            log.warning("Oyun kayit dizini taranamadi: %s", e)
        return f"{self._on_ek}-{en_buyuk + 1}"

    # ——— Yasam dongusu (panelden yonetilir) ————————————————
    def basla(self, ziyaretci: str = "") -> dict:
        """Kaydi baslat. ziyaretci bos/gecersizse 'ziyaretci-<n>' atanir.

        Kayit zaten aciksa: acik oyun yarim kapatilir ve yeni ziyaretciye gecilir
        (gorevli araya ad girip tekrar baslatirsa satir kaybolmasin).
        """
        with self._lock:
            if self.aktif:
                self._kapat_acik("kayit_degisti")
            ad = (ziyaretci or "").strip()
            slug = slugla(ad)
            if not slug:
                ad = self._otomatik_ad()
                slug = slugla(ad)
            self.ziyaretci = ad
            self.slug = slug
            self.aktif = True
            self._acik = None
            self._yazilan = 0
            try:
                self.kayit_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                log.warning("Oyun kayit dizini olusturulamadi: %s", e)
            log.info("Ziyaretci oyun kaydi basladi: %s (%s.jsonl)", ad, slug)
            return self.durum()

    def bitir(self, sebep: str = "kayit_durduruldu") -> dict:
        """Kaydi durdur. Acik oyun tamamlandi=false ile kapatilir."""
        with self._lock:
            self._kapat_acik(sebep)
            d = self.durum()
            d["aktif"] = False
            if self.aktif:
                log.info("Ziyaretci oyun kaydi bitti: %s (%d oyun)",
                         self.ziyaretci or "-", self._yazilan)
            self.aktif = False
            self.ziyaretci = ""
            self.slug = ""
            self._acik = None
            return d

    def oturum_kapat(self) -> dict:
        """Sunucu kapanisi: acik oyun tamamlandi=false ile kapanir, kayit durur."""
        with self._lock:
            if not self.aktif and self._acik is None:
                return self.durum()
            return self.bitir("oturum_kapandi")

    def acik_oyunu_kapat(self, sebep: str = "cikis") -> dict:
        """Yalniz acik oyunu yarim kapat (kayit acik kalir) — /api/game/exit icin."""
        with self._lock:
            self._kapat_acik(sebep)
            return self.durum()

    def durum(self) -> dict:
        with self._lock:
            acik = self._acik
            return {
                "aktif": self.aktif,
                "ziyaretci": self.ziyaretci,
                "slug": self.slug,
                "dosya": str(self._dosya(self.slug)) if self.slug else "",
                "oyun_sayisi": self._yazilan,
                "acik_oyun": ({"oyun": acik["oyun"], "tur": acik["tur"],
                               "baslangic": acik["baslangic"]} if acik else None),
            }

    # ——— game_engine koprusu ————————————————————————————————
    def oyun_olayi(self, mode: str, event: str, detail: str = "",
                   skor=None, tur=None) -> None:
        """game_engine._log_game koprusu — hata YUTAR, oyunu asla dusurmez.

        mode: 'tkm' | 'kelime' | 'quiz'
        event: 'basladi' | 'bitti' | 'yarim_birakildi'
        skor: mod bazli skor sozlugu (word_score / quiz_score kopyasi)
        """
        try:
            with self._lock:
                if not self.aktif:
                    return              # kayit kapali -> hicbir sey yazilmaz
                detay = _detay_coz(detail)
                tur = tur or detay.get("tur")
                if event == "basladi":
                    self._oyun_basladi(mode, tur, skor)
                elif event in ("bitti", "yarim_birakildi"):
                    self._oyun_bitti(mode, tur, skor, detay,
                                     tamamlandi=(event == "bitti"))
        except Exception as e:  # noqa: BLE001 — kayit oyunu asla durdurmasin
            log.warning("Oyun kaydi islenemedi (%s/%s): %s", mode, event, e)

    def _oyun_basladi(self, oyun: str, tur, skor) -> None:
        # Onceki oyun yarim kaldiysa (menuye/yeni oyuna atlandi) satiri simdi yaz.
        self._kapat_acik("yeni_oyun_basladi")
        self._acik = {
            "ziyaretci": self.ziyaretci,
            "slug": self.slug,
            "oyun": oyun,
            "tur": tur,
            "baslangic": datetime.now().isoformat(timespec="seconds"),
            # Sure monotonic ile olculur (sistem saati oynasa da bozulmaz).
            "t0": time.monotonic(),
            "skor": dict(skor or {}),
        }

    def _oyun_bitti(self, oyun: str, tur, skor, detay: dict, tamamlandi: bool) -> None:
        acik = self._acik
        if acik is not None and acik["oyun"] != oyun:
            # Beklenmeyen sira: baska bir oyun acik kalmis — onu yarim kapat.
            self._kapat_acik("beklenmeyen_sira")
            acik = None
        if acik is None:
            if not tamamlandi:
                # Hic baslamamis oyun (kural/hazirlik ekranindan cikis) -> satir yok.
                return
            # Baslangici kacirdik (kayit oyunun ortasinda acildi): satir KAYBETME,
            # sifir sureli kayit yaz.
            self._oyun_basladi(oyun, tur, skor)
            acik = self._acik
        if tur and not acik["tur"]:
            acik["tur"] = tur
        if skor:
            acik["skor"] = dict(skor)
        self._bitis_yaz(acik, tamamlandi, detay)

    def _kapat_acik(self, sebep: str = "") -> None:
        """Acik oyunu tamamlandi=false ile kapat (skor: son bilinen deger)."""
        if self._acik is None:
            return
        self._bitis_yaz(self._acik, False, {"sebep": sebep} if sebep else {})

    def _bitis_yaz(self, acik: dict, tamamlandi: bool, detay: dict) -> None:
        skor = dict(acik.get("skor") or {})
        kayit = {
            "ziyaretci": acik["ziyaretci"],
            "oyun": acik["oyun"],
            "tur": acik["tur"],
            "baslangic": acik["baslangic"],
            "bitis": datetime.now().isoformat(timespec="seconds"),
            "sure_sn": round(max(0.0, time.monotonic() - acik["t0"]), 1),
            "skor": skor,
            "tamamlandi": bool(tamamlandi),
            "sonuc": self._sonuc_metni(acik["oyun"], skor, tamamlandi, detay),
            "kazanan": detay.get("kazanan") or None,
            "sebep": detay.get("sebep") or None,
        }
        # _acik ONCE bosaltilir: yazma hata verse bile ayni satir tekrar denenmez.
        self._acik = None
        self._satir_yaz(acik["slug"], kayit)

    @staticmethod
    def _sonuc_metni(oyun: str, skor: dict, tamamlandi: bool, detay: dict) -> str:
        """Kisa, okunabilir sonuc ozeti (panel + ozet bunu gosterir)."""
        if not tamamlandi:
            return YARIM_SONUC
        if oyun == "quiz":
            return f"{skor.get('dogru', 0)}/{skor.get('toplam', 0)} dogru"
        if oyun == "kelime":
            kazanan = detay.get("kazanan")
            temel = f"ai:{skor.get('ai', 0)} ziyaretci:{skor.get('user', 0)}"
            return f"{temel} kazanan:{kazanan}" if kazanan else temel
        return detay.get("sonuc", "tamamlandi")

    # ——— Okuma / ozet ————————————————————————————————————
    def kayitlari_oku(self, slug: str) -> list:
        """Bir ziyaretcinin satirlarini oku; bozuk/yarim satir sessizce atlanir."""
        satirlar = []
        try:
            metin = self._dosya(slug).read_text(encoding="utf-8")
        except OSError:
            return satirlar
        for satir in metin.splitlines():
            satir = satir.strip()
            if not satir:
                continue
            try:
                k = json.loads(satir)
            except ValueError:
                continue          # yarim yazilmis satir (guc kesintisi) — atla
            if isinstance(k, dict):
                satirlar.append(k)
        return satirlar

    def ozet(self, son_n: int = SON_KAYIT_ADEDI) -> dict:
        """Ziyaretci basina oyun sayisi, toplam sure ve skor toplamlari.

        Panel "son kayitlar" listesi icin son_kayitlar (bitise gore yeniden eskiye)
        de ayni yanitta doner.
        """
        with self._lock:
            aktif, ziyaretci = self.aktif, self.ziyaretci
        try:
            dosyalar = sorted(self.kayit_dir.glob("*.jsonl"))
        except OSError as e:
            log.warning("Oyun kayit dizini okunamadi: %s", e)
            dosyalar = []
        ziyaretciler = []
        tum = []
        for p in dosyalar:
            satirlar = self.kayitlari_oku(p.stem)
            if not satirlar:
                continue
            skorlar, oyunlar = {}, {}
            sure = 0.0
            tamam = 0
            for k in satirlar:
                oyun = k.get("oyun") or "?"
                oyunlar[oyun] = oyunlar.get(oyun, 0) + 1
                try:
                    sure += float(k.get("sure_sn") or 0)
                except (TypeError, ValueError):
                    pass
                if k.get("tamamlandi"):
                    tamam += 1
                hedef = skorlar.setdefault(oyun, {})
                for alan, deger in (k.get("skor") or {}).items():
                    # Yalniz sayisal alanlar toplanir (bool sayi degildir).
                    if isinstance(deger, bool) or not isinstance(deger, (int, float)):
                        continue
                    hedef[alan] = hedef.get(alan, 0) + deger
                tum.append(k)
            ziyaretciler.append({
                "slug": p.stem,
                "ziyaretci": satirlar[-1].get("ziyaretci") or p.stem,
                "oyun_sayisi": len(satirlar),
                "tamamlanan": tamam,
                "yarim": len(satirlar) - tamam,
                "toplam_sure_sn": round(sure, 1),
                "oyunlar": oyunlar,
                "skorlar": skorlar,
                "ilk": satirlar[0].get("baslangic"),
                "son": satirlar[-1].get("bitis"),
            })
        # ISO tarih metni sozlukse siralanabilir (yeniden eskiye).
        tum.sort(key=lambda k: str(k.get("bitis") or ""), reverse=True)
        try:
            son_n = max(0, int(son_n))
        except (TypeError, ValueError):
            son_n = SON_KAYIT_ADEDI
        return {
            "aktif": aktif,
            "ziyaretci": ziyaretci,
            "toplam_ziyaretci": len(ziyaretciler),
            "toplam_oyun": sum(z["oyun_sayisi"] for z in ziyaretciler),
            "toplam_sure_sn": round(sum(z["toplam_sure_sn"] for z in ziyaretciler), 1),
            "ziyaretciler": ziyaretciler,
            "son_kayitlar": tum[:son_n],
        }
