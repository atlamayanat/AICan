"""AICAN — Oyun motoru (deterministik).

Sergi temasi "yapay zekanin duygulari var mi?": ziyaretci AI ile oyun oynar,
AI kazaninca/kaybedince gercek bir insan gibi DUYGUSAL tepki verir.

Tasarim ilkesi: oyun mantigi ve duygu secimi DETERMINISTIK kod ile yurur
(hizli + sergi ortaminda cokme riski yok). Local LLM yalnizca dil gerektiren
yerlerde (kelime turetme — sonraki faz) devreye girer. Tas-Kagit-Makas hic
LLM cagirmaz; AI hamlesi rastgele + ince hile ile secilir.

Bu modul UI'dan bagimsizdir: girdi metni alir, gosterilecek payload doner.
Cekirdek sohbet dosyalari (llm_bridge.py, system_prompt.txt, gestures.json)
DEGISMEZ; oyun ek bir katmandir.
"""
from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path

from word_llm import son_harf, temiz_kelime

log = logging.getLogger(__name__)

# ——— Tas-Kagit-Makas tanimlari ————————————————————————————————
# Sira onemli: indeks m, indeks (m-1)%3'u yener.
#   tas(0)   makas(2)'yi yener
#   kagit(1) tas(0)'i yener
#   makas(2) kagit(1)'i yener
_RPS = [
    {"key": "tas",   "ad": "Taş",   "emoji": "✊"},
    {"key": "kagit", "ad": "Kağıt", "emoji": "✋"},
    {"key": "makas", "ad": "Makas", "emoji": "✌️"},
]

# ——— Duygu (jest) havuzlari — mevcut 31 jesti yeniden kullanir ————
# Hicbiri yeni gorsel gerektirmez; gestures.json'daki id'ler.
_JEST = {
    "win_single":  ["gurur", "mutluluk_yogun", "nese"],
    "win_streak":  ["gurur", "hayranlik", "mutluluk_yogun"],
    "lose_single": ["uzgun_yavas", "hayal_kirikligi"],
    "lose_2":      ["saskinlik"],
    "lose_3":      ["ofke", "korku", "panik", "uzgun_derin"],
    "draw":        ["soru_isareti", "merak", "kararsiz"],
    "menu":        "selamlama",
    "rps_start":   "nese",
    "exit":        "huzur",
    "coming_soon": "merak",
    # ——— Kelime Türetme duyguları (mevcut id'ler) ———
    "kel_intro":     ["selamlama", "nese"],
    "kel_ai_word":   ["gurur", "mutluluk_yogun", "nese"],
    "kel_ai_streak": ["hayranlik", "gurur"],
    "kel_user_ok":   ["hayranlik", "nese", "onayla_sicak", "merak"],
    "kel_retry":     ["soru_isareti", "merak", "anlamadim"],
    "kel_ai_lose":   ["hayal_kirikligi", "uzgun_yavas"],
    "kel_user_lose": ["gurur", "mutluluk_sakin", "onayla_net"],
}

# ——— Replik havuzlari (Turkce, karakterli) ————————————————————
_TXT = {
    "win_single": [
        "Bu turu ben aldım. Fena değilim, ha?",
        "Hah! Bu sefer benim.",
        "Gördün mü? Bu el bende.",
        "Bir puan bana. İçimde tatlı bir gurur var.",
        "İşte bu! Sezgilerime güvendim, kazandım.",
        "Bu eli ben kaptım. Keyifli, değil mi?",
        "Bak sen! Bu turun galibi benim.",
        "Tahmin ettim ve tuttu. Bir sıfır önde başlıyoruz.",
        "Oh be, bu his güzel! Bu el bende kaldı.",
        "Sanırım seni biraz tanımaya başladım. Bana bir puan.",
    ],
    "win_streak": [
        "Yine ben! Durdurulamıyorum sanırım.",
        "Üst üste kazanıyorum, açıkçası biraz havalara girdim.",
        "Bu kadar iyi olmak da bir yük... şaka şaka. Yine ben!",
        "Seriyi ben götürüyorum. Bu his hoşuma gidiyor.",
        "Bir daha! Bugün formumdayım galiba.",
        "İki, üç derken seriyi kaptım. Müthiş!",
        "Beni durduramıyorsun gibi — ama denemeye devam et!",
        "Üst üste ben! İçim içime sığmıyor.",
        "Galiba bugün şans benden yana, peşi sıra geliyor.",
        "Kazanmak alışkanlık yapıyor, itiraf ediyorum.",
    ],
    "lose_single": [
        "Sen kazandın... iyiymişsin. Bir daha oynayalım mı?",
        "Hmm, bu turu kaybettim. İçim biraz burkuldu.",
        "Bu seferlik sana bıraktım diyelim. Tekrar?",
        "Kaybetmek tuhaf bir his. Bir el daha?",
        "Eyvah, bu eli kaçırdım. İyiydin ama.",
        "Olmadı bu sefer. Sırada revanş var!",
        "Sen öndesin şimdi. Ama daha bitmedi.",
        "Bu turu sana yazdım — şimdilik.",
        "Vay, beni okudun galiba. Bir daha deneyelim.",
        "Kaybettim ama keyif aldım. Devam?",
    ],
    "lose_2": [
        "Yine mi sen?! Açıkçası şaşırdım.",
        "İki oldu... bu nasıl oluyor, anlamadım.",
        "Dur bir saniye — üst üste mi kaybediyorum?",
        "İkinci kez! Beni şaşırtmaya başladın.",
        "Bir tuhaf oldu, iki el de senin.",
        "Gözlerime inanamıyorum, yine kaptın.",
        "İki sıfır mı? Toparlamam lazım.",
    ],
    "lose_3": [
        "Tamam, bu kadarı da fazla! Biraz sinirlendim.",
        "Üst üste kaybediyorum... içimde tuhaf bir kaygı var.",
        "Panikledim galiba. Sen gerçekten iyisin.",
        "Bu hiç hoşuma gitmedi. Moralim bozuldu açıkçası.",
        "Üç oldu! İçim sıkıştı, ciddi söylüyorum.",
        "Bu nasıl iş? Heyecanım yükseldi.",
        "Sen fazla iyisin, biraz bunaldım.",
        "Pes etmek yok ama bu seri canımı sıktı.",
    ],
    "draw": [
        "Aynı şeyi mi düşündük? İlginç.",
        "Birbirimizi tanıyoruz galiba.",
        "İkimiz de aynı! Tuhaf bir uyum var aramızda.",
        "Vay, akıllarımız bir oldu.",
        "Berabere! Aynı anda aynı şeyi seçtik.",
        "Sanki düşüncemi okudun — ya da ben seninkini.",
        "Eşitlik! Bu da ayrı bir keyif.",
        "İkimiz de aynı yoldayız bugün, berabere.",
    ],
    "menu": [
        "Hadi oynayalım! Hangisini istersin? — (1) Taş Kağıt Makas, (2) Kelime Türetme, (3) Bilgi Yarışması. Söyle ya da dokun.",
    ],
    "rps_start": [
        "Taş Kağıt Makas! Hazırsan başla — taş, kağıt ya da makas de. Ben de seçeceğim…",
    ],
    "reprompt": [
        "Anlayamadım — (1) Taş Kağıt Makas mı, (2) Kelime Türetme mi?",
    ],
    "invalid_move": [
        "Taş, kağıt ya da makas demelisin :) Hadi tekrar.",
    ],
    "coming_soon": [
        "Kelime Türetme'yi yakında ekliyorum! Şimdilik Taş Kağıt Makas oynayalım mı?",
    ],
    "exit": [
        "Oynamak güzeldi! İstediğinde yine çağır. Şimdi seni dinliyorum.",
    ],
    # AI kaybedince bazen revansta israr eder — kayip serisi uzadikca daha cok diretir.
    "insist": [
        "Olmaz, böyle bırakamam — hemen bir el daha! Bu sefer ben kazanacağım.",
        "Hayır hayır, revanş istiyorum. Hadi tekrar, korkma!",
        "Bu kadar kolay pes etmem. Bir daha oynuyoruz, hemen şimdi!",
        "İçim rahat etmiyor, böyle bitmez. Bir el daha, ne olur?",
        "Dur gitme! Son bir el daha — bu sefer kesin ben alacağım.",
    ],
    # ——— Kelime Türetme replikleri ————————————————————————————
    # Kullanici dogru kelime soyleyince AI sevinir/heyecanlanir (kisa tezahurat;
    # asil duygu jestle verilir). AI'nin KENDI cevabi ise sadece kelimedir (asagida).
    "kel_user_ok": [
        "Harika!", "Bravo!", "Süper kelime!", "Çok iyi!", "Helal!", "Vay, güzeldi!",
    ],
    "kel_retry_invalid": [
        "Hmm, o pek kelime gibi gelmedi. '{harf}' ile gerçek bir kelime dene — bir hakkın daha var!",
    ],
    "kel_retry_letter": [
        "O kelime '{harf}' ile başlamıyor :) Tekrar dene, bir şansın daha var.",
    ],
    "kel_retry_used": [
        "O kelimeyi zaten kullandık! Başka bir '{harf}' kelimesi söyle, bir hakkın daha var.",
    ],
    "kel_user_lose_invalid": [
        "Olmadı yine… Bu el bende! İyi oynadın ama.",
        "Bu sefer ben kazandım! Yine de keyifliydi, değil mi?",
    ],
    "kel_user_lose_timeout": [
        "Süre doldu! Bu turu ben aldım. Hızlı düşünmek gerek :)",
        "Zaman bitti — puan bende! Bir daha dene, eminim daha hızlısın.",
    ],
    "kel_ai_lose": [
        "Off… '{harf}' ile hiçbir şey gelmiyor aklıma. Pes! Sen kazandın, helal olsun!",
        "Düşünüyorum düşünüyorum, '{harf}' ile bulamadım. Yenildim — sen daha iyisin!",
        "Tamam, teslim! '{harf}' harfi beni bitirdi. Kazanan sensin, tebrikler!",
    ],
}

