![Version](https://img.shields.io/badge/version-2.10.8-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)

## 🔈️ KLmp3 📢

Extracteur audio YouTube, Twitch, Audiomeans et Podcasts web pour Linux, Windows et macOS.
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

## 🎙️ Podcasts web : épisodes et séries

Collez l’URL dans le champ habituel, choisissez le dossier et le format de sortie,
puis cliquez sur **Démarrer**.

| URL et mode choisis | Résultat |
| --- | --- |
| Page d’un épisode Blast ou Radio France | Cet épisode uniquement |
| Page d’une série reconnue, mode fichier unique | Premier épisode dans l’ordre de la page |
| Page d’une série reconnue, **La playlist complète** | Épisodes dans l’ordre, avec la limite éventuelle |
| Flux RSS de podcast | Premier épisode ou playlist, dans l’ordre du flux |

**Pour télécharger plusieurs épisodes d’une série, pensez à sélectionner
« La playlist complète ».** La limite maximale est de 1 000 épisodes.

Après application du mode et de la limite :

- **Plusieurs fichiers** : sous-dossier au nom de la série, fichiers numérotés.
- **Un seul fichier** : directement dans le dossier de sortie, sans numéro ajouté.

La conversion et la normalisation restent disponibles. Le titre, l’auteur, la date
et la série sont renseignés lorsque ces informations sont disponibles et que le
format source permet leur insertion. L’option de pochette utilise le visuel fourni
par la source lorsqu’il est disponible.

Le moteur reconnaît les liens audio et les données structurées exposés par les
pages, ainsi que les flux RSS associés. Il prend notamment en charge les épisodes
et séries Blast, et les séries Radio France décrites par une liste structurée
d’épisodes. Il ne suit pas les simples liens de recommandation.

**Limites actuelles :** la pagination des collections et les lecteurs nécessitant
l’exécution de JavaScript ne sont pas gérés. Les séries Radio France annonçant
plusieurs pages sont signalées comme non prises en charge. Un épisode sans audio
arrête la playlist avec un message explicite. La compatibilité avec d’autres sites
dépend des données qu’ils exposent ; la fonction n’est pas universelle.

## 🎧 Audiomeans

Collez l’URL d’un lecteur Audiomeans ou d’une page qui l’intègre pour télécharger
l’épisode auquel vous avez accès. La conversion, la normalisation et la récupération
de pochette sont disponibles. Les playlists Audiomeans ne sont pas prises en charge.

## 🔄 Mise à jour de KLMP3

Dans **Options**, KLMP3 recherche une version plus récente compatible avec le
système et l’architecture de l’ordinateur. Sur macOS, il vérifie aussi la version
du système requise par le paquet.

Si une nouvelle release existe mais qu’aucun paquet compatible n’est confirmé,
le bouton de téléchargement reste désactivé. Par exemple, un paquet destiné à
macOS récent n’est pas proposé à un utilisateur sous Catalina ou High Sierra.
Une erreur réseau est signalée comme une vérification indisponible.

Cette vérification dépend des informations de compatibilité publiées avec chaque
release. Les futures variantes High Sierra et Catalina restent à construire et
à vérifier ; elles ne sont pas encore produites par le workflow actuel.

La mise à jour de **yt-dlp** utilise un bouton distinct : le filtrage de compatibilité
décrit ici concerne les paquets **KLMP3**.

---

## 📥 Téléchargement

## 💾 Applications standalone (recommandé)

Version **2.10.8** : les paquets ci-dessous seront disponibles après réussite
des builds et publication de la release.

- 🐧 **Linux**
  - [KLMP3-2.10.8-linux-x86_64.AppImage](https://github.com/mrklm/klmp3/releases)
  - [KLMP3-2.10.8-linux-x86_64.tar.gz](https://github.com/mrklm/klmp3/releases)
  
- 🍎 **macOS**
  - [KLMP3-2.10.8-macOS-x86_64.dmg](https://github.com/mrklm/klmp3/releases)

- 🪟 **Windows**  
  - [KLMP3-v2.10.8-windows-x86_64.zip](https://github.com/mrklm/klmp3/releases)

---         

## 🧰 Fonctionnalités

🪠 Extraction audio YouTube, Twitch VOD, lecteurs Audiomeans et Podcasts web (notamment Blast et Radio France)

📟️ Conversion des imports au choix en MP3, M4A, OPUS, FLAC, OGG, WAV

🔧 Options de normalisation avancées

📷️ Option de récupération du visuel associé au fichier

🗃️ Choix de telechargement: un fichier ou playlist entière

⚠️ Option nombre de fichiers maximum dans une playlist

📁 Dossier de sortie personnalisable dans l’onglet Général

🗂️ Podcasts web : sous-dossier de série et numérotation si plusieurs épisodes sont sélectionnés

🐚 Onglet de conversion de fichiers 

🏳️‍🌈 Thèmes variés: sombres, clairs et rigolos.

📺️ Interface graphique légère (Tkinter pur)

🦏 Détection robuste de ffmpeg / ffprobe (PATH ou tools/)

⚡️ Fonction de mise à jour de YT-DLP (outil de téléchargement)

⚡️ Recherche automatique d’une mise à jour compatible avec votre ordinateur

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

Conservez l’ensemble des fichiers du dépôt : les modules de téléchargement,
de mise à jour et les onglets sont répartis dans plusieurs fichiers Python.
Le dossier `assets/` contient notamment les visuels et l’aide ; `tools/` peut
contenir les exécutables embarqués.

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
