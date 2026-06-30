# Eş/Zıt Anlam Modu Uygulama Planı

> **Ajan işçiler için:** Bu planı görev-görev uygula. Adımlar `- [ ]` checkbox kullanır.

**Hedef:** Oyun moduna 3. mod (Eş/Zıt Anlam) ekle — AI bir kelime + "eş/zıt anlamlısı?" sorar, kullanıcı cevaplar; dostça puanlı quiz (N=5, sert kayıp yok).

**Mimari:** Statik veri dosyası `ai/es_zit_anlam.json` (kelime → {es:[...], zit:[...]}). GameEngine init'te normalize-li kabul kümeleri kurulur. AI soruları saf havuzdan (LLM yok). Tek yönlü → `ai_turn` gerekmez; `web_server.py` DEĞİŞMEZ. Çekirdek sohbet/jest sistemi DEĞİŞMEZ; mevcut jestler kullanılır.

**Teknoloji Yığını:** Python 3.13, Flask, vanilla JS. Test = standalone betik (`test_runner.py` deseni; pytest yok). Türkçe konsol: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`.

**Spec:** `docs/specs/2026-06-30-es-zit-anlam-modu-tasarim.md`

**Çalıştırma:** Tüm komutlar proje kökünden: `C:/Users/mehme/Desktop/v1/v1/01-Projects/aican`

---

## Görev 1: `ai/es_zit_anlam.json` — küratörlü eş/zıt anlam verisi

**Dosyalar:**
- Oluştur: `ai/es_zit_anlam.json`

Tanınır, ortak kelimeler; standart (TDK/KeNet/mythes-tr ile uyumlu) eş/zıt anlam çiftleri. Tüm değerler tek sözcük, küçük, Türkçe harf.

- [ ] **Adım 1: Dosyayı oluştur**

```json
{
  "siyah": {"zit": ["beyaz", "ak"]},
  "beyaz": {"zit": ["siyah", "kara"], "es": ["ak"]},
  "büyük": {"zit": ["küçük"], "es": ["iri", "kocaman"]},
  "küçük": {"zit": ["büyük"], "es": ["ufak", "minik"]},
  "uzun": {"zit": ["kısa"]},
  "kısa": {"zit": ["uzun"]},
  "hızlı": {"zit": ["yavaş"], "es": ["çabuk", "seri"]},
  "yavaş": {"zit": ["hızlı"], "es": ["ağır"]},
  "sıcak": {"zit": ["soğuk"]},
  "soğuk": {"zit": ["sıcak"]},
  "açık": {"zit": ["kapalı"]},
  "kapalı": {"zit": ["açık"]},
  "yeni": {"zit": ["eski"]},
  "eski": {"zit": ["yeni"], "es": ["kadim"]},
  "güzel": {"zit": ["çirkin"], "es": ["hoş", "şirin"]},
  "çirkin": {"zit": ["güzel"]},
  "iyi": {"zit": ["kötü"], "es": ["güzel"]},
  "kötü": {"zit": ["iyi"], "es": ["fena"]},
  "mutlu": {"zit": ["üzgün", "mutsuz"], "es": ["sevinçli", "neşeli", "mesut"]},
  "üzgün": {"zit": ["mutlu", "neşeli"], "es": ["kederli", "mahzun"]},
  "zengin": {"zit": ["fakir", "yoksul"]},
  "fakir": {"zit": ["zengin"], "es": ["yoksul"]},
  "güçlü": {"zit": ["zayıf", "güçsüz"], "es": ["kuvvetli"]},
  "zayıf": {"zit": ["güçlü", "şişman"], "es": ["cılız"]},
  "kalın": {"zit": ["ince"]},
  "ince": {"zit": ["kalın"]},
  "dolu": {"zit": ["boş"]},
  "boş": {"zit": ["dolu"]},
  "genç": {"zit": ["yaşlı", "ihtiyar"]},
  "yaşlı": {"zit": ["genç"], "es": ["ihtiyar"]},
  "doğru": {"zit": ["yanlış"], "es": ["gerçek"]},
  "yanlış": {"zit": ["doğru"], "es": ["hatalı"]},
  "ileri": {"zit": ["geri"]},
  "geri": {"zit": ["ileri"]},
  "yukarı": {"zit": ["aşağı"]},
  "aşağı": {"zit": ["yukarı"]},
  "sağ": {"zit": ["sol"]},
  "sol": {"zit": ["sağ"]},
  "gece": {"zit": ["gündüz"]},
  "gündüz": {"zit": ["gece"]},
  "ağır": {"zit": ["hafif"], "es": ["yavaş"]},
  "hafif": {"zit": ["ağır"]},
  "geniş": {"zit": ["dar"]},
  "dar": {"zit": ["geniş"]},
  "temiz": {"zit": ["kirli", "pis"]},
  "kirli": {"zit": ["temiz"], "es": ["pis"]},
  "sevgi": {"zit": ["nefret"], "es": ["aşk", "muhabbet"]},
  "nefret": {"zit": ["sevgi"]},
  "cesur": {"zit": ["korkak"], "es": ["yürekli"]},
  "korkak": {"zit": ["cesur"]},
  "cömert": {"zit": ["cimri"]},
  "cimri": {"zit": ["cömert"]},
  "çalışkan": {"zit": ["tembel"]},
  "tembel": {"zit": ["çalışkan"]},
  "akıllı": {"zit": ["aptal"], "es": ["zeki"]},
  "aptal": {"zit": ["akıllı"], "es": ["salak"]},
  "tatlı": {"zit": ["acı"], "es": ["şirin"]},
  "acı": {"zit": ["tatlı"]},
  "yumuşak": {"zit": ["sert"]},
  "sert": {"zit": ["yumuşak"], "es": ["katı"]},
  "sevinç": {"zit": ["keder", "üzüntü"], "es": ["neşe", "mutluluk"]},
  "keder": {"zit": ["sevinç"], "es": ["üzüntü", "hüzün"]},
  "barış": {"zit": ["savaş"]},
  "savaş": {"zit": ["barış"], "es": ["harp"]},
  "dost": {"zit": ["düşman"], "es": ["arkadaş"]},
  "düşman": {"zit": ["dost"]},
  "son": {"zit": ["başlangıç", "ilk"]},
  "ilk": {"zit": ["son"]},
  "gelmek": {"zit": ["gitmek"]},
  "gitmek": {"zit": ["gelmek"]},
  "almak": {"zit": ["vermek"]},
  "vermek": {"zit": ["almak"]},
  "gülmek": {"zit": ["ağlamak"]},
  "ağlamak": {"zit": ["gülmek"]},
  "kuru": {"zit": ["yaş", "ıslak"]},
  "ıslak": {"zit": ["kuru"], "es": ["yaş"]},
  "tok": {"zit": ["aç"]},
  "aç": {"zit": ["tok"]},
  "hasta": {"zit": ["sağlam"], "es": ["rahatsız"]},
  "sağlam": {"zit": ["hasta", "bozuk"], "es": ["sağlıklı"]},
  "düz": {"zit": ["eğri"]},
  "eğri": {"zit": ["düz"]},
  "canlı": {"zit": ["cansız", "ölü"]},
  "ölü": {"zit": ["canlı", "diri"]},
  "yakın": {"zit": ["uzak"]},
  "uzak": {"zit": ["yakın"]},
  "çok": {"zit": ["az"]},
  "az": {"zit": ["çok"]},
  "sabah": {"zit": ["akşam"]},
  "akşam": {"zit": ["sabah"]},
  "erken": {"zit": ["geç"]},
  "geç": {"zit": ["erken"]},
  "kolay": {"zit": ["zor"], "es": ["basit"]},
  "zor": {"zit": ["kolay"], "es": ["çetin", "güç"]},
  "ucuz": {"zit": ["pahalı"]},
  "pahalı": {"zit": ["ucuz"]},
  "gerçek": {"zit": ["yalan", "sahte"], "es": ["hakiki"]},
  "yalan": {"zit": ["gerçek", "doğru"]},
  "korku": {"zit": ["cesaret"]},
  "cesaret": {"zit": ["korku"], "es": ["yüreklilik"]},
  "bol": {"zit": ["kıt"], "es": ["çok"]},
  "neşeli": {"zit": ["üzgün"], "es": ["şen", "mutlu"]}
}
```

- [ ] **Adım 2: Geçerli JSON + sağlık doğrula**

Çalıştır:
```bash
python -c "import json; d=json.load(open('ai/es_zit_anlam.json',encoding='utf-8')); es=sum('es' in v for v in d.values()); zit=sum('zit' in v for v in d.values()); multi=[w for v in d.values() for lst in v.values() for w in lst if ' ' in w]; print('kelime:',len(d),'| es olan:',es,'| zit olan:',zit,'| cok-kelime:',multi)"
```
Beklenen: `kelime: ~100 | es olan: >25 | zit olan: ~95 | cok-kelime: []`

- [ ] **Adım 3: Commit**

```bash
git add ai/es_zit_anlam.json
git commit -m "feat(esanlam): es/zit anlam sozcuk havuzu verisi"
```

---

## Görev 2: Veri yükleme + normalize kümeleri + `_reset_ea` + init

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (modül başı: yükleyici + `_EA_FALLBACK` + yol; `__init__`; `_reset_ea`)
- Oluştur: `orchestrator/test_es_zit_anlam.py`

- [ ] **Adım 1: Başarısız testi yaz**

Oluştur `orchestrator/test_es_zit_anlam.py`:

```python
"""Es/Zit Anlam modu — standalone birim testleri (Ollama gerektirmez).
Calistir: PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py
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
        _PASS += 1
        print(f"[PASS] {name}")
    else:
        _FAIL += 1
        print(f"[FAIL] {name}")


TEST_EA = {
    "siyah": {"zit": ["beyaz", "ak"]},
    "mutlu": {"zit": ["üzgün"], "es": ["sevinçli", "neşeli"]},
    "büyük": {"zit": ["küçük"]},
}


def make_engine():
    return GameEngine(bridge=None, word_llm=None, ea_data=dict(TEST_EA))


def test_ea_init():
    g = make_engine()
    check("ea_data yuklendi", "siyah" in g._ea_data)
    check("ea_norm normalize", "beyaz" in g._ea_norm["siyah"]["zit"])
    check("ea_words >=3", len(g._ea_words) >= 3)
    check("ea_turn baslangic None", g.ea_turn is None)
    check("ea_score sifir", g.ea_score == {"dogru": 0, "toplam": 0})


if __name__ == "__main__":
    test_ea_init()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: FAIL — `GameEngine` `ea_data` argümanını / `_ea_data` / `ea_turn` bilmiyor.

- [ ] **Adım 3: Yükleyici + sabitleri ekle**

`game_engine.py` modül seviyesine (kategori yükleyicilerinin yakınına; `normalize`, `temiz_kelime`, `json`, `Path`, `log` zaten mevcut):

```python
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
```

- [ ] **Adım 4: `__init__`'e ea verisini + `_reset_ea` ekle**

`game_engine.py` `__init__` sonundaki `self._reset_word()` satırından ÖNCE ekle (kategori kurulumundan sonra):

```python
        # Es/Zit Anlam verisi + normalize-li kabul kumeleri
        ea_src = ea_data if ea_data is not None else _load_es_zit(ea_path or _EA_DEFAULT_PATH)
        if not ea_src:
            ea_src = {temiz_kelime(k): v for k, v in _EA_FALLBACK.items()}
        self._ea_data = ea_src
        self._ea_norm = {
            w: {tip: {normalize(x) for x in vals} for tip, vals in entry.items()}
            for w, entry in self._ea_data.items()
        }
        self._ea_words = [w for w, e in self._ea_data.items() if e]
        self._reset_ea()
```

Ayrıca `__init__` imzasına parametre ekle:
```python
    def __init__(self, bridge=None, word_llm=None, categories=None, categories_path=None,
                 ea_data=None, ea_path=None):
```

`_reset_word` metodunun hemen ardına yeni metot ekle:
```python
    def _reset_ea(self) -> None:
        self.ea_turn = None              # "hazir" | "soru" | None
        self.ea_used = set()
        self.ea_score = {"dogru": 0, "toplam": 0}
        self.ea_q_index = 0
        self.ea_current = None
```

Sınıf sabiti (diğer `EA`/`WORD` sabitleriyle birlikte, örn. `WORD_AI_FLOOR` yanına):
```python
    EA_QUESTION_COUNT = 5      # es/zit anlam: soru sayisi
```

- [ ] **Adım 5: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: 5 PASS / 0 FAIL.

- [ ] **Adım 6: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_es_zit_anlam.py
git commit -m "feat(esanlam): veri yukleyici + normalize kumeleri + init/reset"
```

---

## Görev 3: Soru üretici + cevap doğrulama

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (yeni metotlar)
- Değiştir: `orchestrator/test_es_zit_anlam.py`

- [ ] **Adım 1: Başarısız testleri yaz**

`test_es_zit_anlam.py`'ye ekle (+ `__main__`):

```python
def test_next_question():
    g = make_engine()
    q = g._ea_next_question()
    check("soru kelime gecerli", q["kelime"] in TEST_EA)
    check("soru tip gecerli", q["tip"] in ("es", "zit"))
    check("kelime used'e eklendi", q["kelime"] in g.ea_used)
    # tum kelimeler kullanilinca None
    for _ in range(10):
        g._ea_next_question()
    check("tukenince None", g._ea_next_question() is None)


def test_check_answer():
    g = make_engine()
    g.ea_current = {"kelime": "siyah", "tip": "zit",
                    "kabul_norm": g._ea_norm["siyah"]["zit"],
                    "kabul_goster": g._ea_data["siyah"]["zit"]}
    check("dogru cevap", g._ea_check_answer("beyaz") is True)
    check("ikinci dogru cevap", g._ea_check_answer("ak") is True)
    check("ascii-fold dogru", g._ea_check_answer("BEYAZ") is True)
    check("yanlis cevap", g._ea_check_answer("mavi") is False)
    check("bos cevap", g._ea_check_answer("") is False)
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: FAIL — `_ea_next_question` / `_ea_check_answer` yok.

- [ ] **Adım 3: Metotları ekle**

`game_engine.py`'ye (örn. `_reset_ea` yakınına):

```python
    def _ea_next_question(self):
        """Kullanilmamis rastgele kelime + o kelimede mevcut rastgele tip sec.
        Tukenince None. ea_current'i de gunceller."""
        adaylar = [w for w in self._ea_words if w not in self.ea_used]
        if not adaylar:
            return None
        kelime = random.choice(adaylar)
        tipler = [t for t in ("es", "zit") if self._ea_data[kelime].get(t)]
        tip = random.choice(tipler)
        self.ea_used.add(kelime)
        self.ea_current = {
            "kelime": kelime,
            "tip": tip,
            "kabul_norm": self._ea_norm[kelime][tip],
            "kabul_goster": self._ea_data[kelime][tip],
        }
        return self.ea_current

    def _ea_check_answer(self, text: str) -> bool:
        """Kullanici cevabi (normalize) mevcut sorunun kabul kumesinde mi? (lenient)."""
        cur = self.ea_current
        if not cur:
            return False
        un = normalize(text)
        if not un:
            return False
        cand = {un} | set(un.split())
        return bool(cur["kabul_norm"] & cand)
