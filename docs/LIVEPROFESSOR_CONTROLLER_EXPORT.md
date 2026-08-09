# Export d'un contrôleur LiveProfessor

## Parcours visé

1. choisir un profil de contrôleur intégré, vérifié ou communautaire ;
2. créer un profil avec Controller Studio si le contrôleur n'existe pas ;
3. générer un fichier `.ctrl2` correspondant ;
4. importer ce fichier dans LiveProfessor ;
5. utiliser le Hub pour convertir le protocole matériel vers Companion/OSC ;
6. lancer l'AutoMap sur une copie explicite du projet LiveProfessor.

## Commande actuelle

```powershell
python -m silemio_control_hub export-liveprofessor-controller `
  faderfox.ec4 `
  ".\Faderfox-EC4.ctrl2"
```

Les ports peuvent être choisis explicitement :

```powershell
python -m silemio_control_hub export-liveprofessor-controller `
  generic.midi.16 `
  ".\Mon-Controleur.ctrl2" `
  --name "Mon contrôleur" `
  --osc-in-port 8010 `
  --osc-out-port 8011
```

Le remplacement d'un fichier existant est refusé par défaut. L'option `--replace` constitue une autorisation explicite.

## Préparation complète avec AutoMap

La commande suivante génère à la fois le contrôleur et une nouvelle copie `.rack2` automappée :

```powershell
python -m silemio_control_hub prepare-liveprofessor `
  generic.midi.16 `
  ".\Projet-source.rack2" `
  ".\Projet-source-automap.rack2" `
  ".\Generic-MIDI-16.ctrl2"
```

La commande refuse une destination existante. `--replace-controller` et `--replace-project` sont deux autorisations distinctes. Lorsqu'un projet de destination est remplacé, le moteur AutoMap historique crée sa sauvegarde horodatée.

## FAIT_VERIFIE

- Les `.ctrl2` étudiés sont des flux binaires JUCE ValueTree.
- Le modèle intégré est une copie neutre du contrôleur Companion existant : 99 rotatifs, 16 boutons et aucun preset de plugin.
- L'export adapte le nom, un identifiant déterministe, les ports et le nombre de contrôles au profil sélectionné.
- Le fichier est écrit atomiquement puis relu par le parseur ValueTree.
- Le modèle intégré n'est jamais modifié et aucun projet `.rack2` n'est ouvert par cette commande.
- Le parcours combiné recalcule le SHA-256 du projet source après l'AutoMap et refuse de valider le résultat si la source a changé.
- Un test reproductible construit un projet LiveProfessor synthétique sans contrôleur, génère le `.ctrl2`, embarque ce contrôleur dans la copie et vérifie les affectations créées.

## LIMITE_OBSERVEE

L'export v1 génère un contrôleur **Companion/OSC**, pas un contrôleur MIDI direct LiveProfessor. Le Hub doit donc rester actif entre le matériel et LiveProfessor. Cette stratégie permet à tous les profils matériels d'utiliser un connecteur LiveProfessor commun et maintient les détails MIDI/SysEx hors de l'adaptateur hôte.

La structure produite est équivalente au modèle déjà utilisé par l'AutoMap historique, mais un import dans l'interface LiveProfessor doit encore être testé de bout en bout avant de déclarer cette étape validée sur la version installée.

Si l'AutoMap échoue après la génération du `.ctrl2`, ce fichier contrôleur est conservé comme livrable vérifiable ; aucune suppression automatique n'est effectuée.
