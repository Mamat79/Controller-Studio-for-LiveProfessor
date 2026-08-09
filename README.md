# Controller Studio for LiveProfessor

**Version publique V.2026**

**SiLeMI/O** est la marque et **Controller Studio** le produit. La mention **for LiveProfessor** reste affichée tant que LiveProfessor est le seul hôte intégralement pris en charge.

## Télécharger / Download

### [Télécharger l'installateur Windows V.2026](https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/latest/download/Controller-Studio-for-LiveProfessor-Setup-v2026.0.exe)

**Windows 11/10 x64 — installateur bilingue français/anglais.** Les anciennes releases EC4 LiveProfessor Bridge restent disponibles dans l'historique du dépôt pour revenir à la version précédente.

**English:** download the same bilingual Windows installer above. Controller Studio replaces EC4 Bridge while preserving its validated EC4/LiveProfessor behavior and adding controller and plug-in profile libraries.

Controller Studio est un logiciel SiLeMI/O indépendant d’EC4 LiveProfessor Bridge. Il réunit une banque de contrôleurs, l’export LiveProfessor, Plugin Studio, l’AutoMap et le contrôle en direct lorsqu’un pilote matériel compatible est disponible. Le paquet historique reste uniquement une référence de migration non distribuée.

## État actuel

- noyau de profils de contrôleurs ;
- registre local de profils intégrés et utilisateur ;
- profil Faderfox EC4 ;
- profil MIDI générique à 16 encodeurs ;
- moteur temps réel EC4/LiveProfessor avec reconnexion automatique, message de connexion, setup/groupe, 16 rotatifs et push, Shift, banques, affichage et retours Companion ;
- import non destructif de la configuration EC4 Bridge et apprentissage guidé des 16 rotatifs + push ;
- événements normalisés de rotation, pression, toucher, modificateur et retour ;
- banques, pages et modificateurs indépendants du matériel ;
- premier moteur d'affectation typé, sans doublons et respectant les mappings manuels ;
- simulateur de contrôleur sans matériel ;
- export d'un contrôleur Companion `.ctrl2` neutre depuis un profil ;
- adaptateur LiveProfessor, lecteur JUCE et AutoMap appartenant au cœur SiLeMI/O ;
- assistant AutoMap visible depuis l'onglet Live, la banque et le menu Outils, avec UniBank/FullBank, sélection de toutes les instances ou cases à cocher, et réutilisation sûre du contrôleur Companion/OSC déjà présent ;
- conservation de l'UID et du nom du contrôleur LiveProfessor sélectionné dans le `.ctrl2`, sans second contrôleur concurrent ;
- notice PDF française ou anglaise selon la langue active, soutien PayPal facultatif avec QR code et vérificateur de mises à jour signé par SHA-256 ;
- frontière testée interdisant au paquet produit d'importer le bridge historique ;
- tests de régression historiques exécutés contre le moteur Controller Studio, hors de la distribution produit ;
- identité de plug-in déterministe et résolution locale `User > Suggested > Raw`.
- Plugin Studio bilingue : analyse non bloquante d’un `.rack2`, regroupement des instances, édition versionnée des noms/libellés/types/rôles/priorités et sauvegarde locale avec retour arrière ;
- prise en compte immédiate des priorités du Plugin Studio dans les emplacements AutoMap encore libres, sans jamais déplacer une affectation manuelle.

EC4 Bridge reste installé comme solution de repli jusqu’à la réussite du scénario matériel complet et la confirmation explicite de l’utilisateur. Les deux moteurs ne doivent pas ouvrir simultanément les mêmes ports MIDI/OSC.

## Interface Windows

L’onglet `Live` affiche le contrôleur actif, les actions essentielles, l’état et le dernier événement. Les réglages MIDI/OSC et les outils propres au pilote sont regroupés dans `Réglages`; le journal complet s’ouvre dans une fenêtre séparée. Le bouton bleu `AutoMap` analyse le `.rack2`, propose le contrôleur déjà présent, le mode de banques, puis tous les plug-ins ou les seules instances cochées. Il produit toujours une nouvelle copie `.rack2` et un `.ctrl2` correspondant.

L’onglet `Plug-ins` est un Plugin Studio complet. Il analyse un projet en lecture seule, regroupe les instances identiques, indique le niveau de reconnaissance et permet de créer ou corriger un profil local. La priorité 100 place une fonction avant la priorité 0 dans les emplacements AutoMap libres ; les mappings appris ou manuels conservent toujours la priorité absolue. Le bouton `Utiliser dans AutoMap` transmet directement le projet analysé à l’assistant.