```

- [ ] **Adım 4: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: tüm testler PASS.

- [ ] **Adım 5: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_es_zit_anlam.py
git commit -m "feat(esanlam): soru uretici + lenient cevap dogrulama"
```

---

## Görev 4: Akış (start/ready/begin/ask/handle/end) + payload + yönlendirme

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (`_ea_payload`, akış metotları, `handle` yönlendirme + exit, `exit`)
- Değiştir: `orchestrator/test_es_zit_anlam.py`

- [ ] **Adım 1: Başarısız testleri yaz**

`test_es_zit_anlam.py`'ye ekle (+ `__main__`):

```python
def test_flow_start_to_question():
    g = make_engine()
    g.start()
    p = g.handle("3")
    check("3 -> ea_ready", p.get("kind") == "ea_ready")
    check("ea_turn hazir", g.ea_turn == "hazir")
    p2 = g.handle("başla")
    check("basla -> ea_question", p2.get("kind") == "ea_question")
    check("ea_turn soru", g.ea_turn == "soru")
    check("soru metni var", "anlamlısı" in p2.get("yanit", ""))
    check("timer user", p2.get("timer", {}).get("who") == "user")


def test_flow_correct_and_score():
    g = make_engine()
    g.start(); g.handle("3"); g.handle("başla")
    # mevcut soruya dogru cevap ver (kabul kumesinden)
    cur = g.ea_current
    dogru_cevap = cur["kabul_goster"][0]
    p = g.handle(dogru_cevap)
    check("dogru -> skor arti", g.ea_score["dogru"] == 1)
    check("toplam arti", g.ea_score["toplam"] == 1)
    check("sonraki soru veya bitis", p.get("kind") in ("ea_question", "ea_end"))


def test_flow_timeout_gentle():
    g = make_engine()
    g.start(); g.handle("3"); g.handle("başla")
    p = g.handle("", timeout=True)
    check("timeout: kayip degil (devam/bitis)", p.get("kind") in ("ea_question", "ea_end"))
    check("timeout: toplam arti dogru artmaz", g.ea_score["toplam"] == 1 and g.ea_score["dogru"] == 0)


def test_flow_reaches_end():
    g = make_engine()
    g.start(); g.handle("3"); g.handle("başla")
    last = None
    for _ in range(g.EA_QUESTION_COUNT + 2):
        if g.ea_turn != "soru":
            break
        cur = g.ea_current
        last = g.handle(cur["kabul_goster"][0])
    check("oyun bitti", last is not None and last.get("ended") is True and last.get("kind") == "ea_end")
    check("ea_turn None", g.ea_turn is None)
    check("skor metni", "doğru" in last.get("yanit", ""))


def test_exit_during_quiz():
    g = make_engine()
    g.start(); g.handle("3"); g.handle("başla")
    p = g.handle("çıkış")
    check("cikis -> idle", p.get("phase") == "idle" and g.phase == "idle")
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: FAIL — akış metotları + yönlendirme yok.

- [ ] **Adım 3: `_ea_payload` + akış metotlarını ekle**

`game_engine.py`'ye:

```python
    def _ea_payload(self, kind, *, turn, jest_id, yanit, yogunluk=0.8,
                    ea_progress=None, dogru_mu=None, timer=None, ended=False, buttons=None):
        return {
            "game": "esanlam",
            "phase": self.phase,
            "kind": kind,
            "turn": turn,
            "jest_id": jest_id,
            "yogunluk": yogunluk,
            "yanit": yanit,
            "score": None,                 # quiz ilerlemesi ea_progress'te
            "ea_progress": ea_progress,
            "dogru_mu": dogru_mu,
            "timer": timer,
            "buttons": buttons if buttons is not None else [{"key": "cikis", "label": "Çıkış"}],
            "ended": ended,
            "outcome": None,
        }

    @staticmethod
    def _ea_ready_buttons():
        return [{"key": "basla", "label": "▶ Başla"},
                {"key": "cikis", "label": "Çıkış"}]

    def _start_esanlam(self) -> dict:
        """Kurallari anlat + 'basla' bekle (henuz soru/sure yok)."""
        self.phase = "esanlam"
        self._reset_ea()
        self.ea_turn = "hazir"
        yanit = (
            "Eş/Zıt Anlam oyunu! Sana kelimeler söyleyeceğim; her birinin EŞ ya da ZIT "
            f"anlamlısını bul. {self.EA_QUESTION_COUNT} soru, doğrularını sayacağım. "
            "Hazırsan başlayalım — 'başla' de ya da butona dokun!"
        )
        return self._ea_payload(
            "ea_ready", turn="hazir", jest_id=random.choice(_JEST["kel_intro"]),
            yanit=yanit, yogunluk=0.8, timer=None, buttons=self._ea_ready_buttons())

    def _handle_esanlam_ready(self, text: str) -> dict:
        n = normalize(text)
        if n in _KEL_READY or any(w in _KEL_READY for w in n.split()):
            return self._begin_esanlam()
        return self._ea_payload(
            "ea_ready", turn="hazir", jest_id="bekle",
            yanit="Hazır olunca 'başla' de ya da butona dokun :)", yogunluk=0.6,
            timer=None, buttons=self._ea_ready_buttons())

    def _begin_esanlam(self) -> dict:
        self.ea_used = set()
        self.ea_score = {"dogru": 0, "toplam": 0}
        self.ea_q_index = 0
        return self._ea_ask_next()

    def _ea_ask_next(self, prefix=None, dogru_mu=None) -> dict:
        """Sonraki soruyu sor; soru kalmadi/sayi doldu -> bitir.
        prefix: bir onceki cevabin geri bildirimi (ayni mesaja eklenir)."""
        if self.ea_q_index >= self.EA_QUESTION_COUNT:
            return self._ea_end(prefix=prefix)
        q = self._ea_next_question()
        if q is None:
            return self._ea_end(prefix=prefix)
        self.ea_q_index += 1
        self.ea_turn = "soru"
        tip_ad = "eş" if q["tip"] == "es" else "zıt"
        soru = f"'{_cap(q['kelime'])}' kelimesinin {tip_ad} anlamlısı ne?"
        yanit = f"{prefix} {soru}" if prefix else soru
        if dogru_mu is True:
            jest = random.choice(_JEST["kel_user_ok"])
        elif dogru_mu is False:
            jest = random.choice(_JEST["kel_retry"])
        else:
            jest = random.choice(_JEST["kel_intro"])
        return self._ea_payload(
            "ea_question", turn="soru", jest_id=jest, yanit=yanit, yogunluk=0.85,
            dogru_mu=dogru_mu,
            ea_progress=f"Soru {self.ea_q_index}/{self.EA_QUESTION_COUNT} · Doğru {self.ea_score['dogru']}",
            timer={"seconds": self.USER_TURN_SECONDS, "who": "user"})

    def _handle_esanlam(self, text: str, timeout: bool) -> dict:
        cur = self.ea_current
        beklenen = cur["kabul_goster"][0] if cur else "?"
        self.ea_score["toplam"] += 1
        if not timeout and self._ea_check_answer(text):
            self.ea_score["dogru"] += 1
            geri = random.choice(_TXT["kel_user_ok"]) + f" '{_cap(beklenen)}' doğru."
            dogru = True
        else:
            geri = (f"Süre doldu! Ben '{_cap(beklenen)}' diyecektim."
                    if timeout else f"Yaklaştın! Ben '{_cap(beklenen)}' diyecektim 😊")
            dogru = False
        return self._ea_ask_next(prefix=geri, dogru_mu=dogru)

    def _ea_end(self, prefix=None) -> dict:
        self.ea_turn = None
        d = self.ea_score["dogru"]
        t = self.ea_score["toplam"] or self.EA_QUESTION_COUNT
        if d >= t * 0.8:
            jest = random.choice(_JEST["kel_user_ok"]); kapanis = "Harikasın, kelime hazinen çok geniş!"
        elif d >= t * 0.4:
            jest = random.choice(_JEST["kel_intro"]); kapanis = "İyi gidiyorsun, güzel oynadın!"
        else:
            jest = "huzur"; kapanis = "Önemli değil, oynamak güzeldi — yine beklerim!"
        yanit = f"{prefix + ' ' if prefix else ''}Oyun bitti! {d}/{t} doğru. {kapanis}"
        return self._ea_payload(
            "ea_end", turn=None, jest_id=jest, yanit=yanit, yogunluk=0.9,
            ea_progress=f"Bitti · {d}/{t} doğru", timer=None, ended=True,
            buttons=[{"key": "esanlam", "label": "🔁 Yeni oyun"}, {"key": "cikis", "label": "Çıkış"}])
