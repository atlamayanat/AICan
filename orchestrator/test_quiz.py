"""Ortak quiz motoru + 3 saglayici + DUZ 4 oyunlu menu — standalone testler (Ollama gerektirmez).
Calistir: PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python orchestrator/test_quiz.py
"""
from __future__ import annotations
import importlib
import re
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
    check("eszit display", q["accept_display"].get("beyaz") == "Beyaz")
    check("eszit tukenme", p.next_question({"siyah"}) is None)
    a = _AtasozuProvider([{"bas": "Damlaya damlaya", "tamam": ["göl olur"]}])
    qa = a.next_question(set())
    check("atasozu match substring", qa["match"] == "substring")
    check("atasozu accept", "gol olur" in qa["accept_norm"])
    check("atasozu display", qa["accept_display"].get("gol olur") == "göl olur")
    d = _DogruYanlisProvider([{"ifade": "Test", "dogru": True, "aciklama": "x"}])
    qd = d.next_question(set())
    check("dy accept dogru", "dogru" in qd["accept_norm"] and "evet" in qd["accept_norm"])
    check("dy display varyant -> kanonik", qd["accept_display"].get("evet") == "Doğru")
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


def test_quiz_yakinlik():
    g = make_engine()
    # eszit: kucuk yazim farki -> yakin; alakasiz -> degil
    g.quiz_provider = "eszit"
    q = {"accept_norm": {"beyaz"}, "match": "token"}
    check("yakin: yazim farki", g._quiz_yakin_mi(q, "beyza"))
    check("yakin degil: alakasiz", not g._quiz_yakin_mi(q, "mavi"))
    check("yakin degil: bos", not g._quiz_yakin_mi(q, ""))
    # atasozu: kabul cevabinin AYIRT EDICI bir kelimesi soylenmis -> yakin;
    # tek basina "olur" gibi dolgu fiil yakinlik SAYMAZ (stopword).
    g.quiz_provider = "atasozu"
    qa = {"accept_norm": {"gol olur"}, "match": "substring"}
    check("yakin: kismi eslesme", g._quiz_yakin_mi(qa, "göl oldu"))
    check("yakin degil: atasozu alakasiz", not g._quiz_yakin_mi(qa, "bilmiyorum"))
    check("yakin degil: dolgu fiil", not g._quiz_yakin_mi(qa, "para olur"))
    check("yakin degil: dolgu cumle", not g._quiz_yakin_mi(qa, "hiç bilmiyorum olur mu"))
    check("yakin degil: 3 harfte mesafe yok", not g._quiz_yakin_mi(qa, "yol"))
    # dogruyanlis: yakinlik anlamsiz (iki secenek)
    g.quiz_provider = "dogruyanlis"
    qd = {"accept_norm": {"dogru", "evet"}, "match": "token"}
    check("dy asla yakin", not g._quiz_yakin_mi(qd, "dogr"))


def test_quiz_onek_tts_uzunlugu():
    # Cumle bolucu (SENT_MIN_LEN=10) kisa parcayi sonraki cumleyle birlestirir;
    # onek < 10 karakter olursa "Onek! Cevap: X." birlesik parcasi on-uretim
    # cache'inde bulunmaz -> sergide canli TTS harcamasi. Regresyon bekcisi:
    for s in (GameEngine._QUIZ_DOGRU_CHEER + GameEngine._QUIZ_YAKIN
              + GameEngine._QUIZ_YANLIS + ("Süre doldu!",)):
        check(f"onek >= 10 karakter: '{s}'", len(s) >= 10)


def test_quiz_yanlis_onekleri():
    # Yakin yanlis -> _QUIZ_YAKIN havuzundan; uzak yanlis -> _QUIZ_YANLIS havuzundan.
    # Kontrollu veri: kabul cevaplari 6 harfli tek kelime — boylece 1 harf bozulma
    # STT toleransiyla DOGRU kabul edilir, 2 harf bozulma yakin-yanlis kalir.
    g = GameEngine(bridge=None, word_llm=None,
                   ea_data={"güzel": {"zit": ["çirkin"]}, "cesur": {"zit": ["korkak"]},
                            "sessiz": {"zit": ["gürültü"]}},
                   atasozu_data=list(TEST_ATA), dogru_yanlis_data=list(TEST_DY))
    g.start(); g.handle("eszit"); g.handle("başla")
    cevap = next(iter(g.quiz_current["accept_norm"]))
    p = g.handle(cevap[:-1] + "x")         # 1 harf boz -> STT toleransi: dogru sayilir
    check("stt tolerans dogru", any(p["yanit"].startswith(o) for o in GameEngine._QUIZ_DOGRU_CHEER))
    cevap = next(iter(g.quiz_current["accept_norm"]))
    p = g.handle(cevap[:-2] + "xy")        # 2 harf boz -> kabul edilmez ama yakin
    check("yakin onek", any(p["yanit"].startswith(o) for o in GameEngine._QUIZ_YAKIN))
    check("yakin onek cevap icerir", "Cevap:" in p["yanit"])
    p = g.handle("qqqqq")                  # alakasiz -> notr yanlis
    check("notr onek", any(p["yanit"].startswith(o) for o in GameEngine._QUIZ_YANLIS))
    check("eski sabit 'Yaklaştın!' yok", not p["yanit"].startswith("Yaklaştın!"))


