# EC4 LiveProfessor Bridge

🇬🇧 **English reader? [Jump directly to the English version.](#english-version)**

**Une passerelle intelligente entre le Faderfox EC4 et LiveProfessor.**

**Version stable actuelle : 2026.1**

Le **Faderfox EC4** est un excellent contrôleur MIDI : compact, robuste, équipé de 16 encodeurs avec poussoir et d’un écran OLED très utile pour le retour d’information.

Avec une connexion MIDI classique, on peut bien sûr piloter LiveProfessor directement. Mais on se retrouve vite avec des affectations fixes, peu de contexte sur ce que contrôle chaque encodeur, et une intégration limitée lorsque l’on change de plugin, de banque ou de paramètre.

**EC4 LiveProfessor Bridge a été créé pour transformer l’EC4 en véritable surface de contrôle dynamique pour LiveProfessor.**

Il ajoute une couche de communication entre les deux :

- les 16 encodeurs pilotent les paramètres du plugin sélectionné ;
- les noms et valeurs des paramètres reviennent depuis LiveProfessor ;
- l’écran OLED de l’EC4 affiche directement ce que l’on contrôle ;
- les valeurs sont synchronisées dans les deux sens pour éviter les sauts ;
- jusqu’à **99 paramètres** peuvent être accessibles par banques ;
- les autres setups/groupes de l’EC4 restent libres pour d’autres usages.

Le bridge fonctionne **entièrement en dehors du chemin audio** : il ne charge aucun plugin, ne traite aucun son, n’installe aucun pilote audio et ne modifie pas les projets LiveProfessor.

```text
EC4 → MIDI / SysEx → Bridge → OSC → LiveProfessor
```

et dans l’autre sens :

```text
LiveProfessor → OSC feedback → Bridge → MIDI / SysEx → EC4
```

---

# 🇫🇷 Français

## À quoi sert le bridge ?

EC4 LiveProfessor Bridge permet d’utiliser le Faderfox EC4 comme une surface de contrôle réellement intégrée à LiveProfessor.

Le bridge ne remplace pas le système de **Controller Maps** de LiveProfessor : il s’appuie dessus. Une fois une map créée pour un type de plugin, les mêmes contrôles peuvent suivre l’instance actuellement sélectionnée grâce à l’option **Only If Selected**.

L’EC4 devient ainsi une télécommande dynamique des plugins de la session, avec retour de valeurs et affichage sur son OLED.

## EC4 direct en MIDI ou avec le bridge ?

Les deux approches sont valables. Si vous souhaitez simplement piloter quelques paramètres fixes, connecter l’EC4 directement en MIDI à LiveProfessor reste la solution la plus simple. Le bridge devient intéressant lorsqu’on veut exploiter l’EC4 comme une véritable surface de contrôle dynamique.

| Fonction | EC4 direct en MIDI | Avec EC4 LiveProfessor Bridge |
|---|---:|---:|
| Contrôler les paramètres d’un plugin | ✅ | ✅ |
| Utiliser les Controller Maps | ✅ | ✅ |
| Feedback des valeurs | possible selon configuration | ✅ intégré |
| Gestion de banques | à configurer manuellement | ✅ intégrée jusqu’à 99 contrôles |
| Affichage des noms de paramètres sur l’EC4 | ❌ pas automatiquement | ✅ |
| Affichage des valeurs sur l’OLED | ❌ pas automatiquement | ✅ |
| Suivi du plugin sélectionné | possible selon configuration | ✅ intégré au fonctionnement du bridge |
| Exploitation du SysEx de l’EC4 | à développer/configurer séparément | ✅ intégré |
| Navigation plugins / chaînes / snapshots | à mapper manuellement | ✅ intégrée |
| Anti-écho / synchronisation | à gérer selon configuration | ✅ intégrée |
| Reconnexion automatique de l’EC4 | dépend de la configuration | ✅ |
| Diagnostic MIDI / OSC | limité | ✅ intégré |
| Simplicité de mise en œuvre | ✅ maximale | nécessite le bridge |

**Pour un contrôle fixe de quelques paramètres, le MIDI direct suffit souvent. Le bridge prend tout son intérêt lorsqu’on veut transformer l’EC4 en véritable surface de contrôle dynamique de LiveProfessor, avec affichage, feedback, banques, navigation et synchronisation.**

## Fonctionnalités principales

- connexion MIDI avec le **Faderfox EC4** ;
- détection et reconnexion automatique de l’EC4 ;
- communication OSC avec **LiveProfessor Companion Controller** ;
- jusqu’à **99 contrôles** ;
- banques de **16 paramètres** ;
- feedback bidirectionnel des valeurs ;
- protection anti-écho MIDI / OSC ;
- affichage des noms de paramètres sur l’écran OLED de l’EC4 ;
- affichage temporaire de la valeur du paramètre manipulé ;
- grille permanente des 16 paramètres de la banque active ;
- apprentissage des 16 CC rotatifs ;
- apprentissage des 16 Notes correspondant aux poussoirs ;
- transmission des push simples 1 à 15 vers les boutons Companion apprenables ;
- affichage des raccourcis directement sur l’EC4 pendant le maintien de Shift ;
- contrôleurs neutres `Ec4-UniBank.ctrl2` (16 rotatifs) et `Ec4-FullBank.ctrl2` (99 rotatifs), copiables depuis l’application ;
- auto-mapping assisté dans une copie sécurisée du projet LiveProfessor ;
- choix d’un setup/groupe EC4 réservé à LiveProfessor ;
- navigation entre plugins ;
- navigation entre chaînes ;
- navigation entre banques ;
- navigation entre tous les View Sets ;
- commandes Cue précédente/suivante ;
- rappel des snapshots globaux ;
- Tap Tempo ;
- mode Companion recommandé ;
- mode OSC générique de secours ;
- profils JSON pour les noms de paramètres en mode générique ;
- configuration portable ;
- journal tournant ;
- outils de diagnostic intégrés ;
- fenêtre principale compacte avec réglages, journal et connexions dans des fenêtres dédiées ;
- interface français/anglais avec changement immédiat ;
- réduction dans la zone de notification avec restauration par clic et menu contextuel ;
- vérification automatique ou manuelle des releases GitHub.

## Principe de fonctionnement

Le bridge utilise les contrôles virtuels exposés par le **Companion Controller** de LiveProfessor :

```text
Rotary1
Rotary2
Rotary3
...
Rotary99
```

Dans LiveProfessor, ces contrôles sont ensuite associés aux paramètres des plugins via les **Controller Maps**.

Exemple :

```text
EC4 encodeur 1
        ↓
Bridge
        ↓
/Companion/Rotary1
        ↓
LiveProfessor Controller Map
        ↓
Paramètre du plugin
```

Le feedback effectue le trajet inverse :

```text
Paramètre du plugin
        ↓
LiveProfessor
        ↓
OSC feedback
        ↓
Bridge
        ↓
EC4
```

Cela permet à la valeur de l’encodeur et à celle du plugin de rester synchronisées.

## Pourquoi utiliser une Controller Map ?

L’idée est d’éviter de refaire un MIDI Learn pour chaque instance de plugin.

On crée une fois une map pour un type de plugin. Par exemple :

```text
Rotary1 → Gain
Rotary2 → Frequency
Rotary3 → Q
Rotary4 → Threshold
...
```

Cette map peut ensuite être réutilisée sur les autres instances du même plugin.

Avec **Only If Selected**, les encodeurs suivent automatiquement le plugin actuellement sélectionné.

## Prérequis

- Windows 10 ou Windows 11 x64 ;
- Faderfox EC4 ;
- LiveProfessor 2023.0.8 ou supérieur ;
- licence ou période d’essai officielle LiveProfessor ;
- Companion Controller configuré dans LiveProfessor ;
- Controller Maps pour les plugins à contrôler.

## Télécharger la version stable 2026.1

- [Télécharger l’installateur Windows 2026.1](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/EC4-LiveProfessor-Bridge-Setup-v2026.1.exe) — recommandé ;
- [Télécharger l’archive portable 2026.1](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/EC4-LiveProfessor-Bridge-v2026.1-win64.zip) ;
- [Télécharger `Ec4-UniBank.ctrl2`](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/Ec4-UniBank.ctrl2) — une seule banque de 16 rotatifs ;
- [Télécharger `Ec4-FullBank.ctrl2`](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/Ec4-FullBank.ctrl2) — 99 rotatifs pour toutes les banques ;
- [Consulter la release et ses notes](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest).

L’installateur contient l’application, la documentation et les deux contrôleurs CTRL2.

L’exécutable est autonome :

```text
EC4-LiveProfessor-Bridge.exe
```

Python n’est pas nécessaire et aucun droit administrateur n’est requis.

## Configuration LiveProfessor

### Important : le Companion Controller standard ne contient que 4 Rotary

Quand on ajoute simplement un **Companion Controller** dans **Hardware Controllers**, LiveProfessor ne fournit par défaut que :

```text
Rotary1
Rotary2
Rotary3
Rotary4
```

Or EC4 LiveProfessor Bridge utilise **16 Rotary par banque** et peut adresser jusqu’à **99 contrôles**.

Il faut donc compléter le contrôleur avant de pouvoir exploiter correctement les 16 encodeurs de l’EC4.

### Méthode recommandée — charger le fichier `.ctrl2` fourni

Le plus simple est de **charger/importer directement dans LiveProfessor l’un des deux fichiers `.ctrl2` fournis** :

- `Ec4-UniBank.ctrl2` contient `Rotary1` à `Rotary16` pour une configuration simple à une banque ;
- `Ec4-FullBank.ctrl2` contient `Rotary1` à `Rotary99` pour exploiter toutes les banques du bridge.

Les deux fichiers contiennent aussi `GenericButton1` à `GenericButton16`. Ils sont intégrés dans l’application : cliquez sur **CTRL2 UniBank…** ou **CTRL2 FullBank…**, choisissez un dossier, puis ouvrez **Controllers > Hardware Controllers Setup > Load from file** dans LiveProfessor. Le menu **Aide > Comment importer les CTRL2…** reprend la procédure complète.

Après chargement, vérifiez que le contrôleur contient :

```text
Rotary1 → Rotary16
```

Avec FullBank, la liste continue jusqu’à `Rotary99` sans ajout manuel.

**C’est la méthode recommandée.**

### Méthode manuelle

Si vous préférez créer le contrôleur vous-même :

1. ouvrir **Hardware Controllers** dans LiveProfessor ;
2. ajouter un **Companion Controller** ;
3. conserver les 4 Rotary créés par défaut ;
4. ajouter au minimum `Rotary5` à `Rotary16` ;
5. ajouter éventuellement `Rotary17` à `Rotary99` pour exploiter toutes les banques ;
6. enregistrer le contrôleur ainsi complété pour pouvoir le réutiliser.

Configuration réseau recommandée :

```text
Adresse : 127.0.0.1
Port vers LiveProfessor : 8010
Feedback vers : 127.0.0.1
Port feedback : 8011
```

Le bridge utilise par défaut ces mêmes valeurs.

## Auto-mapping automatique — version 2026.1

Le menu **Outils > Auto-mapping…** analyse un projet LiveProfessor `.rack2` et crée une **nouvelle copie** contenant une map `EC4 AutoMap - Dynamic` :

1. enregistrez d'abord le projet dans LiveProfessor ;
2. choisissez ce fichier `.rack2` dans l'outil d'auto-mapping ;
3. sélectionnez un plugin ou **Tous les plugins détectés** ;
4. conservez **UniBank — 16 paramètres**, sélectionné par défaut, ou choisissez FullBank si le plugin a réellement besoin de plusieurs banques ;
5. enregistrez la copie sous un nouveau nom ;
6. ouvrez cette copie dans LiveProfessor et sélectionnez le plugin à contrôler.

Chaque affectation générée utilise **Only If Selected**. Une même map dynamique peut donc contenir plusieurs plugins et plusieurs instances : seuls les paramètres du plugin sélectionné doivent réagir. Les affectations sont fusionnées dans les `HardwareCtrlMaps` réellement rappelés par le projet et ses snapshots : il n'est plus nécessaire de charger manuellement un preset pour chaque plugin dans LiveProfessor. Les affectations de poussoirs déjà présentes sont conservées.

La version 2026.1 suit l'ordre technique des paramètres exposés par le plugin : 16 paramètres en UniBank ou 99 en FullBank. Elle ne peut pas deviner leur importance musicale, ni créer un paramètre que le plugin n'expose pas à LiveProfessor. Les poussoirs et les raccourcis Shift ne sont jamais modifiés. Le projet source reste intact ; si le fichier de destination existe déjà, une sauvegarde horodatée est créée avant son remplacement.

## Création manuelle d’une Controller Map

Le fait d’avoir `Rotary1` à `Rotary16` dans le Companion Controller ne suffit pas encore à contrôler un plugin : les Rotary doivent ensuite être reliés aux paramètres du plugin dans une **Controller Map**.

Pour chaque type de plugin :

1. charger une instance du plugin ;
2. ouvrir **Controller Maps** ;
3. créer une nouvelle map ;
4. associer `Rotary1`, `Rotary2`, etc. aux paramètres souhaités ;
5. activer **Only If Selected** si le contrôle doit suivre le plugin sélectionné ;
6. conserver le feedback actif ;
7. sauvegarder la map avec **Save Map Preset** ;
8. appliquer ensuite ce preset aux autres instances du même plugin.

Une map VST2 et une map VST3 peuvent être considérées comme deux types de plugins différents par LiveProfessor.

### Mapper les poussoirs des encodeurs

L’apprentissage **Rotatifs + push** du bridge sert uniquement à reconnaître les messages MIDI envoyés par le groupe EC4 choisi. Dans LiveProfessor, les deux fichiers CTRL2 définissent déjà `GenericButton1` à `GenericButton15` : il ne faut donc pas refaire leur Learn comme des boutons MIDI bruts.

Pour affecter un poussoir à une fonction de plugin :

1. ouvrir l’éditeur **Controller Maps** ;
2. sélectionner le contrôleur EC4 puis `GenericButton1`, `GenericButton2`, etc. ;
3. choisir dans la liste le paramètre automatisable du plugin ;
4. activer la transformation **Toggle** pour une fonction marche/arrêt, ou conserver le mode momentané pour une impulsion.

Le **Quick Assign** n’est pas fiable pour tous les boutons. Si le paramètre n’apparaît pas dans la liste de la Controller Map, le plugin ne l’expose probablement pas à LiveProfessor et le bridge ne peut pas le mapper automatiquement.

## Configuration de l’EC4

Le bridge peut apprendre directement n’importe quel setup/groupe EC4 adapté.

Pour utiliser une zone personnalisée :

1. sélectionner sur l’EC4 le setup et le groupe à réserver à LiveProfessor ;
2. démarrer le bridge ;
3. cliquer sur **Utiliser le setup/groupe actuel** ;
4. lancer **Apprendre rotatifs + push** ;
5. tourner successivement les 16 encodeurs ;
6. appuyer successivement sur les 16 poussoirs.

Le mapping est ensuite mémorisé.

Les encodeurs doivent être configurés en **CC absolu 0–127** afin que le feedback puisse correctement resynchroniser leur valeur.

## Commandes principales de l’EC4

| Geste | Fonction |
|---|---|
| Encodeurs 1–16 | Contrôle des paramètres de la banque active |
| Push simples 1–15 | Boutons Companion 1–15 apprenables et mappables dans LiveProfessor |
| Push simple 16 | Tap Tempo (réservé) |
| Shift + Push 1 / 2 | Banque précédente / suivante |
| Shift + Push 3 / 4 | View Set précédent / suivant |
| Shift + Push 5 | Afficher / masquer le plugin sélectionné |
| Shift + Push 6 / 10 | Chaîne précédente / suivante |
| Shift + Push 7 / 8 | Plugin précédent / suivant |
| Shift + Push 9 | Activer / désactiver le traitement du plugin sélectionné |
| Shift + Push 11 / 12 | Plugin précédent / suivant |
| Shift + Push 13 / 14 | Cue précédente / suivante |
| Shift + Push 15 / 16 | Snapshot global précédent / suivant |

## Banques de paramètres

L’EC4 possède 16 encodeurs physiques, mais le Companion Controller de LiveProfessor permet au bridge de gérer jusqu’à **99 contrôles**.

```text
Banque 1 : Rotary1  → Rotary16
Banque 2 : Rotary17 → Rotary32
Banque 3 : Rotary33 → Rotary48
...
```

La banque active est affichée par l’application et l’écran de l’EC4 est mis à jour automatiquement.

## Affichage OLED

Le bridge utilise le protocole **SysEx du Faderfox EC4** pour piloter son écran.

### Grille permanente

Les 16 paramètres de la banque active sont affichés sous forme de grille.

### Affichage temporaire

Lorsqu’un encodeur est manipulé, le bridge peut afficher :

- le nom du paramètre ;
- sa valeur ;
- le plugin concerné.

Après quelques instants, l’affichage revient automatiquement à la grille principale.

## Protection contre les sauts de valeur

Lorsqu’un plugin change ou lorsqu’une valeur est modifiée dans LiveProfessor, le bridge renvoie cette valeur vers l’EC4.

L’encodeur est ainsi remis à la valeur réelle du plugin avant la prochaine manipulation.

Une garde anti-écho empêche le message de feedback d’être immédiatement renvoyé vers LiveProfessor.

## Configuration

Par défaut, la configuration utilisateur est enregistrée dans :

```text
%LOCALAPPDATA%\EC4LiveProfessorBridge\config.json
```

Pour utiliser le bridge en mode totalement portable, placer un fichier :

```text
config.json
```

à côté de l’exécutable.

## Documentation

- [Guide d’installation et d’utilisation](docs/GUIDE_INSTALLATION_UTILISATION.md)
- [Configuration EC4](docs/CONFIGURATION_EC4.md)
- [Cartographie MIDI et SysEx](docs/CARTOGRAPHIE_MIDI_SYSEX.md)
- [Sources techniques](docs/SOURCES.md)
- [Rapport de stabilisation 0.5.0](docs/RAPPORT_STABILISATION_UI_UPDATER_V0.5.0.md)
- [Historique des versions](CHANGELOG.md)

## Développement

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-build.txt
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build.ps1
.\scripts\build-installer.ps1 -NoBuild
```

La version Windows autonome est générée avec **PyInstaller**.

## Architecture

```text
Faderfox EC4
     │
     │ MIDI / SysEx
     ▼
EC4 LiveProfessor Bridge
     │
     │ OSC
     ▼
LiveProfessor Companion Controller
     │
     ▼
Controller Maps
     │
     ▼
Plugins
```

Le bridge ne transporte **aucun signal audio**.

## Mise à jour et contribution

Le menu **Outils > Vérifier les mises à jour** interroge la dernière release stable du dépôt officiel. La vérification au démarrage est désactivable et aucune mise à jour n'est installée silencieusement.

Le menu **Aide** ouvre le [dépôt](https://github.com/Mamat79/EC4-LiveProfessor-Bridge), les [releases](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases), les [issues](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/issues) et les informations de contribution.

## Contribuer

- Signaler un problème ou proposer une amélioration : [GitHub Issues](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/issues) ;
- soutenir le développement : [PayPal — MamatLeroy](https://www.paypal.com/paypalme/MamatLeroy).

## Feuille de route

- **2026.1** : version stable avec auto-mapping automatique validé, UniBank/FullBank, affectation directe aux maps rappelées par le projet et compatibilité snapshots ;
- version ultérieure : profils d'ordre logique personnalisés pour organiser les paramètres selon les plugins ;
- version ultérieure : ouverture à d'autres surfaces MIDI/OSC au moyen de profils matériels, en conservant l'EC4 comme surface de référence.

## Auteur

**SiLeMI/O — By Mamat ------[]---**

Projet indépendant développé pour améliorer l’intégration du Faderfox EC4 dans un environnement LiveProfessor.

## Licence et marques

Ce dépôt est public, mais aucune licence open source n’est actuellement accordée.

**Tous droits réservés à Mamat / SiLeMI/O.**

Faderfox, LiveProfessor, Audioström, VST ainsi que les autres marques citées appartiennent à leurs propriétaires respectifs.

Ce projet est indépendant et n’est ni affilié, ni approuvé, ni sponsorisé par Faderfox, Audioström ou les éditeurs des logiciels et plugins mentionnés.

Aucun logiciel propriétaire tiers n’est redistribué dans ce dépôt.

---

<a id="english-version"></a>

# 🇬🇧 English

## Why does this project exist?

The **Faderfox EC4** is an excellent MIDI controller: compact, rugged, equipped with 16 push encoders and a powerful OLED display.

It can of course control LiveProfessor directly over MIDI. But a conventional MIDI setup quickly becomes limited: fixed assignments, little context about what each encoder currently controls, and a less fluid workflow when switching plugins, banks or parameters.

**EC4 LiveProfessor Bridge was created to turn the EC4 into a dynamic control surface for LiveProfessor.**

It adds a communication layer between both devices:

- the 16 encoders control parameters of the currently selected plugin;
- parameter names and values are received from LiveProfessor;
- the EC4 OLED displays what is currently being controlled;
- parameter values are synchronized in both directions;
- up to **99 parameters** can be accessed through banks;
- other EC4 setups/groups remain available for other uses.

The bridge operates **completely outside the audio path**. It does not load plugins, process audio, install audio drivers or modify LiveProfessor projects.

```text
EC4 → MIDI / SysEx → Bridge → OSC → LiveProfessor
```

and back:

```text
LiveProfessor → OSC feedback → Bridge → MIDI / SysEx → EC4
```

## Direct MIDI or the bridge?

Both approaches are valid. For a small fixed control setup, connecting the EC4 directly to LiveProfessor over MIDI is usually the simplest option. The bridge becomes useful when you want the EC4 to behave as a dynamic, context-aware control surface.

| Feature | EC4 direct over MIDI | With EC4 LiveProfessor Bridge |
|---|---:|---:|
| Control plugin parameters | ✅ | ✅ |
| Use Controller Maps | ✅ | ✅ |
| Parameter feedback | possible depending on configuration | ✅ integrated |
| Bank management | manual configuration | ✅ integrated up to 99 controls |
| Parameter names on the EC4 | ❌ not automatic | ✅ |
| Parameter values on the OLED | ❌ not automatic | ✅ |
| Follow the selected plugin | possible depending on configuration | ✅ integrated into the bridge workflow |
| EC4 SysEx integration | separate development/configuration required | ✅ integrated |
| Plugin / chain / snapshot navigation | manual mapping | ✅ integrated |
| Echo protection / synchronization | configuration dependent | ✅ integrated |
| Automatic EC4 reconnection | configuration dependent | ✅ |
| MIDI / OSC diagnostics | limited | ✅ integrated |
| Setup simplicity | ✅ maximum | requires the bridge |

**For a fixed set of controls, direct MIDI is often enough. The bridge becomes valuable when you want to turn the EC4 into a true dynamic LiveProfessor control surface with display feedback, parameter synchronization, banks and navigation.**

## Main features

- Faderfox EC4 MIDI connection;
- automatic EC4 detection and reconnection;
- LiveProfessor Companion Controller support;
- up to **99 controls**;
- banks of **16 parameters**;
- bidirectional parameter feedback;
- MIDI / OSC echo protection;
- dynamic parameter names on the EC4 OLED;
- temporary parameter value display;
- persistent 16-parameter bank grid;
- MIDI Learn for the 16 encoders;
- MIDI Learn for the 16 encoder push buttons;
- simple push buttons 1 through 15 forwarded to learnable Companion buttons;
- on-device shortcut guide while Shift is held;
- embedded neutral `Ec4-UniBank.ctrl2` (16 rotaries) and `Ec4-FullBank.ctrl2` (99 rotaries), exportable from the application;
- dedicated EC4 setup/group selection;
- plugin navigation;
- chain navigation;
- bank navigation;
- navigation across all View Sets;
- previous/next Cue commands;
- global snapshot recall;
- Tap Tempo;
- recommended Companion mode;
- generic OSC fallback mode;
- JSON parameter profiles;
- portable configuration;
- rotating log files;
- built-in diagnostics;
- compact main window with separate settings, log and connection windows;
- instant French/English language switching;
- reliable notification-area minimization, click restore and context menu;
- automatic or manual GitHub release checks.

## How it works

The bridge uses the virtual controls exposed by LiveProfessor's **Companion Controller**:

```text
Rotary1
Rotary2
Rotary3
...
Rotary99
```

LiveProfessor **Controller Maps** then associate those controls with plugin parameters.

```text
EC4 Encoder 1
        ↓
Bridge
        ↓
/Companion/Rotary1
        ↓
LiveProfessor Controller Map
        ↓
Plugin parameter
```

Feedback follows the reverse path:

```text
Plugin parameter
        ↓
LiveProfessor
        ↓
OSC feedback
        ↓
Bridge
        ↓
EC4
```

## Why use Controller Maps?

A Controller Map only needs to be created once for a plugin type.

```text
Rotary1 → Gain
Rotary2 → Frequency
Rotary3 → Q
Rotary4 → Threshold
...
```

The same map can then be reused on other instances of the same plugin.

With **Only If Selected**, the EC4 controls automatically follow the currently selected plugin.

## Requirements

- Windows 10 or Windows 11 x64;
- Faderfox EC4;
- LiveProfessor 2023.0.8 or later;
- official LiveProfessor licence or trial;
- LiveProfessor Companion Controller;
- Controller Maps for the plugins you want to control.

## Download stable version 2026.1

- [Download the Windows 2026.1 installer](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/EC4-LiveProfessor-Bridge-Setup-v2026.1.exe) — recommended;
- [Download the portable 2026.1 archive](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/EC4-LiveProfessor-Bridge-v2026.1-win64.zip);
- [Download `Ec4-UniBank.ctrl2`](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/Ec4-UniBank.ctrl2) — one bank with 16 rotaries;
- [Download `Ec4-FullBank.ctrl2`](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/Ec4-FullBank.ctrl2) — 99 rotaries for every bank;
- [View the latest release and release notes](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest).

The installer includes the application, documentation and both CTRL2 controller files.

The Windows executable is standalone:

```text
EC4-LiveProfessor-Bridge.exe
```

Python and administrator privileges are not required.

## LiveProfessor configuration

### Important: the standard Companion Controller only contains 4 Rotary controls

When you simply add a **Companion Controller** in **Hardware Controllers**, LiveProfessor provides only:

```text
Rotary1
Rotary2
Rotary3
Rotary4
```

EC4 LiveProfessor Bridge uses **16 Rotary controls per bank** and can address up to **99 controls**.

### Recommended method — load the supplied `.ctrl2` file

The easiest method is to **load/import one of the two supplied `.ctrl2` files directly into LiveProfessor**:

- `Ec4-UniBank.ctrl2` contains `Rotary1` through `Rotary16` for a simple single-bank setup;
- `Ec4-FullBank.ctrl2` contains `Rotary1` through `Rotary99` for every bridge bank.

Both files also contain `GenericButton1` through `GenericButton16`. They are embedded in the application: click **UniBank CTRL2…** or **FullBank CTRL2…**, choose a folder, then open **Controllers > Hardware Controllers Setup > Load from file** in LiveProfessor. The **Help > How to import the CTRL2 files…** menu shows the complete procedure.

Check that the controller contains at least:

```text
Rotary1 → Rotary16
```

With FullBank, the list continues through `Rotary99` without manual additions.

**This is the recommended method.**

### Manual method

1. open **Hardware Controllers** in LiveProfessor;
2. add a **Companion Controller**;
3. keep the 4 Rotary controls created by default;
4. add at least `Rotary5` through `Rotary16`;
5. optionally add `Rotary17` through `Rotary99`;
6. save the completed controller for later reuse.

Recommended network settings:

```text
Address: 127.0.0.1
LiveProfessor input port: 8010
Feedback address: 127.0.0.1
Feedback port: 8011
```

## Automatic mapping — version 2026.1

**Tools > Auto-mapping…** analyzes a saved LiveProfessor `.rack2` project and creates a **new copy** containing an `EC4 AutoMap - Dynamic` map:

1. save the project in LiveProfessor first;
2. choose that `.rack2` file in the auto-mapping tool;
3. select one plugin or **All detected plugins**;
4. keep **UniBank — 16 parameters**, selected by default, or choose FullBank when the plugin genuinely needs several banks;
5. save the copy under a new name;
6. open the copy in LiveProfessor and select the plugin to control.

Every generated assignment uses **Only If Selected**. One dynamic map can therefore contain several plugins and instances while only the selected plugin should react. Assignments are merged into the `HardwareCtrlMaps` actually recalled by the project and its snapshots, so a preset no longer needs to be loaded manually for each plugin in LiveProfessor. Existing push-button assignments are preserved.

Version 2026.1 follows the technical parameter order exposed by the plugin: 16 parameters in UniBank or 99 in FullBank. It cannot infer musical importance or map a parameter that the plugin does not expose to LiveProfessor. Push buttons and Shift shortcuts are never changed. The source project remains untouched; if the destination already exists, a timestamped backup is created first.

## Creating a Controller Map manually

Having `Rotary1` through `Rotary16` in the Companion Controller is not enough by itself: those Rotary controls must then be assigned to actual plugin parameters in a **Controller Map**.

For each plugin type:

1. load an instance of the plugin;
2. open **Controller Maps**;
3. create a new map;
4. assign `Rotary1`, `Rotary2`, etc. to the required parameters;
5. enable **Only If Selected** if the map should follow the selected plugin;
6. keep feedback enabled;
7. save the map using **Save Map Preset**;
8. apply the preset to the other instances of the same plugin.

### Mapping encoder push buttons

The bridge’s **Learn encoders + push** operation only identifies the MIDI messages sent by the selected EC4 group. In LiveProfessor, both CTRL2 files already define `GenericButton1` through `GenericButton15`, so they should not be learned again as raw MIDI buttons.

To assign a push button to a plugin function:

1. open the **Controller Maps** editor;
2. select the EC4 controller and then `GenericButton1`, `GenericButton2`, etc.;
3. choose the plugin’s exposed automatable parameter from the list;
4. enable the **Toggle** transformation for an on/off function, or keep momentary behaviour for a trigger.

**Quick Assign** is not reliable for every button. If a parameter is absent from the Controller Map list, the plugin probably does not expose it to LiveProfessor and the bridge cannot map it automatically.

## EC4 configuration

The bridge can learn any suitable EC4 setup/group directly.

1. select the setup and group you want to dedicate to LiveProfessor;
2. start the bridge;
3. click **Use current setup/group**;
4. start **Learn encoders + push**;
5. turn the 16 encoders in order;
6. press the 16 encoder buttons in order.

Encoders should use **absolute CC values from 0 to 127** so feedback can correctly synchronize them.

## Main EC4 controls

| Gesture | Function |
|---|---|
| Encoders 1–16 | Control parameters in the active bank |
| Simple push 1–15 | Learnable and mappable Companion buttons 1–15 |
| Simple push 16 | Tap Tempo (reserved) |
| Shift + Push 1 / 2 | Previous / next parameter bank |
| Shift + Push 3 / 4 | Previous / next View Set |
| Shift + Push 5 | Show / hide selected plugin |
| Shift + Push 6 / 10 | Previous / next chain |
| Shift + Push 7 / 8 | Previous / next plugin |
| Shift + Push 9 | Enable / disable processing on selected plugin |
| Shift + Push 11 / 12 | Previous / next plugin |
| Shift + Push 13 / 14 | Previous / next Cue |
| Shift + Push 15 / 16 | Previous / next global snapshot |

## Parameter banks

```text
Bank 1: Rotary1  → Rotary16
Bank 2: Rotary17 → Rotary32
Bank 3: Rotary33 → Rotary48
...
```

## OLED display

The bridge uses the EC4 **SysEx protocol** to control the display.

The current bank can be shown as a permanent 16-parameter grid. When an encoder is moved, a temporary overlay can display the parameter name, value and current plugin before returning to the grid.

## Value jump protection

When a plugin changes or a parameter value is modified inside LiveProfessor, the bridge sends the new value back to the EC4.

An echo guard prevents that feedback message from immediately being sent back to LiveProfessor.

## Configuration

```text
%LOCALAPPDATA%\EC4LiveProfessorBridge\config.json
```

For portable operation, place `config.json` next to the executable.

## Documentation

- [Installation and user guide](docs/en/INSTALLATION_AND_USER_GUIDE.md)
- [EC4 configuration](docs/en/EC4_CONFIGURATION.md)
- [MIDI and SysEx mapping](docs/en/MIDI_SYSEX_MAPPING.md)
- [Technical sources](docs/en/SOURCES.md)
- [0.5.0 stabilization report](docs/RAPPORT_STABILISATION_UI_UPDATER_V0.5.0.md)
- [Changelog](CHANGELOG.md)

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-build.txt
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\scripts\build.ps1
.\scripts\build-installer.ps1 -NoBuild
```

## Architecture

```text
Faderfox EC4
     │
     │ MIDI / SysEx
     ▼
EC4 LiveProfessor Bridge
     │
     │ OSC
     ▼
LiveProfessor Companion Controller
     │
     ▼
Controller Maps
     │
     ▼
Plugins
```

The bridge carries **no audio signal**.

## Updates and contribution

**Tools > Check for updates** queries the latest stable release from the official repository. Startup checks can be disabled and no update is installed silently.

The **Help** menu opens the [repository](https://github.com/Mamat79/EC4-LiveProfessor-Bridge), [releases](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases), [issues](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/issues) and contribution information.

## Contribute

- Report a problem or suggest an improvement: [GitHub Issues](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/issues);
- support development: [PayPal — MamatLeroy](https://www.paypal.com/paypalme/MamatLeroy).

## Roadmap

- **2026.1**: stable release with validated automatic mapping, UniBank/FullBank, direct assignment to project-recalled maps and snapshot compatibility;
- later: custom logical-order profiles to organize parameters for specific plugins;
- later: support additional MIDI/OSC control surfaces through hardware profiles while keeping the EC4 as the reference surface.

## Author

**SiLeMI/O — By Mamat ------[]---**

Independent project created to improve Faderfox EC4 integration with LiveProfessor.

## Licence and trademarks

This repository is public, but no open-source licence is currently granted.

**All rights reserved by Mamat / SiLeMI/O.**

Faderfox, LiveProfessor, Audioström, VST and all other trademarks mentioned belong to their respective owners.

This is an independent project and is not affiliated with, endorsed by or sponsored by Faderfox, Audioström or any of the software or plugin manufacturers mentioned.

No proprietary third-party software is redistributed in this repository.
