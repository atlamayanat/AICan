"""ElevenLabs ON-URETIM (batch) betigi — sergi oncesi sabit korpusu bir kez uretir.

Oyun modunun seslendirilen metinlerini (sabit replikler + kelime havuzu + quiz
havuzu) enumere eder, cumle parcalarina boler (runtime ile ayni _split_sentences_tr),
KABA duygu imzasiyla (engine_elevenlabs.emotion_signature) tekillestirir ve WavCache'e
YAZAR. Boylece sergide bu parcalar %100 cache isabeti = 0 kredi.

Anahtar esitligi: runtime /api/speak, ElevenLabs motorunda cache anahtarini
(voice, DUYGU-IMZASI, yogunluk, metin) uzerinden kurar (bkz web_server._cache_jest);
bu betik de AYNI imzayi/anahtari uretir -> sergide dogrudan isabet. Rastgele jest
secimi imza sayesinde tek sese kanoniklesir (emoji/oyun degismez).

Kullanim (orchestrator/ dizininden):
  python -m tts.gen_batch_elevenlabs                 # DRY-RUN: kredi onizlemesi (API'siz)
  python -m tts.gen_batch_elevenlabs --run --yes     # GERCEK uretim (ELEVENLABS_API_KEY gerekli)
  python -m tts.gen_batch_elevenlabs --run --yes --include-selfheal   # harf sablonlarini da uret

self_heal=True birimler (harf'li retry/pes replikleri) VARSAYILAN olarak ON-URETILMEZ;
sergide ilk kullanimda canli uretilip cache'lenir (bkz secilen plan). Dry-run bunlari
ayri "self-heal kuyrugu" olarak raporlar.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # orchestrator/ path'e

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Turkce konsol
except Exception:  # noqa: BLE001
    pass

from game_engine import GameEngine, _JEST, _TXT, _cap        # noqa: E402
from word_llm import son_harf                                 # noqa: E402
from web_server import (                                      # noqa: E402
    _split_sentences_tr, KELIME_KURAL_TEXT, HAZIR_BEKLE_TEXT,
    SESSION_GREETING_TEXT, SESSION_GREETING_JEST, DEFAULT_TTS_VOICE, load_config,
    TEST_OYUNLAR, TEST_SOHBET_KAPALI_TEXT, _test_greeting_yanit,
)
from tts.engine_elevenlabs import emotion_signature           # noqa: E402

_SEN_BASLA = "Sen başla — bir kelime söyle!"


def _guard_templates():
    try:
        from llm_bridge import _SAFE_RESPONSE_TEMPLATES
        return dict(_SAFE_RESPONSE_TEMPLATES)
    except Exception:  # noqa: BLE001
        return {}


def _enumerate_quiz(ge):
    """Tum quiz sorularinin (prompt, reveal) metinlerini uret (saglayici koduyla ayni sablon)."""
    prompts, reveals = [], []
    ez = ge._providers.get("eszit")
    if ez:
        for w in ez.words:
            for tip in ("es", "zit"):
                if ez.data.get(w, {}).get(tip):
                    tip_ad = "eş" if tip == "es" else "zıt"
                    prompts.append(f"'{_cap(w)}' kelimesinin {tip_ad} anlamlısı ne?")
                    reveals.append(_cap(ez.data[w][tip][0]))
    at = ge._providers.get("atasozu")
    if at:
        for it in at.items:
            prompts.append(f"'{it['bas']} …' nasıl devam eder?")
            reveals.append(f"{it['bas']} {it['tamam'][0]}")
    dy = ge._providers.get("dogruyanlis")
    if dy:
        for it in dy.items:
            prompts.append(f"'{it['ifade']}' — doğru mu, yanlış mı?")
            dyw = "Doğru" if it["dogru"] else "Yanlış"
            reveals.append(f"{dyw} — {it.get('aciklama', '')}".strip(" —"))
    return prompts, reveals


def build_units(ge):
    """Seslendirilen her baglam icin {name, texts, jests, yog, self_heal} birimi."""
    U = []
    def add(name, texts, jests, yog, self_heal=False):
        texts = [t for t in (texts or []) if (t or "").strip()]
        if texts:
            U.append({"name": name, "texts": texts, "jests": list(jests),
                      "yog": yog, "self_heal": self_heal})

    # 1) Sabit cekirdek replikler
    add("menu", [ge._menu_payload()["yanit"], ge._menu_payload(reprompt=True)["yanit"]],
        [_JEST["menu"]], 0.8)
    # Test modu ('g' tusu: sinirli menu + sohbet kapali) replikleri de cache'te olsun.
    eski_izin = ge.izinli_oyunlar
    ge.izinli_oyunlar = TEST_OYUNLAR
    tm_menu = ge._menu_payload()
    add("menu_test",
        [_test_greeting_yanit(), tm_menu["yanit"],
         ge._menu_payload(reprompt=True)["yanit"], TEST_SOHBET_KAPALI_TEXT],
        [_JEST["menu"], SESSION_GREETING_JEST], 0.8)
    ge.izinli_oyunlar = eski_izin
    # KIOSK (panelsiz sergi) voice_only=True kullanir -> menu birincil metni
    # "Söyle: ..." olur ("Dokun ya da söyle" YERINE; bkz game_engine._menu_payload).
    # Batch varsayilani voice_only=False oldugundan bu varyant SADECE web_server
    # startup pre-warm'u ile cache'lenirdi (kirilgan; ozellikle NON-test 4-oyunlu
    # menu hic uretilmiyordu). Burada dogrudan uret: hem tum oyunlar (non-test)
    # hem TEST_OYUNLAR (test modu). Zaten cache'te olan atlanir (kredi harcanmaz).
    eski_vo = ge.voice_only
    ge.voice_only = True
    vo_menu = [ge._menu_payload()["yanit"]]              # tum oyunlar (non-test kiosk)
    ge.izinli_oyunlar = TEST_OYUNLAR
    vo_menu.append(ge._menu_payload()["yanit"])          # test modu kiosk
    ge.izinli_oyunlar = eski_izin
    ge.voice_only = eski_vo
    add("menu_voice", vo_menu, [_JEST["menu"], SESSION_GREETING_JEST], 0.8)
    add("exit", list(_TXT["exit"]), [_JEST["exit"]], 0.6)
    add("kelime_kural", [KELIME_KURAL_TEXT], _JEST["kel_intro"], 0.8)
    add("hazir_bekle", [HAZIR_BEKLE_TEXT], ["bekle"], 0.6)
    add("sen_basla", [_SEN_BASLA], _JEST["kel_intro"], 0.8)
    add("tezahurat", list(_TXT["kel_user_ok"]), _JEST["kel_user_ok"], 0.85)
    add("user_lose", list(_TXT["kel_user_lose_timeout"]) + list(_TXT["kel_user_lose_invalid"]),
        _JEST["kel_user_lose"], 0.8)
    add("greeting", [SESSION_GREETING_TEXT], [SESSION_GREETING_JEST], 0.8)
    for k, v in _guard_templates().items():
        add(f"guard:{k}", [v], [None if k == "sicaklik_default" else k], 0.7)
    for prov in ge._providers.values():
        add(f"quiz_intro:{prov.key}",
            [prov.intro(ge.QUIZ_QUESTION_COUNT) +
             " Hazırsan başlayalım — 'başla' de ya da butona dokun!"],
            _JEST["kel_intro"], 0.8)

    # 2) Kazanma (AI pes) + tekrar-uyari replikleri — ARTIK harfsiz -> harf-basi
    # genisletme yok, dogrudan on-uretilir (Mert sesiyle cache'te olsun).
    words = sorted({w for ws in ge._ai_pool.values() for w in ws})
    add("retry", [_TXT["kel_retry_invalid"][0], _TXT["kel_retry_letter"][0],
                  _TXT["kel_retry_used"][0]], _JEST["kel_retry"], 0.65)
    add("ai_lose", list(_TXT["kel_ai_lose"]), _JEST["kel_ai_lose"], 0.85)

    # 3) Kelime havuzu — AI kelimesi 3 baglamda cikabilir (imza cogunu birlestirir)
    caps = [_cap(w) for w in words]
    add("word_opener", caps, _JEST["kel_intro"], 0.8)
    add("word_normal", caps, _JEST["kel_ai_word"], 0.85)
    add("word_streak", caps, _JEST["kel_ai_streak"], 0.9)

    # 4) Quiz sorulari + SADELESTIRILMIS geri bildirim (cevap TEK, paylasilan cumle)
    prompts, reveals = _enumerate_quiz(ge)
    add("quiz_prompts", prompts,
        _JEST["kel_intro"] + _JEST["kel_user_ok"] + _JEST["kel_retry"], 0.85)
    # rstrip(' .'): runtime'daki beklenen = reveal.rstrip(" .") ile BIREBIR ayni
    # metin (aksi halde "doner.." cift nokta -> farkli cache anahtari -> miss).
    fb = [f"Cevap: {rv.rstrip(' .')}." for rv in reveals]  # dogru/yanlis'ta ORTAK cevap cumleleri
    fb += list(GameEngine._QUIZ_DOGRU_CHEER)              # 3 tezahurat cumlesi
    fb += list(GameEngine._QUIZ_YAKIN)                    # yakin-cevap onekleri
    fb += list(GameEngine._QUIZ_YANLIS)                   # notr yanlis onekleri
    fb += ["Süre doldu!"]                                  # zaman asimi
    add("quiz_feedback", fb, _JEST["kel_user_ok"] + _JEST["kel_retry"], 0.85)

    # 5) Quiz bitisi (yog=0.85, _quiz_end ile AYNI): "Bitti!" min_len altinda kaldigi
    # icin skor cumlesiyle BIRLESIR -> tum ulasilabilir skor varyantlari
    # (d <= t <= soru sayisi) birlesik haliyle on-uretilir; kapanis replikleri ayri.
    # AYRICA son sorunun geri bildirim oneki (tezahurat/onek + "Cevap: X.") _quiz_end
    # payload'ina EKLENIR ve OYUN-SONU jest havuzuyla + yog=0.85'te seslendirilir;
    # bu yuzden fb (feedback cumleleri) burada da uretilmeli — aksi halde son sorunun
    # onek/cevap parcasi (orta oyun jest havuzunda uretildigi icin) edge'e duser.
    n_q = GameEngine.QUIZ_QUESTION_COUNT
    bitis = [f"Bitti! {d}/{t} doğru." for t in range(1, n_q + 1) for d in range(0, t + 1)]
    bitis += ["Harikasın!", "Güzel oynadın!", "Önemli değil, yine beklerim!"]
    bitis += fb   # tezahurat + "Cevap: X." + yakin/yanlis onekleri + "Süre doldu!"
    add("quiz_end", bitis, _JEST["kel_user_ok"] + _JEST["kel_intro"] + ["huzur"], 0.85)

    return U


def unit_key_map(unit):
    """{(chunk, imza, yog): (chunk, temsili_jest, yog)} — TUM pool jest'leri enumere
    edilir, imza benzer olanlari tek anahtara indirir (= gercek runtime maliyeti);
    her anahtar icin ilk (temsili) jest saklanir, --run onunla DUYGULU ses uretir."""
    m = {}
    for text in unit["texts"]:
        for chunk in _split_sentences_tr(text):
            for j in unit["jests"]:
                key = (chunk, emotion_signature(j, unit["yog"]), unit["yog"])
                if key not in m:
                    m[key] = (chunk, j, unit["yog"])
    return m


def summarize(units):
    """(pre_gen_cat, self_heal_cat) -> her biri {name: [parca_sayisi, karakter]}."""
    pre, heal = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    seen = set()
    for u in units:
        bucket = heal if u["self_heal"] else pre
        for key in unit_key_map(u):
            if key in seen:            # ayni anahtar iki baglamda -> tek say
                continue
            seen.add(key)
            bucket[u["name"]][0] += 1
            bucket[u["name"]][1] += len(key[0])
    return pre, heal


def _print_cat(title, cat, cpc):
    n_chunks = sum(v[0] for v in cat.values())
    n_chars = sum(v[1] for v in cat.values())
    print(f"--- {title} ---")
    for name in sorted(cat, key=lambda k: -cat[k][1]):
        c, ch = cat[name]
        print(f"  {name:16} {c:6} parca  {ch:8} karakter")
    print(f"  {'TOPLAM':16} {n_chunks:6} parca  {n_chars:8} karakter  "
          f"=> {n_chars * cpc:,.0f} kredi\n")
    return n_chunks, n_chars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="Gercekten sentezle (API + kredi)")
    ap.add_argument("--yes", action="store_true", help="--run icin onay")
    ap.add_argument("--include-selfheal", action="store_true",
                    help="self_heal birimleri (harf sablonlari) de uret")
    args = ap.parse_args()

    ge = GameEngine(bridge=None)
    units = build_units(ge)
    model = "eleven_flash_v2_5"
    cpc = 0.5 if ("flash" in model or "turbo" in model) else 1.0

    print(f"\n=== ElevenLabs on-uretim ONIZLEME (imza-kanonik, model={model}, "
          f"{cpc} kredi/karakter) ===\n")
    pre, heal = summarize(units)
    _, pre_chars = _print_cat("ON-URETILECEK (pre-gen)", pre, cpc)
    _, heal_chars = _print_cat("SELF-HEAL kuyrugu (sergide ilk kullanimda canli)", heal, cpc)
    print(f"ONDEN uretim: {pre_chars * cpc:,.0f} kredi   |   "
          f"self-heal ust siniri: {heal_chars * cpc:,.0f} kredi (yalnizca gercekten "
          f"karsilasilan parcalar, 32k tavanla sinirli)\n")

    if not args.run:
        print("Dry-run bitti (hicbir sey uretilmedi). Gercek uretim: --run --yes\n")
        return
    if not args.yes:
        print("GUVENLIK: gercek uretim icin --yes ekle. Iptal.\n")
        return

    # ——— GERCEK URETIM ———
    import os
    from tts.cache import WavCache
    from tts.engine_elevenlabs import ElevenLabsEngine
    cfg = load_config()
    voice = cfg.get("tts_voice", DEFAULT_TTS_VOICE)
    api_key = cfg.get("tts_elevenlabs_api_key") or os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print("HATA: ELEVENLABS_API_KEY yok (env ya da config). Iptal.\n")
        return
    cache = WavCache(Path(__file__).resolve().parent / "cache",
                     max_files=int(cfg.get("tts_cache_max", 5000)), enabled=True)
    # Batch BILINCLI tek-seferlik harcama (dry-run + --yes ile onaylandi) -> runtime
    # tavanina (cap) TAKILMASIN: cap=0 (guard kapali) ama harcama ayni usage dosyasina
    # yazilir; boylece runtime motoru (cap'li) ayni ayda bu harcamayi gorur.
    engine = ElevenLabsEngine(
        voice=voice, api_key=api_key,
        model=cfg.get("tts_elevenlabs_model", model),
        language=cfg.get("tts_elevenlabs_language", "tr"),
        monthly_cap=0,
        usage_path=Path(__file__).resolve().parent / "elevenlabs_usage.json")

    key_reps = {}
    for u in units:
        if u["self_heal"] and not args.include_selfheal:
            continue
        for key, rep in unit_key_map(u).items():
            key_reps.setdefault(key, rep)
    print(f"Uretiliyor: {len(key_reps)} benzersiz parca (voice={voice})...\n")
    done = hit = fail = 0
    for i, (key, rep) in enumerate(sorted(key_reps.items()), 1):
        chunk, sig, yog = key
        _, jest, _ = rep
        k = cache.make_key(chunk, sig, yog, voice)
        if cache.get(k) is not None:
            hit += 1
            continue
        # Temsili jest ile DUYGULU ses uret; anahtar imzayla kurulur (runtime ile ayni).
        audio = engine.synthesize(chunk, jest, yog)
        if audio:
            cache.put(k, audio)
            done += 1
        else:
            fail += 1
        if i % 50 == 0:
            print(f"  {i}/{len(key_reps)}  yeni={done} cache={hit} bos/atlanan={fail} "
                  f"harcanan~{engine.guard.spent:,.0f} kredi")
    print(f"\nBITTI. yeni={done} cache_isabet={hit} bos/atlanan={fail}  "
          f"toplam_harcanan~{engine.guard.spent:,.0f} kredi\n")


if __name__ == "__main__":
    main()
