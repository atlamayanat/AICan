# Ortak Quiz Motoru + Atasözü & Doğru/Yanlış — Uygulama Planı

> **Ajan işçiler için:** Bu planı görev-görev uygula. Adımlar `- [ ]` checkbox kullanır.

**Hedef:** `esanlam` quiz'ini genel bir quiz motoruna (`quiz` faz + sağlayıcılar) dönüştür; Eş/Zıt'ı sağlayıcı yap; Atasözü + Doğru/Yanlış sağlayıcılarını ve "Bilgi Yarışması" alt-menüsünü ekle.

**Mimari:** Modül seviyesi 3 sağlayıcı sınıfı (`next_question(used)` → tekdüze soru dict). GameEngine'de tek genel quiz akışı (start/secim/hazir/N-soru/skor/timer/payload) + tek `_quiz_check`. `web_server.py` değişmez.

**Teknoloji Yığını:** Python 3.13, Flask, vanilla JS. Test = standalone betik. Türkçe konsol: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`.

**Spec:** `docs/specs/2026-06-30-ortak-quiz-motoru-tasarim.md`
**Komutlar proje kökünden:** `C:/Users/mehme/Desktop/v1/v1/01-Projects/aican`

> **Refactor notu:** `test_es_zit_anlam.py` SİLİNİR, yerine `test_quiz.py` gelir (genel motor + 3 sağlayıcı). Eş/Zıt davranışı `_EsZitProvider` ile korunur.

---

## Görev 1: Yeni veri dosyaları

**Dosyalar:** Oluştur `ai/atasozu.json`, `ai/dogru_yanlis.json`

- [ ] **Adım 1: `ai/atasozu.json`** — `[{"bas","tamam":[...]}]`, ~50 standart atasözü. Başlangıç (genişletilecek ≥40):

```json
[
  {"bas": "Damlaya damlaya", "tamam": ["göl olur"]},
  {"bas": "Sakla samanı", "tamam": ["gelir zamanı"]},
  {"bas": "Bir elin nesi var", "tamam": ["iki elin sesi var"]},
  {"bas": "Ayağını yorganına göre", "tamam": ["uzat"]},
  {"bas": "Ak akçe kara gün", "tamam": ["içindir"]},
  {"bas": "Sütten ağzı yanan", "tamam": ["yoğurdu üfleyerek yer"]},
  {"bas": "Damlaya damlaya göl olur", "tamam": ["aka aka sel olur"]},
  {"bas": "İşleyen demir", "tamam": ["ışıldar", "pas tutmaz"]},
  {"bas": "Son pişmanlık", "tamam": ["fayda etmez"]},
  {"bas": "Tatlı dil", "tamam": ["yılanı deliğinden çıkarır"]},
  {"bas": "Ağaç yaşken", "tamam": ["eğilir"]},
  {"bas": "Sabreden derviş", "tamam": ["muradına ermiş"]},
  {"bas": "Bugünün işini", "tamam": ["yarına bırakma"]},
  {"bas": "Üzüm üzüme baka baka", "tamam": ["kararır"]},
  {"bas": "Komşu komşunun külüne", "tamam": ["muhtaçtır"]},
  {"bas": "Gülü seven", "tamam": ["dikenine katlanır"]},
  {"bas": "Yuvarlanan taş", "tamam": ["yosun tutmaz"]},
  {"bas": "Görünen köy", "tamam": ["kılavuz istemez"]},
  {"bas": "İti an", "tamam": ["çomağı hazırla"]},
  {"bas": "Acele işe", "tamam": ["şeytan karışır"]}
]
```

- [ ] **Adım 2: `ai/dogru_yanlis.json`** — `[{"ifade","dogru","aciklama"}]`, ~60 objektif olgu. Başlangıç (genişletilecek ≥50):

```json
[
  {"ifade": "Dünya, Güneş'in etrafında döner", "dogru": true, "aciklama": "Dünya bir yılda Güneş çevresinde döner."},
  {"ifade": "Balıklar suda solungaçla solunum yapar", "dogru": true, "aciklama": "Solungaçlarıyla sudan oksijen alırlar."},
  {"ifade": "Örümcekler böcektir", "dogru": false, "aciklama": "Örümcekler 8 bacaklıdır, böcek değil arachnid'dir."},
  {"ifade": "Su 100 derecede kaynar", "dogru": true, "aciklama": "Deniz seviyesinde su 100°C'de kaynar."},
  {"ifade": "Yarasalar kördür", "dogru": false, "aciklama": "Yarasalar görebilir; ayrıca ekolokasyon kullanır."},
  {"ifade": "Ay kendi ışığını üretir", "dogru": false, "aciklama": "Ay, Güneş ışığını yansıtır."},
  {"ifade": "İnsan vücudunda en büyük organ deridir", "dogru": true, "aciklama": "Deri en büyük organdır."},
  {"ifade": "Bukalemun renk değiştirebilir", "dogru": true, "aciklama": "Derisindeki hücrelerle renk değiştirir."},
  {"ifade": "Penguenler kuzey kutbunda yaşar", "dogru": false, "aciklama": "Penguenler çoğunlukla güney yarım kürede yaşar."},
  {"ifade": "Bal bozulmayan bir besindir", "dogru": true, "aciklama": "Bal uygun saklanırsa çok uzun süre bozulmaz."},
  {"ifade": "Türkiye'nin başkenti Ankara'dır", "dogru": true, "aciklama": "Başkent Ankara'dır."},
  {"ifade": "Elmas kömürle aynı elementtendir", "dogru": true, "aciklama": "İkisi de karbondan oluşur."},
  {"ifade": "Devekuşu uçabilir", "dogru": false, "aciklama": "Devekuşu uçamaz ama çok hızlı koşar."},
  {"ifade": "Kalp kan pompalayan bir kastır", "dogru": true, "aciklama": "Kalp bir kas organıdır."},
  {"ifade": "Şimşek aynı yere iki kez düşmez", "dogru": false, "aciklama": "Şimşek aynı yere defalarca düşebilir."},
  {"ifade": "Buz sudan daha hafiftir", "dogru": true, "aciklama": "Bu yüzden buz suda yüzer."},
  {"ifade": "Arılar bal yapar", "dogru": true, "aciklama": "Bal arıları nektardan bal üretir."},
  {"ifade": "Güneş bir gezegendir", "dogru": false, "aciklama": "Güneş bir yıldızdır."},
  {"ifade": "Salyangozun kabuğu vardır", "dogru": true, "aciklama": "Salyangozlar kabuk taşır."},
  {"ifade": "İnsan beyni kemikle korunur", "dogru": true, "aciklama": "Kafatası beyni korur."}
]
```

- [ ] **Adım 3: Doğrula**

```bash
python -c "import json; a=json.load(open('ai/atasozu.json',encoding='utf-8')); d=json.load(open('ai/dogru_yanlis.json',encoding='utf-8')); print('atasozu:',len(a),'| dogru_yanlis:',len(d), '| dy bool:', all(isinstance(x['dogru'],bool) for x in d))"
```
Beklenen: sayılar + `dy bool: True`. Genişletme kabul ölçütü: atasözü ≥40, dogru_yanlis ≥50.

- [ ] **Adım 4: Commit**

```bash
git add ai/atasozu.json ai/dogru_yanlis.json
git commit -m "feat(quiz): atasozu + dogru/yanlis veri havuzlari"
```

---

## Görev 2: Modül seviyesi loader + 3 sağlayıcı sınıfı

**Dosyalar:** Değiştir `orchestrator/game_engine.py` (modül seviyesi, `_load_es_zit` yakını); Oluştur `orchestrator/test_quiz.py`

- [ ] **Adım 1: Başarısız testi yaz** — Oluştur `orchestrator/test_quiz.py`:

```python
"""Ortak quiz motoru + 3 saglayici — standalone testler (Ollama gerektirmez).
Calistir: PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_quiz.py
"""
from __future__ import annotations
import importlib, sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
import game_engine as ge
from game_engine import GameEngine, _EsZitProvider, _AtasozuProvider, _DogruYanlisProvider

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    if cond: _PASS += 1; print(f"[PASS] {name}")
    else: _FAIL += 1; print(f"[FAIL] {name}")

