# tab_convert.py
# -*- coding: utf-8 -*-

import os
import threading
import queue
import subprocess
from datetime import datetime
import json
import tkinter as tk
from tkinter import ttk, filedialog


def _format_size(num_bytes: int) -> str:
    try:
        n = float(num_bytes)
    except Exception:
        return "?"
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024.0:
            if unit == "o":
                return f"{int(n)} {unit}"
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} Po"


class ConvertTab(ttk.Frame):
    """
    Onglet Conversion
    - Sélection fichier(s)
    - Destination
    - Format + Qualité (côte à côte)
    - Options: Normaliser + Conserver métadonnées + Supprimer la source
    - Actions en haut (Convertir — Progress — Stop) sur toute la largeur
    - Progression :
        * 1 fichier : % (0..100) via ffmpeg -progress pipe:1 + durée via ffprobe
        * N fichiers : progression par fichier (0..N)
    """

    FORMATS = ["mp3", "m4a", "opus", "flac", "ogg", "wav"]

    MP3_QUALITIES = [str(i) for i in range(0, 10)]                 # VBR LAME: 0..9
    AAC_BITRATES = [f"{k}k" for k in (96, 128, 160, 192, 224, 256, 320)]
    OPUS_BITRATES = [f"{k}k" for k in (64, 96, 128, 160, 192)]
    VORBIS_QUALITIES = [str(i) for i in range(0, 11)]              # 0..10
    FLAC_LEVELS = [str(i) for i in range(0, 13)]                   # 0..12

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self._files: list[str] = []
        self._worker: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._q: "queue.Queue[object]" = queue.Queue()

        # Destination par défaut : Bureau/klmp3conversionsAAMMJJ
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        stamp = datetime.now().strftime("%y%m%d")  # AAMMJJ
        default_dest = os.path.join(desktop, f"klmp3conversions{stamp}")
        if not os.path.isdir(desktop):
            default_dest = os.path.join(os.path.expanduser("~"), f"klmp3conversions{stamp}")

        try:
            os.makedirs(default_dest, exist_ok=True)
        except Exception:
            pass

        self.dest_dir_var = tk.StringVar(value=default_dest)

        self.keep_metadata_var = tk.BooleanVar(value=True)
        self.delete_source_var = tk.BooleanVar(value=False)
        self.normalize_var = tk.BooleanVar(value=False)

        # Qualité affichée (miroir des vars app.* selon format)
        self.quality_var = tk.StringVar(value="")

        # Progress mode
        self._single_file_mode = False  # True -> maximum=100 (pourcentage), False -> maximum=N (fichiers)

        self._build_ui()
        self._poll_queue()
        self._on_format_changed()

    # ---------------- UI ----------------

    def _build_ui(self):
        # 2 colonnes (gauche / droite) + 2 lignes (Actions / contenu)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        # ---- Actions (pleine largeur)
        frm_act = ttk.LabelFrame(self, text="Actions")
        frm_act.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))
        frm_act.columnconfigure(0, weight=1)

        act_inner = ttk.Frame(frm_act)
        act_inner.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        # [spacer] [Convertir] [Progress] [Stop] [spacer]
        act_inner.columnconfigure(0, weight=1)
        act_inner.columnconfigure(1, weight=0)
        act_inner.columnconfigure(2, weight=1)
        act_inner.columnconfigure(3, weight=0)
        act_inner.columnconfigure(4, weight=1)

        self.btn_convert = ttk.Button(act_inner, text="Convertir", command=self._start_convert)
        self.btn_convert.grid(row=0, column=1, sticky="w")

        self.pb = ttk.Progressbar(act_inner, mode="determinate", maximum=100, value=0)
        self.pb.grid(row=0, column=2, sticky="ew", padx=(12, 12))
        try:
            self.pb.configure(length=260)
        except Exception:
            pass

        self.btn_stop = ttk.Button(act_inner, text="Stop", command=self._stop_convert, state="disabled")
        self.btn_stop.grid(row=0, column=3, sticky="e")

        # ---- Contenu (gauche/droite)
        left = ttk.Frame(self)
        right = ttk.Frame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=(6, 10))
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=(6, 10))
        left.columnconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        # ---- Gauche : fichiers
        ttk.Button(left, text="Sélectionnez fichier(s)", command=self._select_files).pack(fill="x")

        style = ttk.Style(self)
        style.configure("Convert.Treeview", background="black", foreground="white", fieldbackground="black")
        style.configure("Convert.Treeview.Heading", background="black", foreground="white")
        style.map("Convert.Treeview", background=[("selected", "gray25")], foreground=[("selected", "white")])

        self.tree = ttk.Treeview(
            left,
            columns=("name", "ext", "size"),
            show="headings",
            height=9,
            style="Convert.Treeview",
        )
        self.tree.heading("name", text="Nom")
        self.tree.heading("ext", text="Extension")
        self.tree.heading("size", text="Taille")
        self.tree.column("name", width=260, anchor="w")
        self.tree.column("ext", width=90, anchor="center")
        self.tree.column("size", width=120, anchor="e")
        self.tree.pack(fill="both", expand=True, pady=(8, 8))

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(0, 8))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="Retirer sélection", command=self._remove_selected, padding=(8, 1)).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(btns, text="Tout retirer", command=self._clear_files, padding=(8, 1)).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        # ---- Droite : destination + format/qualité + options
        row_dest = ttk.Frame(right)
        row_dest.pack(fill="x", pady=(0, 10))
        row_dest.columnconfigure(1, weight=1)

        ttk.Button(
            row_dest,
            text="Sélectionner destination",
            command=self._select_dest,
            padding=(8, 1),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        # IMPORTANT: création de l'Entry (sinon AttributeError ent_dest)
        self.ent_dest = ttk.Entry(row_dest, textvariable=self.dest_dir_var)
        self.ent_dest.grid(row=0, column=1, sticky="ew")

        frm_fmt = ttk.Frame(right)
        frm_fmt.pack(fill="x")

        ttk.Label(frm_fmt, text="Type de conversion:").grid(row=0, column=0, sticky="w")

        row_fq = ttk.Frame(frm_fmt)
        row_fq.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        row_fq.columnconfigure(0, weight=0)
        row_fq.columnconfigure(1, weight=0)
        row_fq.columnconfigure(2, weight=0)

        self.cmb_format = ttk.Combobox(
            row_fq,
            values=self.FORMATS,
            state="readonly",
            textvariable=self.app.audio_format_var,
            width=10,
        )
        self.cmb_format.grid(row=0, column=0, sticky="w")
        self.cmb_format.bind("<<ComboboxSelected>>", lambda _e: self._on_format_changed())

        ttk.Label(row_fq, text="Par défaut :").grid(row=0, column=1, sticky="w", padx=(16, 6))

        self.cmb_quality = ttk.Combobox(
            row_fq,
            state="readonly",
            textvariable=self.quality_var,
            width=10,
        )
        self.cmb_quality.grid(row=0, column=2, sticky="w")
        self.cmb_quality.bind("<<ComboboxSelected>>", lambda _e: self._apply_quality_to_app())

        ttk.Checkbutton(frm_fmt, text="Normaliser", variable=self.normalize_var).grid(
            row=2, column=0, sticky="w", pady=(0, 4)
        )
        ttk.Checkbutton(frm_fmt, text="Conserver les métadonnées", variable=self.keep_metadata_var).grid(
            row=3, column=0, sticky="w"
        )
        ttk.Checkbutton(frm_fmt, text="Supprimer la source après succès", variable=self.delete_source_var).grid(
            row=4, column=0, sticky="w", pady=(0, 12)
        )

        self._log("Prêt. Sélectionnez un ou plusieurs fichiers à convertir.")

    # ---------------- Logging & queue ----------------

    def _log(self, msg: str):
        log_fn = getattr(self.app, "log", None)
        if callable(log_fn):
            try:
                log_fn(msg)
                return
            except Exception:
                pass
        try:
            print(msg)
        except Exception:
            pass

    def _qlog(self, msg: str):
        self._q.put({"type": "log", "msg": msg})

    def _qprogress(self, value: int, maximum: int | None = None):
        self._q.put({"type": "progress", "value": int(value), "maximum": None if maximum is None else int(maximum)})

    def _qdone(self):
        self._q.put({"type": "done"})

    def _poll_queue(self):
        try:
            while True:
                item = self._q.get_nowait()

                if isinstance(item, dict):
                    t = item.get("type")

                    if t == "log":
                        self._log(str(item.get("msg", "")))

                    elif t == "progress":
                        if hasattr(self, "pb"):
                            maximum = item.get("maximum")
                            if maximum is not None:
                                try:
                                    self.pb.configure(maximum=int(maximum))
                                except Exception:
                                    pass
                            try:
                                self.pb.configure(value=int(item.get("value", 0)))
                            except Exception:
                                pass

                    elif t == "done":
                        self._set_running(False)

                else:
                    self._log(str(item))

        except queue.Empty:
            pass

        self.after(120, self._poll_queue)

    def _set_running(self, running: bool):
        try:
            self.btn_convert.configure(state="disabled" if running else "normal")
        except Exception:
            pass
        try:
            self.btn_stop.configure(state="normal" if running else "disabled")
        except Exception:
            pass
        try:
            if not running:
                # Fin -> stop éventuel, reset visuel
                self.pb.stop()
        except Exception:
            pass

    # ---------------- Files UI ----------------

    def _select_files(self):
        paths = filedialog.askopenfilenames(
            title="Sélectionnez un ou plusieurs fichiers",
            filetypes=[
                ("Fichiers audio/vidéo", "*.mp3 *.m4a *.aac *.ogg *.opus *.flac *.wav *.mp4 *.mkv *.webm *.mov *.avi"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not paths:
            return

        added = 0
        for p in paths:
            p = os.path.normpath(p)
            if p not in self._files and os.path.isfile(p):
                self._files.append(p)
                added += 1

        if added:
            self._refresh_tree()
            self._log(f"{added} fichier(s) ajouté(s).")
        else:
            self._log("Aucun nouveau fichier ajouté.")

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for p in self._files:
            name = os.path.basename(p)
            ext = os.path.splitext(p)[1].lower().lstrip(".") or "?"
            try:
                size = _format_size(os.path.getsize(p))
            except Exception:
                size = "?"
            self.tree.insert("", "end", values=(name, ext, size))

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            self._log("Aucune sélection.")
            return

        to_remove_names = set()
        for iid in sel:
            vals = self.tree.item(iid, "values")
            if vals:
                to_remove_names.add(vals[0])

        new_files = []
        removed = 0
        for p in self._files:
            if os.path.basename(p) in to_remove_names:
                removed += 1
            else:
                new_files.append(p)
        self._files = new_files

        self._refresh_tree()
        if removed:
            self._log(f"{removed} fichier(s) retiré(s).")

    def _clear_files(self):
        self._files.clear()
        self._refresh_tree()
        self._log("Liste vidée.")

    def _select_dest(self):
        d = filedialog.askdirectory(title="Sélectionnez le dossier de destination")
        if d:
            d = os.path.normpath(d)
            self.dest_dir_var.set(d)
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass

    # ---------------- Format/Quality mapping ----------------

    def _on_format_changed(self):
        fmt = (self.app.audio_format_var.get() or "mp3").strip().lower()

        if fmt == "mp3":
            self.cmb_quality.configure(values=self.MP3_QUALITIES)
            self.quality_var.set(getattr(self.app, "mp3_quality_var").get() if hasattr(self.app, "mp3_quality_var") else "5")
        elif fmt == "m4a":
            self.cmb_quality.configure(values=self.AAC_BITRATES)
            self.quality_var.set(getattr(self.app, "aac_bitrate_var").get() if hasattr(self.app, "aac_bitrate_var") else "192k")
        elif fmt == "opus":
            self.cmb_quality.configure(values=self.OPUS_BITRATES)
            self.quality_var.set(getattr(self.app, "opus_bitrate_var").get() if hasattr(self.app, "opus_bitrate_var") else "128k")
        elif fmt == "flac":
            self.cmb_quality.configure(values=self.FLAC_LEVELS)
            self.quality_var.set(getattr(self.app, "flac_level_var").get() if hasattr(self.app, "flac_level_var") else "5")
        elif fmt == "ogg":
            self.cmb_quality.configure(values=self.VORBIS_QUALITIES)
            self.quality_var.set(getattr(self.app, "vorbis_quality_var").get() if hasattr(self.app, "vorbis_quality_var") else "4")
        elif fmt == "wav":
            self.cmb_quality.configure(values=["(sans perte)"])
            self.quality_var.set("(sans perte)")
        else:
            self.cmb_quality.configure(values=[])
            self.quality_var.set("")

        self._apply_quality_to_app()

    def _apply_quality_to_app(self):
        fmt = (self.app.audio_format_var.get() or "mp3").strip().lower()
        q = (self.quality_var.get() or "").strip()

        if fmt == "mp3" and hasattr(self.app, "mp3_quality_var"):
            self.app.mp3_quality_var.set(q)
        elif fmt == "m4a" and hasattr(self.app, "aac_bitrate_var"):
            self.app.aac_bitrate_var.set(q)
        elif fmt == "opus" and hasattr(self.app, "opus_bitrate_var"):
            self.app.opus_bitrate_var.set(q)
        elif fmt == "flac" and hasattr(self.app, "flac_level_var"):
            self.app.flac_level_var.set(q)
        elif fmt == "ogg" and hasattr(self.app, "vorbis_quality_var"):
            self.app.vorbis_quality_var.set(q)

    # ---------------- Run ----------------

    def _start_convert(self):
        if self._worker and self._worker.is_alive():
            self._log("Une conversion est déjà en cours.")
            return

        if not self._files:
            self._log("Aucun fichier sélectionné.")
            return

        dest = self.dest_dir_var.get().strip()
        if not dest or not os.path.isdir(dest):
            self._log("Dossier de destination invalide.")
            return

        ffmpeg = getattr(self.app, "ffmpeg_path", None)
        if not ffmpeg or not os.path.isfile(ffmpeg):
            self._log("ffmpeg introuvable. Vérifiez l'onglet Options / outils.")
            return

        self._stop_event.clear()

        total = len(self._files)
        self._single_file_mode = (total <= 1)

        try:
            self.pb.stop()
            if self._single_file_mode:
                self.pb.configure(mode="determinate", maximum=100, value=0)
            else:
                self.pb.configure(mode="determinate", maximum=total, value=0)
        except Exception:
            pass

        self._set_running(True)
        self._worker = threading.Thread(target=self._worker_convert, daemon=True)
        self._worker.start()

    def _stop_convert(self):
        self._stop_event.set()
        self._log("Stop demandé — la conversion en cours va s'arrêter.")

    def _worker_convert(self):
        fmt = (self.app.audio_format_var.get() or "mp3").strip().lower()
        keep_meta = bool(self.keep_metadata_var.get())
        delete_src = bool(self.delete_source_var.get())
        dest_dir = self.dest_dir_var.get().strip()

        total = len(self._files)
        if self._single_file_mode:
            self._qprogress(0, maximum=100)
        else:
            self._qprogress(0, maximum=total)

        self._qlog(f"▶️ Conversion vers {fmt} — {total} fichier(s)")

        ok_count = 0

        for idx, src in enumerate(list(self._files), start=1):
            if self._stop_event.is_set():
                self._qlog("⏹️ Arrêt demandé — conversion interrompue.")
                break

            if not os.path.isfile(src):
                self._qlog(f"⚠️ [{idx}] Fichier introuvable : {src}")
                if not self._single_file_mode:
                    self._qprogress(idx)
                continue

            out_path = self._build_output_path(dest_dir, src, fmt)

            duration_s = None
            if self._single_file_mode:
                duration_s = self._get_media_duration_seconds(src)

            if bool(self.normalize_var.get()):
                rc = self._ffmpeg_normalize_convert(src, out_path, fmt, keep_meta, duration_s=duration_s)
            else:
                rc = self._ffmpeg_convert(src, out_path, fmt, keep_meta, duration_s=duration_s)

            if rc == 0 and os.path.isfile(out_path):
                ok_count += 1
                self._qlog(f"✅ [{idx}] OK")
                if delete_src:
                    try:
                        os.remove(src)
                        self._qlog(f"🧹 [{idx}] Source supprimée")
                    except Exception as e:
                        self._qlog(f"⚠️ [{idx}] Source non supprimée : {e}")
            elif rc == 130:
                self._qlog("⏹️ Arrêté par l’utilisateur.")
                break
            else:
                self._qlog(f"❌ [{idx}] Échec (code {rc})")

            if self._single_file_mode:
                # si on n'a pas pu calculer un % pendant l'exécution, au moins conclure visuellement
                self._qprogress(100, maximum=100)
            else:
                self._qprogress(idx, maximum=total)

        self._qlog(f"🏁 Terminé : {ok_count} conversion(s) réussie(s).")
        self._qdone()

    def _build_output_path(self, dest_dir: str, src_path: str, fmt: str) -> str:
        base = os.path.splitext(os.path.basename(src_path))[0]
        out = os.path.join(dest_dir, base + "." + fmt)

        if not os.path.exists(out):
            return out

        i = 2
        while True:
            cand = os.path.join(dest_dir, f"{base} ({i}).{fmt}")
            if not os.path.exists(cand):
                return cand
            i += 1

    # ---------------- Duration / ffprobe ----------------

    def _get_media_duration_seconds(self, src_path: str) -> float | None:
        ffprobe = getattr(self.app, "ffprobe_path", None)
        if not ffprobe or not os.path.isfile(ffprobe):
            return None

        try:
            p = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    src_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            s = (p.stdout or "").strip()
            if not s:
                return None
            dur = float(s)
            if dur > 0:
                return dur
        except Exception:
            return None

        return None

    # ---------------- ffmpeg building ----------------

    def _ffmpeg_convert(self, src_path: str, out_path: str, fmt: str, keep_meta: bool, duration_s: float | None = None) -> int:
        ffmpeg = self.app.ffmpeg_path

        cmd = [ffmpeg, "-y", "-hide_banner", "-nostdin"]
        if duration_s and duration_s > 0:
            cmd += ["-progress", "pipe:1", "-nostats"]
        cmd += ["-i", src_path]

        # Métadonnées
        if keep_meta:
            cmd += ["-map_metadata", "0"]
        else:
            cmd += ["-map_metadata", "-1"]

        # Codec / qualité
        if fmt == "mp3":
            q = (getattr(self.app, "mp3_quality_var").get() if hasattr(self.app, "mp3_quality_var") else "5").strip() or "5"
            cmd += ["-vn", "-codec:a", "libmp3lame", "-q:a", q, out_path]

        elif fmt == "m4a":
            br = (getattr(self.app, "aac_bitrate_var").get() if hasattr(self.app, "aac_bitrate_var") else "192k").strip() or "192k"
            cmd += ["-vn", "-codec:a", "aac", "-b:a", br, out_path]

        elif fmt == "opus":
            br = (getattr(self.app, "opus_bitrate_var").get() if hasattr(self.app, "opus_bitrate_var") else "128k").strip() or "128k"
            cmd += ["-vn", "-codec:a", "libopus", "-b:a", br, out_path]

        elif fmt == "flac":
            lvl = (getattr(self.app, "flac_level_var").get() if hasattr(self.app, "flac_level_var") else "5").strip() or "5"
            cmd += ["-vn", "-codec:a", "flac", "-compression_level", lvl, out_path]

        elif fmt == "ogg":
            q = (getattr(self.app, "vorbis_quality_var").get() if hasattr(self.app, "vorbis_quality_var") else "4").strip() or "4"
            cmd += ["-vn", "-codec:a", "libvorbis", "-q:a", q, out_path]

        elif fmt == "wav":
            cmd += ["-vn", "-codec:a", "pcm_s16le", out_path]

        else:
            self._qlog(f"❌ Format non supporté : {fmt}")
            return 2

        self._qlog("▶️ ffmpeg : " + " ".join(cmd))
        return self._run_subprocess(cmd, duration_s=duration_s)

    def _ffmpeg_normalize_convert(self, src_path: str, out_path: str, fmt: str, keep_meta: bool, duration_s: float | None = None) -> int:
        ffmpeg = self.app.ffmpeg_path

        # Pass 1 : analyse loudnorm
        cmd_analyze = [
            ffmpeg, "-y", "-hide_banner", "-nostdin",
            "-i", src_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"
        ]
        self._qlog("🎚️ Normalisation (2 passes) — Pass 1/2 (analyse)")
        self._qlog("▶️ ffmpeg : " + " ".join(cmd_analyze))

        norm = self._run_subprocess_capture_json(cmd_analyze)
        if norm is None:
            self._qlog("❌ Analyse normalisation impossible.")
            return 2

        loudnorm = (
            f"loudnorm=I=-16:TP=-1.5:LRA=11:"
            f"measured_I={norm.get('input_i','-16')}:"
            f"measured_TP={norm.get('input_tp','-1.5')}:"
            f"measured_LRA={norm.get('input_lra','11')}:"
            f"measured_thresh={norm.get('input_thresh','-26')}:"
            f"offset={norm.get('target_offset','0')}:"
            f"linear=true:print_format=summary"
        )

        # Pass 2 : application + (optionnel) progress pipe
        cmd_apply = [ffmpeg, "-y", "-hide_banner", "-nostdin"]
        if duration_s and duration_s > 0:
            cmd_apply += ["-progress", "pipe:1", "-nostats"]
        cmd_apply += ["-i", src_path]

        if keep_meta:
            cmd_apply += ["-map_metadata", "0"]
        else:
            cmd_apply += ["-map_metadata", "-1"]

        cmd_apply += ["-af", loudnorm]

        if fmt == "mp3":
            q = (getattr(self.app, "mp3_quality_var").get() if hasattr(self.app, "mp3_quality_var") else "5").strip() or "5"
            cmd_apply += ["-vn", "-codec:a", "libmp3lame", "-q:a", q]
        elif fmt == "m4a":
            br = (getattr(self.app, "aac_bitrate_var").get() if hasattr(self.app, "aac_bitrate_var") else "192k").strip() or "192k"
            cmd_apply += ["-vn", "-codec:a", "aac", "-b:a", br]
        elif fmt == "opus":
            br = (getattr(self.app, "opus_bitrate_var").get() if hasattr(self.app, "opus_bitrate_var") else "128k").strip() or "128k"
            cmd_apply += ["-vn", "-codec:a", "libopus", "-b:a", br]
        elif fmt == "flac":
            lvl = (getattr(self.app, "flac_level_var").get() if hasattr(self.app, "flac_level_var") else "5").strip() or "5"
            cmd_apply += ["-vn", "-codec:a", "flac", "-compression_level", lvl]
        elif fmt == "ogg":
            q = (getattr(self.app, "vorbis_quality_var").get() if hasattr(self.app, "vorbis_quality_var") else "4").strip() or "4"
            cmd_apply += ["-vn", "-codec:a", "libvorbis", "-q:a", q]
        elif fmt == "wav":
            cmd_apply += ["-vn", "-codec:a", "pcm_s16le"]
        else:
            self._qlog(f"❌ Format non supporté : {fmt}")
            return 2

        cmd_apply += [out_path]

        self._qlog("🎚️ Normalisation (2 passes) — Pass 2/2 (application)")
        self._qlog("▶️ ffmpeg : " + " ".join(cmd_apply))
        return self._run_subprocess(cmd_apply, duration_s=duration_s)

    def _run_subprocess_capture_json(self, cmd: list[str]) -> dict | None:
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            self._qlog(f"❌ Impossible de lancer ffmpeg : {e}")
            return None

        json_buf = []
        in_json = False

        try:
            assert p.stdout is not None
            for line in p.stdout:
                if self._stop_event.is_set():
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    return None

                line = (line or "").rstrip()
                if line:
                    self._qlog(line)

                if line.strip() == "{":
                    in_json = True
                    json_buf = ["{"]
                    continue
                if in_json:
                    json_buf.append(line)
                    if line.strip() == "}":
                        in_json = False

            p.wait()

            raw = "\n".join(json_buf).strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw)
                except Exception:
                    return None
            return None

        except Exception as e:
            self._qlog(f"❌ Erreur pendant l'analyse : {e}")
            try:
                p.terminate()
            except Exception:
                pass
            return None

    def _run_subprocess(self, cmd: list[str], duration_s: float | None = None) -> int:
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            self._qlog(f"❌ Impossible de lancer ffmpeg : {e}")
            return 2

        last_percent = -1

        try:
            assert p.stdout is not None
            for line in p.stdout:
                if self._stop_event.is_set():
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    return 130

                line = (line or "").strip()
                if not line:
                    continue

                # Progress ffmpeg (key=value) si activé
                if duration_s and duration_s > 0 and "=" in line and self._single_file_mode:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()

                    if key == "out_time_ms":
                        try:
                            out_s = int(val) / 1_000_000.0
                            percent = int(max(0.0, min(100.0, (out_s / duration_s) * 100.0)))
                            if percent != last_percent:
                                last_percent = percent
                                self._qprogress(percent, maximum=100)
                        except Exception:
                            pass
                        continue

                    if key == "progress" and val == "end":
                        self._qprogress(100, maximum=100)
                        continue

                    # évite le spam de log progress
                    continue

                # Log classique
                self._qlog(line)

            rc = p.wait()
            return int(rc) if rc is not None else 1

        except Exception as e:
            self._qlog(f"❌ Erreur pendant la conversion : {e}")
            try:
                p.terminate()
            except Exception:
                pass
            return 1
