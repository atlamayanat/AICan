"""Sergi senaryosu icin regresyon + kalite testi.

ai/test_examples.json'daki 50 kuratorlu ornegi Ollama'ya sirayla gonderir;
her ornek icin JEST dogrulugunu ve YANIT METNI kalitesini (kelime<=12, Turkce,
papagan/dongu yok) olcer. Ek olarak cesitlilik testi yapar: ayni mesaj 3 kez
sorulup 3 farkli yanit bekleniyor. Sonuc JSON rapor olarak da yazilir ki
prompt/sampling/model degisiklikleri (A/B) diff'lenebilsin.

Kullanim:
    python orchestrator/test_runner.py                 # tam kosu (50 ornek + cesitlilik)
    python orchestrator/test_runner.py --limit 10      # hizli duman testi
    python orchestrator/test_runner.py --model gemma3:4b --out logs/ab_gemma.json
    python orchestrator/test_runner.py --no-diversity  # yalniz 50 ornek

Esik: jest dogrulugu >= --threshold (varsayilan 0.84 -> 42/50) ise exit 0.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

# Windows konsolu (cp1254) model yanitindaki emojileri basamiyor — UTF-8'e zorla
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# orchestrator klasorunu sys.path'e ekle ki llm_bridge import edilebilsin
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from llm_bridge import (  # noqa: E402
    LLMBridge,
    guard_no_loop,
    guard_no_parrot,
    guard_turkish,
    guard_word_count,
)

CONFIG_PATH = BASE_DIR / "config.json"
EXAMPLES_PATH = (BASE_DIR / ".." / "ai" / "test_examples.json").resolve()

# Cesitlilik testi: ayni mesaj 3 kez -> 3 farkli yanit beklenir
DIVERSITY_MESSAGES = ["merhaba", "kötüyüm", "çok mutluyum bugün"]
DIVERSITY_REPEATS = 3


def load_examples(limit: int | None) -> list[dict]:
    data = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))
    examples = data["ornekler"]
    if limit:
        examples = examples[:limit]
    return examples


def run_examples(bridge: LLMBridge, examples: list[dict]) -> list[dict]:
    results = []
    for i, ex in enumerate(examples, 1):
        msg = ex["metin"]
        accepted = {ex["beklenen_jest"], *ex.get("kabul_edilebilir_alternatifler", [])}
        bridge.clear_history()  # her ornek bagimsiz
        result = bridge.request(msg)

        if not result or "error" in result:
            err = (result or {}).get("error", "no_response")
            print(f"[{i:2}] HATA  {msg!r} -> {err}")
            results.append({"metin": msg, "hata": err})
            continue

        jest, yanit = result["jest_id"], result["yanit"]
        meta = result.get("meta", {})
        row = {
            "metin": msg,
            "beklenen": sorted(accepted),
            "jest": jest,
            "yanit": yanit,
            "jest_ok": jest in accepted,
            "kelime_ok": guard_word_count(yanit),
            "turkce_ok": guard_turkish(yanit),
            "parrot_ok": guard_no_parrot(msg, yanit),
            "dongu_ok": guard_no_loop(yanit),
            "wall_s": round(meta.get("wall_s", 0.0), 2),
            "prompt_eval_ms": round(meta.get("prompt_eval_ms", 0.0)),
            "tok_per_s": round(meta.get("tok_per_s", 0.0), 1),
        }
        flags = [k for k in ("kelime_ok", "turkce_ok", "parrot_ok", "dongu_ok") if not row[k]]
        marker = "PASS" if row["jest_ok"] else "FAIL"
        flag_s = f"  [metin: {','.join(f.replace('_ok', '') for f in flags)}]" if flags else ""
        print(f"[{i:2}] {marker}  {msg!r:44} -> {jest:<18} {yanit!r}{flag_s}")
        results.append(row)
    return results


def run_diversity(bridge: LLMBridge) -> list[dict]:
    out = []
    for msg in DIVERSITY_MESSAGES:
        yanitlar = []
        for _ in range(DIVERSITY_REPEATS):
            bridge.clear_history()
            result = bridge.request(msg)
            if result and "error" not in result:
                yanitlar.append(result["yanit"])
        distinct = len(set(yanitlar))
        out.append({"metin": msg, "yanitlar": yanitlar, "farkli": distinct})
        print(f"[cesitlilik] {msg!r}: {distinct}/{len(yanitlar)} farkli yanit")
    return out


def summarize(results: list[dict], diversity: list[dict], bridge: LLMBridge) -> dict:
    ok_rows = [r for r in results if "hata" not in r]
    n = len(results)

    def ratio(key: str) -> float:
        return round(sum(1 for r in ok_rows if r[key]) / n, 3) if n else 0.0

    def timing(key: str) -> dict:
        vals = [r[key] for r in ok_rows if r.get(key)]
        if not vals:
            return {}
        return {
            "ort": round(statistics.mean(vals), 2),
            "medyan": round(statistics.median(vals), 2),
            "maks": round(max(vals), 2),
        }

    return {
        "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": bridge.model,
        "sampling": {
            "temperature": bridge.temperature,
            "top_p": bridge.top_p,
            "top_k": getattr(bridge, "top_k", None),
            "min_p": getattr(bridge, "min_p", None),
            "repeat_penalty": bridge.repeat_penalty,
            "frequency_penalty": bridge.frequency_penalty,
            "presence_penalty": bridge.presence_penalty,
            "num_ctx": bridge.num_ctx,
            "num_predict": bridge.num_predict,
        },
        "ornek_sayisi": n,
        "hata_sayisi": n - len(ok_rows),
        "jest_dogruluk": ratio("jest_ok"),
        "metin_metrikleri": {
            "kelime_max12": ratio("kelime_ok"),
            "turkce": ratio("turkce_ok"),
            "papagan_yok": ratio("parrot_ok"),
            "dongu_yok": ratio("dongu_ok"),
        },
        "sure": {
            "wall_s": timing("wall_s"),
            "prompt_eval_ms": timing("prompt_eval_ms"),
            "tok_per_s": timing("tok_per_s"),
        },
        "cesitlilik": [
            {"metin": d["metin"], "farkli": d["farkli"], "toplam": len(d["yanitlar"])}
            for d in diversity
        ],
        "basarisizlar": [
            {"metin": r["metin"], "bekledi": r["beklenen"], "aldi": r["jest"]}
            for r in ok_rows if not r["jest_ok"]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="ilk N ornekle sinirla")
    ap.add_argument("--config", default=None, help="farkli config dosyasi (A/B profilleri)")
    ap.add_argument("--model", default=None, help="config yerine bu modeli kullan (A/B)")
    ap.add_argument("--out", default=None, help="JSON rapor yolu (varsayilan logs/test_report_*.json)")
    ap.add_argument("--threshold", type=float, default=0.84, help="jest dogruluk esigi (0-1)")
    ap.add_argument("--no-diversity", action="store_true", help="cesitlilik testini atla")
    args = ap.parse_args()

    config_path = Path(args.config) if args.config else CONFIG_PATH
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["history_max_turns"] = 0  # her mesaj bagimsiz degerlendirilsin
    if args.model:
        config["ollama_model"] = args.model
    bridge = LLMBridge(config, BASE_DIR)

    if not bridge.is_alive():
        print("[X] Ollama erişilemiyor. Önce Ollama'yı başlat.")
        return 2

    examples = load_examples(args.limit)
    print(f"Model: {bridge.model}")
    print(f"Ornek sayisi: {len(examples)}")
    print("-" * 78)

    t0 = time.monotonic()
    results = run_examples(bridge, examples)
    diversity = [] if args.no_diversity else run_diversity(bridge)
    toplam_sure = time.monotonic() - t0

    summary = summarize(results, diversity, bridge)
    summary["toplam_kosu_s"] = round(toplam_sure, 1)
    summary["detay"] = results

    # JSON rapor
    if args.out:
        out_path = Path(args.out)
    else:
        safe_model = re.sub(r"[^\w.-]+", "_", bridge.model)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = (BASE_DIR / ".." / "logs" / f"test_report_{safe_model}_{stamp}.json").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("-" * 78)
    jest_pass = int(summary["jest_dogruluk"] * summary["ornek_sayisi"])
    print(f"Jest dogrulugu : {jest_pass}/{summary['ornek_sayisi']} ({summary['jest_dogruluk']:.0%})")
    mm = summary["metin_metrikleri"]
    print(f"Metin kalitesi : kelime<=12 {mm['kelime_max12']:.0%} | turkce {mm['turkce']:.0%}"
          f" | papagan-yok {mm['papagan_yok']:.0%} | dongu-yok {mm['dongu_yok']:.0%}")
    if summary["sure"]["wall_s"]:
        s = summary["sure"]
        print(f"Sure           : wall {s['wall_s']['ort']}s ort / {s['wall_s']['maks']}s maks"
              f" | prompt_eval {s['prompt_eval_ms'].get('ort', 0)}ms | {s['tok_per_s'].get('ort', 0)} tok/s")
    for d in summary["cesitlilik"]:
        print(f"Cesitlilik     : {d['metin']!r} -> {d['farkli']}/{d['toplam']} farkli")
    print(f"Rapor          : {out_path}")

    return 0 if summary["jest_dogruluk"] >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