def test_providers():
    p = _EsZitProvider({"siyah": {"zit": ["beyaz", "ak"]}})
    q = p.next_question(set())
    check("eszit prompt", "anlamlısı" in q["prompt"])
    check("eszit accept", "beyaz" in q["accept_norm"])
    a = _AtasozuProvider([{"bas": "Damlaya damlaya", "tamam": ["göl olur"]}])
    qa = a.next_question(set())
    check("atasozu match substring", qa["match"] == "substring")
    check("atasozu accept", "gol olur" in qa["accept_norm"])
    d = _DogruYanlisProvider([{"ifade": "Test", "dogru": True, "aciklama": "x"}])
    qd = d.next_question(set())
    check("dy accept dogru", "dogru" in qd["accept_norm"] and "evet" in qd["accept_norm"])
    check("dy reveal", qd["reveal"].startswith("Doğru"))
    check("tukenme None", p.next_question({"siyah"}) is None)

if __name__ == "__main__":
    test_providers()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
```

- [ ] **Adım 2: Çalıştır, FAIL doğrula** — `python orchestrator/test_quiz.py` → ImportError (`_EsZitProvider` yok).

- [ ] **Adım 3: Loader + sağlayıcıları ekle** — `game_engine.py`'de `_load_es_zit` fonksiyonundan SONRA:

```python
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
    {"ifade": "Buz suda yüzer", "dogru": True, "aciklama": "Buz sudan hafiftir."},
]


