# Rapport de stabilisation — EC4 LiveProfessor Bridge 0.5.0

Date : 8 août 2026

Branche : `agent/fix-ec4-0.5`

Point de départ : `4fff689`

Retour arrière : tag `safety/pre-v0.5-20260808`

## Résultat

La version 0.5.0 stabilise les commandes EC4, le rafraîchissement Companion, l'interface, le système tray et la vérification des mises à jour. Elle conserve les mappings utilisateur et ne modifie aucun projet LiveProfessor.

Le README bilingue publié sur la branche GitHub principale a été repris comme référence documentaire, puis complété avec les fonctions 0.5.0.

## Correctifs fonctionnels

- **View Sets** : le nombre d'arguments OSC n'est plus utilisé comme index. Le bridge extrait l'index numérique renvoyé par LiveProfessor, suit l'inventaire et parcourt tous les View Sets avec retour circulaire.
- **Show/Hide** : `Shift + push 5` envoie une seule commande officielle `/Command/PluginWindows/ShowHideselectedplugin`.
- **Enable/Disable** : `Shift + push 9` envoie une seule commande officielle `/Command/SelectedPlugin/EnableProcessingOnSelectedPlugin`.
- **Cues et snapshots** : une adresse officielle unique est envoyée par action, sans double fallback silencieux.
- **Boutons simples** : les push 1 à 15 émettent maintenant les états pression `1.0` et relâchement `0.0` vers `/Companion/GenericButtons/ButtonN`. Le push simple 16 reste réservé au Tap Tempo.
- **Plugins déjà chargés** : le bridge redemande l'état Companion au démarrage et effectue une relance bornée si l'inventaire est incomplet.
- **Valeurs et étiquettes** : les retours Companion continuent d'alimenter l'EC4, avec garde anti-écho et affichage vide pour les emplacements non affectés.
- **Robustesse OSC** : fermeture propre du socket et recréation paresseuse lors de l'envoi suivant.

## Interface et tray

- fenêtre principale recentrée sur les actions courantes ;
- réglages avancés, connexions et journal déplacés dans des fenêtres secondaires ;
- changement français/anglais immédiat ;
- nouveau titre et bandeau : `EC4 Bridge 0.5.0 | SiLeMI/O | By Mamat` ;
- réduction dans la zone de notification sans fermeture ;
- clic gauche ou double-clic : restauration ;
- clic droit : menu Ouvrir, Démarrer, Arrêter, Redémarrer, Journal, Mise à jour et Quitter ;
- fermeture par la croix et vraie sortie par Quitter séparées ;
- journal copiable, effaçable et accessible depuis le menu.

## Mise à jour et contribution

- vérification manuelle et optionnelle au démarrage via la dernière release stable GitHub ;
- comparaison sémantique des versions ;
- affichage des notes de version et ouverture de l'asset officiel ;
- liens dépôt, releases, issues, contribution et soutien dans le menu Aide ;
- aucune installation silencieuse et aucun téléchargement depuis un domaine non autorisé.

## Validation exécutée

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -W default -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

Résultat : **39 tests réussis**, aucune erreur de compilation Python et aucun défaut d'espace détecté par Git.

Contrôles supplémentaires :

- ouverture réelle de l'exécutable installé sous Windows ;
- changement visuel français → anglais sans redémarrage ;
- réduction puis restauration du tray par le callback Windows : `TRAY_RESTORE_SMOKE_OK` ;
- contrôle structurel de `Ec4.ctrl2` : 32 contrôles uniques, 16 boutons et 16 rotatifs ;
- vérification de l'absence des notes internes dans les paquets publics.

## Validation matérielle restant à faire

L'EC4 était débranché et LiveProfessor n'était pas lancé pendant la validation finale. Les scénarios suivants sont donc couverts par tests automatisés et conformité aux commandes officielles, mais doivent encore être rejoués avec le matériel et une session LiveProfessor réelle :

- parcours de plus de deux View Sets ;
- Show/Hide et Enable/Disable sur plusieurs formats de plugins ;
- Cue précédente/suivante ;
- snapshot global précédent/suivant ;
- apprentissage réel des 16 push et 16 rotatifs ;
- remontée initiale des noms et valeurs d'un plugin déjà chargé.

## Fichiers distribués

- `EC4-LiveProfessor-Bridge.exe`
- `EC4-LiveProfessor-Bridge-Setup-v0.5.0.exe`
- `EC4-LiveProfessor-Bridge-v0.5.0-windows.zip`
- `Ec4.ctrl2`
- `SHA256SUMS.txt`

Empreintes SHA-256 finales :

```text
609A1FA117F21FCB3932A28B6D6CE3663C51ADD5C561A8971F3AA996A40DBC70  EC4-LiveProfessor-Bridge.exe
CF6FF324A8D0031AC3E8BF82BD83B72D50962B0DC63B9E24DC5EF08AF2A2D7E9  EC4-LiveProfessor-Bridge-Setup-v0.5.0.exe
AFF5BE5590864E16FB81E19256CA178E02193726D779DDED37EFF64B6F8259C0  EC4-LiveProfessor-Bridge-v0.5.0-win64.zip
CA47042D5878A8AC000CA2855418F0568F17708B5C7569CED7C4DD310EF1793F  Ec4.ctrl2
```

## Suite recommandée

La version 1.0 pourra ajouter l'auto-mapping assisté puis automatique. Après validation sur l'EC4, l'architecture pourra être ouverte à d'autres interfaces MIDI/OSC au moyen de profils matériels, sans casser le comportement de référence EC4.
