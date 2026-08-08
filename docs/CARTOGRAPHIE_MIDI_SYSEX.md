# Cartographie MIDI et SysEx du Faderfox EC4

🇬🇧 [English version](en/MIDI_SYSEX_MAPPING.md)

Les numéros de canaux ci-dessous sont ceux affichés à l’utilisateur sur l’EC4. Le code Python emploie une numérotation à partir de zéro : le canal utilisateur 13 correspond à `12`, et le canal utilisateur 14 à `13`.

## Contrôle des paramètres — mapping de repli par défaut

| Fonction | Canal utilisateur | Message | Plage | Mode de contrôle |
|---|---:|---|---:|---|
| Paramètres 1–8 | 13 | CC | 48–55 | Absolu, feedback de valeur, takeover désactivé |
| Paramètres 9–16 | 14 | CC | 73–80 | Absolu, feedback de valeur, takeover désactivé |
| Afficher le détail des paramètres 1–16 | 13 | Notes | 40–55 | Appui momentané |
| Banque précédente | 14 | Note | 112 | Appui momentané |
| Banque suivante | 14 | Note | 113 | Appui momentané |

Ce mapping est utilisé lorsqu’aucun mapping personnalisé n’a été appris pour le setup/groupe sélectionné. Depuis la version 0.3.0, l’interface peut apprendre les 16 CC des encodeurs et les 16 Notes des push de n’importe quel setup/groupe.

Les encodeurs restent en mode absolu. Le feedback OSC reçu de LiveProfessor est converti en valeur CC de 0 à 127 et renvoyé à l’encodeur appris correspondant. Cette synchronisation constitue la stratégie anti-saut. Une garde de 100 ms empêche qu’un feedback identique soit interprété comme un nouveau mouvement de l’utilisateur.

## Navigation plugin et chaîne

| Action LiveProfessor | Canal | Note |
|---|---:|---:|
| Afficher/masquer le plugin sélectionné | 13 | 112 |
| Activer/désactiver le traitement du plugin sélectionné | 13 | 113 |
| Plugin précédent | 13 | 114 |
| Plugin suivant | 13 | 115 |
| Afficher/masquer le plugin sélectionné | 13 | 116 |
| Verrouillage du plugin | 13 | 117 — aucune commande OSC publique correspondante trouvée |
| Chaîne précédente | 13 | 118 |
| Chaîne suivante | 13 | 119 |

## Gestes Shift+push en SysEx

L’EC4 fournit 16 messages de boutons SysEx correspondant aux poussoirs d’encodeurs utilisés avec Shift.

| Index interne | Encodeur | Action du bridge |
|---:|---:|---|
| 0 | 1 | Indisponible : aucune commande publique correspondante trouvée |
| 1 | 2 | Snapshot global précédent |
| 2 | 3 | Snapshot global suivant |
| 3 | 4 | Indisponible |
| 4 | 5 | Indisponible |
| 5 | 6 | Plugin précédent |
| 6 | 7 | Plugin suivant |
| 7 | 8 | Indisponible |
| 8 | 9 | Première banque |
| 9 | 10 | Banque précédente |
| 10 | 11 | Banque suivante |
| 11 | 12 | Dernière banque |
| 12 | 13 | Activer/désactiver le traitement du plugin sélectionné |
| 13 | 14 | Banque précédente |
| 14 | 15 | Banque suivante |
| 15 | 16 | Afficher/masquer le plugin sélectionné |

Un **push simple sur l’encodeur 16** déclenche le Tap Tempo. Les push simples sur les encodeurs 1 à 15 affichent le détail du paramètre correspondant. Les actions de banque et de snapshot du tableau exigent Shift+push.

## Contrôles supplémentaires présents dans le preset EC4 historique mais non transmis par le bridge

Les contrôles suivants restent documentés à titre de référence. Le bridge actuel ne les redirige volontairement pas vers LiveProfessor.

### Seize tranches de contrôle

Les tranches 1–8 utilisent le canal utilisateur 13, tandis que les tranches 9–16 utilisent le canal utilisateur 14. Pour le second groupe, les numéros de contrôleurs 0–7 sont réutilisés sur l’autre canal MIDI.

| Fonction par tranche | Type | Base pour tranche 1/9 | Plage sur chaque canal MIDI |
|---|---|---:|---:|
| Sélection | Note | 56 | 56–63 |
| Volume | CC | 40 | 40–47 |
| Panoramique | CC | 32 | 32–39 |
| Send 1 | CC | 0 | 0–7 |
| Send 2 | CC | 8 | 8–15 |
| Send 3 | CC | 16 | 16–23 |
| Send 4 | CC | 24 | 24–31 |
| Lancer une action | Note | 64 | 64–71 |
| Arrêter une action | Note | 72 | 72–79 |
| Arm | Note | 80 | 80–87 |
| Monitor | Note | 88 | 88–95 |
| Solo | Note | 96 | 96–103 |
| Mute | Note | 104 | 104–111 |

### Contrôles de la tranche sélectionnée

Ces contrôles utilisent le canal utilisateur 14.

| Fonction | Message |
|---|---|
| Sends 1–3 | CC 56–58 |
| Sends 4–12 | CC 64–72 |
| Panoramique | CC 62 |
| Volume | CC 63 |
| Vue de tranche | Note 120 |
| Vue secondaire | Note 121 |
| Arrêter l’action | Note 122 |
| Lancer l’action | Note 123 |
| Arm | Note 124 |
| Monitor | Note 125 |
| Solo | Note 126 |
| Mute | Note 127 |

