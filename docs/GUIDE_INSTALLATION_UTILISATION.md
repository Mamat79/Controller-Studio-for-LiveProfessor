# Guide d'installation et d'utilisation

## Avant de commencer

Le pont ne modifie pas LiveProfessor. Il est néanmoins recommandé de sauvegarder le projet et les presets de Controller Maps avant tout essai.

Deux modes sont disponibles :

- **Companion** : recommandé, noms et valeurs dynamiques, 99 rotatifs ; demande LiveProfessor 2023.0.8 ou supérieur.
- **Generic** : solution de repli ; les valeurs sont contrôlables, mais les noms doivent venir d'un profil JSON.

Utilisez une licence, une période d'essai ou une licence de test fournie officiellement par Audioström.

## Installation de la passerelle

1. Copier le dossier de livraison où vous le souhaitez.
2. Lancer `EC4-LiveProfessor-Bridge.exe` ; aucune installation et aucun droit administrateur ne sont nécessaires.
3. Brancher le Faderfox EC4.
4. Dans l'application, ouvrir **Outils > Réglages**, cliquer sur **Actualiser les ports MIDI** et choisir les entrées/sorties contenant `Faderfox EC4`.
5. Ne cliquer sur **Démarrer** qu'après la configuration du contrôleur LiveProfessor ci-dessous.

La configuration est enregistrée dans `%LOCALAPPDATA%\EC4LiveProfessorBridge\config.json`. Pour une version portable, copier `config.example.json` à côté de l'exécutable sous le nom `config.json`.

## Mode recommandé — Companion

### Prérequis

- LiveProfessor 2023.0.8 ou supérieur ;
- aucune autre application à l'écoute du port UDP 8011 ;
- EC4 sur sa configuration Ableton existante décrite dans [CONFIGURATION_EC4.md](CONFIGURATION_EC4.md).

### Définir le contrôleur LiveProfessor

Les intitulés peuvent varier selon la version :

1. Ouvrir **Hardware Controllers** dans LiveProfessor.
2. Ajouter un contrôleur de type **Companion Controller**.
3. Configurer l'adresse sur `127.0.0.1`.
4. Configurer le port d'entrée LiveProfessor sur `8010`.
5. Configurer la sortie/feedback vers `127.0.0.1:8011`.
6. Vérifier que ce contrôleur propose `Rotary1` à `Rotary99` et leurs retours.

Le module Bitfocus Companion 2.0 installé sur la machine de référence ne documente par défaut que `Rotary1` à `Rotary4`. Pour exploiter les 16 encodeurs de la première banque, ajouter des contrôles rotatifs dans Hardware Controllers Setup et leur apprendre successivement les messages `Rotary5` à `Rotary16` envoyés par le pont. Le journal indique désormais combien de rotatifs LiveProfessor a réellement renvoyés et liste ceux qui manquent.

Si ce type de contrôleur n'existe pas, la version de LiveProfessor est trop ancienne : ne tentez pas de contourner le problème avec une injection ou une automatisation d'écran.

### Créer une map par type de plugin

Cette opération remplace les MIDI Learn répétés par une déclaration unique dans LiveProfessor :

1. Charger une instance de test du plugin, hors session sensible.
2. Ouvrir **Controller Maps** et créer une nouvelle map.
3. Utiliser **Quick Assign** ou l'éditeur de mapping pour relier `Rotary1`, `Rotary2`, etc. aux paramètres souhaités.
4. Activer **Only If Selected** pour que les mêmes rotatifs suivent l'instance sélectionnée.
5. Conserver un contrôle absolu 0–1 ; laisser le feedback activé.
6. Enregistrer la map avec **Save Map Preset. For later use with same plugin-type**.
7. Utiliser **Apply Map Preset** sur les autres instances du même type. Sur les versions qui le proposent, appliquer/copier la map à toutes les instances du même type.

La map est spécifique au **type** de plugin. Ne présumez pas qu'une map VST2 est interchangeable avec une VST3 du même produit.

Attention à ne pas confondre les deux apprentissages : **Learn** dans Hardware Controllers Setup apprend à LiveProfessor quel message OSC correspond à un `RotaryN`; il ne relie pas encore ce contrôle à un paramètre audio. Cette deuxième liaison se fait dans le **Controller Map actif**. Avec Quick Assign, activer `QA`, bouger le paramètre du plugin à la souris et tourner l'encodeur EC4 pendant le même apprentissage.

