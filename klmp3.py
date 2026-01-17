#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KLmp3 - Extracteur audio YouTube/Twitch (Tkinter)
- Télécharge l'audio avec yt-dlp, puis convertit avec ffmpeg selon le format choisi.
- YouTube : bestaudio/best (évite m3u8 quand possible)
- Twitch VOD : Audio_Only
Notes:
- Nécessite: ffmpeg + ffprobe (dans le PATH ou dans tools/<platform>/).
- yt-dlp est utilisé via le module Python "yt_dlp" (recommandé pour la distribution).
  En secours, un binaire "yt-dlp" dans le PATH peut aussi être utilisé.
- Interface en français avec vouvoiement (préférence utilisateur)
"""

import os
import re
import sys
import shutil
import threading
import subprocess
import random
import platform
import json
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ffmpeg_locator import find_ffmpeg_tools_first
from PIL import Image, ImageTk


def _setup_ssl_certificates() -> None:
    """Configure un bundle de certificats CA pour éviter les erreurs SSL en app packagée."""
    try:
        import certifi  # type: ignore
        ca_path = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca_path)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_path)
    except Exception:
        pass


# Important : faire ça le plus tôt possible, avant tout accès réseau.
_setup_ssl_certificates()


MAX_URLS = 10

# Bibli de thèmes (issus de Garage)
THEMES = {
    # ===== Thèmes sombres (sobres / quotidiens) =====
    "[Sombre] Midnight Garage": dict(
        BG="#151515", PANEL="#1F1F1F", FIELD="#2A2A2A",
        FG="#EAEAEA", FIELD_FG="#F0F0F0", ACCENT="#FF9800"
    ),
    "[Sombre] AIR-KLM Night flight": dict(
        BG="#0B1E2D", PANEL="#102A3D", FIELD="#16384F",
        FG="#EAF6FF", FIELD_FG="#FFFFFF", ACCENT="#00A1DE"
    ),
    "[Sombre] Café Serré": dict(
        BG="#1B120C", PANEL="#2A1C14", FIELD="#3A281D",
        FG="#F2E6D8", FIELD_FG="#FFF4E6", ACCENT="#C28E5C"
    ),
    "[Sombre] Matrix Déjà Vu": dict(
        BG="#000A00", PANEL="#001F00", FIELD="#003300",
        FG="#00FF66", FIELD_FG="#66FF99", ACCENT="#00FF00"
    ),
    "[Sombre] Miami Vice 1987": dict(
        BG="#14002E", PANEL="#2B0057", FIELD="#004D4D",
        FG="#FFF0FF", FIELD_FG="#FFFFFF", ACCENT="#00FFD5"
    ),
    "[Sombre] Cyber Licorne": dict(
        BG="#1A0026", PANEL="#2E004F", FIELD="#3D0066",
        FG="#F6E7FF", FIELD_FG="#FFFFFF", ACCENT="#FF2CF7"
    ),
    # ===== Thèmes clairs =====
    "[Clair] AIR-KLM Day flight": dict(
        BG="#EAF6FF", PANEL="#D6EEF9", FIELD="#FFFFFF",
        FG="#0B2A3F", FIELD_FG="#0B2A3F", ACCENT="#00A1DE"
    ),
    "[Clair] Matin Brumeux": dict(
        BG="#E6E7E8", PANEL="#D4D7DB", FIELD="#FFFFFF",
        FG="#1E1F22", FIELD_FG="#1E1F22", ACCENT="#6B7C93"
    ),
    "[Clair] Latte Vanille": dict(
        BG="#FAF6F1", PANEL="#EFE6DC", FIELD="#FFFFFF",
        FG="#3D2E22", FIELD_FG="#3D2E22", ACCENT="#D8B892"
    ),
    "[Clair] Miellerie La Divette": dict(
        BG="#E6B65C", PANEL="#F5E6CC", FIELD="#FFFFFF",
        FG="#50371A", FIELD_FG="#50371A", ACCENT="#F2B705"
    ),
    # ===== Thèmes Pouêt-Pouêt =====
    "[Pouêt] Chewing-gum Océan": dict(
        BG="#00A6C8", PANEL="#0083A1", FIELD="#00C7B7",
        FG="#082026", FIELD_FG="#082026", ACCENT="#FF4FD8"
    ),
    "[Pouêt] Pamplemousse": dict(
        BG="#FF4A1C", PANEL="#E63B10", FIELD="#FF7A00",
        FG="#1A0B00", FIELD_FG="#1A0B00", ACCENT="#00E5FF"
    ),
    "[Pouêt] Raisin Toxique": dict(
        BG="#7A00FF", PANEL="#5B00C9", FIELD="#B000FF",
        FG="#0F001A", FIELD_FG="#0F001A", ACCENT="#39FF14"
    ),
    "[Pouêt] Citron qui pique": dict(
        BG="#FFF200", PANEL="#E6D800", FIELD="#FFF7A6",
        FG="#1A1A00", FIELD_FG="#1A1A00", ACCENT="#0066FF"
    ),
    "[Pouêt] Barbie Apocalypse": dict(
        BG="#FF1493", PANEL="#004D40", FIELD="#1B5E20",
        FG="#E8FFF8", FIELD_FG="#FFFFFF", ACCENT="#FFEB3B"
    ),
    "[Pouêt] Compagnie Créole": dict(
        BG="#8B3A1A", PANEL="#F2C94C", FIELD="#FFFFFF",
        FG="#5A2E0C", FIELD_FG="#5A2E0C", ACCENT="#8B3A1A"
    ),
}

# Formats proposés dans l'UI (clé interne -> label)
FORMAT_LABELS = {
    "mp3": "MP3",
    "m4a": "M4A (AAC)",
    "opus": "OPUS",
    "flac": "FLAC",
    "ogg": "OGG (Vorbis)",
    "wav": "WAV",
}
FORMAT_KEYS_IN_ORDER = ["mp3", "m4a", "opus", "flac", "ogg", "wav"]


# Navigateur cookies-from-browser (label UI -> token yt-dlp)
YTB_BROWSER_LABELS = ["Firefox", "Chrome", "Chromium", "Edge"]
YTB_BROWSER_LABEL_TO_TOKEN = {
    "Firefox": "firefox",
    "Chrome": "chrome",
    "Chromium": "chromium",
    "Edge": "edge",
}
YTB_BROWSER_TOKEN_TO_LABEL = {v: k for k, v in YTB_BROWSER_LABEL_TO_TOKEN.items()}


def is_twitch(url: str) -> bool:
    return "twitch.tv" in url.lower()


def is_youtube(url: str) -> bool:
    u = url.lower()
    return ("youtube.com" in u) or ("youtu.be" in u)


@dataclass(frozen=True)
class ToolPath:
    path: str | None
    source: str  # "PATH" or "TOOLS" or "MISSING"


def _app_base_dir() -> str:
    """
    Dossier de base où se trouvent assets/ et tools/.
    Compatible PyInstaller (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.abspath(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))


