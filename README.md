## 🔈️ KLmp3 📢

Extracteur audio YouTube / Twitch simple et multi-OS, écrit en Python + Tkinter.
Objectif : récupérer rapidement de l’audio propre (MP3,M4A,OPUS,FLAC,OGG,WAV) sans dépendre d’un environnement exotique.

---

## Aperçu

![Fenêtre general](screenshots/general.png)
![Fenêtre options](screenshots/options.png)

---

📥 Téléchargement

👉 Les versions compilées sont disponibles dans la section Releases :
https://github.com/mrklm/klmp3/releases
Applications standalone (recommandé)

    Linux
        (à venir)

    macOS

        `KLMP3-1.3-macOS-x86_64.dmg` 
        `KLMP3-1.3-macOS-x86_64.zip`  

    Windows
        (à venir)

---         

## Fonctionnalités

🪠 Extraction audio YouTube et Twitch VOD

📋️ File d’attente jusqu’à 10 URLs

📟️ Conversion au choix en MP3, M4A, OPUS, FLAC, OGG, WAV

📺️ Interface graphique légère (Tkinter pur)

📁 Dossier de sortie automatique par date --> ~/klmp3/AA/MM/JJ/

🦏 Détection robuste de ffmpeg / ffprobe (PATH ou tools/)

🗒️ Journal d’exécution intégré

🏳️‍🌈 Thèmes variiés: sombres, clairs et rigolos.

---

 ## 💊 Dépendances:

Python ≥ 3.9

-yt-dlp (module Python)

-ffmpeg / ffprobe

-Installation de yt-dlp :

-python3 -m pip install --user -U yt-dlp


FFmpeg peut être :

-installé sur le système (PATH)

-ou placé dans tools/<platform>/

--- 

## 🚀 Lancement: python3 klmp3.py

Arborescence minimale:

klmp3/

- klmp3.py
- ffmpeg_locator.py
- assets/ logo.png
- tools / ffmpeg + ffprobe

--- 

✏️ Notes

Aucun accès réseau autre que celui de yt-dlp

Le programme ne modifie pas le PATH système

Fonctionne sous macOS / Linux / Windows

📜 Licence

Ce logiciel est distribué sous la GNU General Public License v3.0.
🛠️ Contribuer

Les contributions sont les bienvenues via Pull Requests.
📬 Contact

clementmorel@free.fr

🎧️ Bonne écoute avec KLmp3 !