### Configurer et lancer le pont

Dans **Outils > Réglages** :

- Mode : `companion` ;
- Adresse LiveProfessor : `127.0.0.1` ;
- Port LP : `8010` ;
- Port retour : `8011` ;
- Zone EC4 dédiée : choisir un setup et un groupe qui ne servent pas à Ableton ;
- Affichage SysEx : activé ;
- Affichage permanent des paramètres du plugin sélectionné : activé ;
- Profil : vide, sauf libellés de secours souhaités.

Cliquer sur **Enregistrer**, puis **Démarrer**. L'état doit passer de « Recherche du Faderfox EC4 » à « Connecté ». Après la réponse SysEx, l'état affiche le setup et le groupe.

Pour reprendre la page actuellement affichée par l'EC4, placez-vous sur le setup/groupe désiré puis cliquez sur **Utiliser le setup/groupe actuel**. Le choix est enregistré immédiatement. Hors de cette zone, le pont n'écoute pas les commandes et n'envoie aucun feedback, ce qui protège le groupe dédié à Ableton.

Pour employer n'importe quel groupe sans recopier les CC du preset Ableton :

1. rester sur le setup/groupe choisi et garder le pont démarré ;
2. cliquer sur **Apprendre rotatifs + push** ;
3. tourner légèrement les encodeurs 1 à 16, dans cet ordre ;
4. lorsque la seconde phase commence, appuyer sur les push 1 à 16, dans cet ordre ;
5. attendre la confirmation **Mapping appris et enregistré**.

Le mapping est mémorisé pour ce couple setup/groupe et réutilisé au prochain lancement. Les rotatifs doivent être programmés sur l'EC4 en **CC absolu 0–127** et les push en **Notes MIDI**. Les gestes Shift+push sont des messages SysEx séparés et ne font pas partie de l'apprentissage.

### Affichage des paramètres du plugin sélectionné

Lorsque **Afficher en permanence les paramètres du plugin sélectionné** est coché, l'EC4 montre une grille de 16 libellés correspondant à la banque active. Un mouvement ou un push affiche temporairement le nom complet et la valeur, puis la grille revient automatiquement.

En mode Companion, les libellés viennent des retours `ControllerNames` de LiveProfessor. Ils suivent donc les contrôles de la Controller Map du plugin sélectionné. Le pont envoie `/init` et `/refresh` au démarrage, effectue un second rafraîchissement différé et renouvelle la demande de façon bornée si l'inventaire reste incomplet. Sans LiveProfessor actif, sans Companion Controller correctement configuré ou sans Controller Map, les emplacements concernés restent volontairement vides : le pont ne peut pas inventer les noms internes du plugin.

## Mode de repli — OSC générique

Ce mode est une solution de repli et peut demander une adaptation selon la version de LiveProfessor. Commencez sur un projet de test avec un seul paramètre.

1. Ouvrir **Hardware Controllers**.
2. Ajouter un contrôleur **OSC** générique.
3. Définir l'entrée `127.0.0.1:8010` et le feedback vers `127.0.0.1:8011`.
4. Déclarer des contrôles flottants normalisés avec les adresses `/EC4/Rotary1` à `/EC4/Rotary99`. Commencer par 1 à 16 pour un essai minimal.
5. Activer le feedback sur les mêmes adresses.
6. Mapper ces contrôles aux paramètres et enregistrer un preset de map par type de plugin.
7. Dans le pont, sélectionner `generic`.
8. Facultatif : sélectionner un profil de noms, par exemple `profiles\exemple-plugin.json`.

Sans profil, l'écran montre `P001`, `P002`, etc. Le contrôleur OSC générique ne fournit pas par ce chemin les noms dynamiques utilisés par le contrôleur Companion moderne.

## Commandes quotidiennes

