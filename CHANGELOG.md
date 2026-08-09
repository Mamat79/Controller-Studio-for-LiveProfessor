# Changelog

## 2026.1

- correction de la collision entre la map dynamique rappelée par les snapshots et le premier preset généré ;
- ajout de **Réparer les mappings**, qui crée une copie consolidée sans modifier le projet source et donne toujours priorité aux affectations actuellement actives ;
- synchronisation des presets dynamiques devenus obsolètes afin que le rappel d'un preset ne supprime plus les mappings appris ensuite ;
- profil unique et déterministe pour toutes les instances d'un même type de plugin ;
- fusion des fonctions manuelles complémentaires dans les rotatifs encore libres, sans remapper une fonction déjà présente ailleurs ;
- suppression des doublons entre deux rotatifs, deux poussoirs ou deux emplacements physiques différents ;
- conservation du seul doublon intentionnel `poussoir N + rotatif N`, avec le même paramètre, afin que le label du poussoir reste visible en permanence sur l'EC4 ;
- priorité d'affichage : label du rotatif quand il existe, sinon label du poussoir seul, avec nom et valeur du poussoir lors de l'appui ;
- suppression pendant la réparation des affectations obsolètes visant des instances de plugins qui ne sont plus présentes dans le projet ;
- prise en charge des identifiants JUCE hexadécimaux non complétés à huit chiffres, dont CEDAR StageVox ;
- lorsqu'un plugin est incompatible avec l'auto-mapping, il est maintenant ignoré avec un avertissement tandis que les autres plugins continuent d'être traités ;
- ajout de notices PDF complètes en français et en anglais, accessibles depuis le menu Aide et intégrées aux paquets ;
- ajout de paquets macOS expérimentaux distincts pour Apple Silicon et Intel, construits nativement par GitHub Actions ;
- ouverture multiplateforme des notices, projets et journaux locaux ;
- l'auto-mapping injecte désormais automatiquement le modèle EC4 intégré quand le projet
  LiveProfessor ne contient encore aucun contrôleur Companion/OSC, au lieu de refuser l'analyse ;
- le bouton principal d'auto-mapping est maintenant mis en évidence par une couleur et une icône ;
- après la création, une alerte propose d'ouvrir directement la copie dans LiveProfessor tout en
  rappelant que le projet actuellement ouvert sera remplacé ;

- premier auto-mapping assisté des paramètres exposés par les plugins d'un projet LiveProfessor ;
- création obligatoire d'une nouvelle copie `.rack2`, sans modification du projet source ;
- map `EC4 AutoMap - Dynamic` combinant les plugins présents avec `Only If Selected` ;
- application directe dans les `HardwareCtrlMaps` réellement rappelés par le projet et ses snapshots : aucun chargement manuel plugin par plugin n'est nécessaire ;
- conservation des affectations de boutons existantes lors de la fusion dans la map active ;
- prise en charge de plusieurs instances d'un même type de plugin dans la map dynamique ;
- choix explicite UniBank/FullBank, avec UniBank 16 paramètres recommandé et sélectionné par défaut ;
- extension optionnelle du Companion Controller à 99 rotatifs en mode FullBank ;
- validation binaire du projet généré avant son enregistrement et sauvegarde de la destination si elle existe déjà ;
- fenêtre bilingue accessible depuis la page principale et le menu **Outils** ;
- les poussoirs de plugin déjà appris sont conservés ; les raccourcis Shift et projets originaux restent inchangés.

## 0.5.1

- affichage immédiat des 16 raccourcis sur l'EC4 pendant le maintien de Shift ;
- retour automatique à la grille des paramètres au relâchement de Shift ;
- repères `ChUp` / `ChDn` pour les chaînes et `<Plg` / `Plg>` pour les plugins, compatibles avec le jeu de caractères de l'EC4 ;
- prise en compte explicite des messages SysEx de pression et de relâchement de Shift.
- deux contrôleurs neutres intégrés : `Ec4-UniBank.ctrl2` (16 rotatifs) et `Ec4-FullBank.ctrl2` (99 rotatifs), tous deux avec 16 boutons et sans ancien preset lié à un plugin.
- choix UniBank/FullBank dans l'application, copie vers le dossier choisi et guide d'import LiveProfessor bilingue.

## 0.5.0

- correction de la navigation dans tous les View Sets à partir des index réellement renvoyés par LiveProfessor ;
- utilisation d'une seule adresse OSC par commande Cue, Snapshot, Show/Hide et Enable/Disable ;
- correction de `Shift + push 9` avec la casse OSC réellement acceptée par LiveProfessor ;
- transmission des push simples 1 à 15 aux boutons Companion, avec messages press/release ;
- second rafraîchissement Companion au démarrage et nouvelles tentatives bornées en cas d'inventaire incomplet ;
- sauvegarde atomique de la configuration ;
- fenêtre principale compacte et menus français/anglais ;
- fenêtres dédiées pour les réglages, les connexions et le journal ;
- nouveau titre et bandeau `EC4 Bridge 0.5.0 | SiLeMI/O | By Mamat` ;
- tray Windows basé sur une fenêtre de messages dédiée et une file d'actions séparant le callback Windows de Tkinter, restaurable par clic y compris avec les notifications empaquetées de Windows 11 ;
- vérification automatique ou manuelle des GitHub Releases stables ;
- validation structurelle du fichier `Ec4.ctrl2` (16 boutons + 16 rotatifs) ;
- tests supplémentaires pour les boutons, View Sets, tray, updater et réseau indisponible.
