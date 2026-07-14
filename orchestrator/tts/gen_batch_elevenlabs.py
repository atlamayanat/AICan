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
    fb = [f"Cevap: {rv}." for rv in reveals]              # dogru/yanlis'ta ORTAK cevap cumleleri
    fb += list(GameEngine._QUIZ_DOGRU_CHEER)              # 3 tezahurat cumlesi
    fb += ["Yaklaştın!", "Süre doldu!"]                    # 2 uyari cumlesi
    add("quiz_feedback", fb, _JEST["kel_user_ok"] + _JEST["kel_retry"], 0.85)

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
