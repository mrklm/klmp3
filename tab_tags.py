# tab_tags.py
# -*- coding: utf-8 -*-

import os
import re
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
    i = 2
    while True:
        cand = os.path.join(outdir, f"{base} ({i}){ext}")
        if not os.path.exists(cand):
            return cand
        i += 1


def _cover_supported_for(path: str) -> bool:
    p = path.lower()
    return p.endswith(".mp3") or p.endswith(".m4a") or p.endswith(".mp4") or p.endswith(".flac")


def _extract_track_and_title_from_filename(path: str) -> tuple[str, str, str]:
    """
    Extrait (track, title_without_track, title_full) à partir du nom de fichier.
    Exemples:
      "01 - Ma chanson.mp3" -> ("1", "Ma chanson", "01 - Ma chanson")
      "1.Ma chanson.mp3"    -> ("1", "Ma chanson", "1.Ma chanson")
      "Ma chanson.mp3"      -> ("", "Ma chanson", "Ma chanson")
    """
    base = os.path.basename(path)
    noext, _ext = os.path.splitext(base)
    noext = noext.strip()

    # Pistes: chiffres au début + séparateur + reste
    m = re.match(r"^\s*(\d{1,3})\s*[-._ ]+\s*(.+?)\s*$", noext)
    if m:
        track_raw = m.group(1)
        title_wo = m.group(2).strip()
        # Normaliser le numéro (01 -> 1)
        try:
            track = str(int(track_raw))
        except Exception:
            track = track_raw.lstrip("0") or track_raw
        return track, title_wo or noext, noext

    # Pas de préfixe piste
    return "", noext, noext