Les sélecteurs de scène et de tranche sont dupliqués sur les canaux utilisateur 13 et 14 sous forme de CC 59 et CC 60. Ils utilisent le mode `relative_smooth_two_compliment` dans le preset historique.

### Transport et master

Canal utilisateur 13 :

| Fonction | Message | Mode notable |
|---|---|---|
| Tempo grossier | CC 56 | Relatif lissé, complément à deux |
| Tempo fin | CC 57 | Relatif lissé, complément à deux |
| Quantification | CC 58 | Absolu |
| Sélection de scène | CC 59 | Relatif lissé |
| Sélection de tranche | CC 60 | Relatif lissé |
| Volume cue | CC 61 | Absolu |
| Panoramique master | CC 62 | Absolu |
| Volume master | CC 63 | Absolu |
| Nudge bas/haut | Notes 120/121 | Boutons |
| Arrêt/lancement de scène | Notes 122/123 | Boutons |
| Lecture/stop/enregistrement | Notes 124/125/126 | Boutons |
| Vue arrangement | Note 127 | Bouton |
| Affichage du tempo | Pitch bend | Feedback vers l’EC4 |

Le canal utilisateur 14 contient également un crossfader en CC 48 et l’affectation du crossfader en CC 61.

## Protocole SysEx EC4

### Préfixes

- Requête du setup et du groupe actifs : `F0 00 00 00 4E 20 10 F7`.
- Préfixe des réponses EC4 : `F0 00 00 00 4E 2C 1B`.
- Préfixe des messages de boutons : `F0 00 00 00 4E 2C 1B 4E`.

### Réponse setup/groupe

Format exact de 14 octets :

```text
F0 00 00 00 4E 2C 1B 4E 28 Ss 4E 24 Gg F7
```

La valeur interne du setup est `Ss & 0F`, et celle du groupe `Gg & 0F`.

Le bridge demande cet état à chaque connexion. Le setup et le groupe dédiés sont sélectionnés explicitement dans l’interface. Les commandes CC/Note, le feedback et les mises à jour de l’écran sont ignorés hors de cette zone cible. Depuis la version 0.3.0, un mapping MIDI appris peut être mémorisé pour chaque couple setup/groupe.

La configuration de repli initiale utilise le setup affiché 13 et le groupe 3, mais la sélection cible actuelle accepte n’importe quel couple setup/groupe valide.

### Shift, User et Shift+push

Après le préfixe des boutons :

- Shift : `26 11 4E 2E` ;
- User 1 à 4 : `26 12 4E 2E` à `26 15 4E 2E` ;
- Shift+push de l’encodeur `i` : `2A (10+i) 4E 2E`, avec `i` compris entre 0 et 15.

Un octet d’état suit l’identifiant : `11` signifie pressé ; une autre valeur signifie relâché. Le message se termine par `F7`.

Exemple : Shift+push sur l’encodeur 10, pressé :

```text
F0 00 00 00 4E 2C 1B 4E 2A 19 4E 2E 11 F7
```

### Écran principal — 16 cellules de 4 caractères

```text
F0 00 00 00 4E 2C 1B 4E 22 10 4A 20 10
[64 caractères encodés]
F7
```

Chaque caractère 8 bits `c` devient trois octets :

```text
4D (20 | c>>4) (10 | c&0F)
```

Le message complet fait 206 octets. Chacun des 16 libellés est tronqué ou complété à quatre caractères.

### Affichage temporaire total — 4 lignes de 20 caractères

```text
F0 00 00 00 4E 2C 1B 4E 22 13 4A (20|offset_hi) (10|offset_lo)
[texte encodé]
4E 22 14 F7
```

Un écran complet de 80 caractères fait 257 octets. Pour effacer et masquer l’overlay, le dernier bloc `4E 22 14` est remplacé par `4E 22 15` après l’envoi de 80 espaces.

La version 0.4.0 réutilise également cette zone plein écran sous forme de grille persistante 4 × 4. Chaque cellule contient le nom court d’un paramètre. Après l’overlay temporaire d’une valeur, la grille de la banque active est restaurée au lieu de revenir aux libellés mémorisés dans le groupe EC4.

La table de caractères prend en charge les caractères ASCII courants ainsi que `Ä`, `Ö`, `Ü`, `ä`, `ö`, `ü`, `à`, `²`, `³`, `§`, les crochets, la barre oblique inverse et les signes de comparaison. Un caractère non pris en charge est remplacé par le code `1F`.

## Ce que le bridge écoute réellement

Afin de limiter les conflits, le bridge n’intercepte que :

- les 16 CC de paramètres appris, ou le mapping de repli intégré ;
- les 16 Notes de push apprises, ou le mapping de repli intégré ;
- les deux Notes de banque ;
- les Notes de navigation plugin et chaîne ;
- les gestes Shift+push utiles ;
- les réponses SysEx de setup/groupe ;
- le feedback OSC nécessaire aux valeurs et à l’affichage.

Les contrôles supplémentaires de tranches, transport, actions et sends restent documentés mais ne sont pas redirigés vers LiveProfessor.
