"""Ortak quiz motoru + 3 saglayici — standalone testler (Ollama gerektirmez).
Calistir: PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_quiz.py
"""
from __future__ import annotations
import importlib
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import game_engine as ge  # noqa: E402,F401
from game_engine import (  # noqa: E402
    GameEngine, _EsZitProvider, _AtasozuProvider, _DogruYanlisProvider,
)

_PASS = _FAIL = 0


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"[PASS] {name}")
    else:
        _FAIL += 1
        print(f"[FAIL] {name}")


# ——— Saglayicilar (izole) ———
def test_providers():
    p = _EsZitProvider({"siyah": {"zit": ["beyaz", "ak"]}})
    q = p.next_question(set())
    check("eszit prompt", "anlamlısı" in q["prompt"])
    check("eszit accept", "beyaz" in q["accept_norm"])
    check("eszit tukenme", p.next_question({"siyah"}) is None)
    a = _AtasozuProvider([{"bas": "Damlaya damlaya", "tamam": ["göl olur"]}])
    qa = a.next_question(set())
    check("atasozu match substring", qa["match"] == "substring")
    check("atasozu accept", "gol olur" in qa["accept_norm"])
    d = _DogruYanlisProvider([{"ifade": "Test", "dogru": True, "aciklama": "x"}])
    qd = d.next_question(set())
    check("dy accept dogru", "dogru" in qd["accept_norm"] and "evet" in qd["accept_norm"])
    check("dy reveal", qd["reveal"].startswith("Doğru"))


# ——— Test motoru (enjekte veri) ———
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
    check("quiz_provider None", g.quiz_provider is None)


def test_quiz_check_modes():
    g = make_engine()
    check("token dogru", g._quiz_check({"accept_norm": {"beyaz"}, "match": "token"}, "beyaz"))
    check("token yanlis", not g._quiz_check({"accept_norm": {"beyaz"}, "match": "token"}, "mavi"))
    check("substring", g._quiz_check({"accept_norm": {"gol olur"}, "match": "substring"}, "göl olur derler"))
    check("dy evet", g._quiz_check({"accept_norm": _DogruYanlisProvider._EVET, "match": "token"}, "evet"))
    check("bos", not g._quiz_check({"accept_norm": {"beyaz"}, "match": "token"}, ""))


# ——— Akis ———
def test_menu_to_quiz_submenu():
    g = make_engine()
    p = g.start()
    check("menude bilgi(3)", "3" in {b["key"] for b in p["buttons"]})
    p = g.handle("3")
    check("3 -> quiz_menu", p["kind"] == "quiz_menu")
    keys = {b["key"] for b in p["buttons"]}
    check("alt-menu butonlari", {"eszit", "atasozu", "dogruyanlis"} <= keys)


def test_quiz_full_flow_each_provider():
    for sel, key in (("eszit", "eszit"), ("atasozu", "atasozu"), ("dogruyanlis", "dogruyanlis")):
        g = make_engine()
        g.start()
        g.handle("3")
        p = g.handle(sel)
        check(f"{sel}: ready", p["kind"] == "quiz_ready" and g.quiz_provider == key)
        p = g.handle("başla")
        check(f"{sel}: question", p["kind"] == "quiz_question")
        q = g.quiz_current
        ans = next(iter(q["accept_norm"]))
        p = g.handle(ans)
        check(f"{sel}: cevap islendi",
              g.quiz_score["toplam"] == 1 and p["kind"] in ("quiz_question", "quiz_end"))


def test_quiz_invalid_select_reprompts():
    g = make_engine()
    g.start(); g.handle("3")
    p = g.handle("asdf")
    check("gecersiz secim -> tekrar", p["kind"] == "quiz_menu")
    check("provider hala None", g.quiz_provider is None)


def test_quiz_exit():
    g = make_engine()
    g.start(); g.handle("3"); g.handle("eszit"); g.handle("başla")
    p = g.handle("çıkış")
    check("cikis -> idle", g.phase == "idle" and p["phase"] == "idle")


# ——— HTTP (gercek JSON) ———
def test_http_quiz():
    ws = importlib.import_module("web_server")
    cfg = ws.load_config()
    cfg["warmup_on_start"] = False
    cfg["tts_enabled"] = False
    c = ws.create_app(cfg).test_client()

    def post(u, **b):
        return c.post(u, json=b or None).get_json()

    post("/api/game/start")
    p = post("/api/game/input", text="3")
    check("http quiz_menu", p["kind"] == "quiz_menu")
    for sel in ("eszit", "atasozu", "dogruyanlis"):
        post("/api/game/start")
        post("/api/game/input", text="3")
        post("/api/game/input", text=sel)
        p = post("/api/game/input", text="başla")
        check(f"http {sel} question", p["kind"] == "quiz_question" and p["quiz"] == sel)


if __name__ == "__main__":
    test_providers()
    test_quiz_state_init()
    test_quiz_check_modes()
    test_menu_to_quiz_submenu()
    test_quiz_full_flow_each_provider()
    test_quiz_invalid_select_reprompts()
    test_quiz_exit()
    test_http_quiz()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
