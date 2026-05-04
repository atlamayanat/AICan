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
        self.root.geometry("1600x940")
        self.root.minsize(1320, 860)

        # Renk paleti — neon cyberpunk: koyu zemin + cyan/magenta/green vurgu
        self.COLOR_BG = "#08080f"            # cok koyu mavi-siyah
        self.COLOR_PANEL = "#11111e"         # panel zemini
        self.COLOR_PANEL_ALT = "#0c0c18"     # ic kutu / log / yanit zemini
        self.COLOR_BORDER = "#1f1f3a"        # nötr koyu border
        self.COLOR_TEXT = "#e6f1ff"          # ana yazi (soguk beyaz)
        self.COLOR_TEXT_DIM = "#6a7196"      # ikincil yazi
        self.COLOR_NEON_CYAN = "#00f0ff"     # baslik / matris border / send
        self.COLOR_NEON_PINK = "#ff2d92"     # yanit karti / stop
        self.COLOR_NEON_GREEN = "#39ff14"    # istatistik mono / OK
        self.COLOR_NEON_PURPLE = "#b026ff"   # ikincil aksan
        self.COLOR_WARN = "#ff5e3a"

        # Yazı tipleri
        self.FONT_HEADER = ("Segoe UI", 24, "bold")
        self.FONT_SUBHEADER = ("Consolas", 10)
        self.FONT_PANEL_TITLE = ("Consolas", 10, "bold")
        self.FONT_LABEL = ("Segoe UI", 12)
        self.FONT_LABEL_BOLD = ("Segoe UI", 12, "bold")
        self.FONT_YANIT_TITLE = ("Consolas", 10, "bold")
        self.FONT_YANIT = ("Segoe UI", 20, "bold")
        self.FONT_MONO = ("Consolas", 11)
        self.FONT_INPUT = ("Segoe UI", 14)

        self.root.configure(bg=self.COLOR_BG)

        # ttk stilleri — neon butonlar
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        for name, accent, bg_btn, hover in [
            ("Send.TButton", self.COLOR_NEON_CYAN, "#0a1a26", "#0f2a3a"),
            ("Stop.TButton", self.COLOR_NEON_PINK, "#1a0a18", "#2a0f24"),
        ]:
            style.configure(
                name,
                font=("Consolas", 12, "bold"),
                padding=(20, 10),
                background=bg_btn,
                foreground=accent,
                borderwidth=1,
                bordercolor=accent,
                focusthickness=0,
                relief="flat",
            )
            style.map(
                name,
                background=[("active", hover), ("disabled", "#0a0a14")],
                foreground=[("disabled", self.COLOR_TEXT_DIM)],
                bordercolor=[("disabled", self.COLOR_BORDER)],
            )

        # ---------- KOK GRID — header / govde ----------
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Header — neon cyan accent
        header = tk.Frame(self.root, bg=self.COLOR_BG)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 6))
        tk.Label(
            header,
            text="AI BODY",
            font=self.FONT_HEADER,
            bg=self.COLOR_BG,
            fg=self.COLOR_NEON_CYAN,
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text="// KONYA BİLİM MERKEZİ · SERGI PROTOTIPI",
            font=self.FONT_SUBHEADER,
            bg=self.COLOR_BG,
            fg=self.COLOR_NEON_PURPLE,
        ).pack(side=tk.LEFT, padx=(16, 0), pady=(10, 0))

        # ince neon ayrac cizgisi
        tk.Frame(self.root, bg=self.COLOR_NEON_CYAN, height=1).grid(
            row=0, column=0, sticky="sew", padx=24, pady=(0, 0)
        )

        # Govde — 3 kolon
        body = tk.Frame(self.root, bg=self.COLOR_BG)
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        body.columnconfigure(0, weight=0, minsize=280)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=0, minsize=340)
        body.rowconfigure(0, weight=1)

        # ============ SOL KOLON ============
        left_col = tk.Frame(body, bg=self.COLOR_BG)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        self.var_ollama = tk.StringVar(value="Ollama: ?")
        self.var_active = tk.StringVar(value="Aktif jest: idle")
        self.var_yanit = tk.StringVar(value="—")

        status = self._make_panel(left_col, "// DURUM", self.COLOR_NEON_CYAN)
        status.pack(fill=tk.X)
        for var in (self.var_ollama, self.var_active):
            tk.Label(
                status,
                textvariable=var,
                anchor="w",
                font=self.FONT_LABEL,
                bg=self.COLOR_PANEL,
                fg=self.COLOR_TEXT,
            ).pack(fill=tk.X, padx=16, pady=4)
        tk.Frame(status, bg=self.COLOR_PANEL, height=10).pack()

        last = self._make_panel(left_col, "// SON KOMUT", self.COLOR_NEON_PURPLE)
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
            ).pack(fill=tk.X, padx=16, pady=4)
        tk.Frame(last, bg=self.COLOR_PANEL, height=10).pack()

        stats_frame = self._make_panel(left_col, "// İSTATİSTİK", self.COLOR_NEON_GREEN)
        stats_frame.pack(fill=tk.X, pady=(14, 0))
        self.var_stat_think = tk.StringVar(value="Düşünme süresi: —")
        self.var_stat_tokens = tk.StringVar(value="Token: —")
        self.var_stat_speed = tk.StringVar(value="Üretim hızı: —")
        self.var_stat_ram = tk.StringVar(
            value="RAM: psutil yok" if not HAS_PSUTIL else "RAM: hesaplanıyor…"
        )
        for var in (self.var_stat_think, self.var_stat_tokens, self.var_stat_speed, self.var_stat_ram):
            tk.Label(
                stats_frame,
                textvariable=var,
                anchor="w",
                font=self.FONT_MONO,
                bg=self.COLOR_PANEL,
                fg=self.COLOR_NEON_GREEN,
            ).pack(fill=tk.X, padx=16, pady=3)
        tk.Frame(stats_frame, bg=self.COLOR_PANEL, height=10).pack()

        # ============ ORTA KOLON — etiket / matris / input / yanit ============
        center_col = tk.Frame(body, bg=self.COLOR_BG)
        center_col.grid(row=0, column=1, sticky="nsew", padx=8)
        center_col.columnconfigure(0, weight=1)
        # Dikey: 0 etiket | 1 matris (esnek) | 2 input bar | 3 yanit
        center_col.rowconfigure(0, weight=0)
        center_col.rowconfigure(1, weight=1)
        center_col.rowconfigure(2, weight=0)
        center_col.rowconfigure(3, weight=0)

        # ust etiket
        tk.Label(
            center_col,
            text="// TEPKİ EKRANI · 32×32",
            font=self.FONT_PANEL_TITLE,
            bg=self.COLOR_BG,
            fg=self.COLOR_NEON_CYAN,
        ).grid(row=0, column=0, pady=(0, 8))

        # matris — kare neon cyan border icinde, ortalanmis
        matrix_wrap = tk.Frame(center_col, bg=self.COLOR_BG)
        matrix_wrap.grid(row=1, column=0)
        matrix_frame = tk.Frame(
            matrix_wrap,
            bg=self.COLOR_BG,
            highlightbackground=self.COLOR_NEON_CYAN,
            highlightthickness=2,
        )
        matrix_frame.pack()
        # cell_size=17 → 17*32 + 33 = 577 px (kare). pencere yuksekligine sigar.
        # Matris LED renkleri gesture_engine'den geliyor; UI temasi onlari etkilemez.
        self.matrix = MatrixView(matrix_frame, cell_size=17, padding=1)
        self.matrix.pack()

        # ============ INPUT BAR — orta kolonda yanit ustunde ============
        input_bar = tk.Frame(center_col, bg=self.COLOR_BG)
        input_bar.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        input_bar.columnconfigure(0, weight=1)

        entry_wrap = tk.Frame(
            input_bar,
            bg=self.COLOR_PANEL,
            highlightbackground=self.COLOR_NEON_CYAN,
            highlightthickness=1,
        )
        entry_wrap.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.entry = tk.Entry(
            entry_wrap,
            font=self.FONT_INPUT,
            relief=tk.FLAT,
            bd=0,
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT,
            insertbackground=self.COLOR_NEON_CYAN,
        )
        self.entry.pack(fill=tk.X, padx=14, pady=10)
        self.entry.bind("<Return>", lambda _e: self._on_send())

        self.btn = ttk.Button(input_bar, text="GÖNDER", style="Send.TButton", command=self._on_send)
        self.btn.grid(row=0, column=1)
        self.btn_stop = ttk.Button(input_bar, text="DURDUR", style="Stop.TButton", command=self._on_stop)
        self.btn_stop.grid(row=0, column=2, padx=(8, 0))
        self.btn_stop.configure(state=tk.DISABLED)

        # ============ YANIT KARTI — input altinda, neon pink border ============
        yanit_card = tk.Frame(
            center_col,
            bg=self.COLOR_PANEL_ALT,
            highlightbackground=self.COLOR_NEON_PINK,
            highlightthickness=1,
        )
        yanit_card.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        tk.Label(
            yanit_card,
            text="// AI YANITI",
            font=self.FONT_YANIT_TITLE,
            bg=self.COLOR_PANEL_ALT,
            fg=self.COLOR_NEON_PINK,
        ).pack(anchor="w", padx=20, pady=(12, 4))
        tk.Label(
            yanit_card,
            textvariable=self.var_yanit,
            font=self.FONT_YANIT,
            bg=self.COLOR_PANEL_ALT,
            fg=self.COLOR_TEXT,
            wraplength=720,
            justify="center",
            anchor="center",
        ).pack(fill=tk.X, padx=24, pady=(0, 18))

        # ============ SAG KOLON — log ============
        right_col = tk.Frame(body, bg=self.COLOR_BG)
        right_col.grid(row=0, column=2, sticky="nsew", padx=(16, 0))

        log_frame = self._make_panel(right_col, "// OLAY KAYDI", self.COLOR_NEON_GREEN)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_box = scrolledtext.ScrolledText(
            log_frame,
            height=18,
            font=("Consolas", 10),
            bg=self.COLOR_PANEL_ALT,
            fg=self.COLOR_NEON_GREEN,
            insertbackground=self.COLOR_NEON_GREEN,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=10,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.log_box.configure(state=tk.DISABLED)

        self.entry.focus_set()

    def _make_panel(self, parent: tk.Misc, title: str, accent: str) -> tk.Frame:
        """Neon vurgu cizgili panel: ustte renkli baslik + ince border."""
        outer = tk.Frame(
            parent,
            bg=self.COLOR_PANEL,
            highlightbackground=self.COLOR_BORDER,
            highlightthickness=1,
        )
        tk.Label(
            outer,
            text=title,
            font=self.FONT_PANEL_TITLE,
            bg=self.COLOR_PANEL,
            fg=accent,
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 4))
        # ince renkli ayrac
        tk.Frame(outer, bg=accent, height=1).pack(fill=tk.X, padx=16, pady=(0, 8))
        return outer

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
            self.var_yanit.set(f"⚠ {msg}")
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
            self.var_yanit.set(r["yanit"] if r.get("yanit") else "—")
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
