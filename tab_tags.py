# tab_tags.py
# -*- coding: utf-8 -*-

import os
import threading
import tempfile
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk, filedialog, messagebox


SUPPORTED_EXTS = (".mp3", ".m4a", ".mp4", ".flac", ".ogg", ".opus", ".wav", ".mkv", ".webm", ".aac")


def _is_audio_file(path: str) -> bool:
    return bool(path) and os.path.isfile(path) and path.lower().endswith(SUPPORTED_EXTS)


def _safe_makedirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _default_outdir_for_files(files: list[str]) -> str:
    if not files:
        return os.path.join(os.path.expanduser("~"), "klmp3-tag")
    first_dir = os.path.dirname(os.path.abspath(files[0]))
    return first_dir + "-tag"


def _dedupe_outpath(outdir: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    cand = os.path.join(outdir, filename)
    if not os.path.exists(cand):
        return cand
    i = 1
    while True:
        cand = os.path.join(outdir, f"{base} ({i}){ext}")
        if not os.path.exists(cand):
            return cand
        i += 1


def _cover_supported_for(path: str) -> bool:
    low = path.lower()
    return low.endswith((".mp3", ".m4a", ".mp4", ".flac"))


def _load_and_prepare_cover(cover_path: str, make_square: bool, max_size: int = 1000) -> str:
    if not cover_path:
        return ""

    try:
        from PIL import Image
    except Exception:
        return cover_path

    try:
        img = Image.open(cover_path).convert("RGB")

        if make_square:
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))

        w, h = img.size
        scale = min(max_size / w, max_size / h, 1.0)
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

        fd, tmp = tempfile.mkstemp(prefix="klmp3_cover_", suffix=".jpg")
        os.close(fd)
        img.save(tmp, format="JPEG", quality=92)
        return tmp
    except Exception:
        return cover_path


@dataclass
class _TagPlan:
    title: str
    artist: str
    album: str
    year: str
    genre: str


