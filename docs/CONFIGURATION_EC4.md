# Exemple de configuration EC4

🇬🇧 [English version](en/EC4_CONFIGURATION.md)

Le bridge peut utiliser son mapping de repli intégré ou apprendre les messages MIDI de n’importe quel setup/groupe EC4 adapté, sans qu’il soit nécessaire de reprogrammer tout l’appareil.

## Mapping de repli par défaut

Le mapping suivant est utilisé lorsqu’aucun mapping appris n’existe pour le setup/groupe sélectionné.

| Encodeurs | Canal EC4 affiché | CC | Valeurs |
|---|---:|---:|---:|
| 1–8 | 13 | 48–55 | Absolu 0–127 |
| 9–16 | 14 | 73–80 | Absolu 0–127 |

| Boutons | Canal | Notes |
|---|---:|---:|
| Push paramètres 1–16 | 13 | 40–55 |
| Banque précédente/suivante | 14 | 112/113 |
| Navigation plugin et chaîne | 13 | 112–119 |

L’EC4 doit accepter le feedback CC sur ces mêmes canaux et contrôleurs. Ce retour aligne la valeur interne de l’encodeur avec la valeur actuelle du plugin et évite les sauts brusques.

## Setup et groupe dédiés

Le bridge actuel peut réserver n’importe quel couple setup/groupe compris entre 1 et 16.

Lorsque l’EC4 se trouve sur une autre page, les commandes de paramètres, le feedback et les mises à jour d’affichage sont suspendus. Le bridge ne perturbe donc pas les autres usages de l’EC4.

Procédure recommandée :

1. sélectionnez sur l’EC4 la page à réserver à LiveProfessor ;
2. démarrez le bridge ;
3. cliquez sur **Utiliser le setup/groupe actuel** ;
4. vérifiez que les champs Setup et Groupe correspondent aux valeurs affichées dans la zone d’état.

## Apprentissage d’un mapping personnalisé

La page choisie n’a pas besoin d’utiliser les numéros de CC et de Notes du mapping de repli.

1. Laissez l’EC4 sur le setup/groupe cible.
2. Cliquez sur **Apprendre rotatifs + push**.
3. Tournez les encodeurs 1 à 16 dans l’ordre.
4. Appuyez sur leurs 16 push dans l’ordre.
5. Attendez la confirmation indiquant que le mapping a été appris et enregistré.

Le bridge mémorise les adresses MIDI pour ce couple setup/groupe.

Les encodeurs doivent rester configurés en **CC absolu 0–127** afin que le feedback de valeur puisse éviter les sauts. Les push doivent envoyer des **Notes MIDI**. Les gestes Shift+push sont transmis sous forme de messages SysEx séparés et ne font pas partie de la phase d’apprentissage.

## Fichier de configuration du bridge

L’exemple [config.example.json](../config.example.json) contient notamment :

- jusqu’à 99 contrôles ;
- des banques de 16 ;
- une sortie OSC vers `127.0.0.1:8010` et un feedback sur `127.0.0.1:8011` ;
- une garde anti-écho de 100 ms ;
- une reconnexion MIDI toutes les deux secondes ;
- une protection de l’affichage hors du setup/groupe sélectionné ;
- la grille permanente des paramètres (`persistent_parameter_display`) ;
- le setup et le groupe dédiés (`target_setup`, `target_group`) ;
- la restriction des commandes du bridge à cette zone (`restrict_to_target`) ;
- les mappings appris par setup/groupe (`encoder_mappings`).

Pour un premier test, sélectionnez un groupe EC4 libre, cliquez sur **Utiliser le setup/groupe actuel**, puis lancez **Apprendre rotatifs + push**.
