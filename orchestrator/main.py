"""AI Body — Tkinter arayüzü + gömülü 16×16 yazılım simülatörü.

Akış:
  Kullanıcı metin yazar → arka plan thread → Ollama → jest engine (yazılım LED matrisi)
  Ana thread her 50ms'de queue'yu yoklar; gesture engine her ~33ms'de bir frame render eder.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

from gesture_engine import GestureEngine
from llm_bridge import LLMBridge
from matrix_sim import MatrixView
from session_logger import SessionLogger
from stats import HAS_PSUTIL, fmt_mb, ram_usage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ai_body")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

FRAME_INTERVAL_MS = 33  # ~30 fps yeterli; idle pulse ve oscilasyonlar düzgün görünür


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_gestures(config: dict) -> dict:
    path = (BASE_DIR / config["gestures_path"]).resolve()
    return json.loads(path.read_text(encoding="utf-8"))


class App:
    def __init__(self, root: tk.Tk, config: dict):
        self.root = root
        self.config = config
        self.llm = LLMBridge(config, BASE_DIR)

        gestures_data = load_gestures(config)
        self.engine = GestureEngine(gestures_data)

        # Oturum logger - her oturumun .txt dosyasina yazar
        log_path = (BASE_DIR / config.get("session_log_path", "../logs/session.log")).resolve()
        self.logger = SessionLogger(log_path, config["ollama_url"], config["ollama_model"])
        self.logger.start()
        log.info("Oturum logu: %s", log_path)

        self.event_q: queue.Queue = queue.Queue()
        self._busy = False

        self._build_ui()
        # Pencere kapanisi: oturum ozetini yaz, sonra cikis
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda _e: self._on_close())
        self.root.after(50, self._poll_events)
        self.root.after(FRAME_INTERVAL_MS, self._frame_tick)
        self.root.after(150, self._initial_check)
        self.root.after(200, self._ram_tick)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        self.root.title("AI Body — Sergi Prototipi")
        self.root.geometry("1500x950")
        self.root.minsize(1280, 820)
        self.root.configure(bg="#1a1a22")

        # Yeniden kullanilan stiller
        self.FONT_HEADER = ("Segoe UI", 22, "bold")
        self.FONT_PANEL_TITLE = ("Segoe UI", 12, "bold")
        self.FONT_LABEL = ("Segoe UI", 13)
        self.FONT_LABEL_BOLD = ("Segoe UI", 13, "bold")
        self.FONT_YANIT = ("Segoe UI", 14, "italic")
        self.FONT_MONO = ("Consolas", 12)
        self.FONT_INPUT = ("Segoe UI", 14)
        self.COLOR_BG = "#1a1a22"
        self.COLOR_PANEL = "#22222e"
        self.COLOR_TEXT = "#e6e6f0"
        self.COLOR_ACCENT = "#7eb6ff"
        self.COLOR_MONO = "#9ad0ff"

        header = tk.Label(
            self.root,
            text="AI Body — Sergi Prototipi",
            font=self.FONT_HEADER,
            pady=14,
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT,
        )
        header.pack(fill=tk.X)

        body = tk.Frame(self.root, bg=self.COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        # ---- SOL: matris simülatörü ----
        left_col = tk.Frame(body, bg=self.COLOR_BG)
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        matris_label = tk.Label(
            left_col,
            text="32×32 Matris (yazılım simülasyonu)",
            font=("Segoe UI", 11),
            bg=self.COLOR_BG,
            fg="#999",
        )
        matris_label.pack(anchor="w", pady=(0, 6))
        self.matrix = MatrixView(left_col, cell_size=14, padding=1)
        self.matrix.pack()

        # ---- SAĞ: kontroller ----
        right_col = tk.Frame(body, bg=self.COLOR_BG)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Durum paneli
        status = tk.LabelFrame(
            right_col,
            text=" Durum ",
            padx=18,
            pady=14,
            font=self.FONT_PANEL_TITLE,
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT,
            bd=2,
        )
        status.pack(fill=tk.X)

        self.var_ollama = tk.StringVar(value="Ollama: ?")
        self.var_active = tk.StringVar(value="Aktif jest: idle")
        self.var_yanit = tk.StringVar(value="AI yanıtı: —")

        for var in (self.var_ollama, self.var_active):
            tk.Label(
                status,
                textvariable=var,
                anchor="w",
                font=self.FONT_LABEL,
                bg=self.COLOR_PANEL,
                fg=self.COLOR_TEXT,
            ).pack(fill=tk.X, pady=4)
        tk.Label(
            status,
            textvariable=self.var_yanit,
            anchor="w",
            wraplength=820,
            justify="left",
            font=self.FONT_YANIT,
            bg=self.COLOR_PANEL,
            fg=self.COLOR_ACCENT,
        ).pack(fill=tk.X, pady=(12, 2))

        # Son komut paneli
        last = tk.LabelFrame(
            right_col,
            text=" Son komut ",
            padx=18,
            pady=14,
            font=self.FONT_PANEL_TITLE,
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT,
            bd=2,
        )
        last.pack(fill=tk.X, pady=(14, 0))

        self.var_last_id = tk.StringVar(value="jest_id: —")
        self.var_last_yog = tk.StringVar(value="yoğunluk: —")
        self.var_last_sure = tk.StringVar(value="süre: —")
        for var in (self.var_last_id, self.var_last_yog, self.var_last_sure):
            tk.Label(
                last,
                textvariable=var,
                anchor="w",
                font=self.FONT_LABEL,
                bg=self.COLOR_PANEL,
                fg=self.COLOR_TEXT,
            ).pack(fill=tk.X, pady=4)

        # İstatistik paneli
        stats_frame = tk.LabelFrame(
            right_col,
            text=" İstatistik ",
            padx=18,
            pady=14,
            font=self.FONT_PANEL_TITLE,
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT,
            bd=2,
        )
        stats_frame.pack(fill=tk.X, pady=(14, 0))

        self.var_stat_think = tk.StringVar(value="Düşünme süresi: —")
        self.var_stat_tokens = tk.StringVar(value="Token: —")
        self.var_stat_speed = tk.StringVar(value="Üretim hızı: —")
        self.var_stat_ram = tk.StringVar(
            value="RAM: psutil yok (pip install psutil)" if not HAS_PSUTIL else "RAM: hesaplanıyor…"
        )
        for var in (self.var_stat_think, self.var_stat_tokens, self.var_stat_speed, self.var_stat_ram):
            tk.Label(
                stats_frame,
                textvariable=var,
                anchor="w",
                font=self.FONT_MONO,
                bg=self.COLOR_PANEL,
                fg=self.COLOR_MONO,
            ).pack(fill=tk.X, pady=3)

        # Giriş satırı
        input_frame = tk.Frame(right_col, bg=self.COLOR_BG)
        input_frame.pack(fill=tk.X, pady=(18, 0))
        self.entry = tk.Entry(input_frame, font=self.FONT_INPUT, relief=tk.FLAT, bd=4)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12), ipady=8)
        self.entry.bind("<Return>", lambda _e: self._on_send())
        self.btn = ttk.Button(input_frame, text="Gönder", command=self._on_send)
        self.btn.pack(side=tk.LEFT, ipadx=10)
        self.btn_stop = ttk.Button(input_frame, text="Durdur", command=self._on_stop)
        self.btn_stop.pack(side=tk.LEFT, ipadx=10, padx=(8, 0))
        self.btn_stop.configure(state=tk.DISABLED)

        # Log
        log_frame = tk.LabelFrame(
            right_col,
            text=" Log ",
            padx=10,
            pady=8,
            font=self.FONT_PANEL_TITLE,
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT,
            bd=2,
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=12, font=("Consolas", 11),
            bg="#0e0e16", fg="#c8c8d4", insertbackground="#c8c8d4",
            relief=tk.FLAT, bd=4,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)
        self.log_box.configure(state=tk.DISABLED)

        self.entry.focus_set()

    def _append_log(self, line: str) -> None:
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, line + "\n")
        all_lines = self.log_box.get("1.0", tk.END).splitlines()
        if len(all_lines) > 12:
            self.log_box.delete("1.0", f"{len(all_lines) - 12 + 1}.0")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    # ---------- Kontroller ----------
    def _initial_check(self) -> None:
        threading.Thread(target=self._do_health, daemon=True).start()

    def _do_health(self) -> None:
        ok_ollama = self.llm.is_alive()
        self.event_q.put({"type": "health", "ollama": ok_ollama})

    def _on_send(self) -> None:
        if self._busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        self._busy = True
        self.btn.configure(state=tk.DISABLED)
        self.var_active.set("Aktif jest: AI düşünüyor…")
        self._append_log(f"> {text}")
        threading.Thread(target=self._do_request, args=(text,), daemon=True).start()

    def _do_request(self, text: str) -> None:
        result = self.llm.request(text)
        if result is None or "error" in result:
            self.event_q.put({"type": "error", "user_text": text,
                              "detail": result or {"error": "no_response"}})
            return
        self.event_q.put({"type": "gesture", "user_text": text, "result": result})

    def _on_stop(self) -> None:
        """Kullanici Durdur'a basti — aktif jest durur, idle'a doner."""
        jid = self.engine.stop()
        if jid:
            self._append_log(f"[stop] {jid} kullanici tarafindan durduruldu")
            self.logger.log_event(f"Kullanici durdurdu: {jid}")
        self.btn_stop.configure(state=tk.DISABLED)
        self.var_active.set("Aktif jest: idle")

    # ---------- Olay & frame döngüleri ----------
    def _poll_events(self) -> None:
        try:
            while True:
                evt = self.event_q.get_nowait()
                self._handle_event(evt)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_events)

    def _frame_tick(self) -> None:
        pixels = self.engine.render()
        self.matrix.update_pixels(pixels)
        # Engine aktif degilse durum/buton'u idle'a cek
        if not self._busy and not self.engine.is_active():
            self.var_active.set("Aktif jest: idle")
            if self.btn_stop["state"] != tk.DISABLED:
                self.btn_stop.configure(state=tk.DISABLED)
        self.root.after(FRAME_INTERVAL_MS, self._frame_tick)

    def _handle_event(self, evt: dict) -> None:
        kind = evt.get("type")
        if kind == "health":
            ollama_ok = evt["ollama"]
            self.var_ollama.set("Ollama: ✓" if ollama_ok else "Ollama: ✗ (bağlanamadı)")
            self._append_log(f"[health] Ollama={'OK' if ollama_ok else 'YOK'}")
        elif kind == "error":
            detail = evt["detail"]
            user_text = evt.get("user_text", "")
            err = detail.get("error", "bilinmeyen hata")
            if err == "unknown_jest_id":
                msg = f"Geçersiz jest: {detail.get('jest_id')!r}"
            elif err.startswith("ollama_"):
                msg = "Ollama bağlanamadı"
            else:
                msg = f"Hata: {err}"
            self.var_active.set("Aktif jest: idle")
            self.var_yanit.set(f"AI yanıtı: ⚠ {msg}")
            meta = detail.get("meta")
            if meta:
                self._update_stats(meta)
                self._append_log(f"[hata] {err} (wall={meta.get('wall_s', 0):.2f}s)")
            else:
                self._append_log(f"[hata] {err}")
            # Oturum dosyasina yaz
            self.logger.log_error(user_text, detail)
            self._set_idle()
        elif kind == "gesture":
            r = evt["result"]
            user_text = evt.get("user_text", "")
            meta = r.get("meta", {})
            # Basarili istek = Ollama gercekten ayakta. Durum panelini taze tut.
            self.var_ollama.set("Ollama: ✓")
            # sure_sn=None -> jest sonsuza kadar oynar, Durdur ile biter
            triggered = self.engine.trigger(r["jest_id"], r["yogunluk"], sure_sn=None)
            self.var_active.set(f"Aktif jest: {r['jest_id']}")
            self.var_yanit.set(f"AI yanıtı: {r['yanit']}")
            self.var_last_id.set(f"jest_id: {r['jest_id']}")
            self.var_last_yog.set(f"yoğunluk: {r['yogunluk']:.2f}")
            self.var_last_sure.set("süre: süresiz (Durdur ile biter)")
            self._update_stats(meta)
            # Oturum dosyasina yaz
            self.logger.log_request(user_text, r)
            # Durdur butonunu aktif et
            self.btn_stop.configure(state=tk.NORMAL)
            # Detaylı log: 3 satır per istek
            self._append_log(
                f"[llm]  {meta.get('wall_s', 0):.2f}s · "
                f"prompt {meta.get('prompt_tokens', 0)}tok / "
                f"yanit {meta.get('eval_tokens', 0)}tok @ "
                f"{meta.get('tok_per_s', 0):.0f} tok/s"
            )
            self._append_log(
                f"[jest] {r['jest_id']} yog={r['yogunluk']:.2f} "
                f"sim={'OK' if triggered else '?'}"
            )
            yanit_kisa = (r['yanit'][:60] + '…') if len(r['yanit']) > 60 else r['yanit']
            self._append_log(f"[yanit] {yanit_kisa!r}")
            self._set_idle()

    def _update_stats(self, meta: dict) -> None:
        if not meta:
            return
        wall = meta.get("wall_s", 0)
        load_ms = meta.get("load_ms", 0)
        load_part = f" (model yükleme {load_ms / 1000:.1f}s)" if load_ms > 100 else ""
        self.var_stat_think.set(f"Düşünme süresi: {wall:.2f} sn{load_part}")
        self.var_stat_tokens.set(
            f"Token: {meta.get('prompt_tokens', 0)} → {meta.get('eval_tokens', 0)}"
        )
        self.var_stat_speed.set(
            f"Üretim hızı: {meta.get('tok_per_s', 0):.1f} tok/s"
        )
        ram = ram_usage()
        if ram:
            self.var_stat_ram.set(
                f"RAM: ollama={fmt_mb(ram['ollama_mb'])}  python={fmt_mb(ram['python_mb'])}"
            )

    def _set_idle(self) -> None:
        self._busy = False
        self.btn.configure(state=tk.NORMAL)
        self.entry.focus_set()

    def _ram_tick(self) -> None:
        ram = ram_usage()
        if ram:
            self.var_stat_ram.set(
                f"RAM: ollama={fmt_mb(ram['ollama_mb'])}  python={fmt_mb(ram['python_mb'])}"
            )
        # Her 2 saniyede bir tazele
        self.root.after(2000, self._ram_tick)

    def _on_close(self) -> None:
        """Pencere kapanmadan once oturum ozetini yaz."""
        try:
            self.engine.stop()
            self.logger.end()
            log.info("Oturum ozetini %s'e yazdik.", self.logger.log_path)
        except Exception as e:
            log.exception("Oturum ozetinde hata: %s", e)
        self.root.destroy()


def main() -> None:
    config = load_config()
    root = tk.Tk()
    App(root, config)
    root.mainloop()


if __name__ == "__main__":
    main()
