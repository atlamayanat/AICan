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
        "Hadi oynayalım! Hangisini istersin? — (1) Taş Kağıt Makas, (2) Kelime Türetme. Söyle ya da dokun.",
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

# Kelime fazında yalnızca NET komutlar çıkıştır ("son", "bitti" gerçek kelime olabilir).
_KEL_EXIT = {"cikis", "cik", "dur", "durdur", "kapat", "iptal", "vazgec", "vazgectim"}

# Hazırlık fazında "oyunu başlat" onayı.
_KEL_READY = {"basla", "baslayalim", "baslat", "hazir", "hazirim", "evet",
              "tamam", "tamamdir", "hadi", "oyna", "olur", "devam", "ok", "tabii"}

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

    def __init__(self, bridge=None, word_llm=None, categories=None, categories_path=None):
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
        self._reset_word()

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
            if self.phase == "kelime" and self.word_turn is not None:
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
