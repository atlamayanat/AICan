# Kelime Türetme — Kategorili Sözcük Havuzu Uygulama Planı

> **Ajan işçiler için:** Bu planı görev-görev uygula. Adımlar `- [ ]` checkbox kullanır.

**Hedef:** Kelime Türetme oyununa Edebiyat/Tarih/Bilim/Genel kategorileri ekle; AI temalı kelimeleri **küratörlü havuzdan** (LLM'siz) oynasın, ziyaretçi serbest kelime söylesin.

**Mimari:** Yeni statik veri dosyası `ai/word_categories.json` (3 tema) + koddaki `_TR_COMMON_WORDS` (genel). GameEngine init'te ilk-harfe göre indekslenir. AI kelime üretimi LLM yerine havuzdan rastgele seçer. "Kelime Türetme" seçilince bir kategori alt-menüsü gelir. Çekirdek sohbet/jest sistemi DEĞİŞMEZ.

**Teknoloji Yığını:** Python 3.13 (sistem yorumlayıcısı), Flask backend, vanilla JS frontend. Test = standalone betik (proje konvansiyonu, `test_runner.py` gibi; pytest YOK). Türkçe konsol için `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`.

**Spec:** `docs/specs/2026-06-30-kelime-kategori-havuzu-tasarim.md`

**Önemli tasarım notu (spec düzeltmesi):** `word_category` `_reset_word()`'te SIFIRLANMAZ (çünkü `_start_kelime` `_reset_word` çağırır ve kategoriyi silerdi). Kategori; `__init__` (None), `_start_kelime_category` (None → seçim başlıyor) ve `_handle_kelime_category` (seçilen değer) içinde yönetilir.

**Çalıştırma komutları (referans):**
- Testler: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
- Tüm komutlar proje kökünden: `C:/Users/mehme/Desktop/v1/v1/01-Projects/aican`

---

## Görev 1: `ai/word_categories.json` — küratörlü temalı havuz

**Dosyalar:**
- Oluştur: `ai/word_categories.json`

3 temalı kategori. Tüm kelimeler gerçek, tek sözcük, küçük, Türkçe harf (`temiz_kelime()` çıktısıyla uyumlu). Aşağıdaki liste **fonksiyonel başlangıç**tır.

- [ ] **Adım 1: Dosyayı oluştur**

```json
{
  "edebiyat": [
    "anlatı", "alegori", "atasözü", "beyit", "biyografi", "betimleme", "cinas",
    "dize", "deneme", "destan", "dram", "diyalog", "eleştiri", "epik", "fabl",
    "fıkra", "gazel", "hece", "hiciv", "hikaye", "imge", "ironi", "kafiye",
    "koşma", "kıta", "kurgu", "lirik", "metafor", "mısra", "mizah", "masal",
    "mecaz", "nesir", "nazım", "öykü", "roman", "redif", "rivayet", "sone",
    "sembol", "satır", "şiir", "şair", "tema", "tiyatro", "tezat", "tekerleme",
    "üslup", "yergi"
  ],
  "tarih": [
    "antlaşma", "akıncı", "ayaklanma", "arşiv", "barış", "beylik", "bağımsızlık",
    "cumhuriyet", "cephe", "çağ", "devrim", "devlet", "dönem", "ferman", "fetih",
    "feodalite", "göç", "hanedan", "hükümdar", "hazine", "halife", "imparatorluk",
    "istila", "isyan", "ittifak", "krallık", "kale", "kuşatma", "kanun", "koloni",
    "medeniyet", "monarşi", "miras", "ordu", "padişah", "paşa", "savaş", "saltanat",
    "sülale", "sömürge", "sınır", "sefer", "şövalye", "taht", "toplum", "tımar",
    "uygarlık", "ulus", "vergi", "vatan", "veliaht", "yenilgi", "yurt", "zafer", "zırh"
  ],
  "bilim": [
    "atom", "asit", "alaşım", "akım", "anatomi", "astronomi", "biyoloji", "bakteri",
    "basınç", "bileşik", "canlı", "çekirdek", "deney", "denklem", "doku", "döngü",
    "dalga", "enerji", "element", "evrim", "elektron", "ekosistem", "fizik",
    "fonksiyon", "fotosentez", "formül", "frekans", "galaksi", "gezegen", "genetik",
    "hücre", "hipotez", "hidrojen", "izotop", "iklim", "kütle", "kimya", "kromozom",
    "kuvvet", "kuram", "madde", "molekül", "mıknatıs", "mineral", "nötron", "nükleer",
    "oksijen", "organizma", "proton", "periyot", "plazma", "protein", "radyasyon",
    "reaksiyon", "refleks", "sıcaklık", "sistem", "solunum", "sentez", "sinir",
    "teori", "tepkime", "virüs", "vektör", "vitamin", "yörünge", "yerçekimi", "yoğunluk"
  ]
}
```

- [ ] **Adım 2: Geçerli JSON doğrula**

Çalıştır: `python -c "import json; d=json.load(open('ai/word_categories.json',encoding='utf-8')); print({k:len(v) for k,v in d.items()})"`
Beklenen: `{'edebiyat': 50, 'tarih': 56, 'bilim': 68}` benzeri (sıfır olmayan 3 kategori).

- [ ] **Adım 3: Zenginleştirme (kabul ölçütü)**

Her kategoriyi şu ölçütlere göre genişlet: **kategori başına ≥120 kelime**; yaygın başlangıç harflerinin (a, b, c, d, e, g, h, i, k, m, o, s, t, u, y) **her biri için ≥3 kelime**. Terimler tanınır olmalı (müze + çocuk kitlesi), obscure jargon değil; özel isim yok. Harf kapsamını doğrula:

Çalıştır:
```bash
python -c "import json; d=json.load(open('ai/word_categories.json',encoding='utf-8')); [print(k, sorted({w[0] for w in v})) for k,v in d.items()]"
```
Beklenen: her kategoride yaygın harfler mevcut.

- [ ] **Adım 4: Commit**

```bash
git add ai/word_categories.json
git commit -m "feat(kelime): edebiyat/tarih/bilim kategorili sozcuk havuzu verisi"
```

---

## Görev 2: Kategori yükleyici + indeks + GameEngine init

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (modül başı yardımcılar + `__init__` ~301-311)
- Oluştur: `orchestrator/test_word_categories.py`

- [ ] **Adım 1: Başarısız testi yaz**

Oluştur `orchestrator/test_word_categories.py`:

```python
"""Kelime Türetme kategorili havuz — standalone birim testleri (Ollama gerektirmez).
Calistir: PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py
"""
from __future__ import annotations
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import game_engine as ge
from game_engine import GameEngine

_PASS = 0
_FAIL = 0

def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1; print(f"[PASS] {name}")
    else:
        _FAIL += 1; print(f"[FAIL] {name}")

# Test havuzu (enjekte) — Ollama/JSON'a bagimli degil
TEST_CATS = {
    "edebiyat": ["roman", "redif", "rivayet", "siir", "sair", "tema", "atasozu"],
    "bilim":    ["atom", "asit", "akim", "tepkime", "teori", "molekul"],
}

def make_engine():
    # bridge=None, word_llm=fake -> Ollama'ya hic gidilmez
    return GameEngine(bridge=None, word_llm=_FakeWordLLM(), categories=dict(TEST_CATS))

class _FakeWordLLM:
    def __init__(self): self.unreachable = False
    def gecerli_mi(self, w): return True  # lenient sahte
    def uret_kelime(self, harf, used, denemeler=2): return None  # kullanilmamali

def test_init_pools():
    g = make_engine()
    # 3 tema + genel (koddaki _TR_COMMON_WORDS)
    check("genel kategori var", "genel" in g._pools)
    check("edebiyat indekslendi", "r" in g._pools["edebiyat"])
    check("edebiyat[r] roman icerir", "roman" in g._pools["edebiyat"]["r"])
    check("_all_words temali kelime icerir", "molekul" in g._all_words or "molekül" in g._all_words)
    check("_all_words genel kelime icerir", "elma" in g._all_words)
    check("word_category baslangic None", g.word_category is None)

if __name__ == "__main__":
    test_init_pools()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: FAIL/hata — `GameEngine.__init__()` `categories` argümanını ve `_pools`/`_all_words`/`word_category`'yi henüz bilmiyor (TypeError veya AttributeError).

- [ ] **Adım 3: Yükleyici + indeks yardımcılarını ekle**

`game_engine.py` modül başına (importlardan sonra, `_TR_COMMON_WORDS` tanımından SONRA — `_TR_COMMON_WORDS`'e referans verdiği için aşağıya, örn. `_KEL_SEED` civarına koy). `temiz_kelime` zaten `word_llm`'den import edilidir; `json`, `Path`, `log` mevcut. Değilse importları ekle (`import json`, `from pathlib import Path`).

```python
# ——— Kategorili kelime havuzu (AI temali kelimeler buradan secilir) ————
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
    """JSON'dan temali kategorileri yukle: {kategori: [kelime,...]}. Hata -> {} (genel'e dusulur)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {k: [temiz_kelime(w) for w in v if temiz_kelime(w)]
                for k, v in data.items() if isinstance(v, list)}
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.warning("word_categories.json okunamadi: %s — yalniz 'genel' kullanilacak", e)
        return {}
```

Not: `import json` / `from pathlib import Path` / `log = logging.getLogger(__name__)` dosyada yoksa ekle (dosya başını kontrol et; `word_llm.py` deseniyle aynı).

- [ ] **Adım 4: `__init__`'i güncelle**

`game_engine.py:301-311` mevcut `__init__`'i değiştir. İmza `categories`/`categories_path` parametreleri alır; pools + all_words + word_category kurulur:

```python
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
```

- [ ] **Adım 5: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: 6 PASS / 0 FAIL.

- [ ] **Adım 6: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_word_categories.py
git commit -m "feat(kelime): kategori yukleyici + ilk-harf indeksi + init"
```

---

## Görev 3: `_pick_ai_word` + `ai_turn` havuza geçiş + temalı açılış

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (`_local_ai_word` ~650-659 → `_pick_ai_word`; `_begin_kelime` ~697-705; `ai_turn` ~777-825)
- Değiştir: `orchestrator/test_word_categories.py`

- [ ] **Adım 1: Başarısız testleri yaz**

`test_word_categories.py`'ye ekle (ve `__main__` bloğunda çağır):

```python
def test_pick_ai_word():
    g = make_engine()
    w = g._pick_ai_word("edebiyat", "r", set())
    check("pick: r ile baslar + edebiyat havuzunda", w in {"roman", "redif", "rivayet"})
    check("pick: kullanilmis haric", g._pick_ai_word("edebiyat", "r", {"roman", "redif", "rivayet"}) is None)
    check("pick: seyrek harf None", g._pick_ai_word("edebiyat", "z", set()) is None)
    check("pick: eksik kategori -> genel'e duser",
          g._pick_ai_word("yokboyle", "e", set()) is not None)

def _force_success(val=0.0):
    # ai_turn icindeki random.random() < p kontrolu deterministik olsun
    ge.random.random = lambda: val

def test_ai_turn_themed():
    g = make_engine()
    g.phase = "kelime"; g.word_category = "edebiyat"
    g.word_turn = "ai"; g.word_required_letter = "t"; g.word_used = set()
    _force_success(0.0)  # AI kesin "dener"
    p = g.ai_turn()
    check("ai_turn: temali kelime oynar", p["ai_word"] in {"tema"})
    check("ai_turn: sira user'a gecer", p["turn"] == "user")
    check("ai_turn: ai_error False", p.get("ai_error") is False)

def test_ai_turn_concede_sparse():
    g = make_engine()
    g.phase = "kelime"; g.word_category = "edebiyat"
    g.word_turn = "ai"; g.word_required_letter = "z"; g.word_used = set()  # edebiyat'ta z yok
    _force_success(0.0)
    p = g.ai_turn()
    check("ai_turn: seyrek harfte pes", p["ended"] is True and p["outcome"] == "user_win")
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: yeni testler FAIL — `_pick_ai_word` yok; `ai_turn` hâlâ LLM yolunu kullanıyor.

- [ ] **Adım 3: `_local_ai_word`'ü `_pick_ai_word` ile değiştir**

`game_engine.py:650-659` mevcut `_local_ai_word` metodunu şununla değiştir:

```python
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
```

- [ ] **Adım 4: `_begin_kelime`'de temalı açılış**

`game_engine.py:697-705`'te AI başlarken seed yerine temalı havuzdan seç. Mevcut:

```python
        if self.word_starter == "ai":
            kelime = random.choice(_KEL_SEED)
```
Şununla değiştir:
```python
        if self.word_starter == "ai":
            kelime = self._pick_ai_word(self.word_category, None, self.word_used) or random.choice(_KEL_SEED)
```

- [ ] **Adım 5: `ai_turn`'ü havuza çevir (LLM'i kaldır)**

`game_engine.py:784-798` arasındaki LLM + unreachable bloğunu sadeleştir. Mevcut:

```python
        req = self.word_required_letter
        basarili = random.random() < self._word_ai_success_p()
        kelime = self.word_llm.uret_kelime(req, self.word_used) if basarili else None

        # Sergi saglamligi: AI denemeliyken (basarili) Ollama coktuyse AI her turda
        # sessizce pes etmesin — yerel sozlukten oynayip oyunu surdur, gorevliye logla.
        ai_error = False
        if basarili and not kelime and getattr(self.word_llm, "unreachable", False):
            kelime = self._local_ai_word(req)
            ai_error = True
            if kelime:
                log.warning("Kelime AI: Ollama erisilemiyor — yerel sozlukten oynandi (%r)", kelime)
            else:
                log.warning("Kelime AI: Ollama erisilemiyor, yerel kelime yok (harf=%r) — pes", req)
```
Şununla değiştir:
```python
        req = self.word_required_letter
        # AI kelimeleri artik saf havuzdan (LLM yok) -> Ollama'dan bagimsiz, halusinasyonsuz.
        basarili = random.random() < self._word_ai_success_p()
        kelime = self._pick_ai_word(self.word_category, req, self.word_used) if basarili else None
        ai_error = False  # AI Ollama gerektirmez; "Ollama-down -> sessiz pes" ayrimi yok
```

`ai_turn`'ün geri kalanı (kelime varsa oyna / yoksa pes) AYNI kalır; `payload["ai_error"] = ai_error` satırı (her zaman False) kalabilir.

- [ ] **Adım 6: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: tüm testler PASS (init 6 + pick 4 + ai_turn 3 + concede 1).

- [ ] **Adım 7: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_word_categories.py
git commit -m "feat(kelime): AI kelimeleri saf havuzdan (LLM kaldirildi), temali acilis"
```

---

## Görev 4: Kullanıcı doğrulaması `_all_words` hızlı yolu

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (`_gecerli_kelime` ~642-648)
- Değiştir: `orchestrator/test_word_categories.py`

- [ ] **Adım 1: Başarısız testi yaz**

`test_word_categories.py`'ye ekle (+ `__main__`'de çağır):

```python
def test_gecerli_kelime_fast_path():
    g = make_engine()  # _FakeWordLLM.gecerli_mi True dondurur ama temalida CAGRILMAMALI
    # temali kelime _all_words'te -> LLM'e gitmeden True
    check("temali kelime hizli yol", g._gecerli_kelime("molekul") is True)
    # genel kelime de hizli yol
    check("genel kelime hizli yol", g._gecerli_kelime("elma") is True)
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: `molekul` hızlı yolda olmadığı için `gecerli_mi`'ye düşer; sahte True döner ama bu testin AMACI hızlı-yolu doğrulamak. Bunu kesinleştirmek için sahteyi sayaçlı yap (Adım 1'i güncelle):

```python
class _FakeWordLLM:
    def __init__(self): self.unreachable = False; self.gecerli_calls = 0
    def gecerli_mi(self, w): self.gecerli_calls += 1; return True
    def uret_kelime(self, harf, used, denemeler=2): return None
```
ve testi:
```python
def test_gecerli_kelime_fast_path():
    fake = _FakeWordLLM()
    g = GameEngine(bridge=None, word_llm=fake, categories=dict(TEST_CATS))
    g._gecerli_kelime("molekul"); g._gecerli_kelime("elma")
    check("hizli yol: LLM cagrilmadi", fake.gecerli_calls == 0)
```
Şimdi çalıştır → FAIL (mevcut `_gecerli_kelime` yalnız `_TR_COMMON_WORDS`'e bakıyor, `molekul` orada yok → LLM çağrılır → `gecerli_calls == 1`).

- [ ] **Adım 3: `_gecerli_kelime`'yi güncelle**

`game_engine.py:642-648`. Mevcut:
```python
        if w in _TR_COMMON_WORDS:
            return True
        return self.word_llm.gecerli_mi(w)
```
Şununla değiştir:
```python
        if w in self._all_words:
            return True
        return self.word_llm.gecerli_mi(w)
```

- [ ] **Adım 4: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: tüm testler PASS.

- [ ] **Adım 5: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_word_categories.py
git commit -m "feat(kelime): kullanici dogrulamasi _all_words hizli yolu (temalilar dahil)"
```

---

## Görev 5: Kategori alt-menüsü + akış yönlendirmesi + temalı intro

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (`_handle_menu` ~428-431; `handle` ~415-423; `_start_kelime` ~666-681; yeni metotlar + sabitler)
- Değiştir: `orchestrator/test_word_categories.py`

- [ ] **Adım 1: Başarısız testleri yaz**

`test_word_categories.py`'ye ekle (+ `__main__`'de çağır):

```python
def test_category_menu_flow():
    g = make_engine()
    g.start()                      # phase=menu
    p = g.handle("2")              # Kelime Turetme secildi -> kategori menusu
    check("menu->kategori: kind", p.get("kind") == "category_select")
    check("menu->kategori: word_turn", g.word_turn == "kategori")
    btn_keys = {b["key"] for b in p.get("buttons", [])}
    check("kategori butonlari", {"edebiyat", "tarih", "bilim", "genel"} <= btn_keys)

    p2 = g.handle("edebiyat")      # kategori secimi -> kurallar (hazir)
    check("kategori secildi", g.word_category == "edebiyat")
    check("hazir fazi", g.word_turn == "hazir")
    check("intro temali", "Edebiyat" in p2.get("yanit", ""))

def test_category_invalid_reprompts():
    g = make_engine()
    g.start(); g.handle("2")
    p = g.handle("asdf")           # gecersiz kategori
    check("gecersiz -> tekrar sor", p.get("kind") == "category_select")
    check("kategori hala secilmedi", g.word_category is None)

def test_category_by_number_and_genel():
    g = make_engine()
    g.start(); g.handle("2")
    g.handle("3")                  # 3 -> bilim
    check("rakamla bilim", g.word_category == "bilim")

def test_word_category_not_wiped_by_start_kelime():
    # _start_kelime _reset_word cagirir; word_category KORUNMALI (regresyon)
    g = make_engine()
    g.start(); g.handle("2"); g.handle("tarih")
    check("kategori korundu", g.word_category == "tarih")
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: FAIL — `category_select` akışı/metotları yok; `handle("2")` doğrudan `_start_kelime`'ye gidiyor.

- [ ] **Adım 3: Kategori sabitleri + butonlar + metotları ekle**

`game_engine.py`'ye, `_KEL_READY` sabiti civarına (modül seviyesi):

```python
# Kelime kategorisi eslestirme (rakam + ad). normalize() ciktisiyla eslesir.
_KEL_CATEGORIES = {
    "1": "edebiyat", "edebiyat": "edebiyat",
    "2": "tarih",    "tarih": "tarih",
    "3": "bilim",    "bilim": "bilim",
    "4": "genel",    "genel": "genel",
}
```

`GameEngine` içine (örn. `_kel_ready_buttons` yakınına) yeni statik buton + iki metot:

```python
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
                    cat = _KEL_CATEGORIES[w]; break
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
```

- [ ] **Adım 4: `_start_kelime` intro'yu temalı yap**

`game_engine.py:671-676` mevcut `yanit = (...)` bloğunu şununla değiştir:

```python
        _tema_ad = {"edebiyat": "Edebiyat", "tarih": "Tarih", "bilim": "Bilim"}.get(self.word_category)
        _bas = f"{_tema_ad} temasında kelime türetme oynayalım! " if _tema_ad else "Kelime türetme oynayalım! "
        yanit = (
            _bas +
            "Ben temaya uygun bir kelime söylerim, sen onun SON harfiyle başlayan "
            "(istediğin) bir Türkçe kelime söylersin; sırayla devam ederiz. "
            "Aynı kelimeyi iki kez kullanamayız ve her turda "
            f"{self.USER_TURN_SECONDS} saniyen olur. Hazırsan başlayalım — 'başla' de ya da butona dokun!"
        )
```

- [ ] **Adım 5: Yönlendirmeyi güncelle (`_handle_menu` + `handle`)**

`game_engine.py:430-431` (`_handle_menu`). Mevcut:
```python
        if n in ("2", "iki", "ikinci") or "kelime" in n:
            return self._start_kelime()
```
Şununla değiştir:
```python
        if n in ("2", "iki", "ikinci") or "kelime" in n:
            return self._start_kelime_category()
```

`game_engine.py:415-423` (`handle` kelime bloğu). Mevcut:
```python
        if self.phase == "kelime":
            if self.word_turn is None:
                # oyun bitti — herhangi girdi "yeni oyun" demektir (kurallari tekrar anlatir)
                return self._start_kelime()
            if self.word_turn == "hazir":
                # kurallar anlatildi, oyuncunun "basla" onayini bekliyoruz
                return self._handle_kelime_ready(text)
            # Kelime eslestirmesi Turkce harfleri korur (normalize degil, ham metin)
            return self._handle_kelime(text, timeout)
```
Şununla değiştir:
```python
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
```

- [ ] **Adım 6: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: tüm testler PASS.

- [ ] **Adım 7: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_word_categories.py
git commit -m "feat(kelime): kategori alt-menusu + akis yonlendirmesi + temali intro"
```

---

## Görev 6: Payload'a `category` + kontrol panelinde tema etiketi

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (`_kel_payload` ~613-632)
- Değiştir: `web/control.js` (`applyGamePayload` ~640 civarı)
- Değiştir: `web/Kontrol_Paneli.html` (tema etiketi öğesi)

> **Spec'ten YAGNI kısıtlaması:** Tema etiketi yalnız **kontrol panelinde** (operatör). Sergi ekranı (app.js / AI_Body_v2.html) etiketi ERTELENDİ — sergi zaten AI'nın temalı kelimeleriyle temayı gösteriyor.

- [ ] **Adım 1: `_kel_payload`'a `category` ekle**

`game_engine.py:616-632` dönen dict'e bir alan ekle (return içinde, örn. `"phase"` satırından sonra):

```python
            "category": self.word_category,
```

- [ ] **Adım 2: Kontrol panelinde tema etiketi öğesi**

`web/Kontrol_Paneli.html` — oyun skor alanının yakınına (mevcut `#game-score` öğesinin yanına) ekle:

```html
<span id="game-theme" class="game-theme"></span>
```

- [ ] **Adım 3: `control.js`'te tema etiketini güncelle**

`web/control.js`'te `els` tanımına ekle (örn. `gameScore` yanına):
```javascript
    gameTheme: $('#game-theme'),
```
`applyGamePayload` içinde `renderGameButtons(p.buttons || []);` satırından sonra:
```javascript
    if (els.gameTheme) {
      const adlar = { edebiyat: 'Edebiyat', tarih: 'Tarih', bilim: 'Bilim', genel: 'Genel' };
      els.gameTheme.textContent = p.category ? ('Tema: ' + (adlar[p.category] || p.category)) : '';
    }
```

- [ ] **Adım 4: Manuel doğrula (sözdizimi + akış)**

Çalıştır (JS sözdizimi kontrolü, node varsa): `node --check web/control.js`
Beklenen: hata yok. (Node yoksa bu adımı atla; tarayıcı testinde doğrulanır.)

Birim regresyon: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py` → tüm PASS (payload'a `category` eklenmesi mevcut testleri bozmamalı).

- [ ] **Adım 5: Commit**

```bash
git add orchestrator/game_engine.py web/control.js web/Kontrol_Paneli.html
git commit -m "feat(kelime): payload category alani + kontrol panelinde tema etiketi"
```

---

## Görev 7: Uçtan uca akış testi + manuel sergi kontrol listesi

**Dosyalar:**
- Değiştir: `orchestrator/test_word_categories.py`

- [ ] **Adım 1: Tam zincir akış testi yaz**

`test_word_categories.py`'ye ekle (+ `__main__`'de çağır):

```python
def test_full_chain_user_free():
    g = make_engine()
    g.start(); g.handle("2"); g.handle("bilim")   # tema: bilim
    p = g.handle("başla")                          # oyun baslar
    check("oyun basladi (intro)", p.get("kind") == "intro")
    # Kullanici serbest kelime (temasiz) kabul edilmeli
    g.word_turn = "user"
    # gerekli harf yoksa (kullanici basladi) ilk kelime serbest
    p2 = g.handle("kalem")
    check("kullanici serbest kelime kabul", p2.get("kind") == "user_ok")
    check("sira AI'da", p2.get("turn") == "ai")
    check("sonraki harf m", g.word_required_letter == "m")
```

Not: `g.handle("başla")` rastgele başlatıcı (ai/user) seçer; AI başlarsa `word_turn` "user" olur ve gerekli harf dolar. Testte `g.word_turn`/`word_required_letter`'ı sabitlemek için başlatıcıyı zorla: `_force_success` benzeri `ge.random.random = lambda: 0.6` (>=0.5 → user başlar) ekleyip ardından `g.handle("başla")` çağır; veya test öncesi `g.word_starter` kontrolünü kaldırıp doğrudan `_begin_kelime` durumunu kur. Basit yol: testte başlatmayı deterministik yap:

```python
def test_full_chain_user_free():
    g = make_engine()
    g.start(); g.handle("2"); g.handle("bilim")
    ge.random.random = lambda: 0.9   # >=0.5 -> kullanici baslar (ilk kelime serbest)
    p = g.handle("başla")
    check("kullanici basladi", g.word_turn == "user" and g.word_required_letter is None)
    p2 = g.handle("kalem")           # serbest, temasiz
    check("serbest kelime kabul", p2.get("kind") == "user_ok" and g.word_required_letter == "m")
```

- [ ] **Adım 2: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py`
Beklenen: tüm testler PASS.

- [ ] **Adım 3: Commit**

```bash
git add orchestrator/test_word_categories.py
git commit -m "test(kelime): uctan uca kategori akis testi"
```

- [ ] **Adım 4: Manuel sergi kontrol listesi (Ollama + tarayıcı)**

Çalıştır: `python run_web.py` (Ollama açık). Tarayıcıda kontrol paneli + sergi ekranını aç. Doğrula:
1. "Oyna" → menüde "Kelime Türetme" seç → **kategori alt-menüsü** (4 buton) çıkıyor.
2. Her kategori (Edebiyat/Tarih/Bilim) → kural anlatımı **tema adını** içeriyor; "Tema: X" etiketi kontrol panelinde görünüyor.
3. "Başla" → AI başlarsa **temaya uygun** bir kelime söylüyor (anında, gecikmesiz).
4. Kullanıcı **herhangi** geçerli Türkçe kelime söyleyebiliyor (tema zorunlu değil).
5. AI birkaç turda temalı kelimelerle oynayıp ~4-5'te pes ediyor; seyrek harfte erken "pes" tematik.
6. "Genel" kategorisi eski davranışla (yaygın kelimeler) çalışıyor.
7. Ollama KAPALIYKEN bile AI kelimeleri geliyor (havuzdan) — yalnız kullanıcı doğrulaması etkilenir (lenient).
8. Zaman barı, jestler, skor eskisi gibi çalışıyor.

---

## Öz-İnceleme Sonucu (plan yazarı)

- **Spec kapsamı:** Veri dosyası (G1), yükleme+indeks (G2), saf-havuz AI (G3), `_all_words` doğrulama (G4), kategori alt-menü+akış+intro (G5), payload+etiket (G6), test (G2-G7) → tüm spec bölümleri görevlere bağlandı.
- **Spec'ten sapmalar (bilinçli):** (a) `word_category` `_reset_word`'te DEĞİL, ayrı yönetiliyor (silme bug'ı). (b) Sergi-ekranı tema etiketi ertelendi (YAGNI; sergi temalı kelimeleri zaten gösteriyor). (c) web_server.py değişikliği GEREKMEDİ (kategori `/api/game/input` üzerinden akıyor).
- **Tip tutarlılığı:** `_pick_ai_word(category, req_letter, used)`, `word_category`, `_pools`, `_all_words`, `category_select` kind, `_KEL_CATEGORIES`, `_kel_category_buttons` adları tüm görevlerde tutarlı.
- **Yer tutucu yok:** Tüm kod adımları gerçek kod içeriyor; JSON içeriği fonksiyonel başlangıç + ölçülebilir zenginleştirme kriteri.
