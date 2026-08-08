# Changelog

## 0.5.1

- affichage immédiat des 16 raccourcis sur l'EC4 pendant le maintien de Shift ;
- retour automatique à la grille des paramètres au relâchement de Shift ;
- repères `ChUp` / `ChDn` pour les chaînes et `<Plg` / `Plg>` pour les plugins, compatibles avec le jeu de caractères de l'EC4 ;
- prise en compte explicite des messages SysEx de pression et de relâchement de Shift.
- contrôleur `Ec4.ctrl2` nettoyé de son ancien preset Arousor et de ses affectations dupliquées, afin de fournir une base neutre pour les mappings de plugins.

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
