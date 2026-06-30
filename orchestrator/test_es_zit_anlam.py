"""Es/Zit Anlam modu — standalone birim testleri (Ollama gerektirmez).
Calistir: PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_es_zit_anlam.py
"""
from __future__ import annotations
import importlib
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import game_engine as ge  # noqa: E402,F401
from game_engine import GameEngine  # noqa: E402

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


# ——— Gorev 2: init ———
def test_ea_init():
    g = make_engine()
    check("ea_data yuklendi", "siyah" in g._ea_data)
    check("ea_norm normalize", "beyaz" in g._ea_norm["siyah"]["zit"])
    check("ea_words >=3", len(g._ea_words) >= 3)
    check("ea_turn baslangic None", g.ea_turn is None)
    check("ea_score sifir", g.ea_score == {"dogru": 0, "toplam": 0})


# ——— Gorev 3: soru + dogrulama ———
def test_next_question():
    g = make_engine()
    q = g._ea_next_question()
    check("soru kelime gecerli", q["kelime"] in TEST_EA)
    check("soru tip gecerli", q["tip"] in ("es", "zit"))
    check("kelime used'e eklendi", q["kelime"] in g.ea_used)
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


# ——— Gorev 4: akis ———
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
    check("timeout: toplam+ dogru artmaz", g.ea_score["toplam"] == 1 and g.ea_score["dogru"] == 0)


def test_flow_reaches_end():
    g = make_engine()
    g.start(); g.handle("3"); g.handle("başla")
    last = None
    for _ in range(g.EA_QUESTION_COUNT + 3):
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


# ——— Gorev 5: menu ———
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


# ——— Gorev 7: HTTP entegrasyon (gercek JSON) ———
def test_http_flow():
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


if __name__ == "__main__":
    test_ea_init()
    test_next_question()
    test_check_answer()
    test_flow_start_to_question()
    test_flow_correct_and_score()
    test_flow_timeout_gentle()
    test_flow_reaches_end()
    test_exit_during_quiz()
    test_menu_has_three_options()
    test_menu_routes_to_esanlam_by_name()
    test_http_flow()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
