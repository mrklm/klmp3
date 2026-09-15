![Version](https://img.shields.io/badge/version-2.10.5-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)

## 🔈️ KLmp3 📢

Extracteur audio YouTube / Twitch / Audiomeans simple et multi-OS, écrit en Python + Tkinter.
Objectif : récupérer rapidement de l’audio propre (MP3,M4A,OPUS,FLAC,OGG,WAV) sans dépendre d’un environnement exotique.

---

## 👁️ Aperçu

![Fenêtre options](screenshots/KLmp3.png)
![Fenêtre general](screenshots/general.png)
![Fenêtre métadonnées](screenshots/meta.png)
![Fenêtre conversions](screenshots/convert.png)
![Fenêtre options](screenshots/options.png)
![Fenêtre aide](screenshots/aide.png)

---

## 📥 Téléchargement

## 💾 Applications standalone (recommandé)

La version des sources est **2.10.5**. Les liens ci-dessous restent ceux de la
version **2.10.4**, en attendant une prochaine publication des paquets.

- 🐧 **Linux**
  - [KLMP3-2.10.4-linux-x86_64.AppImage](https://github.com/mrklm/klmp3/releases)
  - [KLMP3-2.10.4-linux-x86_64.tar.gz](https://github.com/mrklm/klmp3/releases)
  
- 🍎 **macOS**
  - [KLMP3-2.10.4-macOS-x86_64.dmg](https://github.com/mrklm/klmp3/releases)

- 🪟 **Windows**  
  - [KLMP3-v2.10.4-windows-x86_64.zip](https://github.com/mrklm/klmp3/releases)

---         

## 🧰 Fonctionnalités

🪠 Extraction audio YouTube, Twitch VOD et lecteurs Audiomeans

📟️ Conversion des imports au choix en MP3, M4A, OPUS, FLAC, OGG, WAV

🔧 Options de normalisation avancées

📷️ Option de récupération du visuel associé au fichier

🗃️ Choix de telechargement: un fichier ou playlist entière

⚠️ Option nombre de fichiers maximum dans une playlist

📁 Dossier de sortie automatique par date --> ~/klmp3/AA/MM/JJ/

🗂️ Sous dossier automatique pour les playlist 

🐚 Onglet de conversion de fichiers 

🏳️‍🌈 Thèmes variés: sombres, clairs et rigolos.

📺️ Interface graphique légère (Tkinter pur)

🦏 Détection robuste de ffmpeg / ffprobe (PATH ou tools/)

⚡️ Fonction de mise à jour de YT-DLP (outil de téléchargement)

⚡️ Vérification automatique si mise à jour KLmp3 disponnible  

🗒️ Journal d’exécution intégré

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

## 🚀 Lancement: 

```bash
python3 klmp3.py
```

Arborescence minimale:

klmp3/

- klmp3.py
- ffmpeg_locator.py
- assets/ logo.png
- tools / ffmpeg + ffprobe

--- 

## 🧪 Utilisation depuis les sources (optionnel)

Pour lancer KLMP3 depuis le code source ou contribuer au projet.

## ⚙️ Pré-requis

- Python ≥ 3.9
- Git

---

## 🔧 Installation des dépendances
```bash
python -m pip install -r requirements.txt
```

## 🚀 Lancement
```bash
python klmp3.py
```
## 🏗️ Build (développeurs)
```bash
python -m pip install -r build-requirements.txt
```
---

## ✏️ Notes

Les pages web et lecteurs Audiomeans sont consultés par HTTP ; yt-dlp assure le téléchargement audio.

Le programme ne modifie pas le PATH système

Fonctionne sous  Linux / macOS / Windows

---

## 📜 Licence

Ce logiciel est distribué sous la GNU General Public License v3.0.

---

## 🛠️ Contribuer

Les contributions sont les bienvenues via Pull Requests.

---

## ⚠️ Avertissement

L'utilisation des audios extraits de Youtube & Twitch est
résérvé à un usage **strictement personnel** il ne doit en
aucun cas être diffusé ou partagé.

Ce logiciel est fourni **sans garantie**. L'auteur décline 
toute responsabilité en cas de dommage ou de dysfonctionnement.

---

## 💡 Pourquoi ce projet est-il sous licence libre ?

Ce projet s'inscrit dans la philosophie du logiciel libre, promue par des 
associations comme [April](https://www.april.org/). 

Le partage des connaissances et des outils est essentiel
pour une société numérique plus juste et transparente.

---

## 📬 Contact:

clementmorel@free.fr

---

🎧️ Bonne écoute avec KLmp3 !




## Audiomeans

Collez une URL `https://podcasts.audiomeans.fr/player-v2/<podcast>/episodes/<id>`
ou l’adresse d’une page contenant ce lecteur, puis démarrez le téléchargement.
Les liens intégrés via Embedly et les URL encodées sont reconnus. Le premier
lecteur d’épisode trouvé est téléchargé ; les playlists Audiomeans ne sont pas prises en charge.
La page doit exposer le lecteur dans son HTML. Pour Mediapart, si aucun lecteur
n’est trouvé sur la page publique, KLMP3 réessaie avec les cookies du profil
Firefox par défaut. Connectez-vous au préalable dans Firefox avec un abonnement
donnant accès à l’article. Seuls les cookies Mediapart sont utilisés, en mémoire,
et ils ne sont pas transmis au domaine Audiomeans. Le module Python yt-dlp est
nécessaire pour lire la session, même si le téléchargement utilise le binaire.
Les lecteurs chargés uniquement par JavaScript ne sont pas pris en charge.
En l’absence de lecteur, KLMP3 tente son extraction habituelle avec yt-dlp.

Le lecteur fournit `episode.audio.path` dans `window.__INITIAL_DATA__`.
KLMP3 relit ces données à chaque téléchargement et laisse le serveur audio
rediriger yt-dlp vers le fichier signé. Aucun paramètre de signature n’est
reconstruit ni conservé dans une configuration. Le mode binaire utilise un JSON
privé temporaire, supprimé après exécution, pour transmettre les métadonnées à yt-dlp.
Les liens directs `files.audiomeans.fr` sont également acceptés, mais un lien
signé expiré nécessite de repartir de l’URL du lecteur.

Le titre sert au nom du fichier ; l’option de pochette utilise le visuel du lecteur.
La conversion et la normalisation utilisent le même parcours FFmpeg que les autres sources.

Tests hors réseau (avec les dépendances installées) :

```bash
python -m unittest discover -s tests -v
```

Les tests couvrent les lecteurs directs, les intégrations HTML/Embedly simulées,
les erreurs, le renouvellement des métadonnées, les modes module/binaire de yt-dlp,
la classification YouTube et une conversion audio réelle si FFmpeg embarqué est présent.

## Publication automatique sur GitHub

Le workflow `.github/workflows/release.yml` construit Linux x86_64 (AppImage et
archive tar.gz), Windows x86_64 (ZIP) et macOS Intel (DMG et ZIP).
Il télécharge les outils embarqués, lance les tests et utilise les scripts de build
existants. Les outils sont téléchargés depuis leurs fournisseurs : FFmpeg via
John Van Sickle, Gyan et Evermeet, Deno et yt-dlp via leurs releases GitHub,
et appimagetool via le projet AppImage. Leurs versions sont affichées dans les logs ;
les téléchargements suivent les versions proposées par ces fournisseurs.

Pour publier, mettre à jour `APP_VERSION`, le README et le changelog, puis committer
et pousser les modifications avant de créer le tag correspondant :

```bash
git tag v2.10.5
git push origin v2.10.5
```

Le tag doit correspondre exactement à `APP_VERSION` et à une entrée du changelog.
Après réussite des trois builds, une release est publiée avec les paquets, les
sommes SHA-256 et les notes extraites du changelog. Une release déjà publiée n’est
pas écrasée. Aucun secret supplémentaire n’est requis : le job de publication
utilise le `GITHUB_TOKEN` fourni par GitHub Actions.

Pour essayer les builds sans publier, utiliser **Actions → Build and release →
Run workflow**. Les fichiers restent téléchargeables comme artefacts pendant 14 jours.
Les paquets Windows et macOS ne sont pas signés avec un certificat éditeur ; le
workflow ne réalise pas de notarisation Apple. Les builds distants devront être
validés lors de la première exécution du workflow.

## Podcasts web

Collez l’URL d’un épisode ou d’une série dans le champ habituel :

- Épisode Blast ou Radio France : téléchargement de cet épisode.
- Série Blast, mode **Un fichier** : premier épisode dans l’ordre de la page.
- Série Blast, mode **La playlist complète** : épisodes numérotés dans un
  sous-dossier, avec la limite de nombre choisie (maximum 1 000).
- URL de flux RSS : même choix fichier/playlist, dans l’ordre du flux.

Le moteur lit les données structurées `AudioObject.contentUrl`, les balises audio,
les champs `audio_url` JSON (dont les tables Nuxt) et les liens vers un flux RSS.
Le RSS de la série est prioritaire ; en cas d’échec, les audios présents dans la
page sont utilisés. Les paramètres et URL audio fournis sont conservés.
Les métadonnées disponibles sont insérées lorsque le format source le permet,
puis le parcours habituel assure conversion, normalisation et pochette optionnelle.

Ce premier périmètre ne parcourt pas les pages d’épisodes d’une série Radio France,
ne gère pas la pagination des collections et n’exécute pas le JavaScript des sites.
La compatibilité avec un autre site dépend des données qu’il expose. Aucun nouveau
mécanisme de connexion n’est ajouté ; le support Audiomeans existant est conservé.
