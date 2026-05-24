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

from build_jest_rehberi import build_rehber, OUTPUT_PATH as REHBER_PATH
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
        self._refresh_jest_rehberi(gestures_data)

        # Oturum logger - her oturumun .txt dosyasina yazar
        log_path = (BASE_DIR / config.get("session_log_path", "../logs/session.log")).resolve()
        self.logger = SessionLogger(log_path, config["ollama_url"], config["ollama_model"])
        self.logger.start()
        log.info("Oturum logu: %s", log_path)

        self.event_q: queue.Queue = queue.Queue()
        self._busy = False
        self._pulling = False
        self._local_model_names: list[str] = []

        self._build_ui()
        # Pencere kapanisi: oturum ozetini yaz, sonra cikis
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda _e: self._on_close())
        self.root.after(50, self._poll_events)
        self.root.after(FRAME_INTERVAL_MS, self._frame_tick)
        self.root.after(150, self._initial_check)
        self.root.after(180, self._refresh_local_models)
        self.root.after(200, self._ram_tick)
        # Sergi acilisinda ilk ziyaretci 17sn beklemesin: modeli RAM'e isit.
        self.root.after(220, self._initial_warmup)

    def _refresh_jest_rehberi(self, gestures_data: dict) -> None:
        """JESTLER.md'yi gestures.json'dan yeniden uret.
        Hata olursa app baslatmayi engelleme — sadece logla."""
        try:
            REHBER_PATH.write_text(build_rehber(gestures_data), encoding="utf-8")
            log.info("Jest rehberi guncellendi: %s (%d jest)",
                     REHBER_PATH, len(gestures_data["jestler"]))
        except OSError as e:
            log.warning("Jest rehberi yazilamadi: %s", e)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        self.root.title("AI Body — Sergi Prototipi")
        self.root.geometry("1760x1000")
        self.root.minsize(1440, 880)

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
        # Combobox stili — neon zemin, koyu arka plan
        style.configure(
            "Neon.TCombobox",
            fieldbackground=self.COLOR_PANEL_ALT,
            background=self.COLOR_PANEL,
            foreground=self.COLOR_TEXT,
            bordercolor=self.COLOR_NEON_CYAN,
            arrowcolor=self.COLOR_NEON_CYAN,
            lightcolor=self.COLOR_NEON_CYAN,
            darkcolor=self.COLOR_NEON_CYAN,
            selectbackground=self.COLOR_PANEL_ALT,
            selectforeground=self.COLOR_NEON_CYAN,
            padding=(8, 6),
        )
        style.map(
            "Neon.TCombobox",
            fieldbackground=[("readonly", self.COLOR_PANEL_ALT)],
            foreground=[("readonly", self.COLOR_TEXT)],
            bordercolor=[("focus", self.COLOR_NEON_CYAN), ("hover", self.COLOR_NEON_CYAN)],
        )
        # Acilir liste icindeki yazi/zemin (TCombobox'a ozel TLM stili degil — root option)
        self.root.option_add("*TCombobox*Listbox.background", self.COLOR_PANEL_ALT)
        self.root.option_add("*TCombobox*Listbox.foreground", self.COLOR_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.COLOR_NEON_CYAN)
        self.root.option_add("*TCombobox*Listbox.selectForeground", self.COLOR_BG)
        self.root.option_add("*TCombobox*Listbox.font", ("Consolas", 10))

        for name, accent, bg_btn, hover, font, pad in [
            ("Send.TButton", self.COLOR_NEON_CYAN, "#0a1a26", "#0f2a3a", ("Consolas", 12, "bold"), (20, 10)),
            ("Stop.TButton", self.COLOR_NEON_PINK, "#1a0a18", "#2a0f24", ("Consolas", 12, "bold"), (20, 10)),
            ("Mini.TButton", self.COLOR_NEON_CYAN, "#0a1a26", "#0f2a3a", ("Consolas", 9, "bold"), (8, 4)),
            ("MiniPink.TButton", self.COLOR_NEON_PINK, "#1a0a18", "#2a0f24", ("Consolas", 9, "bold"), (8, 4)),
            ("MiniPurple.TButton", self.COLOR_NEON_PURPLE, "#150a1f", "#22113a", ("Consolas", 9, "bold"), (8, 4)),
        ]:
            style.configure(
                name,
                font=font,
                padding=pad,
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
        body.columnconfigure(2, weight=0, minsize=270)
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
                wraplength=240,
                justify="left",
            ).pack(fill=tk.X, padx=16, pady=4)
        tk.Frame(status, bg=self.COLOR_PANEL, height=10).pack()

        # // MODEL paneli — yuklu modeller arasi gecis + yeni model indirme
        self.PRESET_PULL_MODELS = [
            "qwen2.5:7b-instruct",
            "qwen2.5:3b-instruct",
            "qwen2.5:14b-instruct",
            "gemma3:4b",
            "gemma3:1b",
            "llama3.2:3b",
            "llama3.1:8b",
            "mistral:7b-instruct",
        ]

        model_panel = self._make_panel(left_col, "// MODEL", self.COLOR_NEON_PINK)
        model_panel.pack(fill=tk.X, pady=(14, 0))
        m_inner = tk.Frame(model_panel, bg=self.COLOR_PANEL)
        m_inner.pack(fill=tk.X, padx=16, pady=(0, 12))

        # Aktif model rozeti
        tk.Label(
            m_inner, text="aktif", anchor="w",
            font=("Consolas", 9), bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_DIM,
        ).pack(fill=tk.X)
        self.var_active_model = tk.StringVar(value=self.config["ollama_model"])
        tk.Label(
            m_inner, textvariable=self.var_active_model, anchor="w",
            font=self.FONT_LABEL_BOLD, bg=self.COLOR_PANEL,
            fg=self.COLOR_NEON_GREEN, wraplength=240, justify="left",
        ).pack(fill=tk.X, pady=(0, 8))

        # Yuklu modeller bolumu
        tk.Label(
            m_inner, text="yuklu modeller", anchor="w",
            font=("Consolas", 9), bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_DIM,
        ).pack(fill=tk.X)
        self.cmb_local = ttk.Combobox(
            m_inner, state="readonly", style="Neon.TCombobox",
            font=("Consolas", 10),
        )
        self.cmb_local.pack(fill=tk.X, pady=(2, 4))

        m_btnrow = tk.Frame(m_inner, bg=self.COLOR_PANEL)
        m_btnrow.pack(fill=tk.X, pady=(0, 10))
        self.btn_use_model = ttk.Button(
            m_btnrow, text="AKTIF YAP", style="Mini.TButton",
            command=self._on_use_model,
        )
        self.btn_use_model.pack(side=tk.LEFT)
        self.btn_refresh_models = ttk.Button(
            m_btnrow, text="YENILE", style="MiniPurple.TButton",
            command=self._refresh_local_models,
        )
        self.btn_refresh_models.pack(side=tk.LEFT, padx=(6, 0))

        # ince ayrac
        tk.Frame(m_inner, bg=self.COLOR_BORDER, height=1).pack(fill=tk.X, pady=(2, 8))

        # Yeni model indir bolumu
        tk.Label(
            m_inner, text="yeni model indir", anchor="w",
            font=("Consolas", 9), bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_DIM,
        ).pack(fill=tk.X)
        self.cmb_pull = ttk.Combobox(
            m_inner, values=self.PRESET_PULL_MODELS, style="Neon.TCombobox",
            font=("Consolas", 10),
        )
        self.cmb_pull.pack(fill=tk.X, pady=(2, 6))
        self.btn_pull_model = ttk.Button(
            m_inner, text="INDIR", style="MiniPink.TButton",
            command=self._on_pull_model,
        )
        self.btn_pull_model.pack(fill=tk.X, pady=(0, 6))
        self.var_pull_status = tk.StringVar(value="")
        tk.Label(
            m_inner, textvariable=self.var_pull_status, anchor="w",
            font=("Consolas", 9), bg=self.COLOR_PANEL,
            fg=self.COLOR_NEON_PINK, wraplength=240, justify="left",
        ).pack(fill=tk.X)

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
                wraplength=240,
                justify="left",
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
                wraplength=240,
                justify="left",
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
            text="// TEPKİ EKRANI · 96×96",
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
        # cell_size=7, padding=1 → 7*96 + 97 = 769 px (kare). 96×96 LED matrisi.
        # Matris LED renkleri gesture_engine'den geliyor; UI temasi onlari etkilemez.
        self.matrix = MatrixView(matrix_frame, cell_size=7, padding=1)
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
            height=14,
            width=28,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg=self.COLOR_PANEL_ALT,
            fg=self.COLOR_NEON_GREEN,
            insertbackground=self.COLOR_NEON_GREEN,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=8,
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

    def _initial_warmup(self) -> None:
        """Model RAM'e isinmis olsun ki ilk ziyaretci 17sn beklemesin."""
        if not self.config.get("warmup_on_start", True):
            return
        self.var_active.set("Aktif jest: model ısıtılıyor…")
        threading.Thread(target=self._do_warmup, daemon=True).start()

    def _do_warmup(self) -> None:
        ok = self.llm.warmup()
        self.event_q.put({"type": "warmup_done", "ok": ok})

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

    # ---------- Model yonetimi ----------
    def _refresh_local_models(self) -> None:
        """Ollama'dan lokal model listesini cek (arkadan)."""
        threading.Thread(target=self._do_refresh_local, daemon=True).start()

    def _do_refresh_local(self) -> None:
        models = self.llm.list_local_models()
        self.event_q.put({"type": "local_models", "models": models})

    def _on_use_model(self) -> None:
        """Kullanici lokal listeden secim yapip AKTIF YAP'a basti."""
        if self._busy:
            self.var_pull_status.set("⚠ once cevap bekleniyor")
            return
        if self._pulling:
            self.var_pull_status.set("⚠ indirme suruyor")
            return
        idx = self.cmb_local.current()
        if idx < 0 or idx >= len(self._local_model_names):
            self.var_pull_status.set("⚠ once bir model sec")
            return
        new_model = self._local_model_names[idx]
        if new_model == self.llm.model:
            self.var_pull_status.set("zaten aktif")
            return
        old = self.llm.model
        self.llm.set_model(new_model)
        self.var_active_model.set(new_model)
        self.logger.model_name = new_model
        self._save_config_model(new_model)
        self.var_pull_status.set(f"✓ aktif: {new_model}")
        self._append_log(f"[model] {old} → {new_model}")
        self.logger.log_event(f"Aktif model degisti: {old} → {new_model}")
        # Ollama durumunu yeniden test et — gecerli model varsa /api/chat sorunsuz
        threading.Thread(target=self._do_health, daemon=True).start()

    def _on_pull_model(self) -> None:
        """Kullanici INDIR'e basti — secili veya yazilan model adini cek."""
        if self._pulling:
            return
        name = self.cmb_pull.get().strip()
        if not name:
            self.var_pull_status.set("⚠ model adi bos")
            return
        self._pulling = True
        self.btn_pull_model.configure(state=tk.DISABLED)
        self.var_pull_status.set(f"⇣ {name} baslatiliyor...")
        self._append_log(f"[pull] {name} indiriliyor...")
        self.logger.log_event(f"Model indirme baslatildi: {name}")
        threading.Thread(target=self._do_pull, args=(name,), daemon=True).start()

    def _do_pull(self, name: str) -> None:
        def on_progress(data: dict) -> None:
            self.event_q.put({"type": "pull_progress", "name": name, "data": data})
        ok = self.llm.pull_model(name, on_progress)
        self.event_q.put({"type": "pull_done", "name": name, "ok": ok})

    def _save_config_model(self, model_name: str) -> None:
        """config.json'daki ollama_model alanini guncelle (sonraki acilis icin)."""
        try:
            self.config["ollama_model"] = model_name
            CONFIG_PATH.write_text(
                json.dumps(self.config, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            log.warning("config.json yazilamadi: %s", e)

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

    def _humanize_error(self, err: str, detail: dict) -> str:
        """Sergideki gorevli hatayi anlasin diye Ollama hatalarini Turkceye cevir."""
        e = (err or "").lower()
        if err == "unknown_jest_id":
            return f"Geçersiz jest: {detail.get('jest_id')!r}"
        if "read timed out" in e or "readtimeout" in e or "timed out" in e:
            return "Model yanıt veremedi — bilgisayar yavaşlamış olabilir"
        if "connection refused" in e or "max retries" in e or "failed to establish" in e:
            return "Ollama servisi çalışmıyor — Ollama'yı yeniden başlat"
        if "404" in e or ("model" in e and ("not found" in e or "bulunam" in e)):
            return "Model bulunamadı — Ollama'da model eksik olabilir"
        if "500" in e:
            return "Model anlık yoğunluk, 5 sn sonra tekrar deneyin"
        if "empty_content" in e:
            return "Model boş cevap verdi — tekrar deneyin"
        if "invalid_json" in e:
            return "Model bozuk JSON döndürdü — tekrar deneyin"
        if e.startswith("ollama_"):
            return "Ollama bağlanamadı"
        return f"Hata: {err[:80]}"

    def _handle_event(self, evt: dict) -> None:
        kind = evt.get("type")
        if kind == "health":
            ollama_ok = evt["ollama"]
            self.var_ollama.set("Ollama: ✓" if ollama_ok else "Ollama: ✗ (bağlanamadı)")
            self._append_log(f"[health] Ollama={'OK' if ollama_ok else 'YOK'}")
        elif kind == "local_models":
            models = evt["models"]
            self._local_model_names = [m["name"] for m in models]
            items = [f"{m['name']}  ({m['size_gb']:.1f} GB)" for m in models]
            self.cmb_local["values"] = items
            # Aktif modeli secili goster
            if self.llm.model in self._local_model_names:
                idx = self._local_model_names.index(self.llm.model)
                self.cmb_local.current(idx)
            elif items:
                self.cmb_local.set("")
            if not items:
                self.var_pull_status.set("hic model yok — once indir")
        elif kind == "pull_progress":
            data = evt["data"]
            name = evt["name"]
            if data.get("error"):
                self.var_pull_status.set(f"⚠ {data['error'][:60]}")
            else:
                status = data.get("status", "...")
                completed = data.get("completed", 0) or 0
                total = data.get("total", 0) or 0
                if total > 0:
                    pct = 100.0 * completed / total
                    mb_done = completed / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    self.var_pull_status.set(
                        f"⇣ {name}\n{status} %{pct:.0f} ({mb_done:.0f}/{mb_total:.0f} MB)"
                    )
                else:
                    self.var_pull_status.set(f"⇣ {name}\n{status}")
        elif kind == "pull_done":
            self._pulling = False
            self.btn_pull_model.configure(state=tk.NORMAL)
            name = evt["name"]
            if evt["ok"]:
                self.var_pull_status.set(f"✓ {name} indirildi")
                self._append_log(f"[pull] {name} basarili")
                self.logger.log_event(f"Model indirildi: {name}")
                self._refresh_local_models()
            else:
                self._append_log(f"[pull] {name} hata")
                self.logger.log_event(f"Model indirme HATASI: {name}")
        elif kind == "warmup_done":
            if evt["ok"]:
                self._append_log("[warmup] model RAM'de hazır")
                self.logger.log_event("Model warmup tamamlandi (RAM'e yuklendi)")
            else:
                self._append_log("[warmup] başarısız — ilk istek yavaş olabilir")
            self.var_active.set("Aktif jest: idle")
        elif kind == "error":
            detail = evt["detail"]
            user_text = evt.get("user_text", "")
            err = detail.get("error", "bilinmeyen hata")
            msg = self._humanize_error(err, detail)
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