def test_quiz_user_display():
    # Fuzzy kabulde payload'a kabul edilen cevabin ekran hali (user_display)
    # yazilir: istemci kullanici balonundaki ham STT metnini bununla degistirir.
    g = GameEngine(bridge=None, word_llm=None,
                   ea_data={"güzel": {"zit": ["çirkin"]}, "cesur": {"zit": ["korkak"]}},
                   atasozu_data=[{"bas": "Damlaya damlaya", "tamam": ["göl olur"]}],
                   dogru_yanlis_data=list(TEST_DY))
    # eszit: 1 harf bozuk soyleyis (STT toleransi) kabul -> ekranda kanonik hali
    g.start(); g.handle("eszit"); g.handle("başla")
    dogru_hali = next(iter(g.quiz_current["accept_display"].values()))
    cevap = next(iter(g.quiz_current["accept_norm"]))
    p = g.handle(cevap[:-1] + "x")
    check("eszit fuzzy -> user_display kanonik", p["user_display"] == dogru_hali)
    check("eszit user_display buyuk harfli", p["user_display"][0].isupper())
    p = g.handle("qqqqq")
    check("yanlis cevapta user_display yok", p["user_display"] is None)
    # atasozu: 'göl oldu' fuzzy kabul; tek soruluk veri quiz_end'e dusurse de tasinir
    g.start(); g.handle("atasozu"); g.handle("başla")
    p = g.handle("göl oldu")
    check("atasozu fuzzy -> 'göl olur'", p["user_display"] == "göl olur")
    check("atasozu fuzzy dogru sayildi", g.quiz_score["dogru"] == 1)
    # dogruyanlis: hangi varyant soylenirse soylensin ekranda 'Doğru'/'Yanlış'
    g.start(); g.handle("dogruyanlis"); g.handle("başla")
    ans = "evet" if "evet" in g.quiz_current["accept_norm"] else "hayır"
    p = g.handle(ans)
    check("dy varyant -> kanonik", p["user_display"] in ("Doğru", "Yanlış"))


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


def test_menu_metinleri_degismedi():
    # Dinamik metin uretimi, tum oyunlar izinliyken ESKI SABITLERLE birebir ayni
    # kalmali (TTS on-uretim cache anahtarlari bozulmasin).
    g = make_engine()
    p = g.start()
    check("menu metni ayni", p["yanit"] ==
          "Süper! Hangisini oynayalım? Dokun ya da söyle: 🔤 Kelime Türetme · "
          "🔁 Eş/Zıt Anlam · 📜 Atasözü · ✅ Doğru/Yanlış")
    p = g.handle("asdf")
    check("reprompt metni ayni", p["yanit"] ==
          "Hmm, tam anlamadım :) Hangisini oynayalım — Kelime Türetme, Eş/Zıt Anlam, "
          "Atasözü ya da Doğru/Yanlış?")


def test_hazir_ekranindan_menuye_donus():
    # Hazir ('basla' bekleyen) ekranindaki '🏠 Menü' butonu / sozlu "menü" calismali.
    g = make_engine()
    g.start(); g.handle("eszit")
    p = g.handle("menu")
    check("quiz hazirdan menuye", p["kind"] == "menu" and g.phase == "menu")
    g.start(); g.handle("kelime")
    p = g.handle("menü")
    check("kelime hazirdan menuye", p["kind"] == "menu" and g.phase == "menu")