class TagsTab:
    """
    Onglet "Métadonnées" (ffmpeg-only)
    - multi-sélection fichiers (Ctrl/Maj)
    - dossier de sortie par défaut : <dossier_entree>-tag
    - tags: title/artist/album/date/genre
    - cover: MP3/M4A/FLAC
    """

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app

        self.files: list[str] = []
        self.worker_thread: threading.Thread | None = None
        self.stop_flag = threading.Event()

        # Vars UI
        self.in_summary_var = tk.StringVar(value="Aucun fichier sélectionné.")
        self.outdir_var = tk.StringVar(value="")
        self.cover_path_var = tk.StringVar(value="")

        self.enable_tags_var = tk.BooleanVar(value=False)
        self.enable_cover_var = tk.BooleanVar(value=False)
        self.square_cover_var = tk.BooleanVar(value=True)

        self.title_var = tk.StringVar(value="")
        self.artist_var = tk.StringVar(value="")
        self.album_var = tk.StringVar(value="")
        self.year_var = tk.StringVar(value="")
        self.genre_var = tk.StringVar(value="")

        self._build_ui()
        self._bind_apply_state()
        self._update_apply_state()


    # ---------------- UI ----------------

    def _build_ui(self):
        # Root
        root = ttk.Frame(self.parent)
        root.pack(fill="both", expand=True, padx=10, pady=10)

        # 1) Actions EN HAUT, centrées, pleine largeur
        frm_act = ttk.LabelFrame(root, text="Actions")
        frm_act.pack(fill="x", pady=(0, 10))

        # frame interne centré
        act_inner = ttk.Frame(frm_act)
        act_inner.pack(fill="x", padx=10, pady=10)

        # colonnes: [spacer] [Appliquer] [Progress] [Stop] [spacer]
        act_inner.columnconfigure(0, weight=1)
        act_inner.columnconfigure(1, weight=0)  # Appliquer
        act_inner.columnconfigure(2, weight=1)  # Progressbar (s'étire)
        act_inner.columnconfigure(3, weight=0)  # Stop
        act_inner.columnconfigure(4, weight=1)

        self.btn_apply = ttk.Button(act_inner, text="Appliquer", command=self.start_apply)
        self.btn_apply.grid(row=0, column=1, sticky="w")

        self.pb = ttk.Progressbar(act_inner, mode="determinate")
        self.pb.grid(row=0, column=2, sticky="ew", padx=(12, 12))
        self.pb.configure(length=260)

        self.btn_stop = ttk.Button(act_inner, text="Stop", command=self.stop_apply, state="disabled")
        self.btn_stop.grid(row=0, column=3, sticky="e")

        # 2) Contenu en 2 colonnes (gauche=quoi, droite=comment)
        cols = ttk.Frame(root)
        cols.pack(fill="both", expand=True)

        cols.columnconfigure(0, weight=1)  # gauche
        cols.columnconfigure(1, weight=1)  # droite
        cols.rowconfigure(0, weight=1)

        left = ttk.Frame(cols)
        right = ttk.Frame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        left.columnconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        # -------- GAUCHE : Sélection + Aperçu + Sortie (bas) --------

        frm_pick = ttk.LabelFrame(left, text="Sélection")
        frm_pick.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frm_pick.columnconfigure(1, weight=1)

        ttk.Button(frm_pick, text="Ajouter fichiers…", command=self.pick_files).grid(row=0, column=0, padx=10, pady=(10, 6), sticky="w")
        ttk.Label(frm_pick, text="Ctrl/Maj pour multi-sélection").grid(row=0, column=1, padx=(0, 10), pady=(10, 6), sticky="w")

        ttk.Button(frm_pick, text="Effacer la sélection", command=self.clear_files).grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        ttk.Label(frm_pick, textvariable=self.in_summary_var).grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="w")

        frm_list = ttk.LabelFrame(left, text="Fichiers (aperçu)")
        frm_list.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        frm_list.columnconfigure(0, weight=1)

        # Aperçu réduit : hauteur plus faible
        self.listbox = tk.Listbox(frm_list, height=5)
        self.listbox.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        frm_out = ttk.LabelFrame(left, text="Dossier de sortie")
        frm_out.grid(row=2, column=0, sticky="ew")
        frm_out.columnconfigure(0, weight=1)

        ttk.Label(frm_out, text="Par défaut : un dossier “-tag” est créé à côté des fichiers.").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 2)
        )

        ent_out = ttk.Entry(frm_out, textvariable=self.outdir_var)
        ent_out.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10))

        ttk.Button(frm_out, text="Choisir…", command=self.choose_outdir).grid(
            row=1, column=1, sticky="ew", padx=(0, 10), pady=(4, 10)
        )
        ttk.Button(frm_out, text="Réinitialiser défaut", command=self.reset_outdir_default).grid(
            row=1, column=2, sticky="ew", padx=(0, 10), pady=(4, 10)
        )


        # -------- DROITE : Couverture (haut) + Métadonnées --------

        frm_cov = ttk.LabelFrame(right, text="Image de couverture")
        frm_cov.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frm_cov.columnconfigure(0, weight=1)

        ttk.Checkbutton(frm_cov, text="Appliquer une couverture (MP3 / M4A / FLAC)", variable=self.enable_cover_var).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 6)
        )

        ent_cov = ttk.Entry(frm_cov, textvariable=self.cover_path_var)
        ent_cov.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        ttk.Button(frm_cov, text="Choisir image…", command=self.choose_cover).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 10))
        ttk.Checkbutton(frm_cov, text="Carré (crop + resize)", variable=self.square_cover_var).grid(row=1, column=2, sticky="w", padx=(0, 10), pady=(0, 10))

        frm_meta = ttk.LabelFrame(right, text="Métadonnées (audio)")
        frm_meta.grid(row=1, column=0, sticky="ew")
        frm_meta.columnconfigure(1, weight=1)

        ttk.Checkbutton(frm_meta, text="Appliquer les métadonnées", variable=self.enable_tags_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 6)
        )

        self._grid_labeled_entry(frm_meta, "Titre", self.title_var, row=1)
        self._grid_labeled_entry(frm_meta, "Artiste", self.artist_var, row=2)
        self._grid_labeled_entry(frm_meta, "Album", self.album_var, row=3)
        self._grid_labeled_entry(frm_meta, "Année", self.year_var, row=4)
        self._grid_labeled_entry(frm_meta, "Genre", self.genre_var, row=5)

        ttk.Label(frm_meta, text="champ vide = pas de modification").grid(
            row=6, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 10)
        )

    def _grid_labeled_entry(self, parent, label, var, row):
        ttk.Label(parent, text=f"{label} :").grid(row=row, column=0, sticky="w", padx=10, pady=(0, 6))
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=10, pady=(0, 6))

    # ---------------- Sélection ----------------

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Sélectionner des fichiers audio (Ctrl/Maj pour multi-sélection)",
            filetypes=[
                ("Audio", "*.mp3 *.m4a *.mp4 *.flac *.ogg *.opus *.wav *.aac *.mkv *.webm"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not paths:
            return

        # Robustesse: certains dialogs renvoient une str Tcl
        if isinstance(paths, str):
            paths = self.parent.tk.splitlist(paths)

        new_files = [os.path.abspath(p) for p in paths if _is_audio_file(p)]
        if not new_files:
            messagebox.showwarning("Aucun fichier valide", "Aucun fichier audio reconnu dans la sélection.")
            return

        self._add_files(new_files)

    def _add_files(self, new_files: list[str]):
        existing = set(self.files)
        for p in new_files:
            if p not in existing:
                self.files.append(p)
                existing.add(p)

        self._refresh_files_view()
        if not self.outdir_var.get().strip():
            self.reset_outdir_default()

    def clear_files(self):
        self.files = []
        self._refresh_files_view()
        self.outdir_var.set("")

    def _refresh_files_view(self):
        self.listbox.delete(0, "end")
        if not self.files:
            self.in_summary_var.set("Aucun fichier sélectionné.")
            return

        self.in_summary_var.set(f"{len(self.files)} fichier(s) sélectionné(s).")

        show = self.files[:200]
        for p in show:
            self.listbox.insert("end", os.path.basename(p))
        if len(self.files) > 200:
            self.listbox.insert("end", f"... (+{len(self.files) - 200} autres)")

    # ---------------- Sortie & cover ----------------

    def choose_outdir(self):
        initial = self.outdir_var.get().strip() or (os.path.dirname(self.files[0]) if self.files else os.path.expanduser("~"))
        d = filedialog.askdirectory(initialdir=initial, title="Choisir le dossier de sortie")
        if d:
            self.outdir_var.set(os.path.abspath(d))

    def reset_outdir_default(self):
        if not self.files:
            self.outdir_var.set("")
            return
        self.outdir_var.set(_default_outdir_for_files(self.files))

    def choose_cover(self):
        p = filedialog.askopenfilename(
            title="Choisir une image (JPG/PNG)",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")],
        )
        if p:
            self.cover_path_var.set(os.path.abspath(p))
            
    def _bind_apply_state(self):
        """Recalcule l'état du bouton 'Appliquer' quand les options changent."""
        def _on_change(*_):
            self._update_apply_state()

        for v in (self.enable_tags_var, self.enable_cover_var, self.cover_path_var):
            try:
                v.trace_add("write", _on_change)   # Tk >= 8.5
            except Exception:
                v.trace("w", _on_change)           # fallback ancien Tk

    def _update_apply_state(self):
        """Active/désactive 'Appliquer' selon les options."""
        # Si un traitement est en cours, start_apply gère déjà disabled/stop etc.
        if self.worker_thread and self.worker_thread.is_alive():
            return

        enable_tags = bool(self.enable_tags_var.get())
        enable_cover = bool(self.enable_cover_var.get())

        cover_path = self.cover_path_var.get().strip()
        cover_ok = (not enable_cover) or (cover_path and os.path.isfile(cover_path))

        # Règle: Appliquer seulement si (tags OU cover) ET cover valide si cover cochée
        should_enable = (enable_tags or enable_cover) and cover_ok

        self.btn_apply.configure(state=("normal" if should_enable else "disabled"))

    # ---------------- Traitement ----------------

    def start_apply(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        if not self.files:
            messagebox.showwarning("Sélection vide", "Veuillez sélectionner au moins un fichier.")
            return

        ffmpeg = getattr(self.app, "ffmpeg_path", None)
        if not ffmpeg or not os.path.isfile(ffmpeg):
            messagebox.showerror("ffmpeg introuvable", "ffmpeg est introuvable. Vérifiez tools/<platform>/ ou le PATH.")
            return

        outdir = self.outdir_var.get().strip()
        if not outdir:
            outdir = _default_outdir_for_files(self.files)
            self.outdir_var.set(outdir)

        try:
            _safe_makedirs(outdir)
        except Exception as e:
            messagebox.showerror("Dossier de sortie", f"Impossible de créer le dossier de sortie :\n{outdir}\n\n{e}")
            return

        plan = _TagPlan(
            title=self.title_var.get().strip(),
            artist=self.artist_var.get().strip(),
            album=self.album_var.get().strip(),
            year=self.year_var.get().strip(),
            genre=self.genre_var.get().strip(),
        )

        enable_tags = bool(self.enable_tags_var.get())
        enable_cover = bool(self.enable_cover_var.get())
        cover_path = self.cover_path_var.get().strip() if enable_cover else ""
        square_cover = bool(self.square_cover_var.get())

        if enable_cover and (not cover_path or not os.path.isfile(cover_path)):
            messagebox.showwarning("Image manquante", "Vous avez activé la couverture, mais aucune image valide n'est sélectionnée.")
            return

        # reset stop flags
        self.stop_flag.clear()
        if getattr(self.app, "stop_flag", None) is not None:
            self.app.stop_flag.clear()

        self.btn_apply.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.pb.configure(maximum=len(self.files), value=0)

        self.worker_thread = threading.Thread(
            target=self._worker_apply,
            args=(list(self.files), outdir, enable_tags, plan, cover_path, square_cover),
            daemon=True,
        )
        self.worker_thread.start()

    def stop_apply(self):
        self.stop_flag.set()
        try:
            if getattr(self.app, "stop_flag", None) is not None:
                self.app.stop_flag.set()
        except Exception:
            pass
        if hasattr(self.app, "log"):
            self.app.log("⏹️ Métadonnées : arrêt demandé…")

    def _worker_apply(self, files: list[str], outdir: str, enable_tags: bool, plan: _TagPlan, cover_path: str, square_cover: bool):
        app_log = getattr(self.app, "log", print)
        run_subprocess = getattr(self.app, "run_subprocess", None)

        # Normalement toujours fourni par App (klmp3.py).
        # Le fallback ci-dessous est une sécurité si tab_tags.py est utilisé hors KLMP3.
        if run_subprocess is None:
            from subprocess import Popen, PIPE, STDOUT

            def run_subprocess(cmd, on_line, stop_flag):
                proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
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

        ffmpeg = self.app.ffmpeg_path

        cover_tmp = ""
        if cover_path:
            cover_tmp = _load_and_prepare_cover(cover_path, make_square=square_cover, max_size=1000)

        ok_count = 0
        fail_count = 0

        app_log("")
        app_log("🧾 Métadonnées : démarrage du traitement…")
        app_log(f"📂 Sortie : {outdir}")
        app_log(f"🗂️ Fichiers : {len(files)}")

        try:
            for i, in_path in enumerate(files, start=1):
                if self.stop_flag.is_set():
                    app_log("⏹️ Métadonnées : interrompu par l’utilisateur.")
                    break

                base = os.path.basename(in_path)
                out_path = _dedupe_outpath(outdir, base)

                cmd = [ffmpeg, "-y", "-hide_banner", "-i", in_path]

                use_cover = bool(cover_tmp) and _cover_supported_for(in_path)
                if cover_tmp and not _cover_supported_for(in_path):
                    app_log(f"⚠️ Couverture ignorée (format non supporté) : {base}")

                if use_cover:
                    cmd += ["-i", cover_tmp]
                    cmd += ["-map", "0:a:0", "-map", "1:v:0", "-c:a", "copy", "-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]
                else:
                    cmd += ["-map", "0", "-c", "copy"]

                if enable_tags:
                    if plan.title:
                        cmd += ["-metadata", f"title={plan.title}"]
                    if plan.artist:
                        cmd += ["-metadata", f"artist={plan.artist}"]
                    if plan.album:
                        cmd += ["-metadata", f"album={plan.album}"]
                    if plan.year:
                        cmd += ["-metadata", f"date={plan.year}"]
                    if plan.genre:
                        cmd += ["-metadata", f"genre={plan.genre}"]

                if in_path.lower().endswith(".mp3") or out_path.lower().endswith(".mp3"):
                    cmd += ["-id3v2_version", "3"]

                cmd += [out_path]

                app_log("")
                app_log(f"🧷 [{i}/{len(files)}] {base}")
                app_log("▶️ ffmpeg : " + " ".join(cmd))

                def on_line(line: str):
                    if line and ("error" in line.lower() or "invalid" in line.lower()):
                        app_log(line)

                rc = run_subprocess(cmd, on_line, self.stop_flag)
                if rc == 0 and os.path.isfile(out_path):
                    ok_count += 1
                else:
                    fail_count += 1
                    app_log(f"❌ Échec : {base} (code {rc})")

                self.parent.after(0, self._set_progress, i)

        finally:
            try:
                if cover_tmp and cover_tmp != cover_path and os.path.isfile(cover_tmp):
                    os.remove(cover_tmp)
            except Exception:
                pass

            self.parent.after(0, self._finish_ui, ok_count, fail_count)

    def _set_progress(self, value: int):
        try:
            self.pb.configure(value=value)
        except Exception:
            pass

    def _finish_ui(self, ok_count: int, fail_count: int):
        self._update_apply_state()
        self.btn_stop.configure(state="disabled")

        msg = f"Métadonnées : {ok_count} OK"
        if fail_count:
            msg += f", {fail_count} échec(s)"
        if hasattr(self.app, "log"):
            self.app.log("✅ " + msg)
        try:
            messagebox.showinfo("Métadonnées", msg)
        except Exception:
            pass