def _load_json_list(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.warning("%s okunamadi: %s — gomulu yedek", path, e)
        return []


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
```

- [ ] **Adım 4: Çalıştır, PASS doğrula** — `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_quiz.py` → 7 PASS.

- [ ] **Adım 5: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_quiz.py
git commit -m "feat(quiz): json list loader + 3 saglayici (eszit/atasozu/dogruyanlis)"
```

---

## Görev 3: GameEngine genel quiz motoru (esanlam→quiz refactor)

**Dosyalar:** Değiştir `orchestrator/game_engine.py` (init, _reset, ea_* metotları→quiz_*); `orchestrator/test_quiz.py`

- [ ] **Adım 1: Başarısız akış testleri ekle** (`test_quiz.py`):

```python
TEST_EA = {"siyah": {"zit": ["beyaz", "ak"]}, "mutlu": {"zit": ["üzgün"], "es": ["neşeli"]},
           "büyük": {"zit": ["küçük"]}}
TEST_ATA = [{"bas": "Damlaya damlaya", "tamam": ["göl olur"]},
            {"bas": "Son pişmanlık", "tamam": ["fayda etmez"]}]
TEST_DY = [{"ifade": "Güneş yıldızdır", "dogru": True, "aciklama": "x"},
           {"ifade": "Ay yıldızdır", "dogru": False, "aciklama": "y"}]

def make_engine():
    return GameEngine(bridge=None, word_llm=None, ea_data=dict(TEST_EA),
                      atasozu_data=list(TEST_ATA), dogru_yanlis_data=list(TEST_DY))

def test_quiz_state_init():
    g = make_engine()
    check("providers 3", set(g._providers) == {"eszit", "atasozu", "dogruyanlis"})
    check("quiz_turn None", g.quiz_turn is None)

def test_quiz_check_modes():
    g = make_engine()
    check("token dogru", g._quiz_check({"accept_norm": {"beyaz"}, "match": "token"}, "beyaz"))
    check("token yanlis", not g._quiz_check({"accept_norm": {"beyaz"}, "match": "token"}, "mavi"))
    check("substring", g._quiz_check({"accept_norm": {"gol olur"}, "match": "substring"}, "göl olur derler"))
    check("dy evet", g._quiz_check({"accept_norm": _DogruYanlisProvider._EVET, "match": "token"}, "evet"))
```

- [ ] **Adım 2: Çalıştır, FAIL doğrula** — `_providers`/`quiz_turn`/`_quiz_check` yok.

- [ ] **Adım 3: `__init__`'i güncelle** — imza + ea bloğunu sağlayıcı kaydıyla değiştir.

İmza:
```python
    def __init__(self, bridge=None, word_llm=None, categories=None, categories_path=None,
                 ea_data=None, ea_path=None, atasozu_data=None, dogru_yanlis_data=None):
```
Mevcut ea bloğunu (init içinde `# Es/Zit Anlam verisi ...` → `self._reset_ea()`) ŞUNUNLA değiştir:
```python
        # Quiz saglayicilar (es/zit + atasozu + dogru/yanlis)
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
```
(`self._reset_word()` zaten vardı; ea satırları kaldırıldı.)

- [ ] **Adım 4: `_reset_ea`'yı `_reset_quiz` ile değiştir**

```python
    def _reset_quiz(self) -> None:
        self.quiz_provider = None        # "eszit" | "atasozu" | "dogruyanlis"
        self.quiz_turn = None            # "secim" | "hazir" | "soru" | None
        self.quiz_used = set()
        self.quiz_score = {"dogru": 0, "toplam": 0}
        self.quiz_q_index = 0
        self.quiz_current = None
```

- [ ] **Adım 5: Tüm `_ea_*`/esanlam metot bloğunu `_quiz_*` ile değiştir**

`game_engine.py`'deki `# ——— Es/Zit Anlam (dostca puanli quiz) ———` başlığından `# ——— Durum ———` ÖNCESİNE kadar olan TÜM blok (yani `_ea_next_question`, `_ea_check_answer`, `_ea_payload`, `_ea_ready_buttons`, `_start_esanlam`, `_handle_esanlam_ready`, `_begin_esanlam`, `_ea_ask_next`, `_handle_esanlam`, `_ea_end`) silinip yerine:

```python
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
            "game": "quiz", "phase": self.phase, "kind": kind, "turn": turn,
            "quiz": self.quiz_provider, "jest_id": jest_id, "yogunluk": yogunluk,
            "yanit": yanit, "score": None, "quiz_progress": quiz_progress,
            "dogru_mu": dogru_mu, "timer": timer,
            "buttons": buttons if buttons is not None else [{"key": "cikis", "label": "Çıkış"}],
            "ended": ended, "outcome": None,
        }

    def _start_quiz_menu(self) -> dict:
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
                    key = _QUIZ_SELECT[w]; break
        if key is None or key not in self._providers:
            return self._quiz_payload(
                "quiz_menu", turn="secim", jest_id="soru_isareti",
                yanit="Bir yarışma seç :)  1) Eş/Zıt  2) Atasözü  3) Doğru/Yanlış",
                yogunluk=0.6, timer=None, buttons=self._quiz_menu_buttons())
        self.quiz_provider = key
        return self._start_quiz()

    def _start_quiz(self) -> dict:
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
        beklenen = q["reveal"] if q else "?"
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
```

`EA_QUESTION_COUNT = 5` sabitini `QUIZ_QUESTION_COUNT = 5` olarak yeniden adlandır.

Modül seviyesine (örn. `_KEL_CATEGORIES` yakını) ekle:
```python
_QUIZ_SELECT = {
    "1": "eszit", "eszit": "eszit", "es": "eszit", "zit": "eszit", "anlam": "eszit",
    "2": "atasozu", "atasozu": "atasozu", "atasoz": "atasozu", "deyim": "atasozu",
    "3": "dogruyanlis", "dogruyanlis": "dogruyanlis", "yanlis": "dogruyanlis", "dy": "dogruyanlis",
}
```

- [ ] **Adım 6: Çalıştır, PASS doğrula** — `python orchestrator/test_quiz.py` → state + check testleri PASS.

- [ ] **Adım 7: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_quiz.py
git commit -m "refactor(quiz): esanlam -> genel quiz motoru + saglayici kayit"
```

---

## Görev 4: Yönlendirme + menü + exit

**Dosyalar:** Değiştir `orchestrator/game_engine.py` (`handle`, `_handle_menu`, `_menu_buttons`, `_TXT`, `exit`); `orchestrator/test_quiz.py`

- [ ] **Adım 1: Başarısız akış testleri ekle** (`test_quiz.py`):

```python
def test_menu_to_quiz_submenu():
    g = make_engine()
    p = g.start()
    check("menude bilgi", "3" in {b["key"] for b in p["buttons"]})
    p = g.handle("3")
    check("3 -> quiz_menu", p["kind"] == "quiz_menu")
    keys = {b["key"] for b in p["buttons"]}
    check("alt-menu butonlari", {"eszit", "atasozu", "dogruyanlis"} <= keys)

def test_quiz_full_flow_each_provider():
    for sel, key in (("eszit", "eszit"), ("atasozu", "atasozu"), ("dogruyanlis", "dogruyanlis")):
        g = make_engine()
        g.start(); g.handle("3")
        p = g.handle(sel)
        check(f"{sel}: ready", p["kind"] == "quiz_ready" and g.quiz_provider == key)
        p = g.handle("başla")
        check(f"{sel}: question", p["kind"] == "quiz_question")
        # dogru cevap ver
        q = g.quiz_current
        ans = next(iter(q["accept_norm"]))
        p = g.handle(ans)
        check(f"{sel}: cevap islendi", g.quiz_score["toplam"] == 1 and p["kind"] in ("quiz_question", "quiz_end"))

def test_quiz_exit():
    g = make_engine()
    g.start(); g.handle("3"); g.handle("eszit"); g.handle("başla")
    p = g.handle("çıkış")
    check("cikis -> idle", g.phase == "idle" and p["phase"] == "idle")
```

- [ ] **Adım 2: Çalıştır, FAIL doğrula.**

- [ ] **Adım 3: `handle()` esanlam bloğunu quiz ile değiştir**

Mevcut:
```python
        if self.phase == "esanlam":
            if self.ea_turn is None:
                return self._start_esanlam()   # bitti -> yeni oyun
            if self.ea_turn == "hazir":
                return self._handle_esanlam_ready(text)
            return self._handle_esanlam(text, timeout)
```
Şununla:
```python
        if self.phase == "quiz":
            if self.quiz_turn is None:
                return self._start_quiz_menu()    # bitti -> alt-menu
            if self.quiz_turn == "secim":
                return self._handle_quiz_select(text)
            if self.quiz_turn == "hazir":
                return self._handle_quiz_ready(text)
            return self._handle_quiz(text, timeout)
```

- [ ] **Adım 4: `handle()` exit kontrolünü güncelle**

Mevcut `active_game = (... "esanlam" and self.ea_turn is not None)` →
```python
            active_game = ((self.phase == "kelime" and self.word_turn is not None) or
                           (self.phase == "quiz" and self.quiz_turn is not None))
```

- [ ] **Adım 5: `exit()` `_reset_ea`→`_reset_quiz`**

```python
        self.phase = "idle"
        self._reset_word()
        self._reset_quiz()
```

- [ ] **Adım 6: `_handle_menu` "3" yönlendirme**

Mevcut:
```python
        # Es/Zit Anlam
        if n in ("3", "uc", "ucuncu") or "anlam" in n:
            return self._start_esanlam()
```
Şununla:
```python
        # Bilgi Yarismasi (quiz alt-menu)
        if n in ("3", "uc", "ucuncu") or "bilgi" in n or "yaris" in n or "anlam" in n or "quiz" in n:
            return self._start_quiz_menu()
```

- [ ] **Adım 7: `_menu_buttons` + `_TXT["menu"]`**

`_menu_buttons` 3. buton:
```python
            {"key": "3", "label": "🧠 Bilgi Yarışması"},
```
`_TXT["menu"]`:
```python
        "Hadi oynayalım! Hangisini istersin? — (1) Taş Kağıt Makas, (2) Kelime Türetme, (3) Bilgi Yarışması. Söyle ya da dokun.",
```

- [ ] **Adım 8: Çalıştır, PASS doğrula** — tüm `test_quiz.py` PASS.

- [ ] **Adım 9: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_quiz.py
git commit -m "feat(quiz): bilgi yarismasi alt-menu + yonlendirme + exit"
```

---

## Görev 5: Frontend control.js (esanlam→quiz)

**Dosyalar:** Değiştir `web/control.js`

- [ ] **Adım 1: `isTimed` ve game id'leri güncelle** — `applyGamePayload` içinde:
  - `const isTimed = (p.game === 'kelime' || p.game === 'quiz');`
  - Timer bloğundaki AI turu satırı zaten `p.game === 'kelime'` ile kısıtlı (değişmez).
  - İlerleme bloğu: `'esanlam'` → `'quiz'`, `p.ea_progress` → `p.quiz_progress`:
    ```javascript
    if (p.game === 'quiz' && els.gameScore) {
      els.gameScore.textContent = p.quiz_progress || '—';
    }
    ```
  - Log dalı: `} else if (p.game === 'esanlam') {` → `} else if (p.game === 'quiz') {` ve metni `'bilgi: '` yap.

- [ ] **Adım 2: JS sözdizimi** — `node --check web/control.js` → hata yok.

- [ ] **Adım 3: Commit**

```bash
git add web/control.js
git commit -m "feat(quiz): control.js esanlam->quiz (timer/ilerleme/log)"
```

---

## Görev 6: Temizlik + HTTP entegrasyon

**Dosyalar:** Sil `orchestrator/test_es_zit_anlam.py`; Değiştir `orchestrator/test_quiz.py`

- [ ] **Adım 1: Eski testi sil** — `git rm orchestrator/test_es_zit_anlam.py`

- [ ] **Adım 2: HTTP entegrasyon testi ekle** (`test_quiz.py`):

```python
def test_http_quiz():
    ws = importlib.import_module("web_server")
    cfg = ws.load_config(); cfg["warmup_on_start"] = False; cfg["tts_enabled"] = False
    c = ws.create_app(cfg).test_client()
    def post(u, **b): return c.post(u, json=b or None).get_json()
    post("/api/game/start")
    p = post("/api/game/input", text="3")
    check("http quiz_menu", p["kind"] == "quiz_menu")
    for sel in ("eszit", "atasozu", "dogruyanlis"):
        post("/api/game/input", text="3")
        post("/api/game/input", text=sel)
        p = post("/api/game/input", text="başla")
        check(f"http {sel} question", p["kind"] == "quiz_question" and p["quiz"] == sel)
```

- [ ] **Adım 3: Çalıştır, PASS doğrula** — gerçek JSON üzerinden tüm `test_quiz.py` PASS.

- [ ] **Adım 4: Commit**

```bash
git add orchestrator/test_quiz.py
git rm orchestrator/test_es_zit_anlam.py
git commit -m "test(quiz): genel motor + 3 saglayici + HTTP; eski esanlam testi kaldirildi"
```

- [ ] **Adım 5: Manuel kontrol listesi (tarayıcı)** — `python run_web.py` (sunucu YENİDEN başlat!):
  1. Menüde **🧠 Bilgi Yarışması** → alt-menü (Eş/Zıt · Atasözü · Doğru/Yanlış).
  2. Her üçü: kural + başla + sorular + süre barı + ilerleme ("Soru 2/5").
  3. Atasözü: "'Damlaya damlaya …' nasıl devam eder?" → "göl olur" doğru.
  4. Doğru/Yanlış: ifade + "doğru/yanlış" → açıklamalı geri bildirim.
  5. Bitişte skor + "Yeni yarışma" (alt-menüye döner).
  6. Ollama kapalı olsa bile çalışır (offline).

---

## Öz-İnceleme Sonucu (plan yazarı)

- **Spec kapsamı:** veri (G1), loader+sağlayıcı (G2), genel motor+refactor (G3), menü+yönlendirme (G4), frontend (G5), temizlik+HTTP (G6) → tüm spec bölümleri kapsandı.
- **Tip tutarlılığı:** `quiz_provider`/`quiz_turn`/`quiz_score`/`quiz_q_index`/`quiz_current`, soru dict (`id/prompt/accept_norm/reveal/match`), kind'lar (`quiz_menu/quiz_ready/quiz_question/quiz_end`), `_QUIZ_SELECT`, `QUIZ_QUESTION_COUNT`, `game="quiz"`, `quiz_progress` tüm görevlerde tutarlı.
- **Refactor güvenliği:** Eş/Zıt davranışı `_EsZitProvider` + genel motorla korunur; `test_quiz.py` 3 sağlayıcıyı da kapsar.
- **web_server.py değişmez.** **Yer tutucu yok:** tüm kod gerçek; veri gerçek + ölçülebilir genişletme kriteri.
