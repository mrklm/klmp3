#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import tkinter as tk
from tkinter import ttk


def _resource_path(relpath: str) -> str:
    """
    Renvoie un chemin lisible vers une ressource:
    - en dev: relatif au dossier du .py
    - en PyInstaller: depuis sys._MEIPASS
    - fallback: dossier de l'exécutable / cwd
    """
    # PyInstaller
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, relpath)
        if os.path.exists(p):
            return p

    # Dossier du script
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, relpath)
    if os.path.exists(p):
        return p

    # Dossier de l'exécutable
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    p = os.path.join(exe_dir, relpath)
    if os.path.exists(p):
        return p

    # CWD
    return os.path.join(os.getcwd(), relpath)


class HelpTab(ttk.Frame):
    """
    Onglet Aide : affiche le contenu de AIDE.md dans une zone texte
    - fond noir
    - texte gris clair
    - texte centré
    - scroll vertical
    - lecture seule
    """

    def __init__(self, parent, md_filename: str = "AIDE.md"):
        super().__init__(parent)
        self.md_filename = md_filename

        # Layout
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Zone texte + scrollbar
        frm = ttk.Frame(self)
        frm.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(0, weight=1)

        self.txt = tk.Text(
            frm,
            wrap="word",
            height=20,
            bg="#0f0f10",
            fg="#d0d0d0",
            insertbackground="#d0d0d0",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=18,
            pady=14,
            font=("Helvetica", 18),
        )
        self.txt.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(frm, orient="vertical", command=self.txt.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.txt.configure(yscrollcommand=yscroll.set)

        # Tag de style : centrage global
        self.txt.tag_configure("center", justify="center")

        self.load()

    def load(self):
        path = _resource_path(self.md_filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Nettoyage Unicode : supprime les Variation Selectors (ex: U+FE0F) (espaces fantomes sous win)
            content = content.replace("\uFE0F", "")

        except Exception as e:
            content = (
                f"❌ Impossible de lire {self.md_filename}.\n\n"
                f"📍 Chemin essayé : {path}\n"
                f"💥 Erreur : {e}\n\n"
                f"🧠 Astuce : placez {self.md_filename} à côté de klmp3.py (en dev),\n"
                f"ou embarquez-le dans le build (PyInstaller --add-data).\n"
            )

        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", content)

        # Appliquer centrage sur tout le texte
        self.txt.tag_add("center", "1.0", "end")

        self.txt.configure(state="disabled")
