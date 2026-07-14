"""Kelime Türetme — birlesik temali havuz + dogrudan baslama (Ollama gerektirmez).
Calistir: PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_word_categories.py

Tasarim: "oyun" DOGRUDAN Kelime Türetme baslatir (menu/kategori/TKM/quiz YOK).
AI kelimeleri edebiyat + tarih + bilim havuzlarinin BIRLESIMINDEN gelir.
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


# Test havuzu (enjekte) — Ollama/JSON'a bagimli degil.
# edebiyat+tarih+bilim: AI havuzu bu ucunun BIRLESIMI olmali.
TEST_CATS = {
    "edebiyat": ["roman", "redif", "rivayet", "siir", "sair", "tema", "atasozu"],
    "tarih":    ["savas", "tarih", "ordu", "kale", "zafer"],
    "bilim":    ["atom", "asit", "akim", "tepkime", "teori", "molekul"],
}


class _FakeWordLLM:
    def __init__(self):
        self.unreachable = False
        self.gecerli_calls = 0

    def gecerli_mi(self, w):
        self.gecerli_calls += 1
        return True

    def uret_kelime(self, harf, used, denemeler=2):
        return None  # cagrilmamali (AI artik havuzdan)


def make_engine():
    return GameEngine(bridge=None, word_llm=_FakeWordLLM(), categories=dict(TEST_CATS))


def _force_success(val=0.0):
    """ai_turn/basla icindeki random.random() < p kontrolu deterministik olsun."""
    ge.random.random = lambda: val


# ——— init: birlesik AI havuzu + gecerlilik kumesi ———
def test_init_pool_birlesik():
    g = make_engine()
    check("_ai_pool var", hasattr(g, "_ai_pool"))
    check("kategori kavrami kaldirildi", not hasattr(g, "_pools") and not hasattr(g, "word_category"))
    # 'r' harfi yalniz edebiyat'ta -> havuzda olmali
    check("_ai_pool[r] roman icerir", "roman" in g._ai_pool.get("r", []))
    # 't' harfi HEM edebiyat (tema) HEM tarih (tarih) HEM bilim (teori/tepkime) -> BIRLESIK
    t_words = set(g._ai_pool.get("t", []))
    check("_ai_pool[t] edebiyat+tarih birlesik", {"tema", "tarih"} <= t_words)
    check("_ai_pool[t] bilim de dahil", {"teori", "tepkime"} <= t_words)
    check("_all_words temali kelime icerir", "molekul" in g._all_words)
    check("_all_words genel kelime icerir", "elma" in g._all_words)


# ——— _pick_ai_word: tek arguman (kategori yok) + birlesik ———
def test_pick_ai_word_birlesik():
    g = make_engine()
    check("pick: r -> edebiyat havuzu",
          g._pick_ai_word("r", set()) in {"roman", "redif", "rivayet"})
    check("pick: t -> birlesik aday (edebiyat+tarih+bilim)",
          g._pick_ai_word("t", set()) in {"tema", "tarih", "tepkime", "teori"})
    check("pick: kullanilmis haric",
          g._pick_ai_word("r", {"roman", "redif", "rivayet"}) is None)
    check("pick: seyrek harf None", g._pick_ai_word("x", set()) is None)


def test_ai_turn_themed():
    g = make_engine()
    g.phase = "kelime"
    g.word_turn = "ai"
    g.word_required_letter = "m"   # havuzda yalniz 'molekul'
    g.word_used = set()
    _force_success(0.0)
    p = g.ai_turn()
    check("ai_turn: temali kelime oynar", p["ai_word"] == "molekul")
    check("ai_turn: sira user'a gecer", p["turn"] == "user")
    check("ai_turn: gercek hata yok", not p.get("ai_error"))


def test_ai_turn_concede_sparse():
    g = make_engine()
    g.phase = "kelime"
    g.word_turn = "ai"
    g.word_required_letter = "x"   # havuzda x yok
    g.word_used = set()
    _force_success(0.0)
    p = g.ai_turn()
    check("ai_turn: seyrek harfte pes", p["ended"] is True and p["outcome"] == "user_win")


# ——— _all_words hizli yolu (LLM'e gitmez) ———
def test_gecerli_kelime_fast_path():
    fake = _FakeWordLLM()
    g = GameEngine(bridge=None, word_llm=fake, categories=dict(TEST_CATS))
    g._gecerli_kelime("molekul")  # temali -> _all_words
    g._gecerli_kelime("elma")     # genel -> _all_words
    check("hizli yol: LLM cagrilmadi", fake.gecerli_calls == 0)


# ——— dogrudan baslama: menu/kategori YOK ———
def test_start_dogrudan_kelime():
    g = make_engine()
    p = g.start()
    check("start -> kelime fazi", g.phase == "kelime")
    check("start -> hazir turu (kural ekrani)", g.word_turn == "hazir")
    check("start kind 'ready' (menu/kategori degil)", p.get("kind") == "ready")
    check("kural metni kelime turetme", "Kelime türetme" in p.get("yanit", ""))
    check("tema sorusu YOK", "Tema" not in p.get("yanit", "") and "tema seç" not in p.get("yanit", ""))
    check("category alani None", p.get("category") is None)
    btn_keys = {b["key"] for b in p.get("buttons", [])}
    check("basla + cikis butonlari", {"basla", "cikis"} <= btn_keys)


def test_handle_idle_starts_game():
    g = make_engine()
    p = g.handle("oyun oynayalım")
    check("idle girdi -> dogrudan kural ekrani", p.get("kind") == "ready" and g.word_turn == "hazir")


def test_ready_reprompt_on_nonstart():
    g = make_engine()
    g.start()
    p = g.handle("edebiyat")   # artik kategori degil; 'basla' beklenir
    check("basla disi girdi -> hazir tekrar", p.get("kind") == "ready" and g.word_turn == "hazir")


# ——— tam zincir: AI baslar (temali ilk kelime) ———
def test_begin_ai_starter():
    g = make_engine()
    g.start()
    _force_success(0.0)   # <0.5 -> AI baslar
    p = g.handle("başla")
    check("AI basladi", g.word_starter == "ai")
    check("AI ilk kelime verdi", p.get("ai_word") is not None)
    check("sira user'da", g.word_turn == "user")
    check("gerekli harf = AI kelimesinin son harfi",
          g.word_required_letter == ge.son_harf(p["ai_word"]))


# ——— tam zincir: kullanici baslar (serbest ilk kelime) ———
def test_begin_user_starter_full_chain():
    g = make_engine()
    g.start()
    ge.random.random = lambda: 0.9   # >=0.5 -> kullanici baslar (ilk kelime serbest)
    g.handle("başla")
    check("kullanici basladi", g.word_turn == "user" and g.word_required_letter is None)
    p2 = g.handle("kalem")           # serbest, gecerli genel kelime
    check("serbest kelime kabul", p2.get("kind") == "user_ok" and g.word_required_letter == "m")


def test_exit_and_new_game():
    g = make_engine()
    g.start()
    p = g.exit()
    check("exit -> idle", g.phase == "idle" and p.get("ended") is True)
    # oyun bittikten sonra herhangi girdi yeni oyunu (kural ekrani) acar
    g.phase = "kelime"
    g.word_turn = None
    p2 = g.handle("kelime")
    check("bitince yeni oyun kural ekrani", p2.get("kind") == "ready" and g.word_turn == "hazir")


if __name__ == "__main__":
    test_init_pool_birlesik()
    test_pick_ai_word_birlesik()
    test_ai_turn_themed()
    test_ai_turn_concede_sparse()
    test_gecerli_kelime_fast_path()
    test_start_dogrudan_kelime()
    test_handle_idle_starts_game()
    test_ready_reprompt_on_nonstart()
    test_begin_ai_starter()
    test_begin_user_starter_full_chain()
    test_exit_and_new_game()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
