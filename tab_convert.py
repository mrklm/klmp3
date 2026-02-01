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
    - Journal temps réel
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
        self._q: "queue.Queue[str]" = queue.Queue()

        self.dest_dir_var = tk.StringVar(value=os.path.expanduser("~"))

        self.keep_metadata_var = tk.BooleanVar(value=True)
        self.delete_source_var = tk.BooleanVar(value=False)
        self.normalize_var = tk.BooleanVar(value=False)


        # Qualité affichée (synchro avec les variables de l'app)
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
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self)
        right = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)

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
        ttk.Button(btns, text="Retirer sélection", command=self._remove_selected).pack(side="left")
        ttk.Button(btns, text="Tout retirer", command=self._clear_files).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(left, text="Conserver les métadonnées", variable=self.keep_metadata_var).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(left, text="Supprimer fichier(s) source", variable=self.delete_source_var).pack(anchor="w", pady=(4, 0))

        # ---- Droite
        frm_fmt = ttk.Frame(right)
        frm_fmt.pack(fill="x")

        # Type de conversion
        ttk.Label(frm_fmt, text="Type de conversion").grid(row=0, column=0, sticky="w")
        self.cmb_format = ttk.Combobox(
            frm_fmt,
            values=self.FORMATS,
            state="readonly",
            textvariable=self.app.audio_format_var,  # même variable que l'onglet Options
            width=10,
        )
        self.cmb_format.grid(row=1, column=0, sticky="w", pady=(4, 10))
        self.cmb_format.bind("<<ComboboxSelected>>", lambda _e: self._on_format_changed())

        # Qualité + indications (comme l'onglet Options)
        ttk.Label(frm_fmt, textvariable=self.quality_label_var).grid(row=2, column=0, sticky="w")

        row_q = ttk.Frame(frm_fmt)
        row_q.grid(row=3, column=0, sticky="ew", pady=(4, 12))
        row_q.columnconfigure(0, weight=0)
        row_q.columnconfigure(1, weight=1)

        # Combo qualité plus étroite (~2/3)
        self.cmb_quality = ttk.Combobox(row_q, state="readonly", textvariable=self.quality_var, width=10)
        self.cmb_quality.grid(row=0, column=0, sticky="w")
        self.cmb_quality.bind("<<ComboboxSelected>>", lambda _e: self._apply_quality_to_app())

        self.lbl_quality_hint = ttk.Label(row_q, textvariable=self.quality_hint_var)
        self.lbl_quality_hint.grid(row=0, column=1, sticky="w", padx=(10, 0))
        
        # Normalisation (optionnel) — sous la qualité
        ttk.Checkbutton(
            frm_fmt,
            text="Normaliser",
            variable=self.normalize_var
        ).grid(row=4, column=0, sticky="w", pady=(0, 12))


        frm_dest = ttk.Frame(right)
        frm_dest.pack(fill="x", pady=(0, 10))
        ttk.Button(frm_dest, text="Sélectionnez Destination", command=self._select_dest).pack(fill="x", pady=(0, 6))
        ttk.Label(frm_dest, textvariable=self.dest_dir_var, anchor="w").pack(fill="x")

        frm_run = ttk.Frame(right)
        frm_run.pack(fill="x", pady=(6, 8))
        ttk.Button(frm_run, text="Convertir", command=self._start_convert).pack(side="left", fill="x", expand=True)
        ttk.Button(frm_run, text="Stop", command=self._stop_convert).pack(side="left", fill="x", expand=True, padx=(10, 0))

        ttk.Label(right, text="Journal").pack(anchor="w")
        self.txt_log = tk.Text(right, height=12, wrap="word")
        self.txt_log.pack(fill="both", expand=True, pady=(4, 0))

        self._log("Prêt. Sélectionnez un ou plusieurs fichiers à convertir.")

    # ---------------- Helpers ----------------

    def _log(self, msg: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _qlog(self, msg: str):
        self._q.put(msg)

    def _poll_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                self._log(msg)
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

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
            return
        idxs = sorted([self.tree.index(i) for i in sel], reverse=True)
        removed = 0
        for idx in idxs:
            try:
                self._files.pop(idx)
                removed += 1
            except Exception:
                pass
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
            if q in self.MP3_QUALITIES:
                self.app.mp3_quality_var.set(q)

        elif fmt == "m4a":
            if q in self.AAC_BITRATES:
                self.app.aac_bitrate_var.set(q)

        elif fmt == "opus":
            if q in self.OPUS_BITRATES:
                self.app.opus_bitrate_var.set(q)

        elif fmt == "flac":
            if q in self.FLAC_LEVELS:
                self.app.flac_level_var.set(q)

        elif fmt == "ogg":
            if q in self.VORBIS_QUALITIES:
                self.app.vorbis_quality_var.set(q)

        # wav: rien à appliquer

    # ---------------- Conversion engine ----------------

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

        self._qlog(f"▶️ Conversion vers {fmt} — {len(self._files)} fichier(s)")

        ok_count = 0
        for idx, src in enumerate(list(self._files), start=1):
            if self._stop_event.is_set():
                self._qlog("⏹️ Arrêt demandé — conversion interrompue.")
                break

            if not os.path.isfile(src):
                self._qlog(f"⚠️ [{idx}] Fichier introuvable : {src}")
                continue

            out_path = self._build_output_path(dest_dir, src, fmt)
            self._qlog(f"🎛️ [{idx}/{len(self._files)}] Source : {src}")
            self._qlog(f"🎧 [{idx}/{len(self._files)}] Sortie : {out_path}")

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

        self._qlog(f"🏁 Terminé : {ok_count} conversion(s) réussie(s).")

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

    def _ffmpeg_convert(self, in_path: str, out_path: str, fmt: str, keep_meta: bool) -> int:
        if fmt == "mp3":
            codec = "libmp3lame"
            args = ["-q:a", self.app.mp3_quality_var.get().strip()]

        elif fmt == "m4a":
            codec = "aac_at" if (os.sys.platform == "darwin" and getattr(self.app, "has_aac_at", False)) else "aac"
            args = ["-b:a", self.app.aac_bitrate_var.get().strip()]

        elif fmt == "opus":
            codec = "libopus"
            args = ["-b:a", self.app.opus_bitrate_var.get().strip()]

        elif fmt == "flac":
            codec = "flac"
            args = ["-compression_level", self.app.flac_level_var.get().strip()]

        elif fmt == "ogg":
            codec = "libvorbis"
            args = ["-q:a", self.app.vorbis_quality_var.get().strip()]

        elif fmt == "wav":
            codec = "pcm_s16le"
            args = []

        else:
            self._qlog(f"❌ Format inconnu : {fmt}")
            return 2

        cmd = [
            self.app.ffmpeg_path,
            "-y",
            "-i", in_path,
            "-map", "0:a:0",
            "-vn",
        ]

        if keep_meta:
            cmd += ["-map_metadata", "0"]

        cmd += ["-c:a", codec]
        cmd += args
        cmd += [out_path]

        self._qlog("▶️ ffmpeg : " + " ".join(cmd))
        return self._run_subprocess(cmd)
    
    def _get_norm_targets(self) -> tuple[float, float, float]:
        #Récupère (I, TP, LRA) depuis l'app si disponible.
        #Fallback sur (-16, -1.5, 11) si absent ou invalide.
        def _read_float(var_name: str, default: float) -> float:
            try:
                v = getattr(self.app, var_name)
                # var Tk (StringVar) -> .get()
                if hasattr(v, "get"):
                    s = str(v.get()).strip().replace(",", ".")
                else:
                    s = str(v).strip().replace(",", ".")
                return float(s)
            except Exception:
                return default

        I = _read_float("norm_target_i_var", -16.0)
        TP = _read_float("norm_target_tp_var", -1.5)
        LRA = _read_float("norm_target_lra_var", 11.0)

        # garde-fous raisonnables
        if not (-30.0 <= I <= -5.0):
            I = -16.0
        if not (-6.0 <= TP <= 0.0):
            TP = -1.5
        if not (1.0 <= LRA <= 20.0):
            LRA = 11.0

        return I, TP, LRA

    def _parse_loudnorm_json(self, collected_output: str) -> dict | None:
        m = re.search(r"\{.*\}", collected_output, flags=re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    def _run_subprocess_collect(self, cmd: list[str]) -> tuple[int, str]:
        """
        Exécute une commande et retourne (code, stdout+stderr).
        Respecte le bouton Stop.
        """
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            self._qlog(f"❌ Impossible de lancer ffmpeg : {e}")
            return 2, ""

        out_lines: list[str] = []
        try:
            assert p.stdout is not None
            for line in p.stdout:
                if self._stop_event.is_set():
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    return 130, "\n".join(out_lines)

                line = (line or "").rstrip()
                if line:
                    out_lines.append(line)
                    self._qlog(line)

            rc = p.wait()
            return (int(rc) if rc is not None else 1), "\n".join(out_lines)

        except Exception as e:
            self._qlog(f"❌ Erreur pendant la conversion : {e}")
            try:
                p.terminate()
            except Exception:
                pass
            return 1, "\n".join(out_lines)

    def _ffmpeg_normalize_convert(self, in_path: str, out_path: str, fmt: str, keep_meta: bool) -> int:
        """
        Convertit + normalise (loudnorm).
        - Si l'app expose normalization_mode_var et NORM_MODE_TWO_PASS : utilise 2 passes.
        - Sinon : 1 passe.
        """
        # codec + args (mêmes règles que _ffmpeg_convert)
        if fmt == "mp3":
            codec = "libmp3lame"
            args = ["-q:a", self.app.mp3_quality_var.get().strip()]

        elif fmt == "m4a":
            codec = "aac_at" if (os.sys.platform == "darwin" and getattr(self.app, "has_aac_at", False)) else "aac"
            args = ["-b:a", self.app.aac_bitrate_var.get().strip()]

        elif fmt == "opus":
            codec = "libopus"
            args = ["-b:a", self.app.opus_bitrate_var.get().strip()]

        elif fmt == "flac":
            codec = "flac"
            args = ["-compression_level", self.app.flac_level_var.get().strip()]

        elif fmt == "ogg":
            codec = "libvorbis"
            args = ["-q:a", self.app.vorbis_quality_var.get().strip()]

        elif fmt == "wav":
            codec = "pcm_s16le"
            args = []

        else:
            self._qlog(f"❌ Format inconnu : {fmt}")
            return 2

        I, TP, LRA = self._get_norm_targets()

        # Lecture du mode 1/2 passes depuis l'app si dispo
        mode = ""
        try:
            v = getattr(self.app, "normalization_mode_var", None)
            if v is not None and hasattr(v, "get"):
                mode = str(v.get()).strip()
        except Exception:
            mode = ""

        # Heuristique simple : si le libellé contient "Deux passes", on fait 2 passes
        two_pass = ("Deux passes" in mode)

        if not two_pass:
            af = f"loudnorm=I={I}:TP={TP}:LRA={LRA}"

            cmd = [
                self.app.ffmpeg_path, "-y",
                "-i", in_path,
                "-map", "0:a:0",
                "-vn",
                "-af", af,
            ]
            if keep_meta:
                cmd += ["-map_metadata", "0"]

            cmd += ["-c:a", codec]
            cmd += args
            cmd += [out_path]

            self._qlog("🎚️ Normalisation (1 passe) : " + af)
            self._qlog("▶️ ffmpeg : " + " ".join(cmd))
            return self._run_subprocess(cmd)

        # -------- 2 passes --------
        af_measure = f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json"
        cmd_measure = [
            self.app.ffmpeg_path, "-y",
            "-i", in_path,
            "-map", "0:a:0",
            "-vn",
            "-af", af_measure,
            "-f", "null",
            "-"
        ]

        self._qlog("🎚️ Normalisation (2 passes) — Pass 1/2 (mesure)")
        self._qlog("▶️ ffmpeg : " + " ".join(cmd_measure))
        rc1, out1 = self._run_subprocess_collect(cmd_measure)
        if rc1 != 0:
            return rc1

        meas = self._parse_loudnorm_json(out1)
        if not meas:
            self._qlog("❌ Mesures loudnorm introuvables (JSON).")
            return 1

        try:
            measured_I = float(meas["input_i"])
            measured_TP = float(meas["input_tp"])
            measured_LRA = float(meas["input_lra"])
            measured_thresh = float(meas["input_thresh"])
            offset = float(meas["target_offset"])
        except Exception:
            self._qlog("❌ Mesures loudnorm invalides/incomplètes.")
            return 1

        af_apply = (
            f"loudnorm=I={I}:TP={TP}:LRA={LRA}"
            f":measured_I={measured_I}:measured_TP={measured_TP}:measured_LRA={measured_LRA}"
            f":measured_thresh={measured_thresh}:offset={offset}:linear=true:print_format=summary"
        )

        cmd_apply = [
            self.app.ffmpeg_path, "-y",
            "-i", in_path,
            "-map", "0:a:0",
            "-vn",
            "-af", af_apply,
        ]
        if keep_meta:
            cmd_apply += ["-map_metadata", "0"]

        cmd_apply += ["-c:a", codec]
        cmd_apply += args
        cmd_apply += [out_path]

        self._qlog("🎚️ Normalisation (2 passes) — Pass 2/2 (application)")
        self._qlog("▶️ ffmpeg : " + " ".join(cmd_apply))
        return self._run_subprocess(cmd_apply)


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
