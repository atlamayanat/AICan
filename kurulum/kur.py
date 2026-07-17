#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AICAN sergi kurulumu — temiz bir Windows PC'yi oyunu çalıştıracak hâle getirir.

KUR.bat bu betiği çağırır (Python'u o kurar/bulur). Betik İDEMPOTENTTİR:
yarıda kesilirse ya da bir adım hata verirse tekrar çalıştırmak güvenlidir.

Adımlar:
  1. Python sürüm kontrolü
  2. Microsoft VC++ Redistributable (Whisper/Piper DLL'leri için ŞART)
  3. pip bağımlılıkları (orchestrator/requirements.txt)
  4. Profil seçimi (sergi / laptop → config.json)
  5. Ollama kurulumu + sunucu + model indirme
  6. Whisper 'small' modelini ön-indirme (~460 MB)
  7. ElevenLabs API anahtarı (opsiyonel — boşsa edge/piper yedeği çalışır)
  8. Masaüstü kısayolu + opsiyonel otomatik başlatma
  9. Sağlık kontrolü (saglik_kontrol.py)

Parametreler (hepsi opsiyonel; verilmezse soru sorulur):
  --profil sergi|laptop   --anahtar ELEVENLABS_KEY   --otomatik e|h   --sessiz
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BURASI = Path(__file__).resolve().parent
ROOT = BURASI.parent
ORCH = ROOT / "orchestrator"
TOPLAM_ADIM = 9

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def baslik(no: int, ad: str) -> None:
    print(f"\n=== [{no}/{TOPLAM_ADIM}] {ad} " + "=" * max(1, 46 - len(ad)))


def sor(mesaj: str, varsayilan: str, sessiz: bool) -> str:
    if sessiz:
        return varsayilan
    yanit = input(f"{mesaj} [{varsayilan}]: ").strip()
    return yanit or varsayilan


def calistir(cmd: list, hata_olumcul: bool = True) -> int:
    """Komutu konsola akıtarak çalıştır; dönüş kodu döner."""
    print("  $ " + " ".join(str(c) for c in cmd))
    kod = subprocess.run([str(c) for c in cmd]).returncode
    if kod != 0 and hata_olumcul:
        raise SystemExit(f"HATA: komut {kod} koduyla bitti: {cmd[0]}")
    return kod


# ——— Adım 1: Python ————————————————————————————————————————
def adim_python() -> None:
    baslik(1, "Python sürümü")
    v = sys.version_info
    print(f"  Python {v.major}.{v.minor}.{v.micro} ({sys.executable})")
    if (v.major, v.minor) < (3, 10):
        raise SystemExit("HATA: Python 3.10+ gerekli. KUR.bat'ın kurduğu sürümü kullanın.")
    print("  TAMAM.")


# ——— Adım 2: VC++ Redistributable ——————————————————————————
def _msvcp_yuklu() -> bool:
    """faster-whisper (ctranslate2) ve piper (onnxruntime) MSVCP140 ister;
    temiz Windows'ta ve python.org kurulumunda BU DLL YOKTUR."""
    import ctypes
    try:
        ctypes.WinDLL("msvcp140")
        ctypes.WinDLL("vcruntime140_1")
        return True
    except OSError:
        return False


def adim_vcredist() -> None:
    baslik(2, "Microsoft VC++ Redistributable (Whisper/Piper için şart)")
    if _msvcp_yuklu():
        print("  Zaten kurulu.")
        return
    print("  Kuruluyor (winget)...")
    calistir(["winget", "install", "-e", "--id", "Microsoft.VCRedist.2015+.x64",
              "--accept-source-agreements", "--accept-package-agreements"],
             hata_olumcul=False)   # 'zaten kurulu' çıkış kodları hata sayılmasın
    if _msvcp_yuklu():
        print("  TAMAM.")
    else:
        print("  UYARI: msvcp140.dll hâlâ yüklenemiyor — sesli giriş ve Piper sesi")
        print("  'DLL load failed' verir. Elle kurun: https://aka.ms/vs/17/release/vc_redist.x64.exe")


# ——— Adım 3: pip bağımlılıkları ————————————————————————————
def adim_pip() -> None:
    baslik(3, "Python bağımlılıkları (pip)")
    gereksinim = ORCH / "requirements.txt"
    if not gereksinim.is_file():
        raise SystemExit(f"HATA: {gereksinim} yok — proje klasörü eksik kopyalanmış.")
    calistir([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], hata_olumcul=False)
    calistir([sys.executable, "-m", "pip", "install", "-r", gereksinim])
    print("  TAMAM.")


# ——— Adım 4: Profil ————————————————————————————————————————
def adim_profil(profil: str) -> dict:
    baslik(4, f"Yapılandırma profili: {profil}")
    hedef = ORCH / "config.json"
    if profil == "sergi":
        kaynak = ORCH / "config.sergi.json"
        if not kaynak.is_file():
            raise SystemExit(f"HATA: {kaynak} yok.")
        if hedef.is_file():
            yedek = ORCH / f"config.yedek-{datetime.now():%Y%m%d-%H%M%S}.json"
            shutil.copy2(hedef, yedek)
            print(f"  Mevcut config.json yedeklendi: {yedek.name}")
        shutil.copy2(kaynak, hedef)
        print("  config.sergi.json → config.json kopyalandı.")
    else:
        print("  Laptop profili: mevcut config.json olduğu gibi kullanılıyor.")
    cfg = json.loads(hedef.read_text(encoding="utf-8-sig"))
    print(f"  Model: {cfg.get('ollama_model')}  ·  TTS: {cfg.get('tts_engine')}")
    return cfg


# ——— Adım 5: Ollama ————————————————————————————————————————
def ollama_yolu() -> str | None:
    adaylar = ["ollama",
               str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"),
               r"C:\Program Files\Ollama\ollama.exe"]
    for aday in adaylar:
        try:
            r = subprocess.run([aday, "--version"], capture_output=True, timeout=15)
            if r.returncode == 0:
                return aday
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
    return None


def ollama_sunucu_hazir() -> bool:
    import requests
    try:
        return requests.get("http://localhost:11434", timeout=2).ok
    except Exception:
        return False


def adim_ollama(cfg: dict) -> None:
    baslik(5, "Ollama + dil modeli")
    yol = ollama_yolu()
    if yol is None:
        print("  Ollama bulunamadı — winget ile kuruluyor...")
        calistir(["winget", "install", "-e", "--id", "Ollama.Ollama",
                  "--accept-source-agreements", "--accept-package-agreements"])
        yol = ollama_yolu()
        if yol is None:
            raise SystemExit("HATA: Ollama kurulumu doğrulanamadı. Elle kurun: https://ollama.com/download")
    print(f"  Ollama: {yol}")

    if not ollama_sunucu_hazir():
        print("  Ollama sunucusu başlatılıyor...")
        subprocess.Popen([yol, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(20):
            time.sleep(1)
            if ollama_sunucu_hazir():
                break
        else:
            raise SystemExit("HATA: Ollama sunucusu 20 sn içinde ayağa kalkmadı.")
    print("  Sunucu çalışıyor.")

    model = cfg.get("ollama_model", "")
    if not model:
        raise SystemExit("HATA: config.json içinde ollama_model boş.")
    print(f"  Model indiriliyor (varsa atlanır): {model}")
    calistir([yol, "pull", model])
    print("  TAMAM.")


# ——— Adım 6: Whisper ————————————————————————————————————————
def adim_whisper() -> None:
    baslik(6, "Whisper 'small' ses-tanıma modeli (~460 MB, ilk seferde iner)")
    try:
        from faster_whisper import WhisperModel
        print("  İndiriliyor/yükleniyor — birkaç dakika sürebilir...")
        WhisperModel("small", device="cpu", compute_type="int8")
        print("  TAMAM — model yerel önbellekte, sergide internet gerekmez.")
    except Exception as e:  # noqa: BLE001 — kurulum sürsün, sağlık kontrolü yakalar
        print(f"  UYARI: Whisper ön-indirme başarısız: {e}")
        print("  (Sergiden önce internetli ortamda KUR.bat'ı tekrar çalıştırın.)")


# ——— Adım 7: ElevenLabs anahtarı ————————————————————————————
def adim_elevenlabs(anahtar: str | None, sessiz: bool) -> None:
    baslik(7, "ElevenLabs API anahtarı (opsiyonel)")
    mevcut = os.environ.get("ELEVENLABS_API_KEY", "")
    if anahtar is None and not sessiz:
        print("  Boş bırakılırsa: ses, ücretsiz edge-tts + Piper yedeğiyle çalışır.")
        if mevcut:
            print("  (Bu makinede zaten bir anahtar tanımlı — boş geçersen o kalır.)")
        anahtar = input("  ElevenLabs anahtarı (boş geçilebilir): ").strip()
    if anahtar:
        calistir(["setx", "ELEVENLABS_API_KEY", anahtar], hata_olumcul=False)
        os.environ["ELEVENLABS_API_KEY"] = anahtar
        print("  Anahtar kalıcı ortam değişkenine yazıldı (yeni pencerelerde geçerli).")
    elif mevcut:
        print("  Mevcut anahtar korundu.")
    else:
        print("  Anahtar yok — ElevenLabs devre dışı, edge/piper yedeği kullanılacak.")


# ——— Adım 8: Kısayollar ————————————————————————————————————
def _kisayol(ps_klasor_sabiti: str, ad: str, hedef: Path) -> bool:
    def tek_tirnak(s) -> str:
        # PowerShell tek tırnaklı dizgede kaçış: ' -> '' (yol apostrof içerebilir,
        # ör. "mehmet'in klasörü") — kaçışsız hâli PS ParserError verir.
        return str(s).replace("'", "''")

    ps = (
        "$w = New-Object -ComObject WScript.Shell; "
        f"$d = [Environment]::GetFolderPath('{ps_klasor_sabiti}'); "
        f"$s = $w.CreateShortcut((Join-Path $d '{tek_tirnak(ad)}.lnk')); "
        f"$s.TargetPath = '{tek_tirnak(hedef)}'; "
        f"$s.WorkingDirectory = '{tek_tirnak(hedef.parent)}'; "
        "$s.Save()"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode != 0:
        hata = (r.stderr or "").strip().splitlines()
        if hata:
            print(f"    PowerShell hatası: {hata[-1]}")
    return r.returncode == 0


def adim_kisayol(otomatik: str) -> None:
    baslik(8, "Kısayollar")
    baslat = ROOT / "BASLAT.bat"
    if _kisayol("Desktop", "AICAN Baslat", baslat):
        print("  Masaüstüne 'AICAN Baslat' kısayolu kondu.")
    else:
        print(f"  UYARI: masaüstü kısayolu oluşmadı — elle kullanın: {baslat}")
    if otomatik.lower().startswith("e"):
        if _kisayol("Startup", "AICAN Baslat", baslat):
            print("  Otomatik başlatma AÇIK: PC açılınca oyun kendiliğinden başlar.")
        else:
            print("  UYARI: otomatik başlatma kısayolu oluşmadı.")
    else:
        print("  Otomatik başlatma kapalı (istersen kur.py --otomatik e ile tekrar çalıştır).")


# ——— Adım 9: Sağlık kontrolü ————————————————————————————————
def adim_saglik() -> int:
    baslik(9, "Sağlık kontrolü")
    return subprocess.run([sys.executable, "-X", "utf8",
                           str(BURASI / "saglik_kontrol.py")]).returncode


def main() -> int:
    p = argparse.ArgumentParser(description="AICAN sergi kurulumu")
    p.add_argument("--profil", choices=("sergi", "laptop"))
    p.add_argument("--anahtar", help="ElevenLabs API anahtarı")
    p.add_argument("--otomatik", choices=("e", "h"), help="PC açılışında oyunu başlat")
    p.add_argument("--sessiz", action="store_true", help="soru sorma, varsayılanları kullan")
    a = p.parse_args()

    print("AICAN kurulumu başlıyor — proje klasörü:", ROOT)
    adim_python()
    adim_vcredist()
    adim_pip()
    profil = a.profil or sor("Profil? (sergi = sergi PC'si, laptop = geliştirme)",
                             "sergi", a.sessiz)
    cfg = adim_profil(profil)
    adim_ollama(cfg)
    adim_whisper()
    adim_elevenlabs(a.anahtar, a.sessiz)
    otomatik = a.otomatik or sor("PC açılınca oyun otomatik başlasın mı? (e/h)", "e", a.sessiz)
    adim_kisayol(otomatik)
    kod = adim_saglik()

    print("\n" + "=" * 52)
    if kod == 0:
        print("KURULUM TAMAM ✔  Oyunu başlatmak için: masaüstündeki")
        print("'AICAN Baslat' kısayolu ya da proje kökündeki BASLAT.bat")
    else:
        print("Kurulum bitti ama SAĞLIK KONTROLÜ hata verdi — yukarıya bakın.")
    return kod


if __name__ == "__main__":
    sys.exit(main())
