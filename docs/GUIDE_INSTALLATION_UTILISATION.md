# Guide d’installation et d’utilisation

🇬🇧 [English version](en/INSTALLATION_AND_USER_GUIDE.md)

## Avant de commencer

Le bridge ne modifie pas les projets LiveProfessor. Il est néanmoins recommandé de sauvegarder le projet et les presets de Controller Maps avant tout essai dans une session importante.

Deux modes sont disponibles :

- **Companion** : recommandé ; fournit des noms et des valeurs dynamiques et prend en charge jusqu’à 99 contrôles Rotary. Nécessite LiveProfessor 2023.0.8 ou supérieur.
- **Generic** : solution de repli ; les valeurs sont contrôlables, mais les noms affichés doivent provenir d’un profil JSON.

Utilisez une licence, une période d’essai ou une licence de test fournie officiellement par Audioström.

## Installation du bridge

1. Copiez le dossier de livraison où vous le souhaitez.
2. Lancez `EC4-LiveProfessor-Bridge.exe`. Aucune installation et aucun droit administrateur ne sont nécessaires.
3. Branchez le Faderfox EC4.
4. Dans l’application, cliquez sur **Actualiser les ports MIDI** et choisissez l’entrée et la sortie contenant `Faderfox EC4`.
5. Configurez le contrôleur LiveProfessor décrit ci-dessous avant de cliquer sur **Démarrer**.

La configuration normale est enregistrée dans :

```text
%LOCALAPPDATA%\EC4LiveProfessorBridge\config.json
```

Pour un fonctionnement portable, copiez `config.example.json` à côté de l’exécutable et renommez-le `config.json`.

## Mode recommandé — Companion

### Prérequis

- LiveProfessor 2023.0.8 ou supérieur ;
- aucune autre application à l’écoute du port UDP `8011` ;
- un setup/groupe EC4 pouvant être réservé à LiveProfessor.

### Définir le contrôleur LiveProfessor

Les intitulés exacts peuvent varier légèrement selon la version de LiveProfessor.

#### Méthode recommandée — charger le fichier `.ctrl2` fourni

Un **Companion Controller** nouvellement créé ne propose que quatre contrôles Rotary par défaut :

```text
Rotary1
Rotary2
Rotary3
Rotary4
```

Le bridge utilise 16 Rotary par banque et peut adresser jusqu’à 99 contrôles. La méthode la plus simple consiste donc à charger/importer le fichier `.ctrl2` fourni avec le projet ou l’archive de livraison.

Après l’import, vérifiez que le contrôleur contient au minimum :

```text
Rotary1 → Rotary16
```

Conservez ou ajoutez `Rotary17` à `Rotary99` pour utiliser les banques supplémentaires.

#### Méthode manuelle

1. Ouvrez **Hardware Controllers** dans LiveProfessor.
2. Ajoutez un **Companion Controller**.
3. Conservez les quatre Rotary créés par défaut.
4. Ajoutez au minimum `Rotary5` à `Rotary16`.
5. Ajoutez éventuellement `Rotary17` à `Rotary99`.
6. Enregistrez le contrôleur ainsi complété pour pouvoir le réutiliser.

Utilisez ces réglages réseau :

```text
Adresse : 127.0.0.1
Port d’entrée LiveProfessor : 8010
Adresse de feedback : 127.0.0.1
Port de feedback : 8011
```

Si le type Companion Controller n’existe pas, la version installée de LiveProfessor est trop ancienne. Ne tentez pas de contourner cette limite par injection ou automatisation de l’écran.

### Créer une Controller Map par type de plugin

Cette opération remplace les MIDI Learn répétés par une définition unique et réutilisable dans LiveProfessor :

