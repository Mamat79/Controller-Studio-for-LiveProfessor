# EC4 LiveProfessor Bridge

🇬🇧 **English reader? [Jump directly to the English version.](#english-version)**

**Une passerelle intelligente entre le Faderfox EC4 et LiveProfessor.**

Le **Faderfox EC4** est un excellent contrôleur MIDI : compact, robuste, 16 encodeurs avec poussoir et un écran OLED capable d’afficher beaucoup d’informations.

Le problème, lorsqu’on veut l’utiliser avec **LiveProfessor**, est que l’on perd rapidement une grande partie de cette intelligence : mappings à refaire, paramètres difficiles à identifier, valeurs qui ne suivent pas toujours le logiciel, changements de plugins peu pratiques…

**EC4 LiveProfessor Bridge a été créé pour résoudre ce problème.**

L’application transforme l’EC4 en véritable surface de contrôle dynamique pour LiveProfessor :

- les 16 encodeurs pilotent les paramètres du plugin sélectionné ;
- les noms des paramètres et leurs valeurs reviennent depuis LiveProfessor ;
- l’écran OLED de l’EC4 affiche directement ce que l’on contrôle ;
- les valeurs sont synchronisées dans les deux sens pour éviter les sauts ;
- jusqu’à **99 paramètres** peuvent être accessibles par banques ;
- le même EC4 peut continuer à être utilisé pour d’autres logiciels ou fonctions sur ses autres setups/groupes.

Le bridge fonctionne **entièrement en dehors du chemin audio** : il ne charge aucun plugin, ne traite aucun son, n’installe aucun pilote audio et ne modifie pas les projets LiveProfessor.

En pratique :

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

Sans passerelle, utiliser un contrôleur MIDI générique avec LiveProfessor peut rapidement devenir fastidieux : il faut gérer les affectations, savoir quel encodeur contrôle quoi, éviter les sauts de valeurs et retrouver ses repères lorsqu’on change de plugin.

EC4 LiveProfessor Bridge ajoute une couche de communication entre le **Faderfox EC4** et le système de contrôle de **LiveProfessor**.

Le but n’est pas de remplacer LiveProfessor ni son système de Controller Maps. Au contraire, le bridge utilise les fonctions prévues par LiveProfessor pour permettre à l’EC4 de devenir une surface de contrôle beaucoup plus lisible et agréable à utiliser.

Une fois une **Controller Map** créée pour un type de plugin, les mêmes contrôles peuvent suivre l’instance actuellement sélectionnée grâce à l’option **Only If Selected**.

L’EC4 devient alors une sorte de télécommande universelle des plugins de la session.

## Fonctionnalités principales

- Connexion MIDI avec le **Faderfox EC4**
- Détection et reconnexion automatique de l’EC4
- Communication OSC avec **LiveProfessor Companion Controller**
- Jusqu’à **99 contrôles**
- Banques de **16 paramètres**
- Feedback bidirectionnel des valeurs
- Protection anti-écho MIDI / OSC
- Affichage des noms de paramètres sur l’écran OLED de l’EC4
- Affichage temporaire de la valeur du paramètre manipulé
- Grille permanente des 16 paramètres de la banque active
- Apprentissage des 16 CC rotatifs
- Apprentissage des 16 Notes correspondant aux poussoirs
- Choix d’un setup/groupe EC4 réservé à LiveProfessor
- Navigation entre plugins
- Navigation entre chaînes
- Navigation entre banques
- Rappel des snapshots globaux
- Tap Tempo
- Mode Companion recommandé
- Mode OSC générique de secours
- Profils JSON pour les noms de paramètres en mode générique
- Configuration portable
- Journal tournant
- Outils de diagnostic intégrés

## Principe de fonctionnement

Le bridge ne contrôle pas directement les paramètres internes d’un plugin.

Il utilise les contrôles virtuels exposés par le **Companion Controller** de LiveProfessor :

```text
Rotary1
Rotary2
Rotary3
...
Rotary99
```

Dans LiveProfessor, ces contrôles sont ensuite associés aux paramètres du plugin via les **Controller Maps**.

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
Gain du plugin
```

Le feedback effectue le trajet inverse :

```text
Gain du plugin
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

Avec **Only If Selected**, les 16 encodeurs suivent automatiquement le plugin actuellement sélectionné.

## Prérequis

- Windows 10 ou Windows 11 x64
- Faderfox EC4
- LiveProfessor 2023.0.8 ou supérieur
- licence ou période d’essai officielle LiveProfessor
- Companion Controller configuré dans LiveProfessor
- Controller Maps pour les plugins à contrôler

## Télécharger

La dernière version Windows est disponible dans les **Releases GitHub** :

[Releases — EC4 LiveProfessor Bridge](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest)

L’exécutable est autonome. Il suffit de copier :

```text
EC4-LiveProfessor-Bridge.exe
```

sur le PC et de le lancer.

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

Or EC4 LiveProfessor Bridge utilise **16 Rotary par banque**, et peut adresser jusqu’à **99 contrôles**.

Il faut donc compléter le contrôleur avant de pouvoir exploiter correctement les 16 encodeurs de l’EC4.

### Méthode recommandée — charger le fichier `.ctrl2` fourni

Le plus simple est de **charger/importer directement dans LiveProfessor le fichier `.ctrl2` fourni avec le projet**.

Ce fichier contient déjà la définition Companion nécessaire au bridge et évite de créer les Rotary un par un.

Après chargement, vérifiez simplement que le contrôleur contient au minimum :

```text
Rotary1 → Rotary16
```

et davantage si vous souhaitez utiliser plusieurs banques jusqu’à `Rotary99`.

C’est la méthode recommandée.

### Méthode manuelle

Si vous préférez créer le contrôleur vous-même :

1. ouvrir **Hardware Controllers** dans LiveProfessor ;
2. ajouter un **Companion Controller** ;
3. conserver les 4 Rotary créés par défaut ;
4. ajouter au minimum `Rotary5` à `Rotary16` ;
5. ajouter éventuellement `Rotary17` à `Rotary99` si vous souhaitez exploiter toutes les banques ;
6. enregistrer le contrôleur ainsi complété pour pouvoir le réutiliser.

Configuration réseau recommandée :

```text
Adresse : 127.0.0.1
Port vers LiveProfessor : 8010
Feedback vers : 127.0.0.1
Port feedback : 8011
```

Le bridge utilise par défaut ces mêmes valeurs.

## Création d’une Controller Map

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

## Configuration de l’EC4

Le bridge peut utiliser :

- le mapping historique prévu pour le script Ableton ;
- ou n’importe quel setup/groupe EC4 appris directement par l’application.

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
| Push 1–15 | Affichage détaillé du paramètre |
| Push 16 | Tap Tempo |
| Shift + Push | Navigation et commandes supplémentaires |

Certaines fonctions peuvent évoluer entre les versions du bridge.

## Banques de paramètres

L’EC4 possède 16 encodeurs physiques, mais le Companion Controller de LiveProfessor permet au bridge de gérer jusqu’à **99 contrôles**.

Les paramètres sont donc organisés en banques :

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

Il suffit alors de copier l’exécutable et ce fichier sur un autre PC pour retrouver la configuration.

## Documentation

Documentation détaillée disponible dans le dossier `docs` :

- [Guide d’installation et d’utilisation](docs/GUIDE_INSTALLATION_UTILISATION.md)
- [Configuration EC4](docs/CONFIGURATION_EC4.md)
- [Cartographie MIDI et SysEx](docs/CARTOGRAPHIE_MIDI_SYSEX.md)
- [Sources techniques](docs/SOURCES.md)

## Développement

Le projet est écrit en Python.

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-build.txt

$env:PYTHONPATH = "src"

.\.venv\Scripts\python.exe -m unittest discover -s tests -v

.\scripts\build.ps1
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

## Statut du projet

Le projet est actuellement en développement actif.

La version stable publiée est basée sur la branche `main`.

Certaines nouvelles fonctions et améliorations peuvent être testées dans des branches de développement avant leur intégration à la version stable.

## Auteur

**SiLeMI/O — By Mamat ------[]---**

Projet indépendant développé pour améliorer l’intégration du Faderfox EC4 dans un environnement LiveProfessor.

## Licence et marques

Ce dépôt est public, mais aucune licence open source n’est actuellement accordée.

**Tous droits réservés à Mamat / SiLeMI/O.**

Faderfox, LiveProfessor, Audioström, Ableton, VST ainsi que les autres marques citées appartiennent à leurs propriétaires respectifs.

Ce projet est indépendant et n’est ni affilié, ni approuvé, ni sponsorisé par Faderfox, Audioström ou les éditeurs des logiciels et plugins mentionnés.

Aucun logiciel propriétaire tiers n’est redistribué dans ce dépôt.

---

<a id="english-version"></a>

# 🇬🇧 English

## Why does this project exist?

The **Faderfox EC4** is an excellent MIDI controller: compact, rugged, equipped with 16 push encoders and a powerful OLED display.

When using it with **LiveProfessor**, however, much of that potential can easily be lost.

A generic MIDI controller normally requires a lot of manual mapping, makes it difficult to know which encoder controls which parameter, and can cause value jumps when switching between plugins or presets.

**EC4 LiveProfessor Bridge was created to solve that problem.**

It turns the EC4 into a dynamic control surface for LiveProfessor:

- the 16 encoders control parameters of the currently selected plugin;
- parameter names and values are received from LiveProfessor;
- the EC4 OLED displays what is currently being controlled;
- parameter values are synchronized in both directions;
- up to **99 parameters** can be accessed through banks;
- other EC4 setups and groups can remain available for Ableton or any other application.

The bridge operates **completely outside the audio path**.

It does not load plugins, process audio, install audio drivers or modify LiveProfessor projects.

In practice:

```text
EC4 → MIDI / SysEx → Bridge → OSC → LiveProfessor
```

and back:

```text
LiveProfessor → OSC feedback → Bridge → MIDI / SysEx → EC4
```

## Main features

- Faderfox EC4 MIDI connection
- Automatic EC4 detection and reconnection
- LiveProfessor Companion Controller support
- Up to **99 controls**
- Banks of **16 parameters**
- Bidirectional parameter feedback
- MIDI / OSC echo protection
- Dynamic parameter names on the EC4 OLED
- Temporary parameter value display
- Persistent 16-parameter bank grid
- MIDI Learn for the 16 encoders
- MIDI Learn for the 16 encoder push buttons
- Dedicated EC4 setup/group selection
- Plugin navigation
- Chain navigation
- Bank navigation
- Global snapshot recall
- Tap Tempo
- Recommended Companion mode
- Generic OSC fallback mode
- JSON parameter profiles
- Portable configuration
- Rotating log files
- Built-in diagnostics

## How it works

The bridge does not access plugin parameters directly.

Instead, it uses the virtual controls exposed by the LiveProfessor **Companion Controller**:

```text
Rotary1
Rotary2
Rotary3
...
Rotary99
```

LiveProfessor **Controller Maps** associate those controls with plugin parameters.

Example:

```text
EC4 Encoder 1
        ↓
Bridge
        ↓
/Companion/Rotary1
        ↓
LiveProfessor Controller Map
        ↓
Plugin Gain
```

Feedback follows the reverse path:

```text
Plugin Gain
        ↓
LiveProfessor
        ↓
OSC feedback
        ↓
Bridge
        ↓
EC4
```

This keeps the physical encoder value synchronized with the actual plugin value.

## Why use Controller Maps?

The goal is to avoid performing MIDI Learn again for every plugin instance.

A map can be created once for a plugin type. For example:

```text
Rotary1 → Gain
Rotary2 → Frequency
Rotary3 → Q
Rotary4 → Threshold
...
```

The same map can then be reused for other instances of the same plugin.

With **Only If Selected**, the 16 EC4 encoders automatically follow the currently selected plugin.

## Requirements

- Windows 10 or Windows 11 x64
- Faderfox EC4
- LiveProfessor 2023.0.8 or later
- official LiveProfessor licence or trial
- LiveProfessor Companion Controller
- Controller Maps for the plugins you want to control

## Download

The latest Windows version is available from the GitHub Releases page:

[Releases — EC4 LiveProfessor Bridge](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest)

The executable is standalone.

Simply copy:

```text
EC4-LiveProfessor-Bridge.exe
```

to the computer and run it.

Python is not required and administrator privileges are not needed.

## LiveProfessor configuration

### Important: the standard Companion Controller only contains 4 Rotary controls

When you simply add a **Companion Controller** in **Hardware Controllers**, LiveProfessor provides only these controls by default:

```text
Rotary1
Rotary2
Rotary3
Rotary4
```

EC4 LiveProfessor Bridge uses **16 Rotary controls per bank** and can address up to **99 controls**.

The Companion Controller therefore needs to be extended before all 16 EC4 encoders can be used.

### Recommended method — load the supplied `.ctrl2` file

The easiest method is to **load/import the `.ctrl2` file supplied with this project directly into LiveProfessor**.

This file already contains the Companion definition required by the bridge, avoiding the need to create each Rotary manually.

After loading it, simply check that the controller contains at least:

```text
Rotary1 → Rotary16
```

and more controls if you intend to use additional banks up to `Rotary99`.

This is the recommended method.

### Manual method

If you prefer to build the controller yourself:

1. open **Hardware Controllers** in LiveProfessor;
2. add a **Companion Controller**;
3. keep the 4 Rotary controls created by default;
4. add at least `Rotary5` through `Rotary16`;
5. optionally add `Rotary17` through `Rotary99` if you want to use all available banks;
6. save the completed controller so it can be reused later.

Recommended network settings:

```text
Address: 127.0.0.1
LiveProfessor input port: 8010
Feedback address: 127.0.0.1
Feedback port: 8011
```

These are also the bridge default values.

## Creating a Controller Map

Having `Rotary1` through `Rotary16` in the Companion Controller is not enough by itself: those Rotary controls must then be assigned to actual plugin parameters in a **Controller Map**.

For each plugin type:

1. load a test instance of the plugin;
2. open **Controller Maps**;
3. create a new map;
4. assign `Rotary1`, `Rotary2`, etc. to the required parameters;
5. enable **Only If Selected** if the map should follow the selected plugin;
6. keep feedback enabled;
7. save the map using **Save Map Preset**;
8. apply the preset to the other instances of the same plugin.

LiveProfessor may consider VST2 and VST3 versions of the same product to be different plugin types.

## EC4 configuration

The bridge can use either:

- the historical MIDI mapping used by the Ableton script;
- or any EC4 setup/group learned directly by the application.

To use a custom EC4 area:

1. select the EC4 setup and group you want to dedicate to LiveProfessor;
2. start the bridge;
3. click **Use current setup/group**;
4. start **Learn encoders + push**;
5. turn the 16 encoders in order;
6. press the 16 encoder buttons in order.

The mapping is then stored by the bridge.

Encoders should use **absolute CC values from 0 to 127** so feedback can correctly synchronize them.

## Main EC4 controls

| Gesture | Function |
|---|---|
| Encoders 1–16 | Control parameters in the active bank |
| Push 1–15 | Display parameter details |
| Push 16 | Tap Tempo |
| Shift + Push | Navigation and additional commands |

Some shortcuts may evolve between bridge versions.

## Parameter banks

The EC4 has 16 physical encoders, while the LiveProfessor Companion Controller allows the bridge to address up to **99 controls**.

Parameters are therefore organized into banks:

```text
Bank 1: Rotary1  → Rotary16
Bank 2: Rotary17 → Rotary32
Bank 3: Rotary33 → Rotary48
...
```

The active bank is displayed in the application and the EC4 display is refreshed automatically.

## OLED display

The bridge uses the EC4 **SysEx protocol** to control the display.

### Persistent grid

The 16 parameters of the current bank are displayed as a grid.

### Temporary parameter display

When an encoder is moved, the bridge can display:

- parameter name;
- parameter value;
- current plugin.

After a short delay, the display automatically returns to the main grid.

## Value jump protection

When a plugin changes or a parameter value is modified inside LiveProfessor, the bridge sends the new value back to the EC4.

The physical encoder is therefore synchronized with the current plugin value before it is moved again.

An echo guard prevents that feedback message from immediately being sent back to LiveProfessor.

## Configuration

By default, user configuration is stored in:

```text
%LOCALAPPDATA%\EC4LiveProfessorBridge\config.json
```

For fully portable operation, place:

```text
config.json
```

next to the executable.

The executable and configuration file can then be copied together to another computer.

## Documentation

More detailed documentation is available in the `docs` directory:

- [Installation and user guide](docs/GUIDE_INSTALLATION_UTILISATION.md)
- [EC4 configuration](docs/CONFIGURATION_EC4.md)
- [MIDI and SysEx mapping](docs/CARTOGRAPHIE_MIDI_SYSEX.md)
- [Technical sources](docs/SOURCES.md)

## Development

The project is written in Python.

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-build.txt

$env:PYTHONPATH = "src"

.\.venv\Scripts\python.exe -m unittest discover -s tests -v

.\scripts\build.ps1
```

The standalone Windows executable is built using **PyInstaller**.

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

## Project status

The project is under active development.

The stable public version is maintained on the `main` branch.

New features and diagnostics may first appear in development branches before being merged into the stable version.

## Author

**SiLeMI/O — By Mamat ------[]---**

Independent project created to improve Faderfox EC4 integration with LiveProfessor.

## Licence and trademarks

This repository is public, but no open-source licence is currently granted.

**All rights reserved by Mamat / SiLeMI/O.**

Faderfox, LiveProfessor, Audioström, Ableton, VST and all other trademarks mentioned belong to their respective owners.

This is an independent project and is not affiliated with, endorsed by or sponsored by Faderfox, Audioström or any of the software or plugin manufacturers mentioned.

No proprietary third-party software is redistributed in this repository.
