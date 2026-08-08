# Changelog

## 2026.1

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
- les poussoirs, raccourcis Shift et projets originaux restent inchangés.

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