def test_menu_anlamadim_tetiklemez():
    # Reprompt metni "tam anlamadım" der; ziyaretci tekrarlarsa quiz BASLAMAMALI.
    g = make_engine()
    g.start()
    p = g.handle("hiçbir şey anlamadım")
    check("anlamadim quiz baslatmaz", p["kind"] == "reprompt")
    p = g.handle("eş anlam")
    check("es anlam yine secer", p["kind"] == "quiz_ready" and g.quiz_provider == "eszit")


def test_test_modu_sinirli_menu():
    # izinli_oyunlar: menude yalnizca izinli oyunlar; digerleri secilemez.
    g = make_engine()
    g.izinli_oyunlar = ("eszit", "atasozu")
    p = g.start()
    check("sinirli menu 2 buton", [b["key"] for b in p["buttons"]] == ["eszit", "atasozu"])
    check("sinirli menu metni", "Kelime" not in p["yanit"] and "Eş/Zıt Anlam" in p["yanit"])
    p = g.handle("kelime")
    check("kelime secilemez", p["kind"] == "reprompt" and g.phase == "menu")
    p = g.handle("dogru")
    check("dogruyanlis secilemez", p["kind"] == "reprompt")
    p = g.handle("atasozu")
    check("atasozu secilir", p["kind"] == "quiz_ready" and g.quiz_provider == "atasozu")


def test_quiz_exit():
    # SESLI cikis komutu aktif yarismada ARTIK cikmaz (STT gurultusu "dur"/
    # "çıkış" uretip oyunu ortasinda bitiriyordu) — normal girdi gibi islenir.
    # Yarisma ancak BUTONLA, sorular bitince ya da 2 ardisik cevapsiz zaman
    # asimiyla ("ziyaretci gitti") sona erer.
    g = make_engine()
    g.start(); g.handle("eszit"); g.handle("başla")
    p = g.handle("çıkış")
    check("sesli cikis oyunu bitirmez",
          g.phase == "quiz" and p["kind"] == "quiz_question")
    p = g.handle("cikis", button=True)
    check("buton cikis -> idle", g.phase == "idle" and p["phase"] == "idle")
    g = make_engine()
    g.start(); g.handle("eszit"); g.handle("başla")
    g.handle("", timeout=True)
    p = g.handle("", timeout=True)
    check("2 ardisik timeout -> idle", g.phase == "idle" and p["kind"] == "exit")
    g = make_engine()
    g.start(); g.handle("eszit"); g.handle("başla")
    g.handle("", timeout=True)
    g.handle("beyaz")                     # araya cevap girdi -> sayac sifirlanir
    p = g.handle("", timeout=True)
    # TEST_EA 3 kelime: bu noktada havuz bitip normal "quiz_end" gelebilir;
    # onemli olan terk cikisi ("exit") OLMAMASI (sayac sifirlandi).
    check("cevap sayaci sifirlar", p["kind"] != "exit")


# ——— HTTP (gercek JSON) ———
def test_http_quiz():
    ws = importlib.import_module("web_server")
    cfg = ws.load_config()
    cfg["warmup_on_start"] = False
    cfg["tts_enabled"] = False
    # Laptop config'inde test_mode=true kalmis olabilir — testi kararli kilmak
    # icin normal mod zorlanir (sinirli menu davranisi test_http_test_modu'nda).
    cfg["test_mode"] = False
    c = ws.create_app(cfg).test_client()

    def post(u, **b):
        return c.post(u, json=b or None).get_json()

    p = post("/api/game/start")
    check("http menu", p["phase"] == "menu"
          and [b["key"] for b in p["buttons"]] == ["kelime", "eszit", "atasozu", "dogruyanlis"])
    for sel in ("eszit", "atasozu", "dogruyanlis"):
        # Onceki turdan AKTIF yarisma kalir; /api/game/start artik canli oyunu
        # 409 ile korur (desync'li istemci sifirlamasin) — once temiz cikis.
        post("/api/game/exit")
        post("/api/game/start")
        post("/api/game/input", text=sel)
        p = post("/api/game/input", text="başla")
        check(f"http {sel} question", p["kind"] == "quiz_question" and p["quiz"] == sel)
    # Aktif yarisma varken start REDDEDILIR (istemciye faz VE jeton bildirilir:
    # fazi geri yukleyip jetonsuz kalan istemcinin cevabi bayat sayilirdi)
    r = c.post("/api/game/start")
    check("http start aktif oyunu korur", r.status_code == 409
          and r.get_json().get("error") == "game_active"
          and r.get_json().get("phase") == "quiz")
    check("http start 409 jeton tasir", r.get_json().get("turn_id") == p["turn_id"])
    # Aktif yarisma varken sesli selam (session/new) da REDDEDILIR
    r = c.post("/api/session/new", json={"reason": "greet"})
    check("http greet aktif oyunu korur", r.status_code == 409
          and r.get_json().get("phase") == "quiz")
    check("http greet 409 jeton tasir", r.get_json().get("turn_id") == p["turn_id"])
    # Kelime hala menuden erisilebilir
    post("/api/game/exit")
    post("/api/game/start")
    p = post("/api/game/input", text="kelime")
    check("http kelime ready", p["game"] == "kelime" and p["turn"] == "hazir")
    # Kelime hazir ekrani da CANLI sayilir: start/greet sifirlayamaz
    r = c.post("/api/game/start")
    check("http start kelimeyi korur", r.status_code == 409
          and r.get_json().get("phase") == "kelime")


