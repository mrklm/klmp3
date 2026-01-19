# ffmpeg_locator.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
import shutil
import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class FFmpegPaths:
    ffmpeg: str | None
    ffprobe: str | None
    source: str  # "PATH" or "TOOLS" or "MISSING"


def _app_base_dir() -> str:
    """
    Retourne le dossier de base où se trouvent assets/ et tools/.
    Compatible PyInstaller (sys._MEIPASS) si un jour tu bundles.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.abspath(sys._MEIPASS)  # PyInstaller extraction dir
    return os.path.dirname(os.path.abspath(__file__))


def _platform_tag() -> str:
    """
    Retourne un tag de dossier dans tools/, ex:
    - macos-x86_64
    - macos-arm64
    - windows-x86_64
    - linux-x86_64
    - linux-arm64
    """
    sysplat = sys.platform
    arch = platform.machine().lower()

    # normalisation arch
    if arch in ("x86_64", "amd64"):
        a = "x86_64"
    elif arch in ("arm64", "aarch64"):
        a = "arm64"
    else:
        a = arch  # fallback

    if sysplat == "darwin":
        return f"macos-{a}"
    if sysplat.startswith("win"):
        return f"windows-{a}"
    return f"linux-{a}"


def _candidate_in_tools(bin_name: str) -> str:
    """
    Chemin candidat dans tools/<platform>/bin_name
    """
    base = _app_base_dir()
    tag = _platform_tag()

    name = bin_name
    if sys.platform.startswith("win") and not name.lower().endswith(".exe"):
        name += ".exe"

    return os.path.join(base, "tools", tag, name)


def _is_executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def find_ffmpeg_tools_first() -> FFmpegPaths:
    """
    Stratégie (portable-friendly) :
    1) Cherche dans tools/<platform>/ en premier
    2) Sinon cherche dans PATH
    """
    cand_ffmpeg = _candidate_in_tools("ffmpeg")
    cand_ffprobe = _candidate_in_tools("ffprobe")

    # 1) TOOLS d'abord
    if _is_executable(cand_ffmpeg) and _is_executable(cand_ffprobe):
        return FFmpegPaths(ffmpeg=cand_ffmpeg, ffprobe=cand_ffprobe, source="TOOLS")

    # 2) PATH ensuite
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        return FFmpegPaths(ffmpeg=ffmpeg_path, ffprobe=ffprobe_path, source="PATH")

    # Rien trouvé proprement
    return FFmpegPaths(ffmpeg=None, ffprobe=None, source="MISSING")

    
