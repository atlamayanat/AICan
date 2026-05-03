"""Sistem promptunu içeren özel bir Ollama modeli ('aican') oluşturur.

Ne yapar:
1. ai/system_prompt.txt'yi okur.
2. ai/Modelfile dosyasını üretir (PARAMETER + SYSTEM blokları gömülü).
3. `ollama create aican -f ai/Modelfile` komutunu çalıştırır.

Sonuç: Ollama'da 'aican' adında özel bir model oluşur. Bu model qwen2.5:7b-instruct'ı
base alır ama sistem promptu ve generation parametrelerini kendi içinde tutar.
Orkestratör bu modeli kullanırken sadece kullanıcı mesajını gönderir; sistem promptu
ağ üzerinden tekrar tekrar gönderilmez.

Kullanım:
    cd orchestrator
    python build_model.py

Sistem promptunu değiştirdikten sonra bu script'i tekrar çalıştır.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROMPT_PATH = BASE / "ai" / "system_prompt.txt"
MODELFILE_PATH = BASE / "ai" / "Modelfile"
MODEL_NAME = "aican"
BASE_MODEL = "qwen2.5:7b-instruct"

PARAMETERS = """
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER num_predict 120
PARAMETER repeat_penalty 1.15
""".strip()


def main() -> int:
    if not PROMPT_PATH.exists():
        print(f"HATA: {PROMPT_PATH} bulunamadı.", file=sys.stderr)
        return 1

    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if '"""' in prompt:
        print("HATA: system_prompt.txt içinde üç tırnak (\"\"\") var; "
              "Modelfile'da çakışır.", file=sys.stderr)
        return 1

    modelfile = (
        f"FROM {BASE_MODEL}\n\n"
        f"{PARAMETERS}\n\n"
        f'SYSTEM """\n{prompt}\n"""\n'
    )
    MODELFILE_PATH.write_text(modelfile, encoding="utf-8")
    print(f"[1/2] Modelfile yazıldı: {MODELFILE_PATH}")

    if shutil.which("ollama") is None:
        print("UYARI: 'ollama' komutu PATH'te yok. Modelfile yazıldı ama model "
              "oluşturulamadı.\nManuel komut:")
        print(f"  ollama create {MODEL_NAME} -f \"{MODELFILE_PATH}\"")
        return 0

    print(f"[2/2] 'ollama create {MODEL_NAME}' çalıştırılıyor...")
    try:
        result = subprocess.run(
            ["ollama", "create", MODEL_NAME, "-f", str(MODELFILE_PATH)],
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        print("HATA: ollama komutu çalıştırılamadı.", file=sys.stderr)
        return 2

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"HATA: ollama create başarısız (kod {result.returncode}).",
              file=sys.stderr)
        return result.returncode

    print()
    print(f"✓ '{MODEL_NAME}' modeli hazır.")
    print("Sıradaki: orchestrator/config.json içindeki 'ollama_model' değerini")
    print(f"  '\"ollama_model\": \"{MODEL_NAME}\"'")
    print("yap ve 'use_baked_prompt' anahtarını true yap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
