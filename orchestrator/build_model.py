"""Sistem promptunu + Llama 3 chat sablonunu iceren ozel Ollama modeli ('aican') olusturur.

Neden gerekli:
HuggingFace'ten gelen GGUF modelleri (orn. Turkish-Llama-8b-v0.1-GGUF) Ollama'da
COK temel bir sablonla yuklenir: sadece '{{ .Prompt }}' — yani sistem mesaji ve
konusma gecmisi MODELE ULASMAZ. Bu yuzden model AI Body persona'sini hic gormez,
generic chatbot gibi davranir.

Bu script onu duzeltir:
1. ai/system_prompt.txt'yi okur.
2. ai/Modelfile dosyasini uretir — Llama 3 chat sablonu + PARAMETER + SYSTEM bloklari.
3. `ollama create aican -f ai/Modelfile` calistirir.

Sonuc: 'aican' adli ozel model. Sistem promptu gomulu, Llama 3 chat formati dogru.
Orkestrator bu modeli kullanirken sistem promptu tekrar tekrar gondermesi gerekmez
(config.json'da `use_baked_prompt: true` yapilir).

Kullanim:
    cd orchestrator
    python build_model.py

Sistem promptunu degistirdikten sonra bu script'i tekrar calistir.

Base model degistirmek istersen asagidaki BASE_MODEL sabitini guncelle. Llama 3
ailesi disinda bir model kullanacaksan TEMPLATE'i de uygun formata cevirmen gerekir
(Qwen, Gemma, Mistral icin farkli sablonlar var).
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
BASE_MODEL = "hf.co/QuantFactory/Turkish-Llama-8b-v0.1-GGUF:Q3_K_M"

# Llama 3 chat sablonu — system + user + assistant rollerini dogru token'larla sarar.
# Ollama Go template syntax'i: .Messages (chat API) ve .Prompt (generate API) destekli.
LLAMA3_TEMPLATE = '''TEMPLATE """{{- if .Messages -}}
{{- if .System }}<|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|>{{ end }}
{{- range .Messages }}<|start_header_id|>{{ .Role }}<|end_header_id|>

{{ .Content }}<|eot_id|>
{{- end }}<|start_header_id|>assistant<|end_header_id|>


{{- else -}}
{{- if .System }}<|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>

{{ .Prompt }}<|eot_id|>{{ end }}<|start_header_id|>assistant<|end_header_id|>

{{ end -}}"""'''

PARAMETERS = """
PARAMETER stop "<|start_header_id|>"
PARAMETER stop "<|end_header_id|>"
PARAMETER stop "<|eot_id|>"
PARAMETER stop "<|begin_of_text|>"
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER num_predict 120
PARAMETER repeat_penalty 1.15
PARAMETER num_ctx 6144
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
        f"{LLAMA3_TEMPLATE}\n\n"
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
    print(f"[OK] '{MODEL_NAME}' modeli hazir.")
    print("Sıradaki: orchestrator/config.json içindeki 'ollama_model' değerini")
    print(f"  '\"ollama_model\": \"{MODEL_NAME}\"'")
    print("yap ve 'use_baked_prompt' anahtarını true yap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