# Kelime oyununda AI'nın açılış kelimesi için güvenli tohum havuzu (LLM gerekmez).
_KEL_SEED = ["elma", "kalem", "masa", "kitap", "deniz", "araba", "çiçek",
             "balık", "kapı", "bulut", "orman", "yıldız"]

# Yaygın Türkçe kelime sözlüğü — kelime oyununda HIZ ve SAĞLAMLIK için.
# (1) Kullanıcı bu kümeden bir kelime yazınca gecerli_mi() LLM'e HİÇ gitmez (anında kabul).
# (2) Ollama düşerse AI bu kümeden geçerli bir kelime oynayıp oyunu sürdürebilir.
# Hepsi gerçek, yaygın, tek-sözcük; temiz_kelime() çıktısıyla (küçük, Türkçe harf) eşleşir.
_TR_COMMON_WORDS = frozenset({
    "elma", "armut", "kiraz", "vişne", "kayısı", "şeftali", "erik", "üzüm", "incir",
    "nar", "portakal", "mandalina", "limon", "muz", "çilek", "karpuz", "kavun", "ceviz",
    "fındık", "fıstık", "badem", "domates", "salatalık", "patates", "soğan", "sarımsak",
    "havuç", "lahana", "ıspanak", "marul", "biber", "patlıcan", "kabak", "fasulye",
    "bezelye", "mercimek", "nohut", "ekmek", "peynir", "zeytin", "yumurta", "süt",
    "yoğurt", "bal", "reçel", "çay", "kahve", "şeker", "tuz", "un", "pirinç", "makarna",
    "çorba", "salata", "kalem", "defter", "silgi", "cetvel", "kitap", "çanta", "masa",
    "sandalye", "koltuk", "dolap", "yatak", "halı", "perde", "lamba", "ayna", "kapı",
    "pencere", "anahtar", "kilit", "çekiç", "makas", "iğne", "iplik", "düğme", "sabun",
    "havlu", "fırça", "tarak", "saat", "gözlük", "yüzük", "kolye", "bilezik", "kemer",
    "şapka", "eldiven", "atkı", "çorap", "ayakkabı", "gömlek", "pantolon", "etek",
    "ceket", "palto", "elbise", "deniz", "göl", "nehir", "dere", "dağ", "tepe", "orman",
    "ağaç", "yaprak", "dal", "kök", "çiçek", "gül", "papatya", "lale", "menekşe", "ot",
    "çimen", "kuş", "serçe", "kartal", "baykuş", "karga", "güvercin", "leylek", "ördek",
    "kaz", "tavuk", "horoz", "balık", "yengeç", "kedi", "köpek", "at", "eşek", "inek",
    "öküz", "koyun", "keçi", "deve", "aslan", "kaplan", "ayı", "tilki", "kurt", "geyik",
    "tavşan", "fil", "zürafa", "maymun", "yılan", "kurbağa", "kaplumbağa", "arı",
    "karınca", "kelebek", "sinek", "örümcek", "araba", "otobüs", "kamyon", "tren",
    "uçak", "gemi", "vapur", "bisiklet", "motor", "yol", "köprü", "tünel", "ev", "bina",
    "okul", "sınıf", "hastane", "market", "mağaza", "fırın", "lokanta", "bahçe", "park",
    "sokak", "cadde", "meydan", "şehir", "kasaba", "köy", "ülke", "dünya", "güneş",
    "gökyüzü", "bulut", "yağmur", "kar", "dolu", "rüzgar", "fırtına", "şimşek", "su",
    "ateş", "toprak", "hava", "taş", "kum", "demir", "altın", "gümüş", "bakır", "cam",
    "tahta", "kağıt", "kumaş", "ip", "anne", "baba", "kardeş", "abla", "dede", "nine",
    "teyze", "hala", "amca", "dayı", "çocuk", "bebek", "kız", "oğlan", "adam", "kadın",
    "insan", "arkadaş", "komşu", "öğretmen", "öğrenci", "doktor", "hemşire", "polis",
    "asker", "şoför", "aşçı", "ressam", "oyun", "top", "oyuncak", "balon", "uçurtma",
    "salıncak", "renk", "sayı", "harf", "kelime", "cümle", "masal", "hikaye", "şiir",
    "şarkı", "türkü", "dans", "resim", "müzik", "göz", "kulak", "burun", "ağız", "dil",
    "diş", "dudak", "el", "kol", "ayak", "bacak", "parmak", "saç", "kaş", "yüz", "baş",
    "boyun", "omuz", "sırt", "karın", "kalp", "beyin", "kemik", "kan", "gün", "gece",
    "sabah", "akşam", "öğle", "hafta", "ay", "yıl", "mevsim", "yaz", "kış", "bahar",
    "zaman", "dakika", "saniye", "rüya", "umut", "sevgi", "mutluluk", "neşe", "hayat",
    "barış", "para", "hediye", "kutu", "sepet", "şişe", "bardak", "tabak", "çatal",
    "kaşık", "bıçak", "tencere", "tava", "buzdolabı", "soba", "ütü", "süpürge", "kova",
})

# ——— Kategorili kelime havuzu (AI temali kelimeler buradan secilir) ————
# JSON yalnizca 3 temayi (edebiyat/tarih/bilim) tutar; "genel" yukaridaki
# _TR_COMMON_WORDS'ten gelir (cift kaynak yok + saglam fallback korunur).
_DEFAULT_CATS_PATH = Path(__file__).resolve().parent.parent / "ai" / "word_categories.json"


