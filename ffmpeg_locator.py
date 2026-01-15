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
    Stratégie :
    1) Cherche dans PATH
    2) Sinon cherche dans tools/<platform>/
    """
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        return FFmpegPaths(ffmpeg=ffmpeg_path, ffprobe=ffprobe_path, source="PATH")

    cand_ffmpeg = _candidate_in_tools("ffmpeg")
    cand_ffprobe = _candidate_in_tools("ffprobe")

    if _is_executable(cand_ffmpeg) and _is_executable(cand_ffprobe):
        return FFmpegPaths(ffmpeg=cand_ffmpeg, ffprobe=cand_ffprobe, source="TOOLS")

    # Si l'un des deux manque, on garde ce qu'on a trouvé.
    # (Mais KLmp3 exigera les deux au check.)
    return FFmpegPaths(
        ffmpeg=ffmpeg_path if ffmpeg_path else (cand_ffmpeg if _is_executable(cand_ffmpeg) else None),
        ffprobe=ffprobe_path if ffprobe_path else (cand_ffprobe if _is_executable(cand_ffprobe) else None),
        source="MISSING",
    )
