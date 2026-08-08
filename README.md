# SiLeMI/O EC4 LiveProfessor Bridge

Passerelle Windows portable reliant un **Faderfox EC4** à **LiveProfessor** par MIDI, SysEx et OSC. Le pont reste entièrement hors du chemin audio : il ne charge aucun plugin, n'installe aucun pilote et ne modifie pas les projets LiveProfessor.

Créé par **SiLeMI/O — By Mamat ------[]---**.

## Télécharger

La dernière version Windows est disponible dans les [releases GitHub](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest).

L'exécutable est autonome : copiez `EC4-LiveProfessor-Bridge.exe` sur le PC, branchez l'EC4 et lancez-le. Python n'est pas requis et aucun droit administrateur n'est nécessaire.

### Installer `.exe` (recommandé)

L'installateur Windows peut être généré avec :

```powershell
pwsh .\scripts\build-installer.ps1
```

Le fichier généré sera :

`output\installer\windows\EC4-LiveProfessor-Bridge-Setup-vX.Y.Z.exe`

Ce fichier propose un vrai assistant d'installation (choix du répertoire) et déploie le fichier `Ec4.ctrl2` présent dans le dépôt.

Si Inno Setup n'est pas installé, lance la commande suivante (avec droits utilisateur suffisants) :

```powershell
pwsh .\scripts\build-installer.ps1 -AutoInstallInnoSetup
```

Si l'installation automatique échoue, installe Inno Setup 6 une fois, puis relance la commande sans `-AutoInstallInnoSetup`.

## Prérequis

- Windows 10 ou 11 x64 ;
- Faderfox EC4 connecté en USB/MIDI ;
- LiveProfessor 2023.0.8 ou supérieur, avec une licence ou période d'essai officielle valide ;
- un **Companion Controller** LiveProfessor configuré sur `127.0.0.1:8010`, avec feedback vers `127.0.0.1:8011` ;
- des Controller Maps reliant `Rotary1` à `Rotary99` aux paramètres souhaités.

## Fonctionnalités

- détection et reconnexion automatique de l'EC4 ;
- choix d'un setup/groupe EC4 dédié ;
- apprentissage des 16 CC rotatifs et des 16 Notes de push pour n'importe quel groupe ;
- 99 contrôles OSC organisés en banques de 16 ;
- valeurs bidirectionnelles et garde anti-écho ;
- grille permanente des 16 paramètres du plugin sélectionné ;
- noms et textes de valeurs reçus dynamiquement depuis LiveProfessor Companion ;
- affichages SysEx principal et temporaire sur l'OLED de l'EC4 ;
- snapshots globaux, navigation plugin/chaîne et Tap Tempo ;
- profils JSON de secours pour le mode OSC générique ;
- configuration portable, journal tournant et diagnostic intégré.

## Commandes EC4 principales

| Geste | Action |
|---|---|
| Tourner les encodeurs 1–16 | Modifier les paramètres de la banque active |
| Shift + push 1 / 2 | Banque précédente / suivante |
| Shift + push 3 / 4 | Viewset précédent / suivant |
| Shift + push 5 | Afficher / masquer le plugin |
| Shift + push 6 | Chaîne précédente |
| Shift + push 7 / 8 | Plugin précédent / suivant |
| Shift + push 9 | Activer / désactiver le plugin |
| Shift + push 10 | Chaîne suivante |
| Shift + push 11 / 12 | Plugin précédent / suivant |
| Shift + push 13 / 14 | Cue précédent / suivant |
| Shift + push 15 / 16 | Snapshot global précédent / suivant |
| Push simple 16 | Tap Tempo |

Install simple sur un autre PC :

1. Télécharger l'archive de release depuis GitHub.
2. Décompresser dans `C:\\Apps\\EC4-LiveProfessor-Bridge`.
3. Lancer `install-ec4-liveprofessor-bridge.bat` (ou `install-ec4-liveprofessor-bridge.ps1`) pour copier l'application, créer le raccourci et préparer `config.json`.
4. Lancer l'application depuis le raccourci.

## Fichier `Ec4.ctrl2` (concept et personnalisation)

`Ec4.ctrl2` est le contrôleur Companion exporté depuis LiveProfessor utilisé par le pont pour mapper les 16 boutons et 16 rotatifs de l'EC4.

Concrètement, c’est le format attendu par LiveProfessor pour :

- les notes/inputs MIDI des boutons (`GenericButton1` à `GenericButton16`) ;
- les messages OSC `/Companion/RotaryN` avec les tags `Rotary1` à `Rotary16`.

Le dépôt propose une version prête à l’emploi :

- [Ec4.ctrl2](./Ec4.ctrl2)

Pour le personnaliser :

1. Exporter ton contrôleur Companion (`.ctrl2`) depuis LiveProfessor ;
2. (Recommandé) corriger le format avec :

```powershell
python .\scripts\repair_ctrl2.py "C:\chemin\mon.ctrl2" .\Ec4.ctrl2
```

3. Re-générer l'installateur pour inclure cette version.

## Démarrage rapide

1. Dans LiveProfessor, ajouter un **Companion Controller** avec entrée `8010` et feedback `8011`, puis vérifier que `Rotary1` à `Rotary16` existent pour la première banque. Le preset Companion standard peut n'en proposer que quatre ; ajouter les rotatifs manquants dans Hardware Controllers Setup.
2. Dans le **Controller Map actif**, relier les `RotaryN` aux paramètres du plugin, idéalement avec **Only If Selected**. Le bouton Learn de la définition du contrôleur apprend seulement le message OSC ; il ne crée pas cette affectation au plugin.
3. Brancher l'EC4 et lancer `EC4-LiveProfessor-Bridge.exe`.
4. Choisir les ports `Faderfox EC4`, puis cliquer sur **Démarrer**.
5. Sélectionner le setup/groupe EC4 souhaité et cliquer sur **Utiliser le setup/groupe actuel**.
6. Pour un groupe personnalisé, cliquer sur **Apprendre rotatifs + push**, puis suivre les deux séquences 1–16.

L'application enregistre sa configuration dans `%LOCALAPPDATA%\EC4LiveProfessorBridge\config.json`. Pour un fonctionnement portable, placez un `config.json` à côté de l'exécutable. Copiez ce fichier avec l'exécutable pour retrouver le mapping sur un autre PC.

## Documentation

- [Guide d'installation et d'utilisation](docs/GUIDE_INSTALLATION_UTILISATION.md)
- [Configuration EC4](docs/CONFIGURATION_EC4.md)
- [Cartographie MIDI et SysEx](docs/CARTOGRAPHIE_MIDI_SYSEX.md)
- [Sources techniques](docs/SOURCES.md)

## Développement

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-build.txt
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build.ps1
.\scripts\build-installer.ps1 -NoBuild
```

La version 0.4.1 trace chaque mouvement EC4 jusqu'au `RotaryN` envoyé et confirme le retour LiveProfessor. Elle passe les tests unitaires ainsi que les diagnostics autonomes `--self-test` et `--list-midi`.

## Statut juridique

Ce dépôt est public, mais aucune licence open source n'est accordée pour le moment. Tous droits réservés à Mamat / SiLeMI/O.

Faderfox, LiveProfessor, Audioström, Ableton, VST et les autres marques citées appartiennent à leurs propriétaires respectifs. Ce projet indépendant n'est ni affilié ni approuvé par ces sociétés. Aucun logiciel, script ou élément propriétaire tiers n'est redistribué dans ce dépôt.
