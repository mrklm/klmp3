Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.
Le format est inspiré de Keep a Changelog et le versionnement suit une logique sémantique pragmatique.




---

[2.9.10] – 2026-02-13

Modifié

 - Versionnage lisible par le buld script Linux 

---

[2.9.9] – 2026-02-13

Modifié

 - Sous Linux, les fichiers convertits arrivent dans un répertoire sur le bureau et non dans user
 
---

[2.9.8] – 2026-02-03

Modifié

 - yt-dlp chemin en cas de maj fonctionnel

---

[2.9.7] – 2026-02-03

Modifié

 - Partie du code "multi URL" enlevée.
 
---

[2.9.6] – 2026-02-02

Modifié

 - Plus de création de répertoire "conversion" à l'ouverture du programme

[2.9.5] – 2026-02-02

Modifié

 - Réorganisation des onglets métadonnées & conversion

---

[2.9.4] – 2026-02-02

Modifié

 - Interversion bouton texte dans la section téléchargement de KLmp3 

 - Modification du texte dans la section téléchargement de KLmp3 

---

[2.9.3] – 2026-02-2

Ajouté

 - Option de téléchargement de KLmp3 avec vérification de version dans l'onglet options

---

[2.9.2] – 2026-02-01

Modifié

 - Chemnin du fichier AIDE.md dans l'onglet aide enlevé

 - Réctification du procédé d'arrêt (boutons stop)

 - Suppression du bouton rafraichir dans l'onglet aide

---

[2.9.1] – 2026-02-01

Modifié

 - Les fichiers convértits vont dans un répértoire sur le bureau
   appelé "Klmp3conversions" suivi de AAMMJJ (année, mois, jour)
   suppression du journal --> infos vers l'ongelt général
   barre de progression comme dans l'onglet métadonnées 

 - Amélioration du comportement de la barre progréssion dans 
   l'onglet conversion

 - Boutons de choix du dossier cible et chemin intervertits dans onglet général

 - Ré organisation de l'ordre: Démarrer ---barre de progréssion--- Arrêter dans général

 - Ré organisation de l'ordre des onglets (général / métadonnées / conversion / options / aide)
 
---

[2.9] – 2026-02-01

Modifié

 - Ré organisation de l'onglet conversion
   suppression du journal --> infos vers l'ongelt général
   barre de progression comme dans l'onglet métadonnées 

---

[2.8.9] – 2026-02-01

Ajouté

 - Bouton Normaliser dans l'onglet conversion

---

[2.8.8] – 2026-02-02

Modifié

- Option avancée de normalisation dans l'onglet option -> LUFS-TP-LRA

---

[2.8.7] – 2026-02-01

Ajouté

 - Fonction de normalisation raccordée à l'interface graphique:
   case à cocher dans l'onglet général 
   choix du type de normalisation dans l'onglet option

 - mise a jour de l'aide (section normalisation)

---

[2.8.6] – 2026-02-01

Ajouté

 - Fonction de normalisation (pas encore raccordée à l'interface graphique)

Modifié

 - Boutons multi URL (+/-) enlevés 
 - Boutons "Coller" / "Effacer" placés de chaque coté de l'URL


 ---

[2.8.5] – 2026-01-28

 Ajouté

 - Mise en place de sous-processus en mode “no console” afin d'éviter les fenêtres fantomes lors
   de l'éxécution du programme sous windows.

---

[2.8.3] – 2026-01-28

Modifié

  - YouTube (Windows) — Correction d’un bug empêchant le téléchargement de vidéos lorsque 
    le client yt-dlp tv_embedded était forcé (erreur 152-18, VPN).

---

[2.8.2] – 2026-01-27

Ajouté

 - Bouton pour que l'utilisateur puisse mettre à jour YT-DLP dans l'onglet options
   (téléchargé dans un répertoire "tools" utilisateur)

---   

[2.8.1] – 2026-01-27

Modifié

 - Augmentation des temps (timeout) pour eviter les décrochages en cas de wifi bof
   timeout de téléchargement et timeout de création de répertoire de playlist

---

[2.8] – 2026-01-27

Ajouté

 - Onglet Coversion: possibilité de convertir des fichiers dans les formats MP3 - FLAC - OGG - M4A - OPUS - WAV
   options pour conserver ou non les métadonnées et le(s) fichier(s) source

---

[2.7.1] – 2026-01-27

Modifié

 - Re numérotation automatique si numerotation existente dans les nom de fichiers ex: 
   001 - fichier.mp3 = 01 - fichier.mp3 - Pas de N° si une seul fichier

---

[2.7] – 2026-01-26

Modifié

 - Systeme anticolision de noms revu: plus de code ID type:"[HHF697HHGV]" en mode automatique mais
   à la place une numérotation type "(02),(03)..." seulement en cas de doublons.
   
 - Numerotation automatique des playlists (01 - ,02 - ...) si moins de 100 titres, et (001 - ,002 - ...)
   pour plus de 100 titres et si le mode "playlist complète" est séléctionné

 ---

[2.6.4] – 2026-01-26

Modifié

 - Métadonnées: Le chemin de sortie se remet à zéro lorsque l'on change de répertoire d'entrée

---

[2.6.3] – 2026-01-26

Ajouté

 - Champs N° dans édition des métadonnées, on utilise le N° dans le 
   nom du fichier par defaut (case à cocher cochée)

Modifié

 - logique de métadonnées : nom de fichier n'égale pas titre on utilise le 
   titre dans le nom du fichier par defaut (case à cocher cochée) 

 - Si la case "ajouter une pochette" n'est pas cochée et qu'il y à déja une pochette, elle reste en place  

---

[2.6.2] – 2026-01-19

Ajouté

 - Ajout onglet aide

Modifié

 - Nommage des répertoires 
 - Chemins pour les répertoires
 - maj Aide + Section pour les geeks à la fin

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

    
