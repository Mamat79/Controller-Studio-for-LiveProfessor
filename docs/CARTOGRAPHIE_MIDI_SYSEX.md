# Cartographie MIDI et SysEx du script Faderfox Universal 2

Les nombres de canaux affichés ci-dessous sont ceux vus par l'utilisateur. Le code Python emploie une numérotation à partir de zéro : canal 13 = `12`, canal 14 = `13`.

## Contrôle des paramètres — utilisé par le prototype

| Fonction | Canal utilisateur | Message | Plage | Mode dans Ableton |
|---|---:|---|---:|---|
| Paramètres 1 à 8 | 13 | CC | 48–55 | Absolu, retour de valeur, takeover désactivé |
| Paramètres 9 à 16 | 14 | CC | 73–80 | Absolu, retour de valeur, takeover désactivé |
| Afficher le détail des paramètres 1 à 16 | 13 | Notes | 40–55 | Appui momentané |
| Banque précédente | 14 | Note | 112 | Appui momentané |
| Banque suivante | 14 | Note | 113 | Appui momentané |

Cette table est le mapping de repli hérité d'Ableton. En version 0.3.0, l'interface peut apprendre les 16 CC rotatifs et les 16 Notes de push de n'importe quel setup/groupe. Le mode des rotatifs reste absolu. Un retour OSC reçu de LiveProfessor est converti en CC 0–127 et renvoyé à l'encodeur appris correspondant. Cette synchronisation est la stratégie anti-saut ; une garde de 100 ms bloque un éventuel écho identique.

## Navigation device/plugin et piste/chaîne — utilisée par le prototype

| Fonction Ableton | Adaptation LiveProfessor | Canal | Note |
|---|---|---:|---:|
| Afficher/masquer la vue rack | Afficher/masquer le plugin sélectionné | 13 | 112 |
| Device actif/inactif | Activer/désactiver le traitement du plugin sélectionné | 13 | 113 |
| Device précédent | Plugin précédent | 13 | 114 |
| Device suivant | Plugin suivant | 13 | 115 |
| Afficher/masquer le device | Afficher/masquer le plugin sélectionné | 13 | 116 |
| Verrouiller le device | Non exposé par la commande OSC publique étudiée | 13 | 117 |
| Piste précédente | Chaîne précédente | 13 | 118 |
| Piste suivante | Chaîne suivante | 13 | 119 |

## Gestes Shift + push en SysEx

Le script crée 16 boutons SysEx correspondant aux poussoirs d'encodeurs utilisés avec Shift.

| Index interne | Encodeur | Fonction Ableton | Adaptation du prototype |
|---:|---:|---|---|
| 0 | 1 | Banque précédente | Banque précédente |
| 1 | 2 | Banque suivante | Banque suivante |
| 2 | 3 | ViewSet précédent | ViewSet précédent |
| 3 | 4 | ViewSet suivant | ViewSet suivant |
| 4 | 5 | Afficher/masquer le plugin sélectionné | Afficher/masquer le plugin |
| 5 | 6 | Chaîne précédente | Chaîne précédente |
| 6 | 7 | Plugin précédent | Plugin précédent |
| 7 | 8 | Plugin suivant | Plugin suivant |
| 8 | 9 | Traitement plugin actif/inactif | Activer/désactiver le traitement du plugin |
| 9 | 10 | Chaîne suivante | Chaîne suivante |
| 10 | 11 | Plugin précédent | Plugin précédent |
| 11 | 12 | Plugin suivant | Plugin suivant |
| 12 | 13 | Cue précédent | Cue précédent |
| 13 | 14 | Cue suivant | Cue suivant |
| 14 | 15 | Snapshot global précédent | Snapshot global précédent |
| 15 | 16 | Snapshot global suivant | Snapshot global suivant |

Le **push simple de l'encodeur 16** déclenche le Tap Tempo. Les push simples 1 à 15 gardent l'affichage du détail du paramètre. Les actions de banque, cue et snapshot ci-dessus exigent bien Shift+push.

## Contrôle de 16 pistes — cartographié dans Ableton, non transmis par le prototype

Les pistes 1–8 utilisent le canal 13 et les pistes 9–16 le canal 14. Pour la seconde moitié, les mêmes numéros 0–7 sont réutilisés sur l'autre canal.

| Fonction par piste | Type | Base pour piste 1/9 | Plage sur chaque canal |
|---|---|---:|---:|
| Sélection | Note | 56 | 56–63 |
| Volume | CC | 40 | 40–47 |
| Panoramique | CC | 32 | 32–39 |
| Send 1 | CC | 0 | 0–7 |
| Send 2 | CC | 8 | 8–15 |
| Send 3 | CC | 16 | 16–23 |
| Send 4 | CC | 24 | 24–31 |
| Lancer clip | Note | 64 | 64–71 |
| Arrêter piste/clip | Note | 72 | 72–79 |
| Arm | Note | 80 | 80–87 |
| Monitor | Note | 88 | 88–95 |
| Solo | Note | 96 | 96–103 |
| Mute | Note | 104 | 104–111 |

## Piste sélectionnée — cartographié dans Ableton, non transmis par le prototype

Tous ces contrôles sont sur le canal utilisateur 14.

