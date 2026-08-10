# Historique des versions

## V.2026 (2026.3) — 2026-08-10

- Lit directement les vrais noms, unités et types des paramètres exposés par les plug-ins VST3 installés, dans un processus isolé par plug-in.
- Ajoute **Récupérer tous les vrais noms** pour traiter en une fois tous les types présents dans le projet analysé et enregistrer leurs profils locaux avec sauvegarde des versions précédentes.
- Refuse automatiquement tout inventaire dont le nombre de paramètres diffère du projet LiveProfessor afin d'empêcher les décalages de labels.
- Conserve l'interception Companion/OSC comme solution de secours pour les formats anciens et les plug-ins qui n'exposent pas directement un inventaire compatible.
- Intercepte en continu les vrais noms envoyés par LiveProfessor au contrôleur actif au lieu de les effacer au début de la capture.
- Réutilise instantanément les libellés déjà visibles sur le contrôleur et conserve leur ordre exact dans la Controller Map enregistrée.
- Attend et relance la demande jusqu’à 30 secondes lorsque LiveProfessor tarde à envoyer son inventaire, sans bloquer l’interface.
- Clarifie en français et en anglais le changement temporaire de plug-in qui déclenche l’émission des noms par LiveProfessor.

## V.2026 (2026.2) — 2026-08-10

- Réunit le logiciel et sa bibliothèque publique versionnée dans le même dépôt GitHub.
- Étend la banque à dix profils documentés, dont X-Touch Compact, X-Touch Mini, X-Touch One, Launch Control XL 3, PC4, UC4, PC12 et MIDI Fighter Twister.
- Ajoute un parcours de contribution depuis l’application vers un formulaire GitHub bilingue, sans stocker de jeton.
- Ajoute des cases par paramètre dans Plugin Studio, avec Tout cocher, Tout décocher et prise en compte immédiate dans AutoMap.
- Récupère les vrais noms de paramètres directement depuis LiveProfessor Companion, même lorsque le moteur EC4 est arrêté, en respectant l’ordre enregistré de chaque Controller Map.
- Bascule les mises à jour du logiciel et de la bibliothèque vers le dépôt public Controller Studio.
- Publie un README français/anglais inspiré de DCE, avec accès rapide, fonctions, workflow, documentation, soutien et liens directs vers la release.

## V.2026 (2026.0) — 2026-08-10

- Renomme le produit, l'EXE, l'installateur, les raccourcis et le dossier Windows en `Controller Studio for LiveProfessor` ; SiLeMI/O reste la marque discrète.
- Simplifie la page Live sur le modèle éprouvé d'EC4 Bridge et masque automatiquement les commandes propres à un pilote lorsqu'elles ne concernent pas le contrôleur sélectionné.
- Déplace le journal temps réel et les connexions MIDI/OSC dans des fenêtres séparées afin de garder la page principale immédiatement lisible.
- Remplace les notices orientées matériel par deux notices génériques de 9 pages en français et en anglais.
- Corrige le changement de langue après fermeture ou reconstruction des fenêtres secondaires.
- Transforme l’onglet Plug-ins en Plugin Studio : analyse non bloquante d’un `.rack2`, regroupement des instances par type et reconnaissance exacte `User > Suggested > Raw`.
- Ajoute l’éditeur bilingue des noms, libellés, unités, types, rôles et priorités des paramètres.
- Enregistre les profils locaux de façon atomique, incrémente leur version et sauvegarde le fichier précédent avant remplacement.
- Relie les priorités du Plugin Studio à AutoMap tout en laissant les mappings appris, manuels et préservés strictement prioritaires.
- Ajoute le passage direct du Plugin Studio vers l’assistant AutoMap et l’ouverture du dossier de profils.
- Rend l’interface plus lisible et plus fluide avec analyse en arrière-plan, hiérarchie visuelle renforcée et tableaux aérés.
- Prépare le remplacement public d’EC4 Bridge tout en conservant son installateur et son historique comme retour arrière.

## 0.2.0 — 2026-08-09

- Corrige les labels AutoMap en réutilisant le contrôleur Companion/OSC existant au lieu d'en ajouter un second sur les mêmes adresses.
- Conserve l'UID et le nom du contrôleur choisi dans le fichier `.ctrl2` correspondant.
- Ajoute les modes UniBank et FullBank ; FullBank étend le contrôleur sélectionné jusqu'à 99 rotatifs sans duplication.
- Ajoute le choix de tous les plug-ins ou d'instances précises par cases à cocher.
- Rend AutoMap directement accessible depuis l'onglet Live, la banque de contrôleurs et le menu Outils.
- Ajoute les notices PDF française et anglaise, le soutien PayPal facultatif avec QR code et le menu Aide bilingue.
- Ajoute la recherche, le téléchargement vérifié par SHA-256 et le lancement des futures mises à jour Controller Studio.
- Ajoute un installateur Windows bilingue par utilisateur et conserve EC4 Bridge comme solution de secours.