| Action EC4 | Résultat |
|---|---|
| Tourner les encodeurs 1–16 | Modifier les 16 paramètres de la banque active |
| Shift+push encodeurs 1/2 | Banque précédente/suivante |
| Shift+push encodeurs 3/4 | Viewset précédent/suivant |
| Shift+push encodeur 5 | Afficher/masquer le plugin sélectionné |
| Shift+push encodeur 6 | Chaîne précédente |
| Shift+push encodeurs 7/8 | Plugin précédent / suivant |
| Shift+push encodeur 9 | Activer/désactiver le traitement du plugin sélectionné |
| Shift+push encodeur 10 | Chaîne suivante |
| Shift+push encodeurs 11/12 | Plugin précédent / suivant |
| Shift+push encodeurs 13/14 | Cue précédent/suivant |
| Shift+push encodeurs 15/16 | Snapshot global précédent/suivant |
| Push simple encodeur 16 | Tap Tempo |
| Push simples encodeurs 1–15 | Envoyer `GenericButton1` à `GenericButton15` au Companion Controller |
| Appuyer sur un encodeur 1–15 | Envoyer le bouton et afficher temporairement nom, valeur, banque et numéro |
| Bouton **Tester l'écran EC4** | Afficher un écran de diagnostic sans toucher à l'audio |

Les gestes premier/dernier plugin ou chaîne et verrouillage affichent une limitation, car aucune commande publique correspondante n'a été trouvée.

## Profils JSON

Un profil sert uniquement de secours d'affichage. Il ne remplace pas une Controller Map LiveProfessor.

```json
{
  "plugin_label": "Compresseur test",
  "manufacturer": "Fabricant",
  "plugin_format": "VST3",
  "plugin_id": "id-de-classe-si-connu",
  "parameters": [
    {"name": "Threshold", "short": "Thrs", "unit": "dB", "stable_id": "id-1"},
    {"name": "Ratio", "short": "Rati", "stable_id": "id-2"}
  ]
}
```

Les champs d'identifiants sont conservés pour une future API, mais ne sont pas utilisés pour reconnaître automatiquement le plugin : le protocole LiveProfessor étudié ne transmet pas cette identité stable.

## Diagnostic et journal

- **Diagnostic** vérifie localement l'encodage OSC/SysEx et liste les ports MIDI.
- **Raccourcis EC4** rappelle directement la disposition des touches Shift.
- Le journal détaillé est accessible par **Affichage > Journal** et continue d'être alimenté quand sa fenêtre est masquée.
- Le bouton `X` réduit par défaut l'application dans la zone de notification ; le clic gauche restaure la fenêtre et le clic droit ouvre les commandes Démarrer/Arrêter/Redémarrer/Journal/Mise à jour/Quitter.
- Journal : `%LOCALAPPDATA%\EC4LiveProfessorBridge\bridge.log`.
- Lorsqu'un encodeur tourne, le journal indique le CC reçu et le `/Companion/RotaryN` envoyé. `LiveProfessor confirme RotaryN` valide le trajet complet. Si aucun retour n'arrive après 0,8 seconde, le pont indique de vérifier le port d'entrée du Companion Controller et le Controller Map actif.
- Quatre fichiers maximum sont conservés : le journal courant et trois rotations de 2 Mo.
- Si l'EC4 est débranché, le pont ferme les ports disparus et tente une reconnexion toutes les deux secondes.

## Déployer sur un autre PC

### Fichier `Ec4.ctrl2` (format attendu)

`Ec4.ctrl2` est le fichier de contrôleur Companion que le pont emporte dans l’installation.  
Il contient les 16 entrées de boutons/rotatifs utilisées pour communiquer avec LiveProfessor.

Le dépôt inclut une version prête à l’emploi à la racine : [Ec4.ctrl2](../Ec4.ctrl2).

Si tu veux en fournir une autre version :

1. Exporter le contrôleur Companion depuis LiveProfessor (`.ctrl2`) ;
2. Utiliser le réparateur du dépôt si nécessaire :

```powershell
python .\scripts\repair_ctrl2.py "C:\chemin\source.ctrl2" .\Ec4.ctrl2
```

3. Recréer l’installateur (les scripts prennent automatiquement `Ec4.ctrl2` à la racine si présent).

### Méthode installateur (recommandée)

1. Sur votre machine de build, exécuter :

```powershell
pwsh .\scripts\build-installer.ps1
```

Le script produit un fichier :

`output\installer\windows\EC4-LiveProfessor-Bridge-Setup-vX.Y.Z.exe`