1. Chargez une instance de test du plugin, hors session de production importante.
2. Ouvrez **Controller Maps** et créez une nouvelle map.
3. Utilisez **Quick Assign** ou l’éditeur de mapping pour relier `Rotary1`, `Rotary2`, etc. aux paramètres souhaités.
4. Activez **Only If Selected** pour que les mêmes encodeurs suivent l’instance actuellement sélectionnée.
5. Conservez une plage normalisée de 0 à 1 et laissez le feedback activé.
6. Enregistrez la map avec **Save Map Preset. For later use with same plugin-type**.
7. Utilisez **Apply Map Preset** sur les autres instances du même type. Lorsque la fonction existe, appliquez ou copiez la map à toutes les instances de ce type.

Une map appartient à un **type de plugin**. Ne supposez pas qu’une map VST2 puisse être réutilisée sans adaptation avec la version VST3 du même produit.

### Configurer et démarrer le bridge

Réglages recommandés :

- Mode : `companion` ;
- Adresse LiveProfessor : `127.0.0.1` ;
- Port LP : `8010` ;
- Port retour : `8011` ;
- Zone EC4 dédiée : choisissez un setup/groupe réservé à LiveProfessor ;
- Affichage SysEx : activé ;
- Affichage permanent des paramètres du plugin sélectionné : activé ;
- Profil : vide, sauf si des libellés de secours sont nécessaires.

Cliquez sur **Enregistrer**, puis sur **Démarrer**. L’état doit passer de `Recherche du Faderfox EC4` à `Connecté`. Après réception de la réponse SysEx de l’EC4, le setup et le groupe actifs apparaissent également.

Pour utiliser la page actuellement affichée sur l’EC4 :

1. sélectionnez le setup et le groupe désirés sur l’EC4 ;
2. cliquez sur **Utiliser le setup/groupe actuel**.

Le choix est enregistré immédiatement. Hors de cette zone cible, le bridge ignore les commandes de paramètres et n’envoie aucun feedback, ce qui laisse les autres pages de l’EC4 disponibles pour d’autres usages.

### Apprendre n’importe quel setup/groupe EC4

Il n’est pas nécessaire de reproduire les numéros de CC et de Notes du mapping de repli intégré.

1. Laissez le bridge démarré et restez sur le setup/groupe choisi.
2. Cliquez sur **Apprendre rotatifs + push**.
3. Tournez légèrement les encodeurs 1 à 16, dans cet ordre.
4. Lorsque la seconde phase commence, appuyez sur les push 1 à 16, dans cet ordre.
5. Attendez la confirmation **Mapping appris et enregistré**.

Le mapping est mémorisé pour ce couple setup/groupe et réutilisé au prochain lancement.

Les encodeurs doivent être programmés sur l’EC4 en **CC absolu de 0 à 127**, et les push en **Notes MIDI**. Les gestes Shift+push utilisent des messages SysEx distincts et ne font pas partie de l’apprentissage.

### Affichage des paramètres du plugin sélectionné

Lorsque **Afficher en permanence les paramètres du plugin sélectionné** est activé, l’EC4 affiche une grille de 16 cellules correspondant à la banque active. Un mouvement ou un push affiche temporairement le nom complet et la valeur, puis la grille revient automatiquement.

En mode Companion, les libellés proviennent du feedback `ControllerNames` de LiveProfessor. Ils suivent donc les contrôles de la Controller Map du plugin sélectionné. Le bridge envoie `/init` et `/refresh` au démarrage et renouvelle la demande tant qu’aucun nom n’a été reçu.

Sans instance LiveProfessor active, sans Companion Controller correctement configuré ou sans Controller Map applicable, les libellés restent génériques (`P001`, `P002`, etc.). Le bridge ne peut pas inventer les noms internes du plugin.

## Mode de repli — OSC générique

Le mode Generic est une solution de repli et peut demander des adaptations selon la version de LiveProfessor. Commencez sur un projet de test avec un seul paramètre.

1. Ouvrez **Hardware Controllers**.
2. Ajoutez un contrôleur **OSC** générique.
3. Définissez son entrée sur `127.0.0.1:8010` et son feedback vers `127.0.0.1:8011`.
4. Déclarez des contrôles flottants normalisés avec les adresses `/EC4/Rotary1` à `/EC4/Rotary99`. Commencez par 1 à 16 pour un test minimal.
5. Activez le feedback sur les mêmes adresses.
6. Mappez ces contrôles aux paramètres et enregistrez un preset de map par type de plugin.
7. Sélectionnez `generic` dans le bridge.
8. Facultatif : choisissez un profil de noms, par exemple `profiles\exemple-plugin.json`.