@dataclass
class _TagPlan:
    track: str
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
    - tags: track/title/artist/album/date/genre
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

        # ✅ Nouveaux comportements "depuis le nom de fichier"
        self.track_from_filename_var = tk.BooleanVar(value=True)
        self.title_from_filename_var = tk.BooleanVar(value=True)

        # Champs
        self.track_var = tk.StringVar(value="")
        self.title_var = tk.StringVar(value="")
        self.artist_var = tk.StringVar(value="")
        self.album_var = tk.StringVar(value="")
        self.year_var = tk.StringVar(value="")
        self.genre_var = tk.StringVar(value="")

        # Widgets à contrôler (enable/disable)
        self.ent_track: ttk.Entry | None = None
        self.ent_title: ttk.Entry | None = None

        self._build_ui()
        self._bind_apply_state()
        self._bind_field_state()
        self._update_title_track_state()
        self._update_apply_state()

    # ---------------
    # UI
    # ---------------

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
        frm_pick.columnconfigure(0, weight=1)

        pick_row = ttk.Frame(frm_pick)
        pick_row.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        pick_row.columnconfigure(0, weight=1)

        ttk.Button(pick_row, text="Ajouter…", command=self.pick_files).grid(row=0, column=0, sticky="w")
        ttk.Button(pick_row, text="Retirer", command=self.remove_selected).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Button(pick_row, text="Tout effacer", command=self.clear_files).grid(row=0, column=2, sticky="w", padx=(8, 0))

        self.lbl_summary = ttk.Label(frm_pick, textvariable=self.in_summary_var)
        self.lbl_summary.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

        frm_list = ttk.Frame(left)
        frm_list.grid(row=1, column=0, sticky="nsew")
        left.rowconfigure(1, weight=1)

        frm_list.columnconfigure(0, weight=1)
        frm_list.rowconfigure(0, weight=1)

        self.lb = tk.Listbox(frm_list, selectmode="extended", height=10)
        self.lb.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(frm_list, orient="vertical", command=self.lb.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self.lb.configure(yscrollcommand=ysb.set)

        # Sortie (en bas à gauche)
        frm_out = ttk.LabelFrame(left, text="Dossier de sortie")
        frm_out.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        frm_out.columnconfigure(0, weight=1)

        out_row = ttk.Frame(frm_out)
        out_row.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        out_row.columnconfigure(0, weight=1)

        ttk.Entry(out_row, textvariable=self.outdir_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(out_row, text="Choisir…", command=self.pick_outdir).grid(row=0, column=1, padx=(8, 0))

        # -------- DROITE : Cover + Métadonnées --------

        frm_cover = ttk.LabelFrame(right, text="Image de couverture")
        frm_cover.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frm_cover.columnconfigure(1, weight=1)

        ttk.Checkbutton(frm_cover, text="Ajouter une couverture", variable=self.enable_cover_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 6)
        )

        ttk.Label(frm_cover, text="Fichier image :").grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        ttk.Entry(frm_cover, textvariable=self.cover_path_var).grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 8))
        ttk.Button(frm_cover, text="Choisir…", command=self.pick_cover).grid(row=1, column=2, sticky="e", padx=(0, 10), pady=(0, 8))

        ttk.Checkbutton(frm_cover, text="Rogner carré (recommandé)", variable=self.square_cover_var).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 10)
        )

        frm_meta = ttk.LabelFrame(right, text="Métadonnées")
        frm_meta.grid(row=1, column=0, sticky="ew")
        frm_meta.columnconfigure(1, weight=1)

        ttk.Checkbutton(frm_meta, text="Appliquer les métadonnées", variable=self.enable_tags_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 6)
        )

        # ✅ Nouveau champ N° de piste
        self.ent_track = self._grid_labeled_entry(frm_meta, "N° de piste", self.track_var, row=1)
        ttk.Checkbutton(
            frm_meta,
            text="N° du fichier = N° de piste",
            variable=self.track_from_filename_var,
            command=self._update_title_track_state,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=26, pady=(0, 8))

        # ✅ Champ Titre + option filename->title
        self.ent_title = self._grid_labeled_entry(frm_meta, "Titre", self.title_var, row=3)
        ttk.Checkbutton(
            frm_meta,
            text="Nom du fichier = titre",
            variable=self.title_from_filename_var,
            command=self._update_title_track_state,
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=26, pady=(0, 8))

        # Autres champs
        self._grid_labeled_entry(frm_meta, "Artiste", self.artist_var, row=5)
        self._grid_labeled_entry(frm_meta, "Album", self.album_var, row=6)
        self._grid_labeled_entry(frm_meta, "Année", self.year_var, row=7)
        self._grid_labeled_entry(frm_meta, "Genre", self.genre_var, row=8)

        ttk.Label(frm_meta, text="champ vide = pas de modification").grid(
            row=9, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 10)
        )

    def _grid_labeled_entry(self, parent, label, var, row) -> ttk.Entry:
        ttk.Label(parent, text=f"{label} :").grid(row=row, column=0, sticky="w", padx=10, pady=(0, 6))
        ent = ttk.Entry(parent, textvariable=var)
        ent.grid(row=row, column=1, sticky="ew", padx=10, pady=(0, 6))
        return ent

    def _bind_apply_state(self):
        """Recalcule l'état du bouton 'Appliquer' quand les options changent."""
        def _on_change(*_):
            self._update_apply_state()

        for v in (self.enable_tags_var, self.enable_cover_var, self.cover_path_var):
            try:
                v.trace_add("write", _on_change)   # Tk >= 8.5
            except Exception:
                v.trace("w", _on_change)           # fallback ancien Tk

    def _bind_field_state(self):
        """Met à jour l'état (editable/non editable) des champs Titre et N°."""
        def _on_change(*_):
            self._update_title_track_state()

        for v in (self.track_from_filename_var, self.title_from_filename_var):
            try:
                v.trace_add("write", _on_change)
            except Exception:
                v.trace("w", _on_change)

    def _update_title_track_state(self):
        """Grise les champs 'N° de piste' et/ou 'Titre' selon les cases cochées."""
        if self.ent_track is not None:
            self.ent_track.configure(state=("disabled" if self.track_from_filename_var.get() else "normal"))
        if self.ent_title is not None:
            self.ent_title.configure(state=("disabled" if self.title_from_filename_var.get() else "normal"))

    def _update_apply_state(self):
        """Active/désactive 'Appliquer' selon les options."""
        if self.worker_thread and self.worker_thread.is_alive():
            return

        enable_tags = bool(self.enable_tags_var.get())
        enable_cover = bool(self.enable_cover_var.get())

        cover_path = self.cover_path_var.get().strip()
        cover_ok = (not enable_cover) or (cover_path and os.path.isfile(cover_path))

        should_enable = (enable_tags or enable_cover) and cover_ok
        self.btn_apply.configure(state=("normal" if should_enable else "disabled"))

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
            self.outdir_var.set(_default_outdir_for_files(self.files))

    def _refresh_files_view(self):
        self.lb.delete(0, "end")
        for p in self.files:
            self.lb.insert("end", os.path.basename(p))

        if not self.files:
            self.in_summary_var.set("Aucun fichier sélectionné.")
        else:
            self.in_summary_var.set(f"{len(self.files)} fichier(s) sélectionné(s).")

    def remove_selected(self):
        sel = list(self.lb.curselection())
        if not sel:
            return
        sel_paths = {self.files[i] for i in sel if 0 <= i < len(self.files)}
        self.files = [p for p in self.files if p not in sel_paths]
        self._refresh_files_view()

    def clear_files(self):
        self.files = []
        self._refresh_files_view()

        # Reset du dossier de sortie : le prochain "Ajouter…" recalculera un défaut
        self.outdir_var.set("")


    def pick_outdir(self):
        d = filedialog.askdirectory(title="Choisir le dossier de sortie")
        if d:
            self.outdir_var.set(os.path.abspath(d))

    def pick_cover(self):
        p = filedialog.askopenfilename(
            title="Choisir une image de couverture",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp"), ("Tous les fichiers", "*.*")],
        )
        if p:
            self.cover_path_var.set(os.path.abspath(p))

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
            track=self.track_var.get().strip(),
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
            messagebox.showerror("Couverture", "Veuillez choisir une image de couverture valide.")
            return

        use_title_from_filename = bool(self.title_from_filename_var.get())
        use_track_from_filename = bool(self.track_from_filename_var.get())

        # UI state
        self.stop_flag.clear()
        self.btn_apply.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.pb.configure(value=0, maximum=max(1, len(self.files)))

        self.worker_thread = threading.Thread(
            target=self._worker_apply,
            args=(ffmpeg, outdir, plan, enable_tags, enable_cover, cover_path, square_cover, use_title_from_filename, use_track_from_filename),
            daemon=True,
        )
        self.worker_thread.start()

    def stop_apply(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_flag.set()

    def _worker_apply(
        self,
        ffmpeg: str,
        outdir: str,
        plan: _TagPlan,
        enable_tags: bool,
        enable_cover: bool,
        cover_path: str,
        square_cover: bool,
        title_from_filename: bool,
        track_from_filename: bool,
    ):
        def app_log(msg: str):
            if hasattr(self.app, "log"):
                try:
                    self.app.log(msg)
                except Exception:
                    pass

        def ui_done(success: bool, msg: str):
            def _f():
                self.btn_stop.configure(state="disabled")
                self._update_apply_state()
                if msg:
                    if success:
                        messagebox.showinfo("Terminé", msg)
                    else:
                        messagebox.showwarning("Arrêté", msg)
            try:
                self.parent.after(0, _f)
            except Exception:
                pass

        cover_tmp = ""
        try:
            if enable_cover and cover_path:
                cover_tmp = self._prepare_cover_tmp(cover_path, square_cover)

            total = len(self.files)
            for idx, in_path in enumerate(self.files, start=1):
                if self.stop_flag.is_set():
                    ui_done(False, "Traitement interrompu.")
                    return

                base = os.path.basename(in_path)
                out_path = _dedupe_outpath(outdir, base)

                # ---- Déductions depuis le nom de fichier (sans renommage) ----
                trk_fn, title_wo_trk, title_full = _extract_track_and_title_from_filename(in_path)

                # Track à écrire
                track_to_write = ""
                if enable_tags:
                    if track_from_filename:
                        track_to_write = trk_fn.strip()
                    else:
                        track_to_write = plan.track.strip()

                # Title à écrire
                title_to_write = ""
                if enable_tags:
                    if title_from_filename:
                        if track_from_filename and trk_fn:
                            title_to_write = title_wo_trk.strip()
                        else:
                            title_to_write = title_full.strip()
                    else:
                        title_to_write = plan.title.strip()

                # ---- Commande ffmpeg ----
                cmd = [ffmpeg, "-y", "-hide_banner", "-i", in_path]

                use_cover = bool(cover_tmp) and _cover_supported_for(in_path)
                if cover_tmp and not _cover_supported_for(in_path):
                    app_log(f"⚠️ Couverture ignorée (format non supporté) : {base}")

                if use_cover:
                    cmd += ["-i", cover_tmp]
                    cmd += ["-map", "0:a:0", "-map", "1:v:0", "-c:a", "copy", "-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]
                else:
                    cmd += ["-map", "0", "-c", "copy"]

                # ✅ Conserver toutes les métadonnées existantes du fichier d'entrée
                cmd += ["-map_metadata", "0"]

                if enable_tags:
                    # Tracknumber (si disponible)
                    if track_to_write:
                        cmd += ["-metadata", f"track={track_to_write}"]

                    # Title (si disponible)
                    if title_to_write:
                        cmd += ["-metadata", f"title={title_to_write}"]

                    if plan.artist:
                        cmd += ["-metadata", f"artist={plan.artist}"]
                    if plan.album:
                        cmd += ["-metadata", f"album={plan.album}"]
                    if plan.year:
                        cmd += ["-metadata", f"date={plan.year}"]
                    if plan.genre:
                        cmd += ["-metadata", f"genre={plan.genre}"]

                # Forcer ID3v2.3 pour MP3 (compat lecteurs/Kodi)
                if in_path.lower().endswith(".mp3") or out_path.lower().endswith(".mp3"):
                    cmd += ["-id3v2_version", "3"]

                # Fichier de sortie 
                cmd += [out_path]

                # Exécuter
                app_log(f"🎛️ Tags: {idx}/{total} — {base}")
                try:
                    import subprocess
                    p = subprocess.run(cmd, capture_output=True, text=True)
                    if p.returncode != 0:
                        app_log("❌ ffmpeg a échoué : " + (p.stderr.strip() or "Erreur inconnue"))
                    else:
                        app_log("✅ OK : " + os.path.basename(out_path))
                except Exception as e:
                    app_log(f"❌ Exception ffmpeg : {e}")

                # progress UI
                try:
                    self.parent.after(0, lambda v=idx: self.pb.configure(value=v))
                except Exception:
                    pass

            ui_done(True, f"Terminé.\n\nFichiers générés dans :\n{outdir}")

        finally:
            # Nettoyage cover tmp
            if cover_tmp and os.path.isfile(cover_tmp):
                try:
                    os.remove(cover_tmp)
                except Exception:
                    pass

    def _prepare_cover_tmp(self, cover_path: str, square_cover: bool) -> str:
        """
        Prépare une image temporaire (jpeg) pour ffmpeg.
        - si square_cover: rogne en carré centré
        """
        try:
            from PIL import Image
        except Exception:
            raise RuntimeError("Pillow est requis pour préparer la couverture (pip install pillow).")

        img = Image.open(cover_path).convert("RGB")

        if square_cover:
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))

        # JPEG temporaire
        fd, tmp_path = tempfile.mkstemp(prefix="klmp3_cover_", suffix=".jpg")
        os.close(fd)
        img.save(tmp_path, format="JPEG", quality=92, optimize=True)
        return tmp_path