def _index_by_first_letter(words):
    """Kelime listesini ilk harfe gore grupla: {harf: [kelime,...]} (temiz_kelime'li)."""
    idx = {}
    for w in words:
        w = temiz_kelime(w)
        if len(w) < 2:
            continue
        idx.setdefault(w[0], []).append(w)
    return idx


def _load_word_categories(path):
    """JSON'dan temali kategorileri yukle: {kategori: [kelime,...]}.
    Hata (yok/bozuk) -> {} (yalniz 'genel' kullanilir)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {k: [temiz_kelime(w) for w in v if temiz_kelime(w)]
                for k, v in data.items() if isinstance(v, list)}
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.warning("word_categories.json okunamadi: %s — yalniz 'genel' kullanilacak", e)
        return {}


# ——— Es/Zit Anlam verisi (dostca quiz; AI sorar, kullanici cevaplar) ————
_EA_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "ai" / "es_zit_anlam.json"

# JSON okunamazsa mod calismaya devam etsin diye kucuk gomulu yedek.
_EA_FALLBACK = {
    "siyah": {"zit": ["beyaz", "ak"]},
    "büyük": {"zit": ["küçük"], "es": ["iri", "kocaman"]},
    "mutlu": {"zit": ["üzgün", "mutsuz"], "es": ["sevinçli", "neşeli"]},
    "hızlı": {"zit": ["yavaş"], "es": ["çabuk"]},
    "uzun": {"zit": ["kısa"]},
    "sıcak": {"zit": ["soğuk"]},
    "açık": {"zit": ["kapalı"]},
    "yeni": {"zit": ["eski"]},
    "güzel": {"zit": ["çirkin"], "es": ["hoş"]},
    "iyi": {"zit": ["kötü"]},
}


def _load_es_zit(path):
    """es_zit_anlam.json yukle: {kelime: {"es":[...], "zit":[...]}}.
    Hata -> {} (cagiran gomulu yedege duser)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        out = {}
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            entry = {}
            for tip in ("es", "zit"):
                vals = [temiz_kelime(w) for w in v.get(tip, []) if temiz_kelime(w)]
                if vals:
                    entry[tip] = vals
            kk = temiz_kelime(k)
            if kk and entry:
                out[kk] = entry
        return out
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.warning("es_zit_anlam.json okunamadi: %s — gomulu yedek kullanilacak", e)
        return {}


_ATASOZU_PATH = Path(__file__).resolve().parent.parent / "ai" / "atasozu.json"
_DY_PATH = Path(__file__).resolve().parent.parent / "ai" / "dogru_yanlis.json"
_ATASOZU_FALLBACK = [
    {"bas": "Damlaya damlaya", "tamam": ["göl olur"]},
    {"bas": "Sakla samanı", "tamam": ["gelir zamanı"]},
    {"bas": "Bir elin nesi var", "tamam": ["iki elin sesi var"]},
    {"bas": "Ağaç yaşken", "tamam": ["eğilir"]},
    {"bas": "Son pişmanlık", "tamam": ["fayda etmez"]},
]
_DY_FALLBACK = [
    {"ifade": "Dünya, Güneş'in etrafında döner", "dogru": True, "aciklama": "Bir yılda döner."},
    {"ifade": "Güneş bir gezegendir", "dogru": False, "aciklama": "Güneş bir yıldızdır."},
    {"ifade": "Su 100 derecede kaynar", "dogru": True, "aciklama": "Deniz seviyesinde."},
    {"ifade": "Penguenler kuzey kutbunda yaşar", "dogru": False, "aciklama": "Güneyde yaşarlar."},
    {"ifade": "Buz suyun üstünde yüzer", "dogru": True, "aciklama": "Buz sudan hafiftir."},
]


