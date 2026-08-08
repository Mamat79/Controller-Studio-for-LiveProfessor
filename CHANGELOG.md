# Changelog

## 0.5.0

- correction de la navigation dans tous les View Sets à partir des index réellement renvoyés par LiveProfessor ;
- utilisation d'une seule adresse OSC officielle par commande Cue, Snapshot, Show/Hide et Enable/Disable ;
- transmission des push simples 1 à 15 aux boutons Companion, avec messages press/release ;
- second rafraîchissement Companion au démarrage et nouvelles tentatives bornées en cas d'inventaire incomplet ;
- sauvegarde atomique de la configuration ;
- fenêtre principale compacte et menus français/anglais ;
- fenêtres dédiées pour les réglages, les connexions et le journal ;
- nouveau titre et bandeau `EC4 Bridge 0.5.0 | SiLeMI/O | By Mamat` ;
- tray Windows restaurable par clic, y compris avec les notifications empaquetées de Windows 11, menu contextuel et sortie idempotente ;
- vérification automatique ou manuelle des GitHub Releases stables ;
- validation structurelle du fichier `Ec4.ctrl2` (16 boutons + 16 rotatifs) ;
- tests supplémentaires pour les boutons, View Sets, tray, updater et réseau indisponible.