```

- [ ] **Adım 4: `handle()` yönlendirme + exit'i güncelle**

`game_engine.py:452-457` exit kontrolünü değiştir. Mevcut:
```python
        if not timeout:
            if self.phase == "kelime" and self.word_turn is not None:
                if n in _KEL_EXIT:
                    return self.exit()
            elif n in _EXIT_WORDS or any(w in _EXIT_WORDS for w in n.split()):
                return self.exit()
```
Şununla değiştir:
```python
        if not timeout:
            active_game = ((self.phase == "kelime" and self.word_turn is not None) or
                           (self.phase == "esanlam" and self.ea_turn is not None))
            if active_game:
                if n in _KEL_EXIT:
                    return self.exit()
            elif n in _EXIT_WORDS or any(w in _EXIT_WORDS for w in n.split()):
                return self.exit()
```

`game_engine.py:463-473` kelime bloğundan SONRA (idle fallback'tan ÖNCE) ekle:
```python
        if self.phase == "esanlam":
            if self.ea_turn is None:
                return self._start_esanlam()   # bitti -> yeni oyun
            if self.ea_turn == "hazir":
                return self._handle_esanlam_ready(text)
            return self._handle_esanlam(text, timeout)
```

`exit()` metodunda (`self._reset_word()` satırının yanına) `self._reset_ea()` ekle:
```python
        self.phase = "idle"
        self._reset_word()
        self._reset_ea()