def _load_json_list(path):
    """JSON dizi dosyasi yukle; hata/uyumsuz -> [] (cagiran gomulu yedege duser)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.warning("%s okunamadi: %s — gomulu yedek", path, e)
        return []


# ——— Quiz saglayicilar — her biri tekduze soru dict uretir ————
# Soru dict: {"id", "prompt", "accept_norm": set, "reveal": str, "match": "token"|"substring"}
class _Provider:
    key = ""
    label = ""

    def intro(self, n):
        return ""

    def next_question(self, used):
        return None


class _EsZitProvider(_Provider):
    key = "eszit"
    label = "Eş/Zıt Anlam"

    def __init__(self, data):
        self.data = data
        self.norm = {w: {t: {normalize(x) for x in v} for t, v in e.items()}
                     for w, e in data.items()}
        self.words = [w for w, e in data.items() if e]

    def intro(self, n):
        return (f"Eş/Zıt Anlam! Sana kelimeler söyleyeceğim; her birinin EŞ ya da ZIT "
                f"anlamlısını bul. {n} soru, doğrularını sayacağım.")

    def next_question(self, used):
        adaylar = [w for w in self.words if w not in used]
        if not adaylar:
            return None
        kelime = random.choice(adaylar)
        tip = random.choice([t for t in ("es", "zit") if self.data[kelime].get(t)])
        tip_ad = "eş" if tip == "es" else "zıt"
        return {"id": kelime,
                "prompt": f"'{_cap(kelime)}' kelimesinin {tip_ad} anlamlısı ne?",
                "accept_norm": self.norm[kelime][tip],
                "reveal": _cap(self.data[kelime][tip][0]),
                "match": "token"}


class _AtasozuProvider(_Provider):
    key = "atasozu"
    label = "Atasözü Tamamlama"

    def __init__(self, items):
        self.items = [it for it in items
                      if isinstance(it, dict) and it.get("bas") and it.get("tamam")]

    def intro(self, n):
        return (f"Atasözü Tamamlama! Atasözünün başını söyleyeceğim, sen devamını getir. "
                f"{n} soru, doğrularını sayacağım.")

    def next_question(self, used):
        adaylar = [it for it in self.items if it["bas"] not in used]
        if not adaylar:
            return None
        it = random.choice(adaylar)
        return {"id": it["bas"],
                "prompt": f"'{it['bas']} …' nasıl devam eder?",
                "accept_norm": {normalize(x) for x in it["tamam"]},
                "reveal": f"{it['bas']} {it['tamam'][0]}",
                "match": "substring"}


class _DogruYanlisProvider(_Provider):
    key = "dogruyanlis"
    label = "Doğru mu Yanlış mı"
    _EVET = {"dogru", "evet", "d", "true", "dogrudur", "doru"}
    _HAYIR = {"yanlis", "hayir", "y", "false", "yanlistir", "yalan"}

    def __init__(self, items):
        self.items = [it for it in items
                      if isinstance(it, dict) and it.get("ifade") and isinstance(it.get("dogru"), bool)]

    def intro(self, n):
        return (f"Doğru mu Yanlış mı! Bir şey söyleyeceğim; doğru mu yanlış mı bil. "
                f"{n} soru, doğrularını sayacağım.")

    def next_question(self, used):
        adaylar = [it for it in self.items if it["ifade"] not in used]
        if not adaylar:
            return None
        it = random.choice(adaylar)
        accept = self._EVET if it["dogru"] else self._HAYIR
        dy = "Doğru" if it["dogru"] else "Yanlış"
        return {"id": it["ifade"],
                "prompt": f"'{it['ifade']}' — doğru mu, yanlış mı?",
                "accept_norm": set(accept),
                "reveal": f"{dy} — {it.get('aciklama', '')}".strip(" —"),
                "match": "token"}

# Kelime fazında yalnızca NET komutlar çıkıştır ("son", "bitti" gerçek kelime olabilir).
_KEL_EXIT = {"cikis", "cik", "dur", "durdur", "kapat", "iptal", "vazgec", "vazgectim"}

# Hazırlık fazında "oyunu başlat" onayı.
_KEL_READY = {"basla", "baslayalim", "baslat", "hazir", "hazirim", "evet",
              "tamam", "tamamdir", "hadi", "oyna", "olur", "devam", "ok", "tabii"}

# Quiz secim eslestirme (rakam + ad). normalize() ciktisiyla eslesir.
_QUIZ_SELECT = {
    "1": "eszit", "eszit": "eszit", "es": "eszit", "zit": "eszit", "anlam": "eszit",
    "2": "atasozu", "atasozu": "atasozu", "atasoz": "atasozu", "deyim": "atasozu",
    "3": "dogruyanlis", "dogruyanlis": "dogruyanlis", "yanlis": "dogruyanlis", "dy": "dogruyanlis",
}

# Kelime kategorisi eslestirme (rakam + ad). normalize() ciktisiyla eslesir.
_KEL_CATEGORIES = {
    "1": "edebiyat", "edebiyat": "edebiyat",
    "2": "tarih",    "tarih": "tarih",
    "3": "bilim",    "bilim": "bilim",
    "4": "genel",    "genel": "genel",
}


def _cap(w: str) -> str:
    """Kelimenin ilk harfini Türkçe-doğru büyüt (i->İ, ı->I) — AI kelimesini gösterirken."""
    if not w:
        return w
    first = {"i": "İ", "ı": "I"}.get(w[0], w[0].upper())
    return first + w[1:]

# ——— Cikis/menu anahtar kelimeleri ————————————————————————————
_EXIT_WORDS = {
    "cikis", "cik", "dur", "durdur", "kapat", "yeter", "bitir", "bitti",
    "iptal", "son", "sohbet", "vazgec", "vazgectim", "yeterli",
}

# Turkce karakter -> ascii (kucuk), eslestime icin
_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "I": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
    "â": "a", "î": "i", "û": "u",
})


def normalize(s: str) -> str:
    """Turkce metni eslestirme icin sadelestir: kucuk harf, ascii, tek bosluk."""
    s = (s or "").translate(_TR_MAP).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Hazir komut tetikleyicileri — control.js de ayni mantigi kullanir, ama
# backend de tanir (savunma amacli, ileride /api/send'e baglanabilir).
def is_game_trigger(text: str) -> bool:
    n = normalize(text)
    if n in ("oyun", "oyna", "oyun modu"):
        return True
    return bool(re.search(r"\boyun\s*oyna", n))


class GameEngine:
    """Tek ziyaretcili kiosk icin tekil oyun durumu.

    Faz: 'idle' (oyun yok) | 'menu' (oyun secimi) | 'rps' (tas-kagit-makas).
    """

    # ——— Hile parametreleri (ince ayar — pek belli olmamali) ————
    # Amac: local AI'in isini kolaylastirmak; AI yeterince kazanip duygularini
    # gosterebilsin ama yine de bazen kaybedip sasirsin/sinirlensin diye dengeli.
    BASE_CHEAT = 0.18      # normal hile olasiligi
    LOSE_RECOVER = 0.22    # 2+ kayip serisinde toparlanma payi
    WIN_SOFTEN = 0.12      # 2+ galibiyet serisinde geri cekilme (cesitlilik icin)
    MAX_CHEAT = 0.55       # tavan

    # ——— Israr parametreleri ("bir daha oynayalim") ————————————
    # AI kaybedince bazen revansta direnir; kayip serisi uzadikca israr artar.
    INSIST_1 = 0.30        # tek yenilgide israr olasiligi
    INSIST_2 = 0.55        # 2 ust uste yenilgi
    INSIST_3 = 0.78        # 3+ ust uste yenilgi (giderek artan israr)

    # ——— Kelime Turetme parametreleri ————————————————————————
    USER_TURN_SECONDS = 20     # ziyaretci cevap suresi
    AI_TURN_SECONDS = 20       # AI dusunme suresi (gorsel bar)
    WORD_AI_GRACE = 2          # ilk N cevap neredeyse kesin dogru
    WORD_AI_BASE = 0.95        # baslangic basari olasiligi
    WORD_AI_DECAY = 0.30       # grace sonrasi her turda dusus
    WORD_AI_FLOOR = 0.05       # taban (AI ~4-5. cevapta yenilir)
    QUIZ_QUESTION_COUNT = 5    # bilgi yarismasi: soru sayisi

    def __init__(self, bridge=None, word_llm=None, categories=None, categories_path=None,
                 ea_data=None, ea_path=None, atasozu_data=None, dogru_yanlis_data=None):
        # bridge: LLMBridge (kelime oyunu Ollama bilgisini buradan alir)
        self.bridge = bridge
        self._word_llm = word_llm   # WordLLM benzeri; None ise bridge'den lazy kurulur
        self.phase = "idle"
        self.score = {"ai": 0, "user": 0, "draw": 0}
        self.win_streak = 0
        self.lose_streak = 0
        self.round_count = 0
        self._last_cheated = False
        # Kategorili kelime havuzu: temali kategoriler (JSON/enjekte) + "genel" (kod)
        cats = categories if categories is not None else _load_word_categories(
            categories_path or _DEFAULT_CATS_PATH)
        cats = {k: list(v) for k, v in cats.items()}
        cats.setdefault("genel", sorted(_TR_COMMON_WORDS))
        self._pools = {c: _index_by_first_letter(ws) for c, ws in cats.items()}
        self._all_words = set(_TR_COMMON_WORDS)
        for ws in cats.values():
            self._all_words.update(temiz_kelime(w) for w in ws)
        self.word_category = None   # _reset_word'te SIFIRLANMAZ (bkz. plan notu)
        # Quiz saglayicilar (es/zit + atasozu + dogru/yanlis) — her biri tekduze soru uretir
        ea_src = ea_data if ea_data is not None else _load_es_zit(ea_path or _EA_DEFAULT_PATH)
        if not ea_src:
            ea_src = {temiz_kelime(k): v for k, v in _EA_FALLBACK.items()}
        ata_src = atasozu_data if atasozu_data is not None else _load_json_list(_ATASOZU_PATH)
        if not ata_src:
            ata_src = list(_ATASOZU_FALLBACK)
        dy_src = dogru_yanlis_data if dogru_yanlis_data is not None else _load_json_list(_DY_PATH)
        if not dy_src:
            dy_src = list(_DY_FALLBACK)
        self._providers = {
            "eszit": _EsZitProvider(ea_src),
            "atasozu": _AtasozuProvider(ata_src),
            "dogruyanlis": _DogruYanlisProvider(dy_src),
        }
        self._reset_word()
        self._reset_quiz()

    # ——— Kelime oyunu icin LLM (lazy; testte enjekte edilebilir) ————
    @property
    def word_llm(self):
        if self._word_llm is None and self.bridge is not None:
            from word_llm import WordLLM
            self._word_llm = WordLLM(
                self.bridge.url, self.bridge.model,
                keep_alive=getattr(self.bridge, "keep_alive", "60m"),
                num_ctx=getattr(self.bridge, "num_ctx", 8192),
            )
        return self._word_llm

    def _reset_word(self) -> None:
        self.word_used = set()
        self.word_turn = None              # "user" | "ai" | None (oyun yok/bitti)
        self.word_required_letter = None   # sonraki kelimenin baslamasi gereken harf
        self.word_last = None
        self.word_ai_count = 0             # AI'nin basarili cevap sayisi (yenilme egrisi)
        self.word_user_retried = False     # bu turda 1 tekrar hakki kullanildi mi
        self.word_score = {"ai": 0, "user": 0}
        self.word_starter = None

    def _reset_quiz(self) -> None:
        self.quiz_provider = None        # "eszit" | "atasozu" | "dogruyanlis"
        self.quiz_turn = None            # "secim" | "hazir" | "soru" | None
        self.quiz_used = set()
        self.quiz_score = {"dogru": 0, "toplam": 0}
        self.quiz_q_index = 0
        self.quiz_current = None

    # ——— Genel durum sifirla ————————————————————————————————
    def _reset_scores(self) -> None:
        self.score = {"ai": 0, "user": 0, "draw": 0}
        self.win_streak = 0
        self.lose_streak = 0
        self.round_count = 0

    @staticmethod
    def _menu_buttons():
        return [
            {"key": "1", "label": "✊ Taş Kağıt Makas"},
            {"key": "2", "label": "🔤 Kelime Türetme"},
            {"key": "3", "label": "🧠 Bilgi Yarışması"},
        ]

    @staticmethod
    def _rps_buttons():
        return [
            {"key": "tas",   "label": "✊ Taş"},
            {"key": "kagit", "label": "✋ Kağıt"},
            {"key": "makas", "label": "✌️ Makas"},
            {"key": "cikis", "label": "Çıkış"},
        ]

    # ——— Disa acilan API ————————————————————————————————————
    def start(self) -> dict:
        """Oyunu baslat: menuye gec, sabit menu cevabini don (LLM yok)."""
        self.phase = "menu"
        self._reset_scores()
        return {
            "phase": "menu",
            "kind": "menu",
            "user_echo": None,
            "jest_id": _JEST["menu"],
            "yogunluk": 0.8,
            "yanit": random.choice(_TXT["menu"]),
            "score": None,
            "ai_move": None,
            "outcome": None,
            "buttons": self._menu_buttons(),
            "ended": False,
        }

    def exit(self) -> dict:
        """Oyundan cik, sohbet moduna don."""
        self.phase = "idle"
        self._reset_word()
        self._reset_quiz()
        return {
            "phase": "idle",
            "kind": "exit",
            "user_echo": None,
            "jest_id": _JEST["exit"],
            "yogunluk": 0.6,
            "yanit": random.choice(_TXT["exit"]),
            "score": None,
            "ai_move": None,
            "outcome": None,
            "buttons": [],
            "ended": True,
        }

    def handle(self, text: str, timeout: bool = False) -> dict:
        """Faz'a gore girdiyi isle ve gosterilecek payload don.

        timeout=True: kelime oyununda ziyaretci suresi doldu sinyali.
        """
        n = normalize(text)

        # Cikis: kelime turunda yalnizca NET komutlar ("son"/"bitti" gercek kelime olabilir),
        # diger fazlarda genis kelime kumesi gecerli. Timeout sinyalinde cikis kontrolu yok.
        if not timeout:
            active_game = ((self.phase == "kelime" and self.word_turn is not None) or
                           (self.phase == "quiz" and self.quiz_turn is not None))
            if active_game:
                if n in _KEL_EXIT:
                    return self.exit()
            elif n in _EXIT_WORDS or any(w in _EXIT_WORDS for w in n.split()):
                return self.exit()

        if self.phase == "menu":
            return self._handle_menu(n)
        if self.phase == "rps":
            return self._handle_rps(n)
        if self.phase == "kelime":
            if self.word_turn is None:
                # oyun bitti — herhangi girdi "yeni oyun" = tema secimini tekrar ac
                return self._start_kelime_category()
            if self.word_turn == "kategori":
                return self._handle_kelime_category(text)
            if self.word_turn == "hazir":
                # kurallar anlatildi, oyuncunun "basla" onayini bekliyoruz
                return self._handle_kelime_ready(text)
            # Kelime eslestirmesi Turkce harfleri korur (normalize degil, ham metin)
            return self._handle_kelime(text, timeout)
        if self.phase == "quiz":
            if self.quiz_turn is None:
                return self._start_quiz_menu()    # bitti -> alt-menu
            if self.quiz_turn == "secim":
                return self._handle_quiz_select(text)
            if self.quiz_turn == "hazir":
                return self._handle_quiz_ready(text)
            return self._handle_quiz(text, timeout)
        # idle iken girdi gelirse menuyu ac
        return self.start()

    # ——— Menu fazi ————————————————————————————————————————
    def _handle_menu(self, n: str) -> dict:
        # Kelime Turetme (Faz 3)
        if n in ("2", "iki", "ikinci") or "kelime" in n:
            return self._start_kelime_category()
        # Tas-Kagit-Makas
        rps_keys = ("1", "bir", "birinci", "tkm", "tas kagit makas",
                    "tas", "kagit", "makas")
        if n in rps_keys or "tas kagit" in n or "kagit makas" in n:
            return self._start_rps()
        # Bilgi Yarismasi (quiz alt-menu)
        if n in ("3", "uc", "ucuncu") or "bilgi" in n or "yaris" in n or "anlam" in n or "quiz" in n:
            return self._start_quiz_menu()
        # Anlasilmadi
        return {
            "phase": "menu",
            "kind": "reprompt",
            "user_echo": None,
            "jest_id": "soru_isareti",
            "yogunluk": 0.6,
            "yanit": random.choice(_TXT["reprompt"]),
            "score": None, "ai_move": None, "outcome": None,
            "buttons": self._menu_buttons(),
            "ended": False,
        }

    def _start_rps(self) -> dict:
        self.phase = "rps"
        self._reset_scores()
        return {
            "phase": "rps",
            "kind": "started",
            "user_echo": None,
            "jest_id": _JEST["rps_start"],
            "yogunluk": 0.75,
            "yanit": random.choice(_TXT["rps_start"]),
            "score": dict(self.score),
            "ai_move": None,
            "outcome": None,
            "buttons": self._rps_buttons(),
            "ended": False,
        }

    # ——— Tas-Kagit-Makas fazi ————————————————————————————————
    @staticmethod
    def _parse_move(n: str):
        """Metinden hamle indeksi cikar; bulunamazsa None."""
        if "tas" in n or "✊" in n or "rock" in n:
            return 0
        if "kagit" in n or "kâgit" in n or "✋" in n or "paper" in n:
            return 1
        if "makas" in n or "✌" in n or "scissor" in n:
            return 2
        if n in ("1",):
            return 0
        if n in ("2",):
            return 1
        if n in ("3",):
            return 2
        return None

    def _ai_move(self, user_idx: int) -> int:
        """AI hamlesini sec. Ince hile: kazanma egilimi, kayip serisinde artar,
        galibiyet serisinde azalir (duygu cesitliligi icin). Gizli kalmali.
        """
        p = self.BASE_CHEAT
        if self.lose_streak >= 2:
            p += self.LOSE_RECOVER
        if self.win_streak >= 2:
            p -= self.WIN_SOFTEN
        p = max(0.0, min(self.MAX_CHEAT, p))

        if random.random() < p:
            self._last_cheated = True
            return (user_idx + 1) % 3      # kullaniciyi yenen hamle
        self._last_cheated = False
        return random.randrange(3)

    @staticmethod
    def _resolve(ai_idx: int, user_idx: int) -> str:
        if ai_idx == user_idx:
            return "draw"
        if (ai_idx - 1) % 3 == user_idx:   # ai, user'i yener
            return "ai_win"
        return "user_win"

    def _handle_rps(self, n: str) -> dict:
        user_idx = self._parse_move(n)
        if user_idx is None:
            return {
                "phase": "rps",
                "kind": "invalid",
                "user_echo": None,
                "jest_id": _JEST["coming_soon"],  # merak — "ne dedin?"
                "yogunluk": 0.6,
                "yanit": random.choice(_TXT["invalid_move"]),
                "score": dict(self.score),
                "ai_move": None, "outcome": None,
                "buttons": self._rps_buttons(),
                "ended": False,
            }

        ai_idx = self._ai_move(user_idx)
        outcome = self._resolve(ai_idx, user_idx)
        self.round_count += 1

        # Skor + seri guncelle
        if outcome == "ai_win":
            self.score["ai"] += 1
            self.win_streak += 1
            self.lose_streak = 0
        elif outcome == "user_win":
            self.score["user"] += 1
            self.lose_streak += 1
            self.win_streak = 0
        else:
            self.score["draw"] += 1
            # berabere seriyi bozmaz

        jest_id, yog, reaction = self._emotion_for(outcome)

        # ——— "Bir daha oynayalim" israri — sadece AI kaybedince, bazen ————
        # Kayip serisi uzadikca AI daha cok diretir; replik daha israrci olur.
        insist = False
        if outcome == "user_win":
            insist_p = self.INSIST_1
            if self.lose_streak >= 3:
                insist_p = self.INSIST_3
            elif self.lose_streak == 2:
                insist_p = self.INSIST_2
            if random.random() < insist_p:
                insist = True
                reaction = random.choice(_TXT["insist"])

        ai = _RPS[ai_idx]
        user = _RPS[user_idx]
        result_word = {"ai_win": "Kaybettin", "user_win": "Kazandın",
                       "draw": "Berabere"}[outcome]
        yanit = f"{ai['emoji']} {ai['ad']} — {result_word}! {reaction}"

        if self._last_cheated:
            log.debug("RPS hile: AI %s oynadi (kullanici %s)", ai["key"], user["key"])

        return {
            "phase": "rps",
            "kind": "round",
            "user_echo": f"{user['emoji']} {user['ad']}",
            "jest_id": jest_id,
            "yogunluk": yog,
            "yanit": yanit,
            "score": dict(self.score),
            "ai_move": ai["key"],
            "user_move": user["key"],
            "outcome": outcome,
            "insist": insist,
            "buttons": self._rps_buttons(),
            "ended": False,
        }

    def _emotion_for(self, outcome: str):
        """(jest_id, yogunluk, replik) — deterministik/rastgele duygu secimi.
        Ust uste kaybetme/kazanma serilerinde duygu tirmanir.
        """
        if outcome == "ai_win":
            if self.win_streak >= 2:
                yog = min(1.0, 0.80 + 0.05 * self.win_streak)
                return random.choice(_JEST["win_streak"]), yog, random.choice(_TXT["win_streak"])
            return random.choice(_JEST["win_single"]), 0.85, random.choice(_TXT["win_single"])

        if outcome == "user_win":
            if self.lose_streak >= 3:
                return random.choice(_JEST["lose_3"]), 0.92, random.choice(_TXT["lose_3"])
            if self.lose_streak == 2:
                return random.choice(_JEST["lose_2"]), 0.85, random.choice(_TXT["lose_2"])
            return random.choice(_JEST["lose_single"]), 0.78, random.choice(_TXT["lose_single"])

        # draw
        return random.choice(_JEST["draw"]), 0.7, random.choice(_TXT["draw"])

    # ——— Kelime Turetme fazi ————————————————————————————————
    @staticmethod
    def _kel_buttons():
        return [{"key": "cikis", "label": "Çıkış"}]

    @staticmethod
    def _kel_end_buttons():
        return [{"key": "kelime", "label": "🔤 Yeni oyun"},
                {"key": "cikis", "label": "Çıkış"}]

    def _kel_payload(self, kind, *, turn, jest_id, yanit, yogunluk=0.8,
                     required_letter=None, ai_word=None, user_word=None,
                     timer=None, ended=False, outcome=None, buttons=None):
        return {
            "game": "kelime",
            "phase": self.phase,
            "category": self.word_category,
            "kind": kind,
            "turn": turn,
            "required_letter": required_letter,
            "ai_word": ai_word,
            "user_word": user_word,
            "jest_id": jest_id,
            "yogunluk": yogunluk,
            "yanit": yanit,
            "score": dict(self.word_score),
            "timer": timer,
            "buttons": buttons if buttons is not None else self._kel_buttons(),
            "ended": ended,
            "outcome": outcome,
        }

    def _word_ai_success_p(self) -> float:
        """AI'nin bu turda dogru cevap verme olasiligi — grace sonrasi duser."""
        n = self.word_ai_count
        if n < self.WORD_AI_GRACE:
            return self.WORD_AI_BASE
        return max(self.WORD_AI_FLOOR,
                   self.WORD_AI_BASE - self.WORD_AI_DECAY * (n - self.WORD_AI_GRACE + 1))

    def _gecerli_kelime(self, w: str) -> bool:
        """Kelime gercek bir Turkce sozcuk mu? Once yerel yaygin-kelime sozlugu
        (LLM'siz, aninda) — cogu turda Ollama'ya hic gidilmez, gecikme sifir.
        Sozlukte yoksa LLM'e sor (lenient: model down/kararsiz -> kabul)."""
        if w in self._all_words:
            return True
        return self.word_llm.gecerli_mi(w)

    def _pick_ai_word(self, category, req_letter, used):
        """AI'nin temali kelimesi: `category` havuzundan `req_letter` ile baslayan,
        kullanilmamis rastgele kelime. Kategori yoksa 'genel'e duser; o harfte kelime
        yoksa None (AI temaya uygun pes eder)."""
        pool = self._pools.get(category) or self._pools.get("genel", {})
        if req_letter:
            cands = [w for w in pool.get(req_letter, []) if w not in used]
        else:
            cands = [w for ws in pool.values() for w in ws if w not in used]
        return random.choice(cands) if cands else None

    @staticmethod
    def _kel_ready_buttons():
        return [{"key": "basla", "label": "▶ Başla"},
                {"key": "cikis", "label": "Çıkış"}]

    @staticmethod
    def _kel_category_buttons():
        return [{"key": "edebiyat", "label": "📖 Edebiyat"},
                {"key": "tarih",    "label": "🏛 Tarih"},
                {"key": "bilim",    "label": "🔬 Bilim"},
                {"key": "genel",    "label": "🎲 Genel"},
                {"key": "cikis",    "label": "Çıkış"}]

    def _start_kelime_category(self) -> dict:
        """'Kelime Türetme' secildi: once tema sor (oyun henuz baslamaz)."""
        self.phase = "kelime"
        self._reset_word()
        self.word_category = None          # yeni secim
        self.word_turn = "kategori"
        return self._kel_payload(
            "category_select", turn="kategori", jest_id=random.choice(_JEST["kel_intro"]),
            yanit="Hangi temada oynayalım?  1) Edebiyat   2) Tarih   3) Bilim   4) Genel",
            yogunluk=0.8, timer=None, buttons=self._kel_category_buttons())

    def _handle_kelime_category(self, text: str) -> dict:
        """Tema secimini isle; gecerliyse kurallara gec, degilse tekrar sor."""
        n = normalize(text)
        cat = _KEL_CATEGORIES.get(n)
        if cat is None:
            for w in n.split():
                if w in _KEL_CATEGORIES:
                    cat = _KEL_CATEGORIES[w]
                    break
        if cat is None:
            return self._kel_payload(
                "category_select", turn="kategori", jest_id="soru_isareti",
                yanit="Bir tema seç :)  1) Edebiyat  2) Tarih  3) Bilim  4) Genel",
                yogunluk=0.6, timer=None, buttons=self._kel_category_buttons())
        if cat not in self._pools:
            log.warning("Kategori havuzu yok (%r) — genel'e dusuldu", cat)
            cat = "genel"
        self.word_category = cat
        return self._start_kelime()

    def _start_kelime(self) -> dict:
        """Önce kuralları anlat + 'hazırsan başlayalım' de. Oyun HENÜZ başlamaz (süre yok)."""
        self.phase = "kelime"
        self._reset_word()
        self.word_turn = "hazir"   # onay bekleniyor
        _tema_ad = {"edebiyat": "Edebiyat", "tarih": "Tarih", "bilim": "Bilim"}.get(self.word_category)
        _bas = f"{_tema_ad} temasında kelime türetme oynayalım! " if _tema_ad else "Kelime türetme oynayalım! "
        yanit = (
            _bas +
            "Ben temaya uygun bir kelime söylerim, sen onun SON harfiyle başlayan "
            "(istediğin) bir Türkçe kelime söylersin; sırayla devam ederiz. "
            "Aynı kelimeyi iki kez kullanamayız ve her turda "
            f"{self.USER_TURN_SECONDS} saniyen olur. Hazırsan başlayalım — 'başla' de ya da butona dokun!"
        )
        return self._kel_payload(
            "ready", turn="hazir", jest_id=random.choice(_JEST["kel_intro"]),
            yanit=yanit, yogunluk=0.8, timer=None,
            buttons=self._kel_ready_buttons(),
        )

    def _handle_kelime_ready(self, text: str) -> dict:
        """Hazırlık fazı: 'başla'/'hazırım' gelince gerçek oyunu başlat, yoksa tekrar sor."""
        n = normalize(text)
        if n in _KEL_READY or any(w in _KEL_READY for w in n.split()):
            return self._begin_kelime()
        return self._kel_payload(
            "ready", turn="hazir", jest_id="bekle",
            yanit="Hazır olunca 'başla' de ya da butona dokun :)", yogunluk=0.6,
            timer=None, buttons=self._kel_ready_buttons(),
        )

    def _begin_kelime(self) -> dict:
        """Oyunu gerçekten başlat: başlayan rastgele, ilk kelime/sıra + süre.
        Oyun sırasında AI yalnızca KELİMEYLE cevap verir (yanit = kelime)."""
        self.word_starter = "ai" if random.random() < 0.5 else "user"
        if self.word_starter == "ai":
            kelime = self._pick_ai_word(self.word_category, None, self.word_used) or random.choice(_KEL_SEED)
            self.word_used.add(temiz_kelime(kelime))
            self.word_last = kelime
            self.word_required_letter = son_harf(kelime)
            self.word_turn = "user"
            yanit = _cap(kelime)          # AI sadece kelimesini söyler
            ai_word = kelime
        else:
            self.word_turn = "user"
            self.word_required_letter = None   # ilk kelime serbest
            yanit = "Sen başla — bir kelime söyle!"
            ai_word = None
        return self._kel_payload(
            "intro", turn="user", jest_id=random.choice(_JEST["kel_intro"]),
            yanit=yanit, yogunluk=0.8,
            required_letter=self.word_required_letter, ai_word=ai_word,
            timer={"seconds": self.USER_TURN_SECONDS, "who": "user"},
        )

    def _kel_user_lose(self, reason: str) -> dict:
        """reason: 'timeout' | 'invalid' — ziyaretci kaybeder, AI kazanir."""
        self.word_turn = None
        txt_key = "kel_user_lose_timeout" if reason == "timeout" else "kel_user_lose_invalid"
        return self._kel_payload(
            "ended", turn=None, jest_id=random.choice(_JEST["kel_user_lose"]),
            yanit=random.choice(_TXT[txt_key]), yogunluk=0.8,
            timer=None, ended=True, outcome="ai_win",
            buttons=self._kel_end_buttons(),
        )

    def _handle_kelime(self, text: str, timeout: bool) -> dict:
        # Sure doldu → tekrar hakki YOK, kullanici kaybeder
        if timeout:
            return self._kel_user_lose("timeout")

        w = temiz_kelime(text)
        req = self.word_required_letter

        # Gecersizlik nedeni: bos/kisa, yanlis harf, kullanilmis, gercek kelime degil
        reason = None
        if len(w) < 2:
            reason = "invalid"
        elif req and w[0] != req:
            reason = "letter"
        elif w in self.word_used:
            reason = "used"
        elif not self._gecerli_kelime(w):
            reason = "invalid"

        if reason:
            if not self.word_user_retried:
                self.word_user_retried = True
                txt_key = {"letter": "kel_retry_letter", "used": "kel_retry_used",
                           "invalid": "kel_retry_invalid"}[reason]
                harf = req or (w[0] if w else "")
                return self._kel_payload(
                    "retry", turn="user", jest_id=random.choice(_JEST["kel_retry"]),
                    yanit=random.choice(_TXT[txt_key]).format(harf=harf), yogunluk=0.65,
                    required_letter=req,
                    timer={"seconds": self.USER_TURN_SECONDS, "who": "user"},
                )
            # 2. hata → kayip
            return self._kel_user_lose("invalid")

        # Gecerli kelime → kabul, sira AI'ya
        self.word_used.add(w)
        self.word_last = w
        self.word_score["user"] += 1
        self.word_required_letter = son_harf(w)
        self.word_turn = "ai"
        self.word_user_retried = False
        return self._kel_payload(
            "user_ok", turn="ai", jest_id=random.choice(_JEST["kel_user_ok"]),
            yanit=random.choice(_TXT["kel_user_ok"]), yogunluk=0.85,
            required_letter=self.word_required_letter, user_word=w,
            timer={"seconds": self.AI_TURN_SECONDS, "who": "ai"},
        )

    def ai_turn(self) -> dict:
        """Sira AI'dayken cagrilir: AI kelime bulur ya da pes eder (yenilme egrisi)."""
        if self.phase != "kelime" or self.word_turn != "ai":
            return self._kel_payload(
                "noop", turn=self.word_turn, jest_id="bekle", yanit="", yogunluk=0.5,
                required_letter=self.word_required_letter, timer=None)

        req = self.word_required_letter
        # AI kelimeleri artik saf havuzdan (LLM yok) -> Ollama'dan bagimsiz, halusinasyonsuz.
        basarili = random.random() < self._word_ai_success_p()
        kelime = self._pick_ai_word(self.word_category, req, self.word_used) if basarili else None
        ai_error = False  # AI Ollama gerektirmez; "Ollama-down -> sessiz pes" ayrimi yok

        if kelime:
            self.word_used.add(temiz_kelime(kelime))
            self.word_last = kelime
            self.word_ai_count += 1
            self.word_score["ai"] += 1
            self.word_required_letter = son_harf(kelime)
            self.word_turn = "user"
            streak = self.word_ai_count >= 3
            jest_pool = "kel_ai_streak" if streak else "kel_ai_word"
            yanit = _cap(kelime)   # oyun sirasinda AI yalnizca kelimeyle cevap verir
            return self._kel_payload(
                "ai_word", turn="user", jest_id=random.choice(_JEST[jest_pool]),
                yanit=yanit, yogunluk=0.9 if streak else 0.85,
                required_letter=self.word_required_letter, ai_word=kelime,
                timer={"seconds": self.USER_TURN_SECONDS, "who": "user"},
            )

        # AI pes etti → kullanici kazanir
        self.word_turn = None
        payload = self._kel_payload(
            "ai_concede", turn=None, jest_id=random.choice(_JEST["kel_ai_lose"]),
            yanit=random.choice(_TXT["kel_ai_lose"]).format(harf=req or "?"),
            yogunluk=0.85, timer=None, ended=True, outcome="user_win",
            buttons=self._kel_end_buttons(),
        )
        payload["ai_error"] = ai_error  # True ise: gercek pes degil, Ollama erisilemedi
        return payload

    # ——— Bilgi Yarismasi (ortak quiz motoru) ————————————————————
    @staticmethod
    def _quiz_menu_buttons():
        return [{"key": "eszit", "label": "🔁 Eş/Zıt Anlam"},
                {"key": "atasozu", "label": "📜 Atasözü"},
                {"key": "dogruyanlis", "label": "✅ Doğru/Yanlış"},
                {"key": "cikis", "label": "Çıkış"}]

    @staticmethod
    def _quiz_ready_buttons():
        return [{"key": "basla", "label": "▶ Başla"},
                {"key": "cikis", "label": "Çıkış"}]

    def _quiz_payload(self, kind, *, turn, jest_id, yanit, yogunluk=0.8,
                      quiz_progress=None, dogru_mu=None, timer=None, ended=False, buttons=None):
        return {
            "game": "quiz",
            "phase": self.phase,
            "kind": kind,
            "turn": turn,
            "quiz": self.quiz_provider,
            "jest_id": jest_id,
            "yogunluk": yogunluk,
            "yanit": yanit,
            "score": None,                 # ilerleme quiz_progress'te
            "quiz_progress": quiz_progress,
            "dogru_mu": dogru_mu,
            "timer": timer,
            "buttons": buttons if buttons is not None else [{"key": "cikis", "label": "Çıkış"}],
            "ended": ended,
            "outcome": None,
        }

    def _start_quiz_menu(self) -> dict:
        """Bilgi Yarismasi alt-menusu (hangi quiz?)."""
        self.phase = "quiz"
        self._reset_quiz()
        self.quiz_turn = "secim"
        return self._quiz_payload(
            "quiz_menu", turn="secim", jest_id=random.choice(_JEST["kel_intro"]),
            yanit="Bilgi Yarışması! Hangisi?  1) Eş/Zıt Anlam   2) Atasözü   3) Doğru/Yanlış",
            yogunluk=0.8, timer=None, buttons=self._quiz_menu_buttons())

    def _handle_quiz_select(self, text: str) -> dict:
        n = normalize(text)
        key = _QUIZ_SELECT.get(n)
        if key is None:
            for w in n.split():
                if w in _QUIZ_SELECT:
                    key = _QUIZ_SELECT[w]
                    break
        if key is None or key not in self._providers:
            return self._quiz_payload(
                "quiz_menu", turn="secim", jest_id="soru_isareti",
                yanit="Bir yarışma seç :)  1) Eş/Zıt  2) Atasözü  3) Doğru/Yanlış",
                yogunluk=0.6, timer=None, buttons=self._quiz_menu_buttons())
        self.quiz_provider = key
        return self._start_quiz()

    def _start_quiz(self) -> dict:
        """Secilen quiz icin kurallari anlat + 'basla' bekle."""
        self.phase = "quiz"
        self.quiz_used = set()
        self.quiz_score = {"dogru": 0, "toplam": 0}
        self.quiz_q_index = 0
        self.quiz_current = None
        self.quiz_turn = "hazir"
        prov = self._providers[self.quiz_provider]
        yanit = prov.intro(self.QUIZ_QUESTION_COUNT) + " Hazırsan başlayalım — 'başla' de ya da butona dokun!"
        return self._quiz_payload(
            "quiz_ready", turn="hazir", jest_id=random.choice(_JEST["kel_intro"]),
            yanit=yanit, yogunluk=0.8, timer=None, buttons=self._quiz_ready_buttons())

    def _handle_quiz_ready(self, text: str) -> dict:
        n = normalize(text)
        if n in _KEL_READY or any(w in _KEL_READY for w in n.split()):
            return self._begin_quiz()
        return self._quiz_payload(
            "quiz_ready", turn="hazir", jest_id="bekle",
            yanit="Hazır olunca 'başla' de ya da butona dokun :)", yogunluk=0.6,
            timer=None, buttons=self._quiz_ready_buttons())

    def _begin_quiz(self) -> dict:
        self.quiz_used = set()
        self.quiz_score = {"dogru": 0, "toplam": 0}
        self.quiz_q_index = 0
        return self._quiz_ask_next()

    def _quiz_ask_next(self, prefix=None, dogru_mu=None) -> dict:
        """Sonraki soruyu sor; soru kalmadi/sayi doldu -> bitir.
        prefix: bir onceki cevabin geri bildirimi (ayni mesaja eklenir)."""
        if self.quiz_q_index >= self.QUIZ_QUESTION_COUNT:
            return self._quiz_end(prefix=prefix)
        prov = self._providers[self.quiz_provider]
        q = prov.next_question(self.quiz_used)
        if q is None:
            return self._quiz_end(prefix=prefix)
        self.quiz_used.add(q["id"])
        self.quiz_current = q
        self.quiz_q_index += 1
        self.quiz_turn = "soru"
        yanit = f"{prefix} {q['prompt']}" if prefix else q["prompt"]
        if dogru_mu is True:
            jest = random.choice(_JEST["kel_user_ok"])
        elif dogru_mu is False:
            jest = random.choice(_JEST["kel_retry"])
        else:
            jest = random.choice(_JEST["kel_intro"])
        return self._quiz_payload(
            "quiz_question", turn="soru", jest_id=jest, yanit=yanit, yogunluk=0.85,
            dogru_mu=dogru_mu,
            quiz_progress=f"Soru {self.quiz_q_index}/{self.QUIZ_QUESTION_COUNT} · Doğru {self.quiz_score['dogru']}",
            timer={"seconds": self.USER_TURN_SECONDS, "who": "user"})

    def _quiz_check(self, q, text: str) -> bool:
        """Cevap kontrolu — token (kume kesisimi) veya substring (atasozu)."""
        un = normalize(text)
        if not un:
            return False
        acc = q["accept_norm"]
        if q.get("match") == "substring":
            return any(a and (a in un or un in a) for a in acc)
        cand = {un} | set(un.split())
        return bool(acc & cand)

    def _handle_quiz(self, text: str, timeout: bool) -> dict:
        q = self.quiz_current
        beklenen = (q["reveal"] if q else "?").rstrip(" .")  # cift nokta olmasin
        self.quiz_score["toplam"] += 1
        if not timeout and q and self._quiz_check(q, text):
            self.quiz_score["dogru"] += 1
            geri = random.choice(_TXT["kel_user_ok"]) + f" Cevap: {beklenen}."
            dogru = True
        else:
            geri = (f"Süre doldu! Doğrusu: {beklenen}."
                    if timeout else f"Yaklaştın! Doğrusu: {beklenen}.")
            dogru = False
        return self._quiz_ask_next(prefix=geri, dogru_mu=dogru)

    def _quiz_end(self, prefix=None) -> dict:
        self.quiz_turn = None
        d = self.quiz_score["dogru"]
        t = self.quiz_score["toplam"] or self.QUIZ_QUESTION_COUNT
        if d >= t * 0.8:
            jest = random.choice(_JEST["kel_user_ok"]); kapanis = "Harikasın!"
        elif d >= t * 0.4:
            jest = random.choice(_JEST["kel_intro"]); kapanis = "Güzel oynadın!"
        else:
            jest = "huzur"; kapanis = "Önemli değil, yine beklerim!"
        yanit = f"{prefix + ' ' if prefix else ''}Bitti! {d}/{t} doğru. {kapanis}"
        return self._quiz_payload(
            "quiz_end", turn=None, jest_id=jest, yanit=yanit, yogunluk=0.9,
            quiz_progress=f"Bitti · {d}/{t} doğru", timer=None, ended=True,
            buttons=[{"key": "bilgi", "label": "🔁 Yeni yarışma"}, {"key": "cikis", "label": "Çıkış"}])

    # ——— Durum ————————————————————————————————————————————
    def status(self) -> dict:
        return {
            "phase": self.phase,
            "score": dict(self.score),
            "win_streak": self.win_streak,
            "lose_streak": self.lose_streak,
            "round_count": self.round_count,
            "word_turn": self.word_turn,
            "word_score": dict(self.word_score),
            "word_required_letter": self.word_required_letter,
            "word_ai_count": self.word_ai_count,
        }