| Fonction | Message |
|---|---|
| Sends 1 à 3 | CC 56–58 |
| Sends 4 à 12 | CC 64–72 |
| Panoramique | CC 62 |
| Volume | CC 63 |
| Vue piste | Note 120 |
| Vue clip | Note 121 |
| Arrêter clip | Note 122 |
| Lancer clip | Note 123 |
| Arm | Note 124 |
| Monitor | Note 125 |
| Solo | Note 126 |
| Mute | Note 127 |

Les sélecteurs de scène et de piste sont dupliqués sur les canaux 13 et 14 : CC 59 et CC 60, en mode `relative_smooth_two_compliment` dans Ableton.

## Transport et master — cartographié dans Ableton, non transmis par le prototype

Canal utilisateur 13 :

| Fonction | Message | Mode notable |
|---|---|---|
| Tempo grossier | CC 56 | Relatif lissé, complément à deux |
| Tempo fin | CC 57 | Relatif lissé, complément à deux |
| Quantification | CC 58 | Absolu |
| Sélection scène | CC 59 | Relatif lissé |
| Sélection piste | CC 60 | Relatif lissé |
| Volume cue | CC 61 | Absolu |
| Pan master | CC 62 | Absolu |
| Volume master | CC 63 | Absolu |
| Nudge bas / haut | Notes 120 / 121 | Boutons |
| Arrêt / lancement scène | Notes 122 / 123 | Boutons |
| Lecture / stop / enregistrement | Notes 124 / 125 / 126 | Boutons |
| Vue Arrangement | Note 127 | Bouton |
| Affichage du tempo | Pitch bend | Retour Ableton vers EC4 |

Canal utilisateur 14 : crossfader en CC 48 et affectation crossfader en CC 61.

## Protocole SysEx EC4

### Préfixes

- Requête du setup et groupe actifs : `F0 00 00 00 4E 20 10 F7`.
- Préfixe des réponses EC4 : `F0 00 00 00 4E 2C 1B`.
- Préfixe des boutons : `F0 00 00 00 4E 2C 1B 4E`.

### Réponse setup/groupe

Format exact de 14 octets :

```text
F0 00 00 00 4E 2C 1B 4E 28 Ss 4E 24 Gg F7
```

Le setup vaut `Ss & 0F` et le groupe `Gg & 0F`. Le script autorise l'affichage device dans les setups internes 12–15, soit 13–16 sur l'appareil, et les groupes internes 2–3, soit 3–4 affichés.

Le prototype demande cet état à chaque connexion. Le setup et le groupe dédiés se choisissent explicitement dans l'interface. Les CC/Notes, le feedback et l'écran sont ignorés hors de cette zone. La version 0.3.0 y ajoute un mapping MIDI appris par zone. Les valeurs 13/3 restent la configuration initiale proposée, issue de la zone device du script.

### Shift, User et Shift+push

Après le préfixe bouton :

- Shift : `26 11 4E 2E` ;
- User 1 à 4 : `26 12 4E 2E` à `26 15 4E 2E` ;
- Shift+push encodeur `i` : `2A (10+i) 4E 2E`, avec `i` de 0 à 15.

Un octet d'état suit l'identifiant : `11` signifie pressé ; une autre valeur signifie relâché ; le message se termine par `F7`.

Exemple, Shift+push sur l'encodeur 10 pressé :

```text
F0 00 00 00 4E 2C 1B 4E 2A 19 4E 2E 11 F7
```

### Écran principal, 16 cellules de 4 caractères

```text
F0 00 00 00 4E 2C 1B 4E 22 10 4A 20 10
[64 caractères encodés]
F7
```

Chaque caractère 8 bits `c` devient trois octets :

```text
4D (20 | c>>4) (10 | c&0F)
```

Le message complet fait 206 octets. Les 16 libellés sont tronqués ou complétés à quatre caractères.

### Affichage temporaire total, 4 lignes de 20 caractères

```text
F0 00 00 00 4E 2C 1B 4E 22 13 4A (20|offset_hi) (10|offset_lo)
[texte encodé]
4E 22 14 F7
```

Un écran complet de 80 caractères fait 257 octets. Pour effacer et masquer l'overlay, le dernier bloc `4E 22 14` est remplacé par `4E 22 15` après l'envoi de 80 espaces.

Depuis la version 0.4.0, cet écran total est également réutilisé sous forme de grille persistante 4 × 4. Chaque cellule contient le nom court d'un paramètre. Après l'overlay temporaire d'une valeur, la grille de la banque active est renvoyée au lieu de revenir aux libellés enregistrés dans le groupe EC4.

La table de caractères issue du script prend en charge les caractères ASCII usuels, `Ä`, `Ö`, `Ü`, `ä`, `ö`, `ü`, `à`, `²`, `³`, `§`, crochets, barre oblique inverse et signes de comparaison. Un caractère inconnu est remplacé par le code `1F`.

## Ce que le prototype écoute réellement

Pour minimiser les conflits, la version 0.3.0 n'intercepte que :

- les 16 CC de paramètres appris, ou le mapping Ableton de repli ;
- les 16 Notes de push apprises, ou le mapping Ableton de repli ;
- les deux Notes de banque ;
- les Notes de navigation device/chaîne ;
- les gestes Shift+push utiles ;
- les réponses SysEx de setup/groupe ;
- les retours OSC nécessaires aux valeurs et à l'affichage.

Les contrôles de mixage, transport, clips et sends restent documentés mais ne sont pas détournés vers LiveProfessor.