```

- [ ] **Adım 5: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: tüm testler PASS.

- [ ] **Adım 6: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_es_zit_anlam.py
git commit -m "feat(esanlam): akis (start/ready/soru/sonuc/bitis) + payload + yonlendirme"
```

---

## Görev 5: Menü entegrasyonu (3. seçenek)

**Dosyalar:**
- Değiştir: `orchestrator/game_engine.py` (`_menu_buttons`, `_handle_menu`, `_TXT["menu"]`)
- Değiştir: `orchestrator/test_es_zit_anlam.py`

- [ ] **Adım 1: Başarısız testi yaz**

`test_es_zit_anlam.py`'ye ekle (+ `__main__`):

```python
def test_menu_has_three_options():
    g = make_engine()
    p = g.start()
    keys = {b["key"] for b in p.get("buttons", [])}
    check("menude 3. secenek", "3" in keys)
    check("menu metni 3", "Eş/Zıt" in p.get("yanit", "") or "Es/Zit" in p.get("yanit", ""))


def test_menu_routes_to_esanlam_by_name():
    g = make_engine()
    g.start()
    p = g.handle("eş anlam")
    check("ad ile esanlam", p.get("kind") == "ea_ready")
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: FAIL — menüde 3 yok, "eş anlam" yönlenmiyor.

- [ ] **Adım 3: `_menu_buttons`'a 3. buton**

`game_engine.py` `_menu_buttons`. Mevcut:
```python
        return [
            {"key": "1", "label": "✊ Taş Kağıt Makas"},
            {"key": "2", "label": "🔤 Kelime Türetme"},
        ]
