# tab_convert.py
# -*- coding: utf-8 -*-

import os
import threading
import queue
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog
import re
import json


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
    Onglet Conversion (fichier(s) -> format audio)
    - Sélection fichiers (unique ou lot)
    - Destination
    - Choix format + qualité (mêmes réglages que l'onglet Options via variables app.*)
    - Conserver métadonnées (map_metadata)
    - Supprimer sources après succès
    """

    FORMATS = ["mp3", "m4a", "opus", "flac", "ogg", "wav"]

    MP3_QUALITIES = [str(i) for i in range(0, 10)]                 # VBR LAME: 0..9
    AAC_BITRATES = [f"{k}k" for k in (96, 128, 160, 192, 224, 256, 320)]
    OPUS_BITRATES = [f"{k}k" for k in (64, 96, 128, 160, 192)]
    VORBIS_QUALITIES = [str(i) for i in range(0, 11)]              # 0..10
    FLAC_LEVELS = [str(i) for i in range(0, 13)]                   # 0..12 (large)

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self._files: list[str] = []
        self._worker: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._q: "queue.Queue[object]" = queue.Queue()

        self.dest_dir_var = tk.StringVar(value=os.path.expanduser("~"))

        self.keep_metadata_var = tk.BooleanVar(value=True)
        self.delete_source_var = tk.BooleanVar(value=False)
        self.normalize_var = tk.BooleanVar(value=False)

        # Qualité affichée (utilisée pour mapper les variables app.* selon le format)
        self.quality_label_var = tk.StringVar(value="Qualité MP3 (VBR)")
        self.quality_hint_var = tk.StringVar(value="(0 = meilleure qualité, 9 = plus léger)")
        self.quality_var = tk.StringVar(value=self.app.mp3_quality_var.get())

        self._build_ui()
        self._poll_queue()

        # Synchronisation format -> qualité
        self._on_format_changed()

    # ---------------- UI ----------------

    def _build_ui(self):
        # Ratio gauche/droite : 1/3 - 2/3
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # 2 lignes : Actions (haut) + contenu (bas)
        self.rowconfigure(0, weight=0)   # Actions
        self.rowconfigure(1, weight=1)   # Contenu

        # ---- Actions (EN HAUT, pleine largeur de l'onglet)
        frm_act = ttk.LabelFrame(self, text="Actions")
        frm_act.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))
        frm_act.columnconfigure(0, weight=1)

        act_inner = ttk.Frame(frm_act)
        act_inner.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        # colonnes: [spacer] [Convertir] [Progress] [Stop] [spacer]
        act_inner.columnconfigure(0, weight=1)
        act_inner.columnconfigure(1, weight=0)
        act_inner.columnconfigure(2, weight=1)
        act_inner.columnconfigure(3, weight=0)
        act_inner.columnconfigure(4, weight=1)

        self.btn_convert = ttk.Button(act_inner, text="Convertir", command=self._start_convert)
        self.btn_convert.grid(row=0, column=1, sticky="w")

        self.pb = ttk.Progressbar(act_inner, mode="determinate", maximum=1, value=0)
        self.pb.grid(row=0, column=2, sticky="ew", padx=(12, 12))
        try:
            self.pb.configure(length=260)
        except Exception:
            pass

        self.btn_stop = ttk.Button(act_inner, text="Stop", command=self._stop_convert, state="disabled")
        self.btn_stop.grid(row=0, column=3, sticky="e")

        # ---- Contenu (gauche/droite) sous Actions
        left = ttk.Frame(self)
        right = ttk.Frame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(10, 6), pady=(6, 10))
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=(6, 10))


        # ---- Gauche
        ttk.Button(left, text="Sélectionnez fichier(s)", command=self._select_files).pack(fill="x")

        # Style Treeview (liste fichiers) : fond noir + texte blanc
        style = ttk.Style(self)
        style.configure(
            "Convert.Treeview",
            background="black",
            foreground="white",
            fieldbackground="black",
        )
        style.configure(
            "Convert.Treeview.Heading",
            background="black",
            foreground="white",
        )
        style.map(
            "Convert.Treeview",
            background=[("selected", "gray25")],
            foreground=[("selected", "white")],
        )

        # Boîte fichiers : ajoute "Nom" + baisse la hauteur (~ -1/4)
        self.tree = ttk.Treeview(left, columns=("name", "ext", "size"), show="headings", height=9, style="Convert.Treeview")
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

        ttk.Button(
            btns,
            text="Retirer sélection",
            command=self._remove_selected,
            padding=(8, 1),
        ).grid(row=0, column=0, sticky="ew")

        ttk.Button(
            btns,
            text="Tout retirer",
            command=self._clear_files,
            padding=(8, 1),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # ---- Droite
        right.columnconfigure(0, weight=1)

        # Destination (avec bouton + entry)
        row_dest = ttk.Frame(right)
        row_dest.pack(fill="x", pady=(0, 10))
        row_dest.columnconfigure(1, weight=1)

        ttk.Button(
            row_dest,
            text="Sélectionner destination",
            command=self._select_dest,
            padding=(8, 1),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.ent_dest = ttk.Entry(row_dest, textvariable=self.dest_dir_var)
        self.ent_dest.grid(row=0, column=1, sticky="ew")

        frm_fmt = ttk.Frame(right)
        frm_fmt.pack(fill="x")

        # Type de conversion + Qualité (côte à côte)
        ttk.Label(frm_fmt, text="Type de conversion:").grid(row=0, column=0, sticky="w")

        row_fq = ttk.Frame(frm_fmt)
        row_fq.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        row_fq.columnconfigure(0, weight=0)
        row_fq.columnconfigure(1, weight=0)

        self.cmb_format = ttk.Combobox(
            row_fq,
            values=self.FORMATS,
            state="readonly",
            textvariable=self.app.audio_format_var,  # même variable que l'onglet Options
            width=10,
        )
        self.cmb_format.grid(row=0, column=0, sticky="w")
        self.cmb_format.bind("<<ComboboxSelected>>", lambda _e: self._on_format_changed())

        ttk.Label(row_fq, text="Par défaut :").grid(
            row=0, column=1, sticky="w", padx=(16, 6)
        )

        self.cmb_quality = ttk.Combobox(
            row_fq,
            state="readonly",
            textvariable=self.quality_var,
            width=10,
        )
        self.cmb_quality.grid(row=0, column=2, sticky="w")
        self.cmb_quality.bind("<<ComboboxSelected>>", lambda _e: self._apply_quality_to_app())

        # Normalisation (optionnel) — sous la qualité
        ttk.Checkbutton(
            frm_fmt,
            text="Normaliser",
            variable=self.normalize_var
        ).grid(row=2, column=0, sticky="w", pady=(0, 12))
        
        ttk.Checkbutton(
            frm_fmt,
            text="Conserver les métadonnées",
            variable=self.keep_metadata_var,
        ).grid(row=3, column=0, sticky="w")

        ttk.Checkbutton(
            frm_fmt,
            text="Supprimer la source après la conversion",
            variable=self.delete_source_var,
        ).grid(row=4, column=0, sticky="w", pady=(0, 12))


        self._log("Prêt. Sélectionnez un ou plusieurs fichiers à convertir.")

    # ---------------- Helpers ----------------

    def _log(self, msg: str):
        """Log côté UI.
        L'onglet Conversion n'affiche pas de journal dédié : on redirige vers le logger de l'app si présent.
        """
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
                    # Compat (anciens messages string)
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
            if running:
                self.pb.configure(value=0)
        except Exception:
            pass

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

        removed = 0
        # Supprime par index dans la liste _files : on map la selection aux lignes affichées
        visible = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if vals:
                visible.append(vals[0])  # name

        to_remove_names = set()
        for iid in sel:
            vals = self.tree.item(iid, "values")
            if vals:
                to_remove_names.add(vals[0])

        new_files = []
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
            self.dest_dir_var.set(os.path.normpath(d))

    def _on_format_changed(self):
        fmt = (self.app.audio_format_var.get() or "mp3").strip().lower()

        if fmt == "mp3":
            self.quality_label_var.set("Qualité MP3 (VBR)")
            self.quality_hint_var.set("(0 = meilleure qualité, 9 = plus léger)")
            self.cmb_quality.configure(values=self.MP3_QUALITIES)
            self.quality_var.set(self.app.mp3_quality_var.get())

        elif fmt == "m4a":
            self.quality_label_var.set("Bitrate AAC")
            self.quality_hint_var.set("(recommandé : 192k)")
            self.cmb_quality.configure(values=self.AAC_BITRATES)
            self.quality_var.set(self.app.aac_bitrate_var.get())

        elif fmt == "opus":
            self.quality_label_var.set("Bitrate OPUS")
            self.quality_hint_var.set("(recommandé : 128k)")
            self.cmb_quality.configure(values=self.OPUS_BITRATES)
            self.quality_var.set(self.app.opus_bitrate_var.get())

        elif fmt == "flac":
            self.quality_label_var.set("Compression FLAC")
            self.quality_hint_var.set("(impacte la taille/CPU, pas la qualité)")
            self.cmb_quality.configure(values=self.FLAC_LEVELS)
            self.quality_var.set(self.app.flac_level_var.get())

        elif fmt == "ogg":
            self.quality_label_var.set("Qualité OGG (Vorbis)")
            self.quality_hint_var.set("(0 = plus léger, 10 = meilleure qualité)")
            self.cmb_quality.configure(values=self.VORBIS_QUALITIES)
            self.quality_var.set(self.app.vorbis_quality_var.get())

        elif fmt == "wav":
            self.quality_label_var.set("WAV")
            self.quality_hint_var.set("= non compressé (16-bit), pas de réglage.")
            self.cmb_quality.configure(values=["(sans perte)"])
            self.quality_var.set("(sans perte)")

        else:
            self.quality_label_var.set("Qualité")
            self.quality_hint_var.set("")
            self.cmb_quality.configure(values=[])
            self.quality_var.set("")

        self._apply_quality_to_app()

    def _apply_quality_to_app(self):
        fmt = (self.app.audio_format_var.get() or "mp3").strip().lower()
        q = (self.quality_var.get() or "").strip()

        if fmt == "mp3":
            self.app.mp3_quality_var.set(q)
        elif fmt == "m4a":
            self.app.aac_bitrate_var.set(q)
        elif fmt == "opus":
            self.app.opus_bitrate_var.set(q)
        elif fmt == "flac":
            self.app.flac_level_var.set(q)
        elif fmt == "ogg":
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

        if not getattr(self.app, "ffmpeg_path", None) or not os.path.isfile(self.app.ffmpeg_path):
            self._log("ffmpeg introuvable. Vérifiez l'onglet Options / outils.")
            return

        self._stop_event.clear()

        # Progression
        try:
            self.pb.configure(maximum=max(1, len(self._files)), value=0)
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
        self._qprogress(0, maximum=total)
        self._qlog(f"▶️ Conversion vers {fmt} — {total} fichier(s)")

        ok_count = 0

        for idx, src in enumerate(list(self._files), start=1):
            if self._stop_event.is_set():
                self._qlog("⏹️ Arrêt demandé — conversion interrompue.")
                break

            if not os.path.isfile(src):
                self._qlog(f"⚠️ [{idx}] Fichier introuvable : {src}")
                self._qprogress(idx)
                continue

            out_path = self._build_output_path(dest_dir, src, fmt)
            self._qlog(f"🎛️ [{idx}/{total}] Source : {src}")
            self._qlog(f"🎧 [{idx}/{total}] Sortie : {out_path}")

            if bool(self.normalize_var.get()):
                rc = self._ffmpeg_normalize_convert(src, out_path, fmt, keep_meta)
            else:
                rc = self._ffmpeg_convert(src, out_path, fmt, keep_meta)

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

            self._qprogress(idx)

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

    # ---------------- ffmpeg building ----------------

    def _ffmpeg_convert(self, src_path: str, out_path: str, fmt: str, keep_meta: bool) -> int:
        ffmpeg = self.app.ffmpeg_path

        cmd = [ffmpeg, "-y", "-hide_banner", "-nostdin", "-i", src_path]

        # métadonnées
        if keep_meta:
            cmd += ["-map_metadata", "0"]
        else:
            cmd += ["-map_metadata", "-1"]

        # format / codec / qualité
        if fmt == "mp3":
            q = (self.app.mp3_quality_var.get() or "5").strip()
            cmd += ["-vn", "-codec:a", "libmp3lame", "-q:a", q, out_path]

        elif fmt == "m4a":
            br = (self.app.aac_bitrate_var.get() or "192k").strip()
            cmd += ["-vn", "-codec:a", "aac", "-b:a", br, out_path]

        elif fmt == "opus":
            br = (self.app.opus_bitrate_var.get() or "128k").strip()
            cmd += ["-vn", "-codec:a", "libopus", "-b:a", br, out_path]

        elif fmt == "flac":
            lvl = (self.app.flac_level_var.get() or "5").strip()
            cmd += ["-vn", "-codec:a", "flac", "-compression_level", lvl, out_path]

        elif fmt == "ogg":
            q = (self.app.vorbis_quality_var.get() or "4").strip()
            cmd += ["-vn", "-codec:a", "libvorbis", "-q:a", q, out_path]

        elif fmt == "wav":
            cmd += ["-vn", "-codec:a", "pcm_s16le", out_path]

        else:
            self._qlog(f"❌ Format non supporté : {fmt}")
            return 2

        self._qlog("▶️ ffmpeg : " + " ".join(cmd))
        return self._run_subprocess(cmd)

    def _ffmpeg_normalize_convert(self, src_path: str, out_path: str, fmt: str, keep_meta: bool) -> int:
        """
        Normalisation simple type EBU R128 :
        1) analyse loudnorm (pass 1)
        2) application loudnorm (pass 2)
        """
        ffmpeg = self.app.ffmpeg_path

        # Pass 1 (analyse)
        cmd_analyze = [
            ffmpeg, "-y", "-hide_banner", "-nostdin",
            "-i", src_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"
        ]
        self._qlog("🎚️ Normalisation (2 passes) — Pass 1/2 (analyse)")
        self._qlog("▶️ ffmpeg : " + " ".join(cmd_analyze))

        rc = self._run_subprocess_capture_json(cmd_analyze)
        if rc is None:
            self._qlog("❌ Analyse normalisation impossible.")
            return 2

        # Pass 2 (application loudnorm)
        loudnorm = (
            f"loudnorm=I=-16:TP=-1.5:LRA=11:"
            f"measured_I={rc.get('input_i','-16')}:"
            f"measured_TP={rc.get('input_tp','-1.5')}:"
            f"measured_LRA={rc.get('input_lra','11')}:"
            f"measured_thresh={rc.get('input_thresh','-26')}:"
            f"offset={rc.get('target_offset','0')}:"
            f"linear=true:print_format=summary"
        )

        cmd_apply = [ffmpeg, "-y", "-hide_banner", "-nostdin", "-i", src_path]

        if keep_meta:
            cmd_apply += ["-map_metadata", "0"]
        else:
            cmd_apply += ["-map_metadata", "-1"]

        cmd_apply += ["-af", loudnorm]

        # format / codec / qualité
        if fmt == "mp3":
            q = (self.app.mp3_quality_var.get() or "5").strip()
            cmd_apply += ["-vn", "-codec:a", "libmp3lame", "-q:a", q]
        elif fmt == "m4a":
            br = (self.app.aac_bitrate_var.get() or "192k").strip()
            cmd_apply += ["-vn", "-codec:a", "aac", "-b:a", br]
        elif fmt == "opus":
            br = (self.app.opus_bitrate_var.get() or "128k").strip()
            cmd_apply += ["-vn", "-codec:a", "libopus", "-b:a", br]
        elif fmt == "flac":
            lvl = (self.app.flac_level_var.get() or "5").strip()
            cmd_apply += ["-vn", "-codec:a", "flac", "-compression_level", lvl]
        elif fmt == "ogg":
            q = (self.app.vorbis_quality_var.get() or "4").strip()
            cmd_apply += ["-vn", "-codec:a", "libvorbis", "-q:a", q]
        elif fmt == "wav":
            cmd_apply += ["-vn", "-codec:a", "pcm_s16le"]
        else:
            self._qlog(f"❌ Format non supporté : {fmt}")
            return 2

        cmd_apply += [out_path]

        self._qlog("🎚️ Normalisation (2 passes) — Pass 2/2 (application)")
        self._qlog("▶️ ffmpeg : " + " ".join(cmd_apply))
        return self._run_subprocess(cmd_apply)

    def _run_subprocess_capture_json(self, cmd: list[str]) -> dict | None:
        """
        Lance ffmpeg et tente d'extraire un JSON loudnorm imprimé (pass 1).
        """
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

            # tente parse
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

    def _run_subprocess(self, cmd: list[str]) -> int:
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            self._qlog(f"❌ Impossible de lancer ffmpeg : {e}")
            return 2

        try:
            assert p.stdout is not None
            for line in p.stdout:
                if self._stop_event.is_set():
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    return 130

                line = (line or "").rstrip()
                if line:
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
