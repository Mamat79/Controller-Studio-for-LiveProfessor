# Exemple de configuration EC4

Le prototype peut réutiliser **le preset EC4 qui fonctionne déjà avec le script Ableton** ou apprendre les messages d'un autre setup/groupe, sans reprogrammer l'appareil.

## Paramètres indispensables

| Encodeurs | Canal EC4 affiché | CC | Valeurs |
|---|---:|---:|---:|
| 1–8 | 13 | 48–55 | Absolu 0–127 |
| 9–16 | 14 | 73–80 | Absolu 0–127 |

| Boutons | Canal | Notes |
|---|---:|---:|
| Push paramètres 1–16 | 13 | 40–55 |
| Banque précédente/suivante | 14 | 112/113 |
| Navigation et commandes device | 13 | 112–119 |

L'appareil doit accepter le feedback CC sur ces mêmes canaux et contrôleurs. C'est ce retour qui aligne la valeur interne de l'encodeur avec le plugin et évite un saut brutal.

## Setup et groupe d'affichage

Le script Ableton ne pilote l'affichage device que lorsque la réponse EC4 indique :

- setup interne 12, 13, 14 ou 15 — setup affiché 13 à 16 ;
- groupe interne 2 ou 3 — groupe affiché 3 ou 4.

Depuis la version 0.2.0, le setup et le groupe dédiés se choisissent dans l'interface. Si l'EC4 est sur une autre page, les commandes, le feedback et l'affichage sont tous suspendus afin de ne pas interférer avec Ableton.

Procédure :

1. sélectionner sur l'EC4 la page à réserver à LiveProfessor ;
2. démarrer le pont ;
3. cliquer sur **Utiliser le setup/groupe actuel** ;
4. vérifier que les champs Setup et Groupe reprennent les valeurs affichées dans l'état.

En version 0.3.0, la page choisie ne doit plus utiliser les mêmes numéros de CC/Notes. Cliquez sur **Apprendre rotatifs + push**, tournez les 16 encodeurs dans l'ordre puis appuyez sur leurs 16 push dans l'ordre. Le pont mémorise ces adresses pour la zone choisie. Les rotatifs doivent rester en CC absolu 0–127 afin que le retour de valeur évite les sauts.

## Fichier de configuration du pont

L'exemple [config.example.json](../config.example.json) contient :

- 99 contrôles au maximum ;
- banques de 16 ;
- OSC `127.0.0.1:8010` et feedback `127.0.0.1:8011` ;
- garde anti-écho de 100 ms ;
- reconnexion MIDI toutes les 2 secondes ;
- protection des setups/groupes d'affichage.
- grille permanente des paramètres (`persistent_parameter_display`) ;
- setup et groupe dédiés (`target_setup`, `target_group`) ;
- restriction de toutes les commandes à cette zone (`restrict_to_target`).
- mappings appris par zone (`encoder_mappings`).

Pour un premier test, sélectionnez un groupe libre, utilisez **Utiliser le setup/groupe actuel**, puis lancez **Apprendre rotatifs + push**.