2. Copier cet `.exe` sur le second PC.
3. Lancer l'installateur, choisir le dossier d'installation (ex. `C:\Program Files\EC4LiveProfessorBridge` ou `%LOCALAPPDATA%\Programs\EC4LiveProfessorBridge`) puis valider.
4. Cochez si vous voulez les raccourcis, puis lancez l'application.

Si vous n'avez pas Inno Setup 6 sur cette machine, le script ne pourra pas compiler l'exécutable. L'installation locale se fait alors avec les scripts PowerShell (méthode portable ci-dessous).
Vous pouvez aussi lancer l'installation automatique d'Inno Setup via Winget :

```powershell
pwsh .\scripts\build-installer.ps1 -AutoInstallInnoSetup
```

### Méthode simple (recommandée)

1. Télécharger l'archive de release depuis GitHub (`EC4-LiveProfessor-Bridge-*.zip`).
2. Décompresser le ZIP.
3. Ouvrir un terminal PowerShell dans le dossier extrait.
4. Lancer :
   - `.\install-ec4-liveprofessor-bridge.bat` (ou `.\install-ec4-liveprofessor-bridge.ps1`)
5. Le script :
   - copie l'exécutable dans `C:\Users\\<vous>\\AppData\\Local\\Programs\\EC4LiveProfessorBridge` (par défaut),
   - crée un raccourci sur le bureau (optionnel),
   - crée un raccourci **Démarrer** dans le menu Démarrer (si disponible),
   - laisse la configuration portable (`config.json`) à côté de l'exécutable.

### Méthode portable

1. Copier le dossier de livraison (avec `EC4-LiveProfessor-Bridge.exe`) où vous voulez.
2. Copier `config.json` si vous l'avez personnalisé.
3. Lancer l'exécutable.

## Dépannage

### L'état reste « EC4 déconnecté »

- Fermer Ableton ou toute autre application ayant ouvert l'EC4 en exclusif.
- Rebrancher l'EC4, cliquer sur **Actualiser les ports MIDI**, puis vérifier les deux sélecteurs.
- Lire le journal pour connaître le nom exact du port.

### Erreur sur le port retour 8011

Un autre logiciel l'utilise probablement, souvent Bitfocus Companion. Fermer l'autre récepteur ou choisir une paire de ports différente dans LiveProfessor et le pont.

### Les paramètres bougent mais l'écran reste inchangé

- Vérifier que l'affichage est activé.
- Vérifier que l'état courant correspond exactement à la **Zone EC4 dédiée** choisie dans l'interface.
- Utiliser **Utiliser le setup/groupe actuel** pour enregistrer la page courante.

### Les noms restent P001, P002…

- En mode Companion, vérifier le retour UDP 8011 et la déclaration Companion Controller.
- Vérifier qu'une Controller Map est appliquée au plugin et que ses rotatifs possèdent des noms.
- Vérifier que le plugin concerné est bien celui sélectionné dans LiveProfessor.
- Vérifier que le nom affiché en haut de LiveProfessor est bien la map modifiée : apprendre un contrôle dans Hardware Controllers Setup ne l'assigne pas au plugin.
- En Quick Assign, activer `QA`, modifier le paramètre à la souris et tourner l'EC4 pendant l'apprentissage.
- En mode Generic, sélectionner un profil JSON ; les noms dynamiques ne sont pas attendus.

### Un plugin réinséré n'est plus contrôlé

Appliquer son preset de Controller Map dans LiveProfessor. Le pont n'écrit pas directement dans les projets et ne peut pas forcer cette opération sans API officielle.

### L'icône du .exe ou du raccourci reste ancienne dans Explorer/Taskbar

Quand l'icône ne se rafraîchit pas :

- Quitter l'application et vérifier le fichier réel lancé :
  `D:\IA\Projets\Codex\Applis Persos\FaderFox EC4\output\windows\EC4-LiveProfessor-Bridge.exe`.
- Si c'est le bon EXE, lancer le script :
  `scripts\refresh_windows_icon_cache.ps1`
- Désancrer puis ré-ancrer le raccourci (desktop / barre des tâches) après nettoyage.
- Si la valeur reste bloquée, démarrer l'exécutable directement depuis le dossier `output\windows` au moins une fois pour régénérer le cache de chemin.