def _platform_tag() -> str:
    """Retourne un tag de dossier dans tools/ (même logique que ffmpeg_locator)."""
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        a = "x86_64"
    elif arch in ("arm64", "aarch64"):
        a = "arm64"
    else:
        a = arch

    if sys.platform == "darwin":
        return f"macos-{a}"
    if sys.platform.startswith("win"):
        return f"windows-{a}"
    return f"linux-{a}"


def _is_executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def ytdlp_module_available() -> bool:
    """Retourne True si le module Python yt_dlp est importable."""
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:
        return False


def find_ytdlp_tools_first() -> ToolPath:
    """
    Stratégie :
    1) Cherche yt-dlp dans le PATH
    2) Sinon cherche dans tools/<platform>/yt-dlp (ou .exe sur Windows)
    """
    p = shutil.which("yt-dlp")
    if p:
        return ToolPath(path=p, source="PATH")

    base = _app_base_dir()
    tag = _platform_tag()
    name = "yt-dlp.exe" if sys.platform.startswith("win") else "yt-dlp"
    cand = os.path.join(base, "tools", tag, name)

    if _is_executable(cand):
        return ToolPath(path=cand, source="TOOLS")

    if os.path.isfile(cand):
        return ToolPath(path=cand, source="MISSING")

    return ToolPath(path=None, source="MISSING")


def find_deno_tools_first() -> ToolPath:
    """Cherche Deno dans tools/<platform>/ (pas dans le PATH volontairement)."""
    base = _app_base_dir()
    tag = _platform_tag()
    name = "deno.exe" if sys.platform.startswith("win") else "deno"
    cand = os.path.join(base, "tools", tag, name)

    if _is_executable(cand):
        return ToolPath(path=cand, source="TOOLS")

    if os.path.isfile(cand):
        return ToolPath(path=cand, source="MISSING")

    return ToolPath(path=None, source="MISSING")


