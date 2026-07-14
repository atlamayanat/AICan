"""Ortak quiz motoru + 3 saglayici + DUZ 4 oyunlu menu — standalone testler (Ollama gerektirmez).
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


# ——— Duz 4 oyunlu menu akisi ———
def test_menu_flat_4():
    g = make_engine()
    p = g.start()
    check("menu fazi", p["phase"] == "menu" and p["game"] == "menu")
    keys = [b["key"] for b in p["buttons"]]
    check("duz 4 buton", keys == ["kelime", "eszit", "atasozu", "dogruyanlis"])


def test_menu_selects_each_game():
    # Menuden dogrudan (alt-menu YOK) her oyuna gecis
    g = make_engine()
    g.start()
    p = g.handle("kelime")
    check("kelime secildi", p["game"] == "kelime" and p["turn"] == "hazir")
    for sel in ("eszit", "atasozu", "dogruyanlis"):
        g.start()
        p = g.handle(sel)
        check(f"{sel} ready (dogrudan)", p["kind"] == "quiz_ready" and g.quiz_provider == sel)


def test_quiz_full_flow_each_provider():
    for sel in ("eszit", "atasozu", "dogruyanlis"):
        g = make_engine()
        g.start()
        p = g.handle(sel)
        check(f"{sel}: ready", p["kind"] == "quiz_ready" and g.quiz_provider == sel)
        p = g.handle("başla")
        check(f"{sel}: question", p["kind"] == "quiz_question")
        q = g.quiz_current
        ans = next(iter(q["accept_norm"]))
        p = g.handle(ans)
        check(f"{sel}: dogru cevap islendi",
              g.quiz_score["toplam"] == 1 and g.quiz_score["dogru"] == 1
              and p["kind"] in ("quiz_question", "quiz_end"))


def _play_until_end(g, answer="evet"):
    """Soru sayisi dolana YA DA veri tukenene kadar cevapla; bitis payload'unu don."""
    p = None
    for _ in range(GameEngine.QUIZ_QUESTION_COUNT + 3):
        p = g.handle(answer)
        if p.get("ended"):
            break
    return p


def test_quiz_ends_and_returns_to_menu():
    # Soru sayisi(5) veya veri tukenmesi -> quiz_end (dogru davranis; TEST_DY 2 madde).
    g = make_engine()
    g.start(); g.handle("dogruyanlis"); g.handle("başla")
    p = _play_until_end(g)
    check("quiz_end", p["kind"] == "quiz_end" and p["ended"] is True)
    end_keys = [b["key"] for b in p["buttons"]]
    check("bitis butonlari", end_keys == ["tekrar", "menu", "cikis"])
    # 'menu' -> ana menuye don
    p = g.handle("menu")
    check("bitisten menuye", p["phase"] == "menu")
    # 'tekrar' -> ayni yarismayi yeniden baslat
    g.start(); g.handle("eszit"); g.handle("başla")
    _play_until_end(g, answer="x")
    p = g.handle("tekrar")
    check("tekrar -> yeni yarisma", p["kind"] == "quiz_ready" and g.quiz_provider == "eszit")


def test_invalid_menu_reprompts():
    g = make_engine()
    g.start()
    p = g.handle("asdf")
    check("gecersiz secim -> reprompt", p["kind"] == "reprompt" and p["phase"] == "menu")


def test_quiz_exit():
    g = make_engine()
    g.start(); g.handle("eszit"); g.handle("başla")
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

    p = post("/api/game/start")
    check("http menu", p["phase"] == "menu"
          and [b["key"] for b in p["buttons"]] == ["kelime", "eszit", "atasozu", "dogruyanlis"])
    for sel in ("eszit", "atasozu", "dogruyanlis"):
        post("/api/game/start")
        post("/api/game/input", text=sel)
        p = post("/api/game/input", text="başla")
        check(f"http {sel} question", p["kind"] == "quiz_question" and p["quiz"] == sel)
    # Kelime hala menuden erisilebilir
    post("/api/game/start")
    p = post("/api/game/input", text="kelime")
    check("http kelime ready", p["game"] == "kelime" and p["turn"] == "hazir")


if __name__ == "__main__":
    test_providers()
    test_quiz_state_init()
    test_quiz_check_modes()
    test_menu_flat_4()
    test_menu_selects_each_game()
    test_quiz_full_flow_each_provider()
    test_quiz_ends_and_returns_to_menu()
    test_invalid_menu_reprompts()
    test_quiz_exit()
    test_http_quiz()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
