"""AI Body — yeni web arayuzu baslatici.

Bu script:
  1. Flask sunucusunu kaldirir (orchestrator/web_server.py)
  2. Sergi ekranini ve Kontrol panelini AYNI tarayicida iki sekmede acar
  3. BroadcastChannel ile iki ekran haberlesir

Calistirma:  python run_web.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "orchestrator"))

from web_server import main  # noqa: E402

if __name__ == "__main__":
    main()
