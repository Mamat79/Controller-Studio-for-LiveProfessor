<p align="center">
  <img src="src/silemio_control_hub/assets/controller-studio.png" alt="Controller Studio for LiveProfessor" width="132">
</p>

<h1 align="center">Controller Studio for LiveProfessor</h1>

<p align="center">
  <strong>SiLeMI/O — By Mamat</strong><br>
  Contrôleurs MIDI, Plugin Studio et AutoMap réunis dans une seule application Windows.
</p>

<p align="center">
  <a href="https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/tag/v2026.4"><img alt="Version V.2026.4" src="https://img.shields.io/badge/version-V.2026.4-0b9fc6"></a>
  <img alt="Windows 10 et 11 x64" src="https://img.shields.io/badge/Windows-10%20%7C%2011%20x64-1674d1">
  <img alt="Français et anglais" src="https://img.shields.io/badge/interface-FR%20%7C%20EN-445064">
</p>

## Dernière version (accès rapide)

**Version stable : [Controller Studio V.2026.4](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/tag/v2026.4)**<br>
Téléchargement direct :

- [Installer Controller Studio pour Windows x64 (.exe)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor-Setup-v2026.4.exe)
- [Version portable Windows x64 (.exe)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor.exe)
- [Notice complète en français (.pdf)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor-Notice-FR.pdf)
- [Full English manual (.pdf)](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/Controller-Studio-for-LiveProfessor-Manual-EN.pdf)
- [Sommes de contrôle SHA-256](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor/releases/download/v2026.4/SHA256SUMS.txt)

[Lire cette présentation en anglais](README_EN.md)

> **Version publique V.2026.4 pour Windows.** Controller Studio travaille sur une copie AutoMap et conserve le projet `.rack2` source intact.

## À quoi sert Controller Studio ?

Controller Studio transforme un contrôleur MIDI en surface de contrôle organisée pour les plug-ins de LiveProfessor. Dans la même application, vous pouvez choisir ou créer un contrôleur, produire son fichier LiveProfessor, analyser les plug-ins d’un projet et fabriquer une copie AutoMap prête à tester.

| Contrôle Live | Banque de contrôleurs | Plugin Studio | AutoMap |
|---|---|---|---|
| Pilote EC4 temps réel, banques, push, Shift, labels, valeurs et reconnexion | Profils prêts à exporter et éditeur de contrôleur | Vrais noms lus dans les plug-ins installés, récupération globale, priorités et cases individuelles | Choix des plug-ins et instances, UniBank ou FullBank, copie `.rack2` validée |

L’interface existe en français et en anglais, se réduit dans la zone de notification et place le journal temps réel dans une fenêtre séparée.

## Utilisation en trois étapes

1. Dans **Banque de contrôleurs**, choisissez votre matériel ou créez son profil, puis exportez le fichier `.ctrl2`.
2. Ajoutez ce contrôleur dans LiveProfessor et analysez votre projet `.rack2` avec **Plugin Studio**.
3. Cliquez sur le bouton bleu **AutoMap**, choisissez les plug-ins et paramètres utiles, puis ouvrez la nouvelle copie produite.

Controller Studio relit la copie générée avant de la proposer. Les affectations manuelles existantes restent prioritaires.

## Plugin Studio

Le fichier `.rack2` conserve l’ordre et les identifiants des paramètres, mais pas toujours leurs libellés humains. Plugin Studio retrouve ces informations directement dans les plug-ins VST3 installés, chacun dans un processus isolé. Le résultat n’est accepté que si son nombre de paramètres correspond exactement au projet LiveProfessor.

Après l’analyse du projet, **Récupérer tous les vrais noms** traite tous ses types de plug-ins en une seule opération, crée ou met à jour les profils locaux et sauvegarde automatiquement les versions précédentes.

Pour un plug-in donné :

1. ouvrez le profil du plug-in puis cliquez sur **Récupérer automatiquement les vrais noms** ;
2. utilisez **Tout cocher**, **Tout décocher** ou les cases individuelles ;
3. ajustez si nécessaire le libellé court, le type, le rôle ou la priorité, puis enregistrez le profil local.

Si un ancien format ou un plug-in particulier ne fournit pas directement un inventaire compatible, Controller Studio propose automatiquement le retour Companion/OSC de LiveProfessor comme seconde méthode.

La relation entre l’emplacement de la Controller Map et l’identifiant interne du paramètre est conservée afin d’éviter qu’un bon réglage reçoive le label d’un autre.