# ——— Tur jetonu: BAYAT girdi soruyu TUKETMEZ (soru kaymasi korumasi) ———
def test_http_turn_id():
    ws = importlib.import_module("web_server")
    cfg = ws.load_config()
    cfg["warmup_on_start"] = False
    cfg["tts_enabled"] = False
    cfg["test_mode"] = False
    c = ws.create_app(cfg).test_client()

    def post(u, **b):
        return c.post(u, json=b or None).get_json()

    # "Soru N/5" -> N (soru tuketildi mi sorusunun tek gozlemlenebilir yaniti)
    def soru_no(p):
        m = re.search(r"Soru (\d+)/", p.get("quiz_progress") or "")
        return int(m.group(1)) if m else None

    post("/api/game/start")
    post("/api/game/input", text="eszit")
    p = post("/api/game/input", text="başla")
    check("jeton payload'da var", isinstance(p.get("turn_id"), int) and p["turn_id"] > 0)
    tid = p["turn_id"]
    check("jeton ilk soruda 1/5", soru_no(p) == 1)

    # 1) BAYAT jeton (bir onceki tur) -> 409 + faz/jeton bildirir
    r = c.post("/api/game/input", json={"text": "beyaz", "turn_id": tid - 1})
    d = r.get_json()
    check("bayat jeton 409", r.status_code == 409 and d.get("error") == "stale_input")
    check("bayat jeton faz+jeton bildirir",
          d.get("phase") == "quiz" and d.get("turn_id") == tid)

    # ...ve soruyu TUKETMEDI: guncel jetonla gelen cevap hala 1. soruyu yanitlar,
    # yani sonraki payload 2. sorudur (bayat POST islenseydi 3'e atlardi).
    p2 = post("/api/game/input", text="beyaz", turn_id=tid)
    check("bayat jeton soruyu tuketmez", soru_no(p2) == 2)
    check("guncel jeton kabul + jeton ilerler", p2.get("turn_id") == tid + 1)

    # 2) AYNI jetonla ikinci POST (VAD'in ikiye boldugu cevabin 2. parcasi) -> 409
    r = c.post("/api/game/input", json={"text": "siyah", "turn_id": tid})
    check("ayni jeton ikinci kez reddedilir",
          r.status_code == 409 and r.get_json().get("error") == "stale_input")

    # 3) BAYAT timeout POST'u da reddedilir: soru N icin baslayan sayac N+1'i
    #    oldurmesin (jetonsuz timeout'ta sahada gorulen "sure doldu" yarisinin koku).
    tid2 = p2["turn_id"]
    r = c.post("/api/game/input", json={"timeout": True, "turn_id": tid2 - 1})
    check("bayat timeout reddedilir",
          r.status_code == 409 and r.get_json().get("error") == "stale_input")
    p3 = post("/api/game/input", text="beyaz", turn_id=tid2)
    check("bayat timeout soruyu tuketmez", soru_no(p3) == 3)

    # 4) GERIYE DONUK UYUM: jeton alanini HIC gondermeyen istemci (eski panel/sekme)
    #    kabul edilir — uyum anahtarin VARLIGINA bakar, degerine degil.
    p4 = post("/api/game/input", text="beyaz")
    check("jetonsuz istemci kabul edilir", soru_no(p4) == 4)

    # 5) turn_id=null GONDEREN istemci: jeton destekliyor ama senkronu kaybetmis
    #    (409 game_active ile fazi geri yukleyip jetonsuz kalan surucu). Koruma
    #    KAPANMAZ: bayat sayilir, soru tuketilmez, gercek jeton bildirilir.
    tid4 = p4["turn_id"]
    r = c.post("/api/game/input", json={"text": "siyah", "turn_id": None})
    d = r.get_json()
    check("null jeton reddedilir",
          r.status_code == 409 and d.get("error") == "stale_input")
    check("null jeton gercek jetonu bildirir", d.get("turn_id") == tid4)
    p5 = post("/api/game/input", text="beyaz", turn_id=tid4)
    check("null jeton soruyu tuketmez", soru_no(p5) == 5)

    # 6) GEC TIMEOUT, aktif tur YOKKEN: yarisma bittikten sonra ulasan sayac
    #    bildirimi handle()'da _start_quiz'e dusup oyunu YENIDEN BASLATIYORDU
    #    (sahada "biten oyun kendi kendine tekrar acildi"). Artik 409 + noop.
    son = post("/api/game/input", text="beyaz", turn_id=p5["turn_id"])
    check("5. cevaptan sonra yarisma biter", son.get("ended") is True)
    tid_son = son["turn_id"]
    r = c.post("/api/game/input", json={"timeout": True, "turn_id": tid_son})
    d = r.get_json()
    check("aktif tur yokken timeout reddedilir",
          r.status_code == 409 and d.get("error") == "stale_input")
    check("gec timeout oyunu yeniden baslatmaz", d.get("turn_id") == tid_son)

    # 7) MENUDE gelen gec timeout da yoksayilir (eskiden menuyu tekrar sordururdu)
    m = post("/api/game/start")
    r = c.post("/api/game/input", json={"timeout": True, "turn_id": m["turn_id"]})
    check("menude timeout yoksayilir",
          r.status_code == 409 and r.get_json().get("phase") == "menu")


