Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.
Le format est inspiré de Keep a Changelog et le versionnement suit une logique sémantique pragmatique.

---

[2.6.2] – 2026-01-19

 - Ajout onglet aide

---

[2.6.1] – 2026-01-19

Modifié

 - Nettoyages des fichiers trnasitoires de Twitch
 - Nettoyages des fichiers temporaires en cas d'annulation utilisateur
 - message journal plus beaux

---

[2.6] – 2026-01-19

Ajouté

 - Onglet Métadonnées permet l'edition des"tags" et l'ajout d'images aux fichiers
 - Onglet Métadonnées créé dans un fichier à part : tab_tags.py
 - Possibilité de choisir plusieurs fichiers d'un coup
 - Permet de choisir le répertoire de déstination

 Modifié

  - Modification de la couleur des étiquettes des onglets: accentuation de la couleur de l'onglet séléctionné

---

[2.5.2] – 2026-01-19

Modifié

 - Pour stocker ffmpeg & ffprobe on priviliégie le repertoire tools au path de l'ordinateur

---

[2.5.1] – 2026-01-18

Modifié

 - windows > Forccage du UTF-8 et remplace les caractères illisibles au lieu de crasher
 - reconnaissance ameliorée des URL raccourcies les "Youtu.be" (non c'est pas la Belgique)
 - Réparation bug: fichier unique VS playlist 

---

[2.5] – 2026-01-18

Ajouté

- Boutons Coller et Couper à gauche du champ URL
- Fonction sélection via combo-box: télécharger un seul fichier ou une playlist
- Option: si option playlist sélectionnée: combien de fichiers --> sélecteur numérique (entre 2 et 1000)
- (si pas de limite cochée, playlist téléchargée entièrement (max 1000 fichiers))

---

[2.4.1] – 2026-01-17

Modifié

- Adaptation fichier embarqué "deno" pour macOS 

---

[2.4] – 2026-01-17

Ajouté

- Possibilité d'importer les sons d'une playlist entière (Youtube)

[2.3] – 2026-01-17

Ajouté

- Bouton "Coller" à gauche le champ URL qui récupere le contenu du presse papier

Modifié

- Déplacement des boutons + /- à droite du champ URL 


[2.2] – 2026-01-17

Ajouté

- Préfèrer un fichier “source” (.webm/.m4a/...) plutôt que de ramasser directement un .mp3 déjà présent
  (ce qui provoquait un ffmpeg in-place).

- Détection “déjà au bon format” via os.path.splitext (plus fiable que endswith quand il y a des caractères bizarres).

- Noms de fichiers Windows : ajout de --windows-filenames pour yt-dlp sur Windows, + renommage de sécurité via ensure_safe_path() 
  pour éviter les titres “toxiques” (variation selectors invisibles, etc.) qui font exploser ffmpeg.

---

[2.1] – 2026-01-17

Modifié

- Ajustement pour que les caractères speciaux et les emojis ne fassent plus crasher l'encodage

---

[2.0] – 2026-01-17

Ajouté

- Fonction choix du navigateur (dans lequel l'utilisateur à un compte Youtube)

---

[1.5] – 2026-01-16

Modifié

- Modifications pour empecher les popups de fenetres firefox sous windows

---

[1.4] – 2026-01-16

Ajouté

- Mise en place de l'autonomie du programme : on embarque "Deno" 
(Deno est le petit moteur JavaScript que yt-dlp utilise pour exécuter les scripts de YouTube (décryptage, challenges anti-bot), quand YouTube l’exige.)

---

[1.3] – 2026-01-15

Ajouté

- Mise en place de l'autonomie du programme : codec FFMPEG integré

--- 

[1.2] – 2026-01-15

Ajouté

- Ajout de type d'exports : MP3 - FLAC - OGG - M4A - OPUS - WAV

---

[1.1] – 2026-01-15

Ajouté

- File d’attente jusqu’à 10 URLs
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

    