```
Şununla değiştir:
```python
        return [
            {"key": "1", "label": "✊ Taş Kağıt Makas"},
            {"key": "2", "label": "🔤 Kelime Türetme"},
            {"key": "3", "label": "🔁 Eş/Zıt Anlam"},
        ]
```

- [ ] **Adım 4: `_handle_menu`'ya yönlendirme**

`game_engine.py` `_handle_menu` içinde, RPS bloğundan SONRA, reprompt `return`'ünden ÖNCE ekle:
```python
        # Es/Zit Anlam
        if n in ("3", "uc", "ucuncu") or "anlam" in n:
            return self._start_esanlam()
```

- [ ] **Adım 5: `_TXT["menu"]` metnini güncelle**

`game_engine.py` `_TXT` içindeki `"menu"`. Mevcut:
```python
    "menu": [
        "Hadi oynayalım! Hangisini istersin? — (1) Taş Kağıt Makas, (2) Kelime Türetme. Söyle ya da dokun.",
    ],
```
Şununla değiştir:
```python
    "menu": [
        "Hadi oynayalım! Hangisini istersin? — (1) Taş Kağıt Makas, (2) Kelime Türetme, (3) Eş/Zıt Anlam. Söyle ya da dokun.",
    ],
```

- [ ] **Adım 6: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: tüm testler PASS.

- [ ] **Adım 7: Commit**

```bash
git add orchestrator/game_engine.py orchestrator/test_es_zit_anlam.py
git commit -m "feat(esanlam): menuye 3. secenek (Es/Zit Anlam)"
```

---

## Görev 6: Frontend — control.js (süre + ilerleme)

**Dosyalar:**
- Değiştir: `web/control.js` (`applyGamePayload`)

> Buton ve menü `renderGameButtons` ile otomatik; `app.js` (sergi) ai_reply/timer/jest mesajlarını zaten işler → DEĞİŞMEZ. Yalnız control.js süre barını ve ilerlemeyi `esanlam` için de tetiklemeli (ai_turn HARİÇ).

- [ ] **Adım 1: `isTimed` tanımı**

`web/control.js` `applyGamePayload` içinde, `const isWord = (p.game === 'kelime');` satırından sonra ekle:
```javascript
    const isTimed = (p.game === 'kelime' || p.game === 'esanlam');