def test_http_test_modu():
    ws = importlib.import_module("web_server")
    cfg = ws.load_config()
    cfg["warmup_on_start"] = False
    cfg["tts_enabled"] = False
    cfg["whisper_enabled"] = False
    cfg["test_mode"] = False
    # save_config gercek config.json'a yazmasin (kalicilik prod ozelligi).
    eski_save = ws.save_config
    ws.save_config = lambda _cfg: None
    try:
        c = ws.create_app(cfg).test_client()

        def post(u, **b):
            return c.post(u, json=b or None).get_json()

        d = post("/api/test_mode", on=True)
        check("http test modu acildi", d["on"] is True)
        d = c.get("/api/config").get_json()
        check("http config test_mode", d.get("test_mode") is True)
        # merhaba -> selamlama + dogrudan sinirli oyun menusu
        p = post("/api/session/new")
        check("http merhaba -> menu", p["phase"] == "menu"
              and [b["key"] for b in p["buttons"]] == ["eszit", "atasozu"]
              and p["yanit"].startswith("Merhaba"))
        # sohbet kapali: LLM'e gitmeden yonlendirme
        p = post("/api/send", text="bugün hava nasıl")
        check("http sohbet kapali", p.get("meta", {}).get("test_mode") is True
              and "oyun" in p.get("yanit", "").lower())
        # menuden kelime secilemez
        post("/api/game/start")
        p = post("/api/game/input", text="kelime")
        check("http kelime engellendi", p["kind"] == "reprompt")
        # parametresiz POST -> toggle (kapat)
        d = post("/api/test_mode")
        check("http test modu kapandi", d["on"] is False)
        p = post("/api/game/start")
        check("http normal menu geri", [b["key"] for b in p["buttons"]]
              == ["kelime", "eszit", "atasozu", "dogruyanlis"])
        p = post("/api/session/new")
        check("http normal selamlama geri", p["phase"] == "idle" and p["buttons"] == [])
    finally:
        ws.save_config = eski_save


if __name__ == "__main__":
    test_providers()
    test_quiz_state_init()
    test_quiz_check_modes()
    test_quiz_yakinlik()
    test_quiz_yanlis_onekleri()
    test_quiz_user_display()
    test_quiz_onek_tts_uzunlugu()
    test_menu_flat_4()
    test_menu_selects_each_game()
    test_quiz_full_flow_each_provider()
    test_quiz_ends_and_returns_to_menu()
    test_invalid_menu_reprompts()
    test_hazir_ekranindan_menuye_donus()
    test_menu_anlamadim_tetiklemez()
    test_menu_metinleri_degismedi()
    test_test_modu_sinirli_menu()
    test_quiz_exit()
    test_http_quiz()
    test_http_turn_id()
    test_http_test_modu()
    print(f"\nSonuc: {_PASS} PASS / {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