VST est une marque déposée de Steinberg Media Technologies GmbH. Les mentions tierces figurent dans [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Banque de contrôleurs intégrée

V.2026.4 fournit 33 profils déclaratifs prêts à exporter et permet d’en fabriquer d’autres directement dans l’application :

- Akai Professional LPD8 MK2, MIDImix, APC Mini MK2, MPK Mini MK3, MPK Mini IV et MPK Mini Plus ;
- Arturia MiniLab 3, KeyLab Essential MK3 et BeatStep ;
- Faderfox EC4, PC4, UC4 et PC12 ;
- Behringer X-Touch, X-Touch Compact, X-Touch Mini et X-Touch One ;
- Korg nanoKONTROL2 (mode CC, réglages d’usine des potentiomètres et faders) ;
- Novation Launch Control XL MK2/XL 3, Launchkey MK3/MK4 et Launchpad X/Mini MK3 ;
- PreSonus FaderPort V2, 8 et 16 ;
- Solid State Logic UF1 et UF8 ;
- DJ TechTools MIDI Fighter Twister ;
- contrôleur MIDI générique à 16 commandes.

Les modes matériels et les sources constructeur utilisés sont regroupés dans [la documentation des profils](docs/CONTROLLER_PROFILE_SOURCES.md). La banque peut être mise à jour depuis l’application puis reste disponible hors ligne.

## Créer et partager un contrôleur

Cliquez sur **Créer un contrôleur…** pour partir d’un modèle de huit encodeurs, puis ajoutez, supprimez ou réordonnez encodeurs absolus ou relatifs, faders et boutons. Chaque commande accepte CC, Note, NRPN ou Pitch Bend, son canal et son numéro. **Apprendre le mouvement** et **Apprendre l’appui** capturent directement les messages reçus sur l’entrée MIDI choisie. Vous pouvez aussi **Modifier / dupliquer…** un modèle existant ou **Importer un profil…**.

**Enregistrer dans ma banque** valide le profil et le rend disponible hors ligne. **Enregistrer + créer .ctrl2** produit aussitôt le fichier LiveProfessor. Le remplacement d’un profil personnel conserve une sauvegarde de la version précédente. La page Live donne aussi accès à **Configurer / apprentissage MIDI…** pour le contrôleur actif ; le setup/groupe visible avec l’EC4 reste une fonction spécifique à ce matériel.

La fenêtre **Réglages** de la page Live retrouve les paramètres avancés d’EC4 Bridge : cadence de l’Overlay, durée d’affichage, rafraîchissement Companion et des labels, délai de confirmation LiveProfessor et affichage persistant. Ces temporisations sont disponibles pour tous les contrôleurs compatibles ; les outils setup/groupe et SysEx restent affichés uniquement pour l’EC4.

Pour proposer un contrôleur à la bibliothèque commune :

1. créez ou sélectionnez le profil dans **Banque de contrôleurs** ;
2. cliquez sur **Proposer à la bibliothèque…** ;
3. Controller Studio valide le profil et place automatiquement tout son contenu dans le formulaire ;
4. GitHub s’ouvre pour identifier l’auteur et demander la confirmation finale ;
5. ajoutez si possible la documentation constructeur ou vos résultats d’essai puis envoyez la proposition.

Cette dernière confirmation reste volontairement chez GitHub : aucun mot de passe ni jeton d’accès n’est demandé ou conservé par Controller Studio.

La bibliothèque publique fait partie de ce dépôt dans [`library/`](library/). Elle contient uniquement des profils JSON déclaratifs, jamais de code téléchargé et exécuté.

## Fonctions principales

- création, import, export et validation de profils de contrôleurs ;
- génération de contrôleurs LiveProfessor Companion/OSC `.ctrl2` ;
- moteur EC4 complet hérité d’EC4 Bridge ;
- choix mémorisé du contrôleur et reconnexion MIDI/OSC ;
- labels et valeurs sur l’afficheur, banques, push et raccourcis ;
- analyse en lecture seule des plug-ins et Controller Maps ;
- sélection de tous les plug-ins, d’une instance ou d’un ensemble précis ;
- sélection et priorité de chaque paramètre dans Plugin Studio ;
- AutoMap UniBank et FullBank dans une nouvelle copie ;
- conservation des mappings manuels et apprentissages existants ;
- mise à jour vérifiée du logiciel et de la bibliothèque ;
- interface FR/EN, réduction dans la zone de notification et journal séparé ;
- notice PDF intégrée et soutien PayPal facultatif.

## Documentation

- [Notice complète en français](src/silemio_control_hub/manuals/Controller-Studio-for-LiveProfessor-Notice-FR.pdf)
- [Full English manual](src/silemio_control_hub/manuals/Controller-Studio-for-LiveProfessor-Manual-EN.pdf)
- [README in English](README_EN.md)
- [Sources des profils de contrôleurs](docs/CONTROLLER_PROFILE_SOURCES.md)
- [Historique des versions](CHANGELOG.md)

La notice correspondant à la langue de l’interface s’ouvre aussi depuis **Aide > Ouvrir la notice PDF**.

## Installation et mises à jour

L’installateur place Controller Studio dans le profil Windows de l’utilisateur et crée les raccourcis du Bureau et du menu Démarrer. Le logiciel se désinstalle ensuite depuis les applications Windows.

Le menu **Aide > Rechercher les mises à jour** consulte la dernière Release de ce dépôt, vérifie le téléchargement puis lance l’installateur. La bibliothèque de contrôleurs se met à jour séparément depuis le menu **Bibliothèque**.

## Développement et vérification

```powershell
python -m pip install -e .
python -m pytest -q
python -m silemio_control_hub profiles
python -m silemio_control_hub validate-profile "chemin\profil.json"
python -m silemio_control_hub export-liveprofessor-controller faderfox.ec4 ".\Faderfox-EC4.ctrl2"
python -m silemio_control_hub library-update
```

## Soutenir le projet

Controller Studio est développé et maintenu indépendamment. Toutes ses fonctions restent disponibles gratuitement.

- [Soutenir SiLeMI/O via PayPal](https://www.paypal.com/paypalme/MamatLeroy)
- le même lien et son QR code sont disponibles dans le menu **Aide**.

## Remerciements

Merci aux utilisateurs qui testent leurs contrôleurs, documentent les plans MIDI et enrichissent la bibliothèque publique.

LiveProfessor, Faderfox, Behringer, Novation, DJ TechTools et les autres noms cités restent les marques de leurs propriétaires respectifs. Controller Studio est un outil indépendant et n’est affilié à aucun de ces éditeurs ou fabricants.

---

**SiLeMI/O**<br>
**By Mamat**<br>
`-------[]--`
