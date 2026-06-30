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
        _PASS += 1
        print(f"[PASS] {name}")
    else:
        _FAIL += 1
        print(f"[FAIL] {name}")


# Test havuzu (enjekte) — Ollama/JSON'a bagimli degil
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
    """ai_turn icindeki random.random() < p kontrolu deterministik olsun."""
    ge.random.random = lambda: val


# ——— Gorev 2: init + pools ———
def test_init_pools():
    g = make_engine()
    check("genel kategori var", "genel" in g._pools)
    check("edebiyat indekslendi", "r" in g._pools["edebiyat"])
    check("edebiyat[r] roman icerir", "roman" in g._pools["edebiyat"]["r"])
    check("_all_words temali kelime icerir", "molekul" in g._all_words)
    check("_all_words genel kelime icerir", "elma" in g._all_words)
    check("word_category baslangic None", g.word_category is None)


# ——— Gorev 3: _pick_ai_word + ai_turn ———
def test_pick_ai_word():
    g = make_engine()
    check("pick: r ile baslar + edebiyat havuzunda",
          g._pick_ai_word("edebiyat", "r", set()) in {"roman", "redif", "rivayet"})
    check("pick: kullanilmis haric",
          g._pick_ai_word("edebiyat", "r", {"roman", "redif", "rivayet"}) is None)
    check("pick: seyrek harf None", g._pick_ai_word("edebiyat", "z", set()) is None)
    check("pick: eksik kategori -> genel'e duser",
          g._pick_ai_word("yokboyle", "e", set()) is not None)


def test_ai_turn_themed():
    g = make_engine()
    g.phase = "kelime"
    g.word_category = "edebiyat"
    g.word_turn = "ai"
    g.word_required_letter = "t"
    g.word_used = set()
    _force_success(0.0)
    p = g.ai_turn()
    check("ai_turn: temali kelime oynar", p["ai_word"] == "tema")
    check("ai_turn: sira user'a gecer", p["turn"] == "user")
    check("ai_turn: gercek hata yok", not p.get("ai_error"))


def test_ai_turn_concede_sparse():
    g = make_engine()
    g.phase = "kelime"
    g.word_category = "edebiyat"
    g.word_turn = "ai"
    g.word_required_letter = "z"   # edebiyat'ta z yok
    g.word_used = set()
    _force_success(0.0)
    p = g.ai_turn()
    check("ai_turn: seyrek harfte pes", p["ended"] is True and p["outcome"] == "user_win")


# ——— Gorev 4: _all_words hizli yolu ———
def test_gecerli_kelime_fast_path():
    fake = _FakeWordLLM()
    g = GameEngine(bridge=None, word_llm=fake, categories=dict(TEST_CATS))
    g._gecerli_kelime("molekul")  # temali -> _all_words
    g._gecerli_kelime("elma")     # genel -> _all_words
    check("hizli yol: LLM cagrilmadi", fake.gecerli_calls == 0)


# ——— Gorev 5: kategori menusu + akis ———
def test_category_menu_flow():
    g = make_engine()
    g.start()
    p = g.handle("2")
    check("menu->kategori: kind", p.get("kind") == "category_select")
    check("menu->kategori: word_turn", g.word_turn == "kategori")
    btn_keys = {b["key"] for b in p.get("buttons", [])}
    check("kategori butonlari", {"edebiyat", "tarih", "bilim", "genel"} <= btn_keys)
    p2 = g.handle("edebiyat")
    check("kategori secildi", g.word_category == "edebiyat")
    check("hazir fazi", g.word_turn == "hazir")
    check("intro temali", "Edebiyat" in p2.get("yanit", ""))


def test_category_invalid_reprompts():
    g = make_engine()
    g.start()
    g.handle("2")
    p = g.handle("asdf")
    check("gecersiz -> tekrar sor", p.get("kind") == "category_select")
    check("kategori hala secilmedi", g.word_category is None)


def test_category_by_number_and_genel():
    g = make_engine()
    g.start()
    g.handle("2")
    g.handle("3")  # 3 -> bilim
    check("rakamla bilim", g.word_category == "bilim")


def test_word_category_not_wiped_by_start_kelime():
    g = make_engine()
    g.start()
    g.handle("2")
    g.handle("tarih")
    check("kategori korundu (regresyon)", g.word_category == "tarih")


# ——— Gorev 7: tam zincir (kullanici serbest) ———
def test_full_chain_user_free():
    g = make_engine()
    g.start()
    g.handle("2")
    g.handle("bilim")
    ge.random.random = lambda: 0.9   # >=0.5 -> kullanici baslar (ilk kelime serbest)
    g.handle("başla")
    check("kullanici basladi", g.word_turn == "user" and g.word_required_letter is None)
    p2 = g.handle("kalem")           # serbest, temasiz
    check("serbest kelime kabul", p2.get("kind") == "user_ok" and g.word_required_letter == "m")


if __name__ == "__main__":
    test_init_pools()
    test_pick_ai_word()
    test_ai_turn_themed()
    test_ai_turn_concede_sparse()
    test_gecerli_kelime_fast_path()
    test_category_menu_flow()
    test_category_invalid_reprompts()
    test_category_by_number_and_genel()
    test_word_category_not_wiped_by_start_kelime()
    test_full_chain_user_free()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