```

- [ ] **Adım 2: Zaman barı bloğunu genelleştir**

Mevcut:
```javascript
    if (isWord) {
      if (p.ended || !p.timer) stopWordTimer();
      else startWordTimer(p.timer.seconds, p.timer.who);
      // Sıra AI'da ise (kullanıcı kelimesi kabul edildi) AI'nın cevabını iste.
      if (!p.ended && p.turn === 'ai') requestAiTurn();
    }
```
Şununla değiştir:
```javascript
    if (isTimed) {
      if (p.ended || !p.timer) stopWordTimer();
      else startWordTimer(p.timer.seconds, p.timer.who);
      // Yalniz kelime modunda AI turu otomatik istenir (esanlam tek yonlu).
      if (p.game === 'kelime' && !p.ended && p.turn === 'ai') requestAiTurn();
    }
```

- [ ] **Adım 3: Bitiş bloğunu genelleştir**

Mevcut:
```javascript
    if (p.ended) {
      if (isWord) {
        // Kelime maçı bitti: timer dur, "Yeni oyun/Çıkış" butonları + skor kalır.
        // gamePhase üstte 'kelime' kaldı (p.phase==='kelime') → tekrar oynanabilir.
        stopWordTimer();
      } else {
```
Şununla değiştir:
```javascript
    if (p.ended) {
      if (isTimed) {
        // Kelime/Es-Zit maci bitti: timer dur, "Yeni oyun/Çıkış" + skor kalir.
        stopWordTimer();
      } else {
```

- [ ] **Adım 4: Eş/Zıt ilerleme + log**

`renderGameButtons(p.buttons || []);` satırından sonra (kategori `gameTheme` bloğunun yakını) ekle:
```javascript
    if (p.game === 'esanlam' && els.gameScore) {
      els.gameScore.textContent = p.ea_progress || '—';
    }
```

Log bloğunda `} else if (isWord) {` dalından sonra, son `} else {`'ten önce ekle:
```javascript
    } else if (p.game === 'esanlam') {
      log('jest', 'eş/zıt: ' + p.kind
        + (p.dogru_mu === true ? ' ✓' : p.dogru_mu === false ? ' ✗' : ''));
```

- [ ] **Adım 5: JS sözdizimi + birim regresyon**

Çalıştır: `node --check web/control.js` → hata yok (node yoksa atla).
Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py` → tüm PASS.

- [ ] **Adım 6: Commit**

```bash
git add web/control.js
git commit -m "feat(esanlam): control.js sure bari + ilerleme (esanlam icin)"
```

---

## Görev 7: HTTP entegrasyon testi + manuel kontrol listesi

**Dosyalar:**
- Değiştir: `orchestrator/test_es_zit_anlam.py`

- [ ] **Adım 1: HTTP akış testi ekle**

`test_es_zit_anlam.py`'ye ekle (+ `__main__`):

```python
def test_http_flow():
    import importlib
    sys.path.insert(0, str(BASE_DIR))
    ws = importlib.import_module("web_server")
    cfg = ws.load_config()
    cfg["warmup_on_start"] = False
    cfg["tts_enabled"] = False
    app = ws.create_app(cfg)
    c = app.test_client()

    def post(url, **body):
        return c.post(url, json=body or None).get_json()

    post("/api/game/start")
    p = post("/api/game/input", text="3")
    check("http: 3 -> ea_ready", p.get("kind") == "ea_ready")
    p = post("/api/game/input", text="başla")
    check("http: basla -> ea_question", p.get("kind") == "ea_question")
    check("http: timer", p.get("timer", {}).get("who") == "user")
```

- [ ] **Adım 2: Testi çalıştır, geçtiğini doğrula**

Çalıştır: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py`
Beklenen: tüm testler PASS (gerçek `ai/es_zit_anlam.json` üzerinden).

- [ ] **Adım 3: Commit**

```bash
git add orchestrator/test_es_zit_anlam.py
git commit -m "test(esanlam): HTTP entegrasyon akis testi"
```

- [ ] **Adım 4: Manuel kontrol listesi (tarayıcı)**

Çalıştır: `python run_web.py`. Doğrula:
1. "Oyna" → menüde **3) Eş/Zıt Anlam** butonu var.
2. Seçince kural anlatımı + "Başla".
3. Başla → soru ("'Siyah' kelimesinin zıt anlamlısı ne?"), süre barı dönüyor, "Soru 1/5" ilerleme.
4. Doğru cevap → "Bravo! ... doğru" + sevinç jesti + sonraki soru.
5. Yanlış/boş → "Yaklaştın! Ben 'X' diyecektim" (kayıp YOK) + sonraki soru.
6. Eş ve zıt sorular karışık geliyor.
7. 5. sorudan sonra skor özeti ("4/5 doğru!") + duygu + "Yeni oyun/Çıkış".
8. Ollama KAPALI olsa bile çalışıyor (tamamen offline veri).

---

## Öz-İnceleme Sonucu (plan yazarı)

- **Spec kapsamı:** veri (G1), yükleme+normalize+reset (G2), soru+doğrulama (G3), akış+payload+yönlendirme+exit (G4), menü (G5), frontend süre/ilerleme (G6), test (G2-G7) → tüm spec bölümleri görevlere bağlandı.
- **Tip tutarlılığı:** `ea_turn`("hazir"|"soru"|None), `ea_score`{dogru,toplam}, `ea_used`, `ea_q_index`, `ea_current`{kelime,tip,kabul_norm,kabul_goster}, `_ea_payload`/`ea_progress`/`dogru_mu`, `EA_QUESTION_COUNT`, kind'lar (`ea_ready|ea_question|ea_end`) tüm görevlerde tutarlı.
- **web_server.py değişmez:** kategori özelliğinde kanıtlandığı gibi `/api/game/input` + `/api/game/start` mevcut; quiz tek-yönlü, `ai_turn` yok.
- **Yer tutucu yok:** tüm kod adımları gerçek kod; JSON gerçek içerik (~100 çift).
- **Sapma (bilinçli):** Geri bildirim + sonraki soru TEK payload'da birleştirildi (ekstra round-trip/ai_turn yok) → frontend basit kalır.