Sans profil, l’EC4 affiche `P001`, `P002`, etc. Cette route OSC générique ne fournit pas les noms dynamiques disponibles avec le Companion Controller moderne.

## Commandes quotidiennes

| Action EC4 | Résultat |
|---|---|
| Tourner les encodeurs 1–16 | Modifier les 16 paramètres de la banque active |
| Shift+push encodeur 2 | Rappeler le snapshot global précédent |
| Shift+push encodeur 3 | Rappeler le snapshot global suivant |
| Shift+push encodeur 14 | Banque précédente |
| Shift+push encodeur 15 | Banque suivante |
| Push simple encodeur 16 | Tap Tempo |
| Shift+push encodeurs 9/10/11/12 | Première/précédente/suivante/dernière banque, raccourcis de compatibilité |
| Notes plugin précédent/suivant | Plugin précédent/suivant |
| Appuyer sur un encodeur | Afficher temporairement son nom, sa valeur, sa banque et son numéro |
| Bouton **Tester l’écran EC4** | Afficher un écran de diagnostic sans toucher au chemin audio |

Les fonctions premier/dernier plugin ou chaîne et le verrouillage affichent une limitation, car aucune commande publique correspondante n’a été trouvée.

## Profils JSON

Un profil sert uniquement de source de secours pour les libellés affichés. Il ne remplace pas une Controller Map LiveProfessor.

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

Les champs d’identifiants sont conservés pour une éventuelle API future, mais ils ne servent pas actuellement à reconnaître automatiquement le plugin : le protocole LiveProfessor étudié ne transmet pas d’identité stable du plugin.

## Diagnostic et journal

- **Diagnostic** vérifie localement l’encodage OSC/SysEx et liste les ports MIDI disponibles.
- Journal : `%LOCALAPPDATA%\EC4LiveProfessorBridge\bridge.log`.
- Quatre fichiers maximum sont conservés : le journal courant et trois rotations de 2 Mo.
- Si l’EC4 est débranché, le bridge ferme les ports disparus et tente une reconnexion toutes les deux secondes.

## Dépannage

### L’état reste `EC4 déconnecté`

- Fermez toute autre application susceptible d’avoir ouvert les ports MIDI de l’EC4 en mode exclusif.
- Rebranchez l’EC4, cliquez sur **Actualiser les ports MIDI**, puis vérifiez les deux sélecteurs MIDI.
- Consultez le journal pour confirmer le nom exact du port détecté par Windows.

### Erreur sur le port retour 8011

Une autre application utilise probablement déjà ce port, souvent Bitfocus Companion. Fermez l’autre récepteur ou choisissez une autre paire de ports identique dans LiveProfessor et le bridge.

### Les paramètres bougent mais l’écran EC4 ne change pas

- Vérifiez que l’affichage SysEx est activé.
- Vérifiez que le setup/groupe actuel correspond exactement à la **zone EC4 dédiée** sélectionnée dans le bridge.
- Utilisez **Utiliser le setup/groupe actuel** pour enregistrer la page affichée par l’EC4.

### Les noms restent P001, P002…

- En mode Companion, vérifiez le feedback UDP sur le port 8011 et la définition du Companion Controller.
- Vérifiez qu’une Controller Map est appliquée au plugin et que ses Rotary possèdent des noms.
- Vérifiez que le plugin concerné est bien celui sélectionné dans LiveProfessor.
- En mode Generic, sélectionnez un profil JSON ; les noms dynamiques ne sont pas attendus dans ce mode.

### Un plugin réinséré n’est plus contrôlé

Appliquez de nouveau son preset de Controller Map dans LiveProfessor. Le bridge n’écrit pas directement dans les projets LiveProfessor et ne peut pas forcer cette opération sans API officielle.
