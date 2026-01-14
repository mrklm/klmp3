#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KLmp3 - Extracteur audio YouTube/Twitch (Tkinter)
- YouTube : yt-dlp -x --audio-format mp3
- Twitch VOD : yt-dlp -f Audio_Only (mp4) puis ffmpeg (genpts) mp4 -> mp3
Notes:
- Nécessite: yt-dlp (pip) + ffmpeg + ffprobe accessibles (PATH)
- Interface en français avec vouvoiement (préférence utilisateur)
"""

import os
import re
import sys
import shutil
import threading
import subprocess
import random
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Pillow (pour redimensionner proprement le logo)
from PIL import Image, ImageTk


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
    # ===== Thèmes Pouêt-Pouêt (mais distincts) =====
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


def is_twitch(url: str) -> bool:
    return "twitch.tv" in url.lower()


def is_youtube(url: str) -> bool:
    u = url.lower()
    return ("youtube.com" in u) or ("youtu.be" in u)


def which_or_none(cmd: str) -> str | None:
    return shutil.which(cmd)


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
    """~/Desktop/KLmp3-AAMMJJ (tout en vrac dedans)"""
    base = os.path.join(os.path.expanduser("~"), "Desktop")
    yymmdd = datetime.now().strftime("%y%m%d")  # AAMMJJ
    return os.path.join(base, f"KLmp3-{yymmdd}")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KLmp3 - v1.1")
        self.geometry("820x620")
        self.minsize(780, 560)

        # Theme
        self.theme_var = tk.StringVar()
        self.current_theme_name = random.choice(list(THEMES.keys()))
        self.theme_var.set(self.current_theme_name)

        # State
        self.worker_thread: threading.Thread | None = None
        self.stop_flag = threading.Event()

        # URL queue (up to 10 entries)
        self.url_vars: list[tk.StringVar] = [tk.StringVar()]
        self.url_entries: list[ttk.Entry] = []

        # UI vars
        self.outdir_var = tk.StringVar(value=default_outdir())
        self.audio_format_var = tk.StringVar(value="mp3")  # mp3 or m4a
        self.mp3_quality_var = tk.StringVar(value="0")     # 0 best, 2..9 smaller
        self.keep_intermediate_var = tk.BooleanVar(value=False)

        # UI refs
        self._logo_img = None  # keep ref
        self.style = ttk.Style()

        self._build_ui()
        self.apply_theme(self.current_theme_name)  # applique le thème aléatoire au démarrage
        self._check_tools()
        self._refresh_url_buttons()

    # ---------------- UI ----------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 8}

        self._setup_styles()

        # Logo (top) + Theme selector (top right)
        self._build_logo_and_theme_selector()

        # URLs block
        frm_urls = ttk.Frame(self)
        frm_urls.pack(fill="x", **pad)

        self.lbl_urls = ttk.Label(frm_urls, text="URL YouTube ou Twitch (VOD) :")
        self.lbl_urls.grid(row=0, column=1, sticky="w")

        # + / - buttons (left of url lines)
        self.btn_add = ttk.Button(frm_urls, text="+", width=3, command=self.add_url_row)
        self.btn_add.grid(row=1, column=0, sticky="n", padx=(0, 8))

        self.btn_remove = ttk.Button(frm_urls, text="-", width=3, command=self.remove_url_row)
        self.btn_remove.grid(row=2, column=0, sticky="n", padx=(0, 8), pady=(6, 0))

        # URL entries container (right)
        self.frm_url_entries = ttk.Frame(frm_urls)
        self.frm_url_entries.grid(row=1, column=1, rowspan=3, sticky="ew")
        frm_urls.columnconfigure(1, weight=1)

        self._rebuild_url_entries()

        # Output dir
        frm_mid = ttk.Frame(self)
        frm_mid.pack(fill="x", **pad)

        self.lbl_out = ttk.Label(frm_mid, text="Dossier de sortie :")
        self.lbl_out.grid(row=0, column=0, sticky="w")

        self.out_ent = ttk.Entry(frm_mid, textvariable=self.outdir_var)
        self.out_ent.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        btn_browse = ttk.Button(frm_mid, text="Parcourir…", command=self.choose_outdir)
        btn_browse.grid(row=1, column=1, padx=(8, 0), sticky="ew")
        frm_mid.columnconfigure(0, weight=1)

        # Options
        self.frm_opts = ttk.LabelFrame(self, text="Options")
        self.frm_opts.pack(fill="x", **pad)

        fmt_row = ttk.Frame(self.frm_opts)
        fmt_row.pack(fill="x", padx=10, pady=(8, 2))

        self.lbl_fmt = ttk.Label(fmt_row, text="Format audio :")
        self.lbl_fmt.pack(side="left")

        self.rb_mp3 = ttk.Radiobutton(fmt_row, text="MP3", value="mp3", variable=self.audio_format_var)
        self.rb_mp3.pack(side="left", padx=(10, 0))

        self.rb_m4a = ttk.Radiobutton(fmt_row, text="M4A (sans perte / recommandé)", value="m4a", variable=self.audio_format_var)
        self.rb_m4a.pack(side="left", padx=(10, 0))

        q_row = ttk.Frame(self.frm_opts)
        q_row.pack(fill="x", padx=10, pady=2)

        self.lbl_q = ttk.Label(q_row, text="Qualité MP3 (VBR) :")
        self.lbl_q.pack(side="left")

        self.cb_q = ttk.Combobox(
            q_row,
            width=6,
            textvariable=self.mp3_quality_var,
            values=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
            state="readonly",
        )
        self.cb_q.pack(side="left", padx=(10, 0))

        self.lbl_q_hint = ttk.Label(q_row, text="(0 = meilleure qualité, 9 = plus léger)")
        self.lbl_q_hint.pack(side="left", padx=(10, 0))

        k_row = ttk.Frame(self.frm_opts)
        k_row.pack(fill="x", padx=10, pady=(2, 8))
        self.chk_keep = ttk.Checkbutton(
            k_row,
            text="Conserver le fichier intermédiaire (utile pour Twitch / debug)",
            variable=self.keep_intermediate_var
        )
        self.chk_keep.pack(side="left")

        # Controls (bigger buttons)
        frm_ctrl = ttk.Frame(self)
        frm_ctrl.pack(fill="x", **pad)

        self.btn_start = ttk.Button(frm_ctrl, text="Démarrer", command=self.start, style="KLM.Big.TButton")
        self.btn_start.grid(row=0, column=0, sticky="ew")

        self.btn_stop = ttk.Button(frm_ctrl, text="Arrêter", command=self.stop, state="disabled", style="KLM.Big.TButton")
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        # Make same width
        frm_ctrl.columnconfigure(0, weight=0)
        frm_ctrl.columnconfigure(1, weight=0)
        self.btn_start.configure(width=14)
        self.btn_stop.configure(width=14)

        self.progress = ttk.Progressbar(frm_ctrl, mode="indeterminate")
        self.progress.grid(row=0, column=2, sticky="ew", padx=(14, 0))
        frm_ctrl.columnconfigure(2, weight=1)

        # Log
        self.frm_log = ttk.LabelFrame(self, text="Journal")
        self.frm_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # +5 lignes : height=17 (au lieu de 12)
        self.txt = tk.Text(self.frm_log, wrap="word", height=17, borderwidth=0, highlightthickness=0)
        self.txt.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt.configure(state="disabled")

    def _setup_styles(self):
        try:
            self.style.theme_use(self.style.theme_use())
        except Exception:
            pass
        # Bigger buttons: padding increases height
        self.style.configure("KLM.Big.TButton", padding=(14, 14))

    def _build_logo_and_theme_selector(self):
        # Try to load assets/logo.png relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "assets", "logo.png")

        # Bandeau top : logo centré + combobox à droite
        top = ttk.Frame(self, height=150)
        top.pack(fill="x", padx=10, pady=(10, 4))
        top.pack_propagate(False)

        # Layout en grid pour centrer le logo tout en gardant un widget à droite
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=0)

        # Logo container (col 0)
        logo_holder = ttk.Frame(top, height=150)
        logo_holder.grid(row=0, column=0, sticky="nsew")
        logo_holder.pack_propagate(False)

        if os.path.isfile(logo_path):
            try:
                img = Image.open(logo_path).convert("RGBA")

                max_w = 680
                max_h = 140

                w, h = img.size
                scale = min(max_w / w, max_h / h, 1.0)  # jamais agrandir

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

        # Theme selector (col 1, en haut à droite, sans titre)
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

    # -------------- Theme system --------------

    def _on_theme_change(self, _event=None):
        name = self.theme_var.get().strip()
        if name in THEMES:
            self.apply_theme(name)

    def apply_theme(self, theme_name: str):
        """Applique couleurs sur les frames/labels/entries/text. Simple et efficace."""
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

        # Fond global (tk)
        self.configure(bg=BG)

        # ttk styles
        # Frame / LabelFrame / Label
        self.style.configure("TFrame", background=BG)
        self.style.configure("TLabel", background=BG, foreground=FG)
        self.style.configure("TLabelframe", background=BG, foreground=FG)
        self.style.configure("TLabelframe.Label", background=BG, foreground=FG)

        # Boutons
        self.style.configure("TButton", padding=(10, 6))
        self.style.map("TButton",
                       foreground=[("disabled", "#888888")],
                       background=[("active", PANEL)])

        # Gros boutons : accent subtil via relief/padding (les couleurs de ttk buttons varient selon OS)
        self.style.configure("KLM.Big.TButton", padding=(14, 14))

        # Champs (Entry, Combobox)
        self.style.configure("TEntry", fieldbackground=FIELD, foreground=FIELD_FG)
        self.style.configure("TCombobox", fieldbackground=FIELD, foreground=FIELD_FG)

        # Text widget (tk) : couleurs directes
        self.txt.configure(bg=FIELD, fg=FIELD_FG, insertbackground=ACCENT)

        # LabelFrame "Journal" : tweak visuel (selon thème)
        # Pour ttk, on reste avec les styles. L'accent est utilisé pour la sélection / curseur.
        try:
            self.txt.tag_configure("accent", foreground=ACCENT)
        except Exception:
            pass

    # ---------------- URL rows ----------------

    def _rebuild_url_entries(self):
        # Clear container
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
        d = filedialog.askdirectory(initialdir=self.outdir_var.get() or os.path.expanduser("~"))
        if d:
            # On force le nom final "KLmp3-AAMMJJ" dans le dossier choisi
            yymmdd = datetime.now().strftime("%y%m%d")
            self.outdir_var.set(os.path.join(d, f"KLmp3-{yymmdd}"))

    def log(self, msg: str):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _check_tools(self):
        missing = []
        if which_or_none("ffmpeg") is None:
            missing.append("ffmpeg")
        if which_or_none("ffprobe") is None:
            missing.append("ffprobe")

        try:
            import yt_dlp  # noqa: F401
        except Exception:
            missing.append("yt-dlp (module python)")

        if missing:
            self.log("⚠️ Outils manquants : " + ", ".join(missing))
            self.log("   - Installez yt-dlp : python3 -m pip install --user -U yt-dlp")
            self.log("   - Assurez-vous que ffmpeg + ffprobe sont accessibles via le PATH (/usr/local/bin).")
        else:
            self.log("✅ Outils détectés : yt-dlp (module), ffmpeg, ffprobe.")
        self.log(f"📁 Dossier de sortie par défaut : {self.outdir_var.get()}")

    # ----------------- Run logic -----------------

    def start(self):
        # IMPORTANT : on force toujours le dossier final "KLmp3-AAMMJJ"
        base_out = self.outdir_var.get().strip()
        if not base_out:
            messagebox.showwarning("Dossier manquant", "Veuillez choisir un dossier de sortie.")
            return

        # Si l'utilisateur a choisi un dossier "parent", on assure le suffixe KLmp3-AAMMJJ
        # Si base_out pointe déjà sur KLmp3-YYMMDD, on garde.
        yymmdd = datetime.now().strftime("%y%m%d")
        expected_suffix = f"KLmp3-{yymmdd}"

        outdir = base_out
        if os.path.basename(os.path.normpath(base_out)) != expected_suffix:
            outdir = os.path.join(base_out, expected_suffix)
            self.outdir_var.set(outdir)

        # Build queue
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

        # Basic validation prompt if strange URLs exist
        weird = [u for u in urls if not (is_twitch(u) or is_youtube(u))]
        if weird:
            if not messagebox.askyesno(
                "URL(s) non reconnue(s)",
                "Au moins une URL ne ressemble pas à YouTube ou Twitch.\n"
                "Voulez-vous tenter quand même ?"
            ):
                return

        # Disable UI
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.stop_flag.clear()
        self.progress.start(10)

        # Start worker (queue)
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
            q = self.mp3_quality_var.get().strip()
            keep_inter = self.keep_intermediate_var.get()

            # Tout en vrac dans outdir (pas de sous-dossiers)
            outtmpl = os.path.join(outdir, "%(title).200s [%(id)s].%(ext)s")

            for idx, url in enumerate(urls, start=1):
                if self.stop_flag.is_set():
                    self.after(0, self._finish, False, "Arrêté par l’utilisateur.")
                    return

                self.log("")
                self.log(f"==================== {idx}/{len(urls)} ====================")
                self.log(f"URL : {url}")

                if is_twitch(url):
                    self.log("🎯 Plateforme détectée : Twitch (VOD) — stratégie 'Audio_Only puis conversion locale'")
                    ok, final_msg = self._twitch_pipeline(url, outtmpl, fmt, q, keep_inter)
                else:
                    self.log("🎯 Plateforme détectée : YouTube (ou autre) — stratégie extraction directe")
                    ok, final_msg = self._youtube_pipeline(url, outtmpl, fmt, q)

                if not ok:
                    self.after(0, self._finish, False, final_msg)
                    return

            self.after(0, self._finish, True, f"{len(urls)} URL traitée(s) avec succès.")

        except Exception as e:
            self.after(0, self._finish, False, str(e))

    def _youtube_pipeline(self, url: str, outtmpl: str, fmt: str, q: str):
        base_cmd = [
            sys.executable, "-m", "yt_dlp", url,
            "-o", outtmpl,
            "--newline",
            "--no-warnings"
        ]

        if fmt == "mp3":
            cmd = base_cmd + ["-x", "--audio-format", "mp3", "--audio-quality", q]
        else:
            cmd = base_cmd + ["-x", "--audio-format", "m4a"]

        self.log("▶️ yt-dlp : " + " ".join(cmd))
        rc = run_subprocess(cmd, self.log, self.stop_flag)
        if rc == 0:
            return True, "Audio récupéré avec succès."
        if rc == 130:
            return False, "Arrêté par l’utilisateur."
        return False, f"yt-dlp a échoué (code {rc})."

    def _twitch_pipeline(self, url: str, outtmpl: str, fmt: str, q: str, keep_inter: bool):
        cmd_dl = [
            sys.executable, "-m", "yt_dlp", url,
            "-f", "Audio_Only",
            "-o", outtmpl,
            "--newline",
            "--no-warnings"
        ]

        self.log("▶️ yt-dlp (Audio_Only) : " + " ".join(cmd_dl))
        downloaded_path = None
        dest_re = re.compile(r"Destination:\s(.+)$")

        def on_line(line: str):
            nonlocal downloaded_path
            self.log(line)
            m = dest_re.search(line)
            if m:
                downloaded_path = m.group(1).strip()

        rc = run_subprocess(cmd_dl, on_line, self.stop_flag)
        if rc != 0:
            if rc == 130:
                return False, "Arrêté par l’utilisateur."
            return False, f"Téléchargement Twitch échoué (code {rc})."

        if not downloaded_path or not os.path.isfile(downloaded_path):
            self.log("⚠️ Chemin de destination non détecté — recherche du fichier le plus récent…")
            folder = os.path.dirname(outtmpl)
            candidates = []
            for name in os.listdir(folder):
                if name.lower().endswith((".mp4", ".m4a", ".webm", ".mkv")):
                    p = os.path.join(folder, name)
                    candidates.append((os.path.getmtime(p), p))
            if candidates:
                downloaded_path = sorted(candidates, reverse=True)[0][1]

        if not downloaded_path or not os.path.isfile(downloaded_path):
            return False, "Impossible de trouver le fichier téléchargé (Audio_Only)."

        self.log(f"📦 Fichier intermédiaire : {downloaded_path}")

        base_name, _ext = os.path.splitext(downloaded_path)

        if fmt == "m4a":
            out_audio = base_name + ".m4a"
            cmd_ff = [
                "ffmpeg", "-y", "-fflags", "+genpts",
                "-i", downloaded_path,
                "-map", "0:a", "-vn",
                "-c:a", "copy",
                out_audio
            ]
            self.log("▶️ ffmpeg (mp4→m4a sans perte) : " + " ".join(cmd_ff))
            rc2 = run_subprocess(cmd_ff, self.log, self.stop_flag)
            if rc2 == 0:
                if not keep_inter:
                    self._safe_remove(downloaded_path)
                return True, f"Audio prêt : {out_audio}"
            if rc2 == 130:
                return False, "Arrêté par l’utilisateur."
            return False, f"ffmpeg a échoué (code {rc2})."

        out_audio = base_name + ".mp3"
        cmd_ff = [
            "ffmpeg", "-y", "-fflags", "+genpts",
            "-i", downloaded_path,
            "-map", "0:a", "-vn",
            "-c:a", "libmp3lame",
            "-q:a", q,
            out_audio
        ]
        self.log("▶️ ffmpeg (mp4→mp3) : " + " ".join(cmd_ff))
        rc2 = run_subprocess(cmd_ff, self.log, self.stop_flag)
        if rc2 == 0:
            if not keep_inter:
                self._safe_remove(downloaded_path)
            return True, f"MP3 prêt : {out_audio}"
        if rc2 == 130:
            return False, "Arrêté par l’utilisateur."
        return False, f"ffmpeg a échoué (code {rc2})."

    def _safe_remove(self, path: str):
        try:
            os.remove(path)
            self.log("🧹 Intermédiaire supprimé.")
        except Exception:
            pass


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        print("Erreur fatale :", e)
        raise