def run_subprocess(cmd: list[str], on_line, stop_flag: threading.Event) -> int:
    """Run a subprocess, stream stdout+stderr line by line to on_line()."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if stop_flag.is_set():
                try:
                    proc.terminate()
                except Exception:
                    pass
                return 130
            on_line(line.rstrip("\n"))
        return proc.wait()
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass


def default_outdir() -> str:
    """Dossier de sortie par défaut (un seul dossier daté sur le Bureau)."""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        desktop = os.path.expanduser("~")
    stamp = datetime.now().strftime("%y-%m-%d")
    return os.path.join(desktop, f"klmp3-{stamp}")


def _config_dir() -> str:
    """Dossier de config utilisateur (écrivable), multi-OS."""
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return os.path.join(base, "KLMP3")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "KLMP3")
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(xdg, "klmp3")


def _config_path() -> str:
    return os.path.join(_config_dir(), "config.json")


def _load_config() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    try:
        os.makedirs(_config_dir(), exist_ok=True)
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Localise ffmpeg/ffprobe (PATH sinon tools/)
        self.ff = find_ffmpeg_tools_first()
        self.ffmpeg_path = self.ff.ffmpeg
        self.ffprobe_path = self.ff.ffprobe

        self.title("KLmp3 - v2.0")
        self.geometry("820x620")
        self.minsize(780, 560)

        # Theme
        self.style = ttk.Style()
        self.theme_var = tk.StringVar()

        # State
        self.worker_thread: threading.Thread | None = None
        self.stop_flag = threading.Event()

        # URL queue (up to 10 entries)
        self.url_vars: list[tk.StringVar] = [tk.StringVar()]
        self.url_entries: list[ttk.Entry] = []

        # UI vars
        self.outdir_var = tk.StringVar(value=default_outdir())

        # Config persistée
        self._config = _load_config()

        # Format (6 formats) — MP3 par défaut
        self.audio_format_var = tk.StringVar(value="mp3")

        # Réglages avancés par format
        self.mp3_quality_var = tk.StringVar(value="0")           # 0 best, 9 smaller
        self.aac_bitrate_var = tk.StringVar(value="192k")         # 96k..320k
        self.opus_bitrate_var = tk.StringVar(value="128k")        # 64k..192k
        self.vorbis_quality_var = tk.StringVar(value="5")         # 0..10
        self.flac_level_var = tk.StringVar(value="5")             # 0..8

        self.keep_intermediate_var = tk.BooleanVar(value=False)

        # YouTube browser selection (cookies-from-browser)
        self.yt_browser_token_var = tk.StringVar(value="firefox")   # token yt-dlp
        self.yt_browser_label_var = tk.StringVar(value="Firefox")   # label UI

        # UI refs
        self._logo_img = None  # keep ref
        self.has_aac_at = False

        # Messages à afficher dans le journal après construction de l'UI
        self._startup_msgs: list[str] = []

        # Ligne demandée (première ligne du journal)
        self._startup_msgs.append("Sélectionner votre navigateur dans l'onglet option")

        # yt-dlp : détection binaire
        self.ytdlp = find_ytdlp_tools_first()
        self.ytdlp_path = self.ytdlp.path

        # Mode par défaut
        self.ytdlp_mode = "module" if ytdlp_module_available() else "binary"

        if getattr(sys, "frozen", False):
            self.ytdlp_mode = "binary"
            if not self.ytdlp_path:
                self._startup_msgs.append("❌ Mode packagé : yt-dlp.exe manquant dans tools/<platform>/")

        # --- Deno ---
        self.deno = find_deno_tools_first()
        self.deno_path = self.deno.path

        # Charge config -> vars
        self._apply_config_to_vars()

        # UI
        self._build_ui()

        # Affiche les messages de démarrage une fois que le widget de log (self.txt) existe
        for m in self._startup_msgs:
            self.log(m)
        self._startup_msgs.clear()

        # Détection encoder aac_at (macOS)
        self.has_aac_at = self._ffmpeg_has_encoder("aac_at")

        # Applique le thème (config ou aléatoire)
        self.apply_theme(self.theme_var.get().strip() or self.current_theme_name)

        # UI dépendant format
        self._update_advanced_controls()

        self._check_tools()
        self._refresh_url_buttons()

        # Onglet par défaut : Général
        self.nb.select(self.tab_general)

        # Save config on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- Config ----------------

    def _apply_config_to_vars(self) -> None:
        # Theme
        theme_name = self._config.get("theme_name")
        if isinstance(theme_name, str) and theme_name in THEMES:
            self.current_theme_name = theme_name
        else:
            self.current_theme_name = random.choice(list(THEMES.keys()))
        self.theme_var.set(self.current_theme_name)

        # Outdir
        outdir = self._config.get("outdir")
        if isinstance(outdir, str) and outdir.strip():
            self.outdir_var.set(outdir)

        # Format
        fmt = self._config.get("audio_format")
        if isinstance(fmt, str) and fmt in FORMAT_LABELS:
            self.audio_format_var.set(fmt)

        # Advanced settings
        mp3q = self._config.get("mp3_quality")
        if isinstance(mp3q, str) and mp3q in [str(i) for i in range(10)]:
            self.mp3_quality_var.set(mp3q)

        aacb = self._config.get("aac_bitrate")
        if isinstance(aacb, str) and aacb.endswith("k"):
            self.aac_bitrate_var.set(aacb)

        opusb = self._config.get("opus_bitrate")
        if isinstance(opusb, str) and opusb.endswith("k"):
            self.opus_bitrate_var.set(opusb)

        vorq = self._config.get("vorbis_quality")
        if isinstance(vorq, str) and vorq.isdigit():
            self.vorbis_quality_var.set(vorq)

        flac = self._config.get("flac_level")
        if isinstance(flac, str) and flac.isdigit():
            self.flac_level_var.set(flac)

        keep = self._config.get("keep_intermediate")
        if isinstance(keep, bool):
            self.keep_intermediate_var.set(keep)

        # YouTube browser
        token = self._config.get("yt_browser")
        if isinstance(token, str) and token in YTB_BROWSER_TOKEN_TO_LABEL:
            self.yt_browser_token_var.set(token)
            self.yt_browser_label_var.set(YTB_BROWSER_TOKEN_TO_LABEL[token])
        else:
            self.yt_browser_token_var.set("firefox")
            self.yt_browser_label_var.set("Firefox")

    def _snapshot_vars_to_config(self) -> dict:
        return {
            "theme_name": self.theme_var.get().strip(),
            "outdir": self.outdir_var.get().strip(),
            "audio_format": self.audio_format_var.get().strip(),
            "mp3_quality": self.mp3_quality_var.get().strip(),
            "aac_bitrate": self.aac_bitrate_var.get().strip(),
            "opus_bitrate": self.opus_bitrate_var.get().strip(),
            "vorbis_quality": self.vorbis_quality_var.get().strip(),
            "flac_level": self.flac_level_var.get().strip(),
            "keep_intermediate": bool(self.keep_intermediate_var.get()),
            "yt_browser": self.yt_browser_token_var.get().strip(),
        }

    def _save_config_now(self) -> None:
        self._config = self._snapshot_vars_to_config()
        _save_config(self._config)

    def _on_close(self) -> None:
        try:
            self._save_config_now()
        finally:
            self.destroy()

    # ---------------- UI ----------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 8}

        self._setup_styles()

        # Logo + Theme selector (hors onglets)
        self._build_logo_and_theme_selector()

        # Notebook (tabs)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.tab_general = ttk.Frame(self.nb)
        self.tab_options = ttk.Frame(self.nb)

        self.nb.add(self.tab_general, text="Général")
        self.nb.add(self.tab_options, text="Options")

        # ---- Contenu onglet Général ----

        # URLs block
        frm_urls = ttk.Frame(self.tab_general)
        frm_urls.pack(fill="x", **pad)

        ttk.Label(frm_urls, text="⬇️ Copiez l'URL ici:").grid(row=0, column=1, sticky="w")

        self.btn_add = ttk.Button(frm_urls, text="+", width=3, command=self.add_url_row)
        self.btn_add.grid(row=1, column=0, sticky="n", padx=(0, 8))

        self.btn_remove = ttk.Button(frm_urls, text="-", width=3, command=self.remove_url_row)
        self.btn_remove.grid(row=2, column=0, sticky="n", padx=(0, 8), pady=(6, 0))

        self.frm_url_entries = ttk.Frame(frm_urls)
        self.frm_url_entries.grid(row=1, column=1, rowspan=3, sticky="ew")
        frm_urls.columnconfigure(1, weight=1)

        self._rebuild_url_entries()

        # Output dir
        frm_mid = ttk.Frame(self.tab_general)
        frm_mid.pack(fill="x", **pad)

        ttk.Label(frm_mid, text="Dossier de sortie :").grid(row=0, column=0, sticky="w")
        self.out_ent = ttk.Entry(frm_mid, textvariable=self.outdir_var)
        self.out_ent.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        btn_browse = ttk.Button(frm_mid, text="Parcourir…", command=self.choose_outdir)
        btn_browse.grid(row=1, column=1, padx=(8, 0), sticky="ew")
        frm_mid.columnconfigure(0, weight=1)

        # Controls
        frm_ctrl = ttk.Frame(self.tab_general)
        frm_ctrl.pack(fill="x", **pad)

        self.btn_start = ttk.Button(frm_ctrl, text="Démarrer", command=self.start, style="KLM.Big.TButton")
        self.btn_start.grid(row=0, column=0, sticky="ew")

        self.btn_stop = ttk.Button(frm_ctrl, text="Arrêter", command=self.stop, state="disabled", style="KLM.Big.TButton")
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        self.btn_start.configure(width=14)
        self.btn_stop.configure(width=14)

        self.progress = ttk.Progressbar(frm_ctrl, mode="indeterminate")
        self.progress.grid(row=0, column=2, sticky="ew", padx=(14, 0))
        frm_ctrl.columnconfigure(0, weight=1)
        frm_ctrl.columnconfigure(1, weight=1)
        frm_ctrl.columnconfigure(2, weight=2)

        # Log
        self.frm_log = ttk.LabelFrame(self.tab_general, text="Journal")
        self.frm_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt = tk.Text(self.frm_log, wrap="word", height=17, borderwidth=0, highlightthickness=0)
        self.txt.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt.configure(state="disabled")

        # ---- Contenu onglet Options ----
        self._build_options_tab(self.tab_options)

    def _setup_styles(self):
        try:
            self.style.theme_use("clam")
        except Exception:
            try:
                self.style.theme_use("alt")
            except Exception:
                pass

        # Bigger buttons: padding increases height
        self.style.configure("KLM.Big.TButton", padding=(18, 18))

    def _build_logo_and_theme_selector(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "assets", "logo.png")

        top = ttk.Frame(self, height=150)
        top.pack(fill="x", padx=10, pady=(10, 4))
        top.pack_propagate(False)

        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=0)

        logo_holder = ttk.Frame(top, height=150)
        logo_holder.grid(row=0, column=0, sticky="nsew")
        logo_holder.pack_propagate(False)

        if os.path.isfile(logo_path):
            try:
                img = Image.open(logo_path).convert("RGBA")
                max_w, max_h = 680, 140
                w, h = img.size
                scale = min(max_w / w, max_h / h, 1.0)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img = img.resize((new_w, new_h), Image.LANCZOS)

                self._logo_img = ImageTk.PhotoImage(img)
                lbl = ttk.Label(logo_holder, image=self._logo_img)
                lbl.pack(anchor="center", pady=2)
            except Exception:
                ttk.Label(logo_holder, text="(Logo non affichable : problème PNG/Pillow)").pack(anchor="w")
        else:
            ttk.Label(logo_holder, text="").pack()

        theme_box_holder = ttk.Frame(top)
        theme_box_holder.grid(row=0, column=1, sticky="ne", padx=(10, 0), pady=(6, 0))

        self.cb_theme = ttk.Combobox(
            theme_box_holder,
            textvariable=self.theme_var,
            values=list(THEMES.keys()),
            state="readonly",
            width=28
        )
        self.cb_theme.pack(anchor="ne")
        self.cb_theme.bind("<<ComboboxSelected>>", self._on_theme_change)

    def _build_options_tab(self, parent):
        pad = {"padx": 10, "pady": 8}

                # ===== Bloc 1 : Navigateur YouTube =====
        frm_browser = ttk.LabelFrame(parent, text="YouTube : navigateur")
        frm_browser.pack(fill="x", **pad)

        row_browser = ttk.Frame(frm_browser)
        row_browser.pack(fill="x", padx=10, pady=(10, 10))

        ttk.Label(
            row_browser,
            text="Sélectionnez le navigateur avec lequel vous vous connectez à YouTube"
        ).pack(side="left")

        self.cb_yt_browser = ttk.Combobox(
            row_browser,
            state="readonly",
            width=14,
            values=YTB_BROWSER_LABELS,
            textvariable=self.yt_browser_label_var,
        )
        self.cb_yt_browser.pack(side="left", padx=(10, 0))

        # Assure cohérence label/token au démarrage
        cur_label = self.yt_browser_label_var.get().strip()
        if cur_label not in YTB_BROWSER_LABELS:
            cur_token = self.yt_browser_token_var.get().strip()
            self.yt_browser_label_var.set(YTB_BROWSER_TOKEN_TO_LABEL.get(cur_token, "Firefox"))

        self.cb_yt_browser.bind("<<ComboboxSelected>>", self._on_yt_browser_change)

        # ===== Bloc 2 : Format audio =====
        frm_audio = ttk.LabelFrame(parent, text="Audio : format de sortie")
        frm_audio.pack(fill="x", padx=10, pady=(0, 8))

        row_fmt = ttk.Frame(frm_audio)
        row_fmt.pack(fill="x", padx=10, pady=(10, 6))

        ttk.Label(row_fmt, text="Format audio :").pack(side="left")

        self.cb_format = ttk.Combobox(
            row_fmt,
            state="readonly",
            width=18,
            values=[FORMAT_LABELS[k] for k in FORMAT_KEYS_IN_ORDER]
        )
        self.cb_format.pack(side="left", padx=(10, 0))

        # Synchronise combobox UI <-> var interne
        self._format_label_to_key = {FORMAT_LABELS[k]: k for k in FORMAT_KEYS_IN_ORDER}
        self._format_key_to_label = {k: FORMAT_LABELS[k] for k in FORMAT_KEYS_IN_ORDER}
        self.cb_format.set(self._format_key_to_label[self.audio_format_var.get()])

        self.cb_format.bind("<<ComboboxSelected>>", self._on_format_change)

        # Keep intermediate (reste dans le bloc Audio)
        row_keep = ttk.Frame(frm_audio)
        row_keep.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Checkbutton(
            row_keep,
            text="Conserver le fichier intermédiaire (utile pour debug)",
            variable=self.keep_intermediate_var
        ).pack(side="left")


        # --- Bloc Réglage avancé (adaptatif) ---
        frm_adv = ttk.LabelFrame(parent, text="Réglage avancé")
        frm_adv.pack(fill="x", padx=10, pady=(0, 8))

        self.adv_desc = ttk.Label(frm_adv, text="")
        self.adv_desc.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        self.adv_holder = ttk.Frame(frm_adv)
        self.adv_holder.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        frm_adv.columnconfigure(0, weight=1)
        self.adv_holder.columnconfigure(0, weight=0)
        self.adv_holder.columnconfigure(1, weight=1)

        # Widgets avancés (un par format) : on affiche/cache selon le format
        # MP3
        self.w_mp3 = ttk.Frame(self.adv_holder)
        ttk.Label(self.w_mp3, text="Qualité MP3 (VBR) :").grid(row=0, column=0, sticky="w")
        self.cb_mp3q = ttk.Combobox(
            self.w_mp3,
            width=6,
            textvariable=self.mp3_quality_var,
            values=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
            state="readonly",
        )
        self.cb_mp3q.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(self.w_mp3, text="(0 = meilleure qualité, 9 = plus léger)").grid(row=0, column=2, sticky="w", padx=(10, 0))

        # AAC
        self.w_aac = ttk.Frame(self.adv_holder)
        ttk.Label(self.w_aac, text="Bitrate AAC :").grid(row=0, column=0, sticky="w")
        self.cb_aac = ttk.Combobox(
            self.w_aac,
            width=10,
            textvariable=self.aac_bitrate_var,
            values=["96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
        )
        self.cb_aac.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(self.w_aac, text="(recommandé : 192k)").grid(row=0, column=2, sticky="w", padx=(10, 0))

        # OPUS
        self.w_opus = ttk.Frame(self.adv_holder)
        ttk.Label(self.w_opus, text="Bitrate OPUS :").grid(row=0, column=0, sticky="w")
        self.cb_opus = ttk.Combobox(
            self.w_opus,
            width=10,
            textvariable=self.opus_bitrate_var,
            values=["64k", "96k", "128k", "160k", "192k"],
            state="readonly",
        )
        self.cb_opus.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(self.w_opus, text="(recommandé : 128k)").grid(row=0, column=2, sticky="w", padx=(10, 0))

        # OGG Vorbis
        self.w_ogg = ttk.Frame(self.adv_holder)
        ttk.Label(self.w_ogg, text="Qualité OGG (Vorbis) :").grid(row=0, column=0, sticky="w")
        self.cb_ogg = ttk.Combobox(
            self.w_ogg,
            width=6,
            textvariable=self.vorbis_quality_var,
            values=[str(i) for i in range(0, 11)],
            state="readonly",
        )
        self.cb_ogg.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(self.w_ogg, text="(0 = plus léger, 10 = meilleure qualité)").grid(row=0, column=2, sticky="w", padx=(10, 0))

        # FLAC
        self.w_flac = ttk.Frame(self.adv_holder)
        ttk.Label(self.w_flac, text="Compression FLAC :").grid(row=0, column=0, sticky="w")
        self.cb_flac = ttk.Combobox(
            self.w_flac,
            width=6,
            textvariable=self.flac_level_var,
            values=[str(i) for i in range(0, 9)],
            state="readonly",
        )
        self.cb_flac.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(self.w_flac, text="(impacte la taille/CPU, pas la qualité)").grid(row=0, column=2, sticky="w", padx=(10, 0))

        # WAV
        self.w_wav = ttk.Frame(self.adv_holder)
        ttk.Label(self.w_wav, text="WAV = non compressé (16-bit), pas de réglage.").grid(row=0, column=0, sticky="w")

        # Keep intermediate
        row_keep = ttk.Frame(frm_audio)
        row_keep.pack(fill="x", padx=10, pady=(2, 10))
        ttk.Checkbutton(
            row_keep,
            text="Conserver le fichier intermédiaire (utile pour debug)",
            variable=self.keep_intermediate_var
        ).pack(side="left")

        ttk.Frame(parent).pack(fill="both", expand=True)

    # -------------- Theme system --------------

    def _on_theme_change(self, _event=None):
        name = self.theme_var.get().strip()
        if name in THEMES:
            self.apply_theme(name)
            self._save_config_now()

    def apply_theme(self, theme_name: str):
        theme = THEMES.get(theme_name)
        if not theme:
            return

        self.current_theme_name = theme_name

        BG = theme["BG"]
        PANEL = theme["PANEL"]
        FIELD = theme["FIELD"]
        FG = theme["FG"]
        FIELD_FG = theme["FIELD_FG"]
        ACCENT = theme["ACCENT"]

        self.configure(bg=BG)

        self.style.configure("TFrame", background=BG)
        self.style.configure("TLabel", background=BG, foreground=FG)
        self.style.configure("TLabelframe", background=BG, foreground=FG)
        self.style.configure("TLabelframe.Label", background=BG, foreground=FG)

        self.style.configure("TEntry", fieldbackground=FIELD, foreground=FIELD_FG)
        self.style.configure("TCombobox", fieldbackground=FIELD, foreground=FIELD_FG)

        self.txt.configure(bg=FIELD, fg=FIELD_FG, insertbackground=ACCENT)

        try:
            self.style.configure("TNotebook", background=BG, borderwidth=0)
            self.style.configure("TNotebook.Tab", background=PANEL, foreground=FG, padding=(10, 6))
            self.style.map(
                "TNotebook.Tab",
                background=[("selected", BG)],
                foreground=[("selected", FG)]
            )
        except Exception:
            pass

    # -------------- YouTube browser UI ----------------

    def _on_yt_browser_change(self, _event=None):
        label = self.yt_browser_label_var.get().strip()
        token = YTB_BROWSER_LABEL_TO_TOKEN.get(label, "firefox")
        self.yt_browser_token_var.set(token)
        self._save_config_now()

    # -------------- Format UI ----------------

    def _on_format_change(self, _event=None):
        label = self.cb_format.get().strip()
        key = self._format_label_to_key.get(label, "mp3")
        self.audio_format_var.set(key)
        self._update_advanced_controls()
        self._save_config_now()

    def _update_advanced_controls(self):
        fmt = self.audio_format_var.get().strip().lower()

        # cache tout
        for w in (self.w_mp3, self.w_aac, self.w_opus, self.w_flac, self.w_ogg, self.w_wav):
            w.grid_forget()

        if fmt == "mp3":
            self.adv_desc.configure(text="MP3 : réglage VBR (qualité).")
            self.w_mp3.grid(row=0, column=0, sticky="w")
        elif fmt == "m4a":
            self.adv_desc.configure(text="M4A (AAC) : réglage du bitrate.")
            self.w_aac.grid(row=0, column=0, sticky="w")
        elif fmt == "opus":
            self.adv_desc.configure(text="OPUS : réglage du bitrate (excellent pour la voix).")
            self.w_opus.grid(row=0, column=0, sticky="w")
        elif fmt == "flac":
            self.adv_desc.configure(text="FLAC : compression sans perte (niveau).")
            self.w_flac.grid(row=0, column=0, sticky="w")
        elif fmt == "ogg":
            self.adv_desc.configure(text="OGG (Vorbis) : réglage de la qualité.")
            self.w_ogg.grid(row=0, column=0, sticky="w")
        elif fmt == "wav":
            self.adv_desc.configure(text="WAV : sortie brute (non compressée).")
            self.w_wav.grid(row=0, column=0, sticky="w")
        else:
            self.adv_desc.configure(text="Réglage avancé :")
            self.w_mp3.grid(row=0, column=0, sticky="w")

    # ---------------- URL rows ----------------

    def _rebuild_url_entries(self):
        for child in self.frm_url_entries.winfo_children():
            child.destroy()
        self.url_entries.clear()

        for i, var in enumerate(self.url_vars):
            ent = ttk.Entry(self.frm_url_entries, textvariable=var)
            ent.grid(row=i, column=0, sticky="ew", pady=(4 if i == 0 else 6, 0))
            self.url_entries.append(ent)

        self.frm_url_entries.columnconfigure(0, weight=1)

    def _refresh_url_buttons(self):
        n = len(self.url_vars)
        self.btn_add.configure(state=("normal" if n < MAX_URLS else "disabled"))
        self.btn_remove.configure(state=("normal" if n > 1 else "disabled"))

    def add_url_row(self):
        if len(self.url_vars) >= MAX_URLS:
            return
        self.url_vars.append(tk.StringVar())
        self._rebuild_url_entries()
        self._refresh_url_buttons()

    def remove_url_row(self):
        if len(self.url_vars) <= 1:
            return
        self.url_vars.pop()
        self._rebuild_url_entries()
        self._refresh_url_buttons()

    # -------------- Helpers --------------

    def choose_outdir(self):
        """Choisit le dossier de sortie (sans rajouter de sous-dossier automatique)."""
        d = filedialog.askdirectory(
            initialdir=self.outdir_var.get() or os.path.expanduser("~")
        )
        if d:
            self.outdir_var.set(d)
            self._save_config_now()

    def log(self, msg: str):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _check_tools(self):
        missing = []

        # Deno : runtime JavaScript pour YouTube (JS challenges)
        if not getattr(self, "deno_path", None):
            self.log("ℹ️ Deno absent : certaines vidéos YouTube peuvent demander un challenge JS (mode dégradé)")
        else:
            self.log("📦 Deno embarqué : support YouTube (JS challenge)")

        # ffmpeg/ffprobe via PATH ou tools/
        if not self.ffmpeg_path:
            missing.append("ffmpeg")
        if not self.ffprobe_path:
            missing.append("ffprobe")

        # yt-dlp : module Python (recommandé) ou binaire (secours)
        ytdlp_ok = (getattr(self, "ytdlp_mode", "binary") == "module") or bool(getattr(self, "ytdlp_path", None))
        if not ytdlp_ok:
            missing.append("yt-dlp")

        if missing:
            self.log("⚠️ Outils manquants : " + ", ".join(missing))
            self.log("   - Installez le module Python yt-dlp (recommandé) : python -m pip install -U yt-dlp")
            self.log("   - (secours) installez le binaire yt-dlp dans le PATH")
            self.log("   - Installez ffmpeg/ffprobe OU mettez-les dans tools/<platform>/")
        else:
            # info sur la source
            if getattr(self, "ff", None) and self.ff.source == "TOOLS":
                self.log("📦 ffmpeg/ffprobe embarqués : utilisés depuis tools/")
            else:
                self.log("🧭 ffmpeg/ffprobe : trouvés dans le PATH")
            if getattr(self, "ytdlp_mode", "binary") == "module":
                self.log("🐍 yt-dlp : module Python (yt_dlp)")
            else:
                if getattr(self, "ytdlp", None) and self.ytdlp.source == "TOOLS":
                    self.log("📦 yt-dlp embarqué : utilisé depuis tools/")
                else:
                    self.log("🧭 yt-dlp : trouvé dans le PATH")

            self.log("✅ Outils détectés : yt-dlp, ffmpeg, ffprobe.")

        self.log(f"📁 Dossier de sortie actuel : {self.outdir_var.get()}")

    def _ffmpeg_has_encoder(self, encoder_name: str) -> bool:
        """Retourne True si l'encodeur est listé par ffmpeg -encoders."""
        if not self.ffmpeg_path:
            return False
        try:
            out = subprocess.check_output(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                text=True,
                stderr=subprocess.STDOUT,
            )
            return encoder_name in out
        except Exception:
            return False

    # ----------------- Run logic -----------------

    def start(self):
        # Toujours revenir sur Général quand on démarre (pour voir le journal)
        self.nb.select(self.tab_general)

        base_out = self.outdir_var.get().strip()
        if not base_out:
            messagebox.showwarning("Dossier manquant", "Veuillez choisir un dossier de sortie.")
            return

        outdir = base_out

        urls = [v.get().strip() for v in self.url_vars]
        urls = [u for u in urls if u]

        if not urls:
            messagebox.showwarning("URL manquante", "Veuillez saisir au moins une URL YouTube ou Twitch.")
            return

        if not os.path.isdir(outdir):
            try:
                os.makedirs(outdir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Erreur dossier", f"Impossible de créer le dossier :\n{outdir}\n\n{e}")
                return

        weird = [u for u in urls if not (is_twitch(u) or is_youtube(u))]
        if weird:
            if not messagebox.askyesno(
                "URL(s) non reconnue(s)",
                "Au moins une URL ne ressemble pas à YouTube ou Twitch.\n"
                "Voulez-vous tenter quand même ?"
            ):
                return

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.stop_flag.clear()
        self.progress.start(10)

        self._save_config_now()

        self.worker_thread = threading.Thread(target=self._worker_queue, args=(urls, outdir), daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.stop_flag.set()
        self.log("⏹️ Arrêt demandé… (le processus va s’interrompre)")

    def _finish(self, ok: bool, msg: str):
        self.progress.stop()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        if ok:
            self.log("✅ Terminé : " + msg)
            messagebox.showinfo("Terminé", msg)
        else:
            self.log("❌ Erreur : " + msg)
            messagebox.showerror("Erreur", msg)

    def _worker_queue(self, urls: list[str], outdir: str):
        try:
            fmt = self.audio_format_var.get().strip().lower()
            keep_inter = self.keep_intermediate_var.get()

            for idx, url in enumerate(urls, start=1):
                if self.stop_flag.is_set():
                    self.after(0, self._finish, False, "Arrêté par l’utilisateur.")
                    return

                self.log("")
                self.log(f"==================== {idx}/{len(urls)} ====================")
                self.log(f"URL : {url}")

                if is_twitch(url):
                    self.log("🎯 Plateforme détectée : Twitch (VOD) — téléchargement Audio_Only")
                    ok, final_msg = self._pipeline_download_and_convert(url, outdir, fmt, keep_inter, platform="twitch")
                else:
                    self.log("🎯 Plateforme détectée : YouTube (ou autre) — téléchargement bestaudio")
                    ok, final_msg = self._pipeline_download_and_convert(url, outdir, fmt, keep_inter, platform="youtube")

                if not ok:
                    self.after(0, self._finish, False, final_msg)
                    return

            self.after(0, self._finish, True, f"{len(urls)} URL traitée(s) avec succès.")

        except Exception as e:
            self.after(0, self._finish, False, str(e))

    # -------------- Download + Convert (unifié) --------------

    def _pipeline_download_and_convert(self, url: str, outdir: str, fmt: str, keep_inter: bool, platform: str):
        """
        Télécharge un fichier audio (intermédiaire) avec yt-dlp, puis convertit avec ffmpeg.
        """
        outtmpl = os.path.join(outdir, "%(title).200s [%(id)s].%(ext)s")

        ok, downloaded_path = self._download_audio(url, outtmpl, platform=platform)
        if not ok:
            return False, downloaded_path  # message d'erreur

        self.log(f"📦 Intermédiaire : {downloaded_path}")

        ok2, msg_or_final = self._convert_audio(downloaded_path, fmt)
        if not ok2:
            return False, msg_or_final

        final_path = msg_or_final
        self.log(f"🎧 Sortie : {final_path}")

        if not keep_inter:
            self._safe_remove(downloaded_path)

        return True, "OK"

    def _download_audio(self, url: str, outtmpl: str, platform: str):
        """
        Retourne (ok, path_ou_message).
        """
        if platform == "twitch":
            fmt_sel = "Audio_Only"
        else:
            fmt_sel = "bestaudio[protocol!*=m3u8]/bestaudio/best"

        # For YouTube, on force le mode binaire (plus fiable pour cookies-from-browser + JS challenges)
        if platform == "youtube":
            self.ytdlp_mode = "binary"

        # lazy resolve yt-dlp path when switching to binary at runtime
        if self.ytdlp_mode == "binary" and not getattr(self, "ytdlp_path", None):
            self.ytdlp = find_ytdlp_tools_first()
            self.ytdlp_path = self.ytdlp.path

        if getattr(self, "ytdlp_mode", "binary") == "module":
            try:
                import yt_dlp
                from yt_dlp.utils import DownloadCancelled
            except Exception:
                self.ytdlp_mode = "binary"

        downloaded_path = None

        if getattr(self, "ytdlp_mode", "binary") == "module":
            self.log("▶️ yt-dlp (module) : téléchargement…")

            def hook(d):
                nonlocal downloaded_path
                if getattr(self, 'stop_flag', None) is not None and self.stop_flag.is_set():
                    raise DownloadCancelled()

                status = d.get("status")
                if status == "downloading":
                    pct = d.get("_percent_str")
                    spd = d.get("_speed_str")
                    eta = d.get("_eta_str")
                    msg = "⬇️"
                    if pct:
                        msg += f" {pct}"
                    if spd:
                        msg += f" {spd}"
                    if eta:
                        msg += f" ETA {eta}"
                    self.log(msg)

                elif status == "finished":
                    downloaded_path = d.get("filename")
                    if downloaded_path:
                        self.log(f"✅ Téléchargé : {downloaded_path}")

            class _YDLLogger:
                def __init__(self, log_fn):
                    self._log = log_fn
                def debug(self, msg):
                    if msg and ("[download]" in msg or "Destination" in msg or "Merging" in msg):
                        self._log(msg)
                def warning(self, msg):
                    if msg:
                        self._log("⚠️ " + msg)
                def error(self, msg):
                    if msg:
                        self._log("❌ " + msg)

            ydl_opts = {
                "format": fmt_sel,
                "outtmpl": outtmpl,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [hook],
                "logger": _YDLLogger(self.log),
            }

            # NB: Pour YouTube, on passe en binaire (cookies-from-browser + deno).
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    rc = ydl.download([url])
                if rc != 0:
                    return False, f"yt-dlp (module) a échoué (code {rc})."
            except DownloadCancelled:
                return False, "Arrêté par l’utilisateur."
            except Exception as e:
                return False, f"yt-dlp (module) a échoué : {e}"

        else:
            frozen = getattr(sys, "frozen", False)
            if frozen and not getattr(self, "ytdlp_path", None):
                return False, "Mode packagé : yt-dlp.exe introuvable. Placez-le dans tools/<platform>/ (ex: tools/windows-x86_64/yt-dlp.exe)."

            cmd = [self.ytdlp_path, "--ignore-config"] if getattr(self, "ytdlp_path", None) else [sys.executable, "-m", "yt_dlp", "--ignore-config"]

            cmd += [
                url,
                "-f", fmt_sel,
                "-o", outtmpl,
                "--newline",
                "--no-warnings",
            ]

            if platform == "youtube":
                # Cookies YouTube : lecture depuis le navigateur (selon choix utilisateur)
                token = self.yt_browser_token_var.get().strip() or "firefox"
                label = YTB_BROWSER_TOKEN_TO_LABEL.get(token, "Firefox")
                cmd += ["--cookies-from-browser", token]
                self.log(f"🍪 Cookies YouTube : lecture depuis le navigateur ({label})")

                # JS challenges YouTube : nécessite un runtime JS (deno)
                if getattr(self, "deno_path", None):
                    cmd += ["--js-runtimes", f"deno:{self.deno_path}", "--remote-components", "ejs:github"]

            self.log("▶️ yt-dlp (binaire) : " + " ".join(cmd))

            dest_re = re.compile(r"Destination:\s(.+)$")

            def on_line(line: str):
                nonlocal downloaded_path
                self.log(line)
                m = dest_re.search(line)
                if m:
                    downloaded_path = m.group(1).strip()

            rc = run_subprocess(cmd, on_line, self.stop_flag)
            if rc == 130:
                return False, "Arrêté par l’utilisateur."
            if rc != 0:
                return False, f"yt-dlp a échoué (code {rc})."

        # fallback : si destination non détectée, on cherche le fichier le plus récent dans outdir
        if not downloaded_path or not os.path.isfile(downloaded_path):
            folder = os.path.dirname(outtmpl)
            if not os.path.isdir(folder):
                folder = os.path.dirname(folder)

            candidates = []
            try:
                for name in os.listdir(folder):
                    if any(name.lower().endswith(ext) for ext in (".m4a", ".mp4", ".webm", ".mkv", ".mp3", ".aac", ".ogg", ".opus")):
                        p = os.path.join(folder, name)
                        candidates.append((os.path.getmtime(p), p))
            except Exception:
                candidates = []

            if candidates:
                downloaded_path = sorted(candidates, reverse=True)[0][1]

        if not downloaded_path or not os.path.isfile(downloaded_path):
            return False, "Impossible de trouver le fichier téléchargé."

        return True, downloaded_path

    def _convert_audio(self, in_path: str, fmt: str):
        """
        Convertit in_path -> format cible.
        Retourne (ok, out_path_ou_message).
        """
        base_name, _ext = os.path.splitext(in_path)

        if fmt == "mp3":
            out_path = base_name + ".mp3"
            codec = "libmp3lame"
            args = ["-q:a", self.mp3_quality_var.get().strip()]

        elif fmt == "m4a":
            out_path = base_name + ".m4a"
            codec = "aac_at" if (sys.platform == "darwin" and self.has_aac_at) else "aac"
            bitrate = self.aac_bitrate_var.get().strip()
            args = ["-b:a", bitrate]

        elif fmt == "opus":
            out_path = base_name + ".opus"
            codec = "libopus"
            bitrate = self.opus_bitrate_var.get().strip()
            args = ["-b:a", bitrate]

        elif fmt == "flac":
            out_path = base_name + ".flac"
            codec = "flac"
            level = self.flac_level_var.get().strip()
            args = ["-compression_level", level]

        elif fmt == "ogg":
            out_path = base_name + ".ogg"
            codec = "libvorbis"
            q = self.vorbis_quality_var.get().strip()
            args = ["-q:a", q]

        elif fmt == "wav":
            out_path = base_name + ".wav"
            codec = "pcm_s16le"
            args = []

        else:
            return False, f"Format inconnu : {fmt}"

        cmd_ff = [
            self.ffmpeg_path, "-y",
            "-i", in_path,
            "-map", "0:a:0",
            "-vn",
            "-c:a", codec,
            *args,
            out_path
        ]

        self.log("▶️ ffmpeg : " + " ".join(cmd_ff))
        rc = run_subprocess(cmd_ff, self.log, self.stop_flag)

        if rc == 0 and os.path.isfile(out_path):
            return True, out_path
        if rc == 130:
            return False, "Arrêté par l’utilisateur."
        return False, f"ffmpeg a échoué (code {rc})."

    def _safe_remove(self, path: str):
        try:
            os.remove(path)
            self.log("🧹 Intermédiaire supprimé.")
        except Exception:
            pass


if __name__ == "__main__":
    app = App()
    app.mainloop()
