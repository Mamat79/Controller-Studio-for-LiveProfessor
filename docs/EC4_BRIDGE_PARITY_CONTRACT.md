# Contrat de parité EC4 Bridge

## Décision produit

`SiLeMI/O` est la marque. Le produit est `Controller Studio`. Tant que LiveProfessor est le seul hôte validé, son nom complet est **SiLeMI/O Controller Studio for LiveProfessor**.

Controller Studio doit reprendre tout ce qui fonctionne dans EC4 Bridge, puis ajouter la sélection et la fabrication de nouveaux contrôleurs ainsi que la bibliothèque de banques. La généralisation ne doit jamais retirer une fonction EC4 validée.

EC4 Bridge reste installé comme solution de secours jusqu'à l'acceptation matérielle explicite. Les deux moteurs ne doivent pas utiliser simultanément les mêmes ports MIDI ou OSC.

## Fonctions obligatoires avant remplacement

| Domaine | Comportement à préserver | État |
|---|---|---|
| Connexion | Recherche automatique des ports Faderfox EC4 | vérifiée avec l'EC4 connecté |
| Reconnexion | Récupération automatique après débranchement/rebranchement | redémarrage/reconnexion logicielle vérifiés ; débranchement physique à faire |
| Identification | Requête SysEx du setup et du groupe, restriction à la zone choisie | setup 1 / groupe 1 lus sur l'EC4 |
| Message EC4 | Affichage de la connexion, de `SiLeMI/O CtrlStudio` et de la signature `By Mamat` / `-----[]---` | test d'écran confirmé ; signature finale exacte couverte par test, à relire sur l'écran |
| Contrôle | 16 encodeurs, 16 poussoirs, Shift et raccourcis | gestes d'encodeur reçus et envoyés en OSC ; couverture matérielle complète à faire |
| Banques | Navigation, dernière banque partielle, valeurs et libellés cohérents | banques 1/7 et 2/7 vérifiées ; parcours complet à faire |
| Companion/OSC | Envoi des gestes et réception des noms/valeurs avec confirmation | moteur migré, import LiveProfessor à valider |
| Affichage | Grille persistante, valeur temporaire, raccourcis Shift et retour à la grille | écran de test vérifié ; scénario matériel complet à faire |
| Sécurité | Anti-écho MIDI et avertissement si LiveProfessor ne confirme pas | moteur migré, tests automatisés présents |
| Exploitation | Démarrer, arrêter, redémarrer, reconnexion, journal et mise à jour depuis l'interface/tray | contrôles principaux et réduction tray vérifiés ; commandes du menu tray couvertes automatiquement |
| Migration | Importer une configuration EC4 existante sans la modifier | implémenté, source conservée en lecture seule par test |
| AutoMap | Bouton visible, UniBank/FullBank, toutes les instances ou sélection par cases, réutilisation du contrôleur existant | implémenté ; validé hors ligne sur le projet fourni avec 1 contrôleur EC4, UID conservé et source inchangée |
| Aide | Notice PDF selon la langue, soutien PayPal facultatif et mise à jour applicative vérifiée | implémenté et couvert par tests ; notices contrôlées visuellement |

## Scénario d'acceptation matérielle

1. Lancer Controller Studio avec l'EC4 absent : l'application reste stable et annonce la recherche.
2. Brancher l'EC4 : connexion automatique, lecture setup/groupe et message lisible sur l'écran.
3. Importer le contrôleur Companion dans une session LiveProfessor sûre et vérifier les 16 rotatifs.
4. Tourner et presser chaque encodeur ; confirmer le mouvement dans LiveProfessor et le retour sur l'EC4.
5. Parcourir toutes les banques, les plugins, les chaînes, les cues, snapshots et View Sets.
6. Débrancher puis rebrancher l'EC4 ; vérifier la reconnexion, l'affichage et les valeurs courantes.
7. Réduire dans la zone de notification, puis utiliser ouvrir, arrêter, démarrer, redémarrer et journal.
8. Effectuer une session prolongée convenue avec l'utilisateur sans décrochage ni modification imprévue d'un projet.

Le remplacement d'EC4 Bridge ne peut être déclaré qu'après réussite de ces huit étapes et confirmation de l'utilisateur.
