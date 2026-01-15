Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.
Le format est inspiré de Keep a Changelog et le versionnement suit une logique sémantique pragmatique.


[0.1.3] – 2026-01-15

Mise en place de l'autonaumie du programme : codec FFMPEG integré

Ajouté

--- 

[0.1.2] – 2026-01-15

Ajouté

Ajout de type d'exports : MP3 - FLAC - OGG - M4A - OPUS - WAV

---

[0.1.1] – 2026-01-15

Ajouté

File d’attente jusqu’à 10 URLs
Boutons d’ajout (+) et suppression (−) d’URL

[0.1.0] – 2026-01-14

---

Ajouté

    Interface graphique Tkinter multiplateforme
    Extraction audio YouTube via yt-dlp
    Extraction audio Twitch VOD (audio-only + conversion MP3)
    Journal d’exécution intégré à l’interface
    Dossier de sortie automatique par date
      klmp3/AA/MM/JJ/

---      

Technique

    Détection robuste de ffmpeg et ffprobe
      – via le PATH système
      – ou via tools/<platform>/
    Tkinter pur (aucun framework UI externe)
    PIL utilisé uniquement pour l’affichage du logo
    Aucune modification du PATH système
    Code structuré pour un futur packaging portable (multi-OS)

    