Le menu `Aide / Help` ouvre la notice localisée, vérifie les mises à jour de Controller Studio, affiche le soutien PayPal facultatif et l'à-propos. Une mise à jour n'est lancée qu'après confirmation, téléchargement complet et validation SHA-256 d'un installateur portant strictement le nom du produit ; un ancien installateur EC4 Bridge est refusé.

Elle est disponible en français et en anglais depuis `Options > Langue / Language`. La fermeture et la réduction peuvent envoyer l’application dans la zone de notification ; son menu permet aussi de démarrer, arrêter ou redémarrer le moteur, afficher le journal et vérifier la bibliothèque.

L'identité visuelle `S/O` est partagée par l'EXE, la fenêtre, la zone de notification, les raccourcis Bureau/menu Démarrer et l'entrée des applications Windows. Le fichier `.ico` contient les résolutions Windows de 16 à 256 px.

```powershell
.\packaging\windows\build.ps1
.\packaging\windows\build_setup.ps1
.\packaging\windows\install.ps1
```

L’installation utilisateur cible `%LOCALAPPDATA%\Programs\Controller Studio for LiveProfessor`, ajoute le raccourci `Controller Studio for LiveProfessor` et enregistre une désinstallation isolée. L'installateur Inno Setup bilingue porte le nom reconnu par le vérificateur de mises à jour. Il ne remplace ni l’ancienne préversion Control Hub, ni EC4 Bridge.

La construction publique exécute la suite de tests avant de produire les artefacts Windows.

## Commandes de développement

```powershell
python -m pip install -e .
python -m silemio_control_hub profiles
python -m silemio_control_hub validate-profile "chemin\profil.json"
python -m silemio_control_hub profile-dir
python -m silemio_control_hub install-profile "chemin\profil.json"
python -m silemio_control_hub simulate generic.midi.16 rotate control_01 0.5
python -m silemio_control_hub export-liveprofessor-controller faderfox.ec4 ".\Faderfox-EC4.ctrl2"
python -m silemio_control_hub prepare-liveprofessor generic.midi.16 ".\source.rack2" ".\source-automap.rack2" ".\Generic-MIDI-16.ctrl2"
python -m silemio_control_hub inspect-liveprofessor-plugins ".\source.rack2"
python -m silemio_control_hub validate-library ".\ma-bibliotheque"
python -m silemio_control_hub library-update
python -m silemio_control_hub library-update --apply
python -m silemio_control_hub library-backups
python -m silemio_control_hub library-rollback "nom-de-sauvegarde" --apply
python -m pytest
```

`library-update` ne modifie rien sans `--apply`. La bibliothèque publique se consulte sans jeton ; `GH_TOKEN` ou `GITHUB_TOKEN` reste facultatif pour augmenter la limite d’appels GitHub ou utiliser un fork privé. Le cache local continue à fonctionner hors ligne et alimente automatiquement `profiles` et `plugin-profiles`. `SILEMIO_LIBRARY_CACHE` permet de choisir un cache isolé pour les tests. Un downgrade, une suppression ou un rollback exigent chacun une autorisation explicite.

Pour comparer temporairement le comportement de l'interface EC4 historique depuis les sources de développement :

```powershell
python legacy_launcher.py
```

Cette commande ne fait pas partie du paquet distribuable `silemio-control-hub`.

## Principes

- LiveProfessor bénéficie de l'AutoMap complet.
- Les autres logiciels peuvent commencer par une compatibilité MIDI générique.
- Chaque intégration annonce ses capacités réelles.
- Les fichiers de projet source ne sont jamais modifiés par l'AutoMap.
- La réutilisation du contrôleur Companion/OSC existant évite deux listes de labels concurrentes sur les mêmes adresses `/Companion/RotaryN`.
- Les profils communautaires sont déclaratifs et ne contiennent aucun code exécutable.
- La reconnaissance automatique distingue identité certaine, profil partagé et suggestion calculée.

L'export `.ctrl2` actuel produit un contrôleur **Companion/OSC** destiné à fonctionner avec le Hub. Sa structure binaire est validée par relecture, mais l'import dans l'interface LiveProfessor doit encore faire l'objet d'un essai reproductible avant d'être déclaré compatible avec tous les contrôleurs.

La [bibliothèque GitHub publique](https://github.com/Mamat79/SiLeMIO-Control-Library) est facultative : le catalogue intégré, le cache local et les profils déjà installés continuent à fonctionner hors ligne. L'approche de Dialr inspire l'expérience « déjà reconnu et déjà mappé », mais pas son implémentation propriétaire.
