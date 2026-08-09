# Profils de travail

Ce dossier est réservé aux profils en cours de conception et de revue.

Les profils intégrés à l'application sont stockés dans `src/silemio_control_hub/controller_profiles`. Les profils installés par l'utilisateur sont placés dans `%LOCALAPPDATA%\SiLeMIO Controller Studio\controller_profiles`. L'ancien dossier `SiLeMIO Control Hub` reste une source de migration en lecture seule.

Le schéma de référence est `docs/controller-profile-schema-v1.json`. Les profils sont strictement déclaratifs : les champs inconnus et les capacités inconnues sont refusés.

Valider un fichier avant son installation :

```powershell
python -m silemio_control_hub validate-profile ".\controller_profiles\mon-controleur.json"
python -m silemio_control_hub install-profile ".\controller_profiles\mon-controleur.json"
```

Générer ensuite le contrôleur Companion importable dans LiveProfessor :

```powershell
python -m silemio_control_hub export-liveprofessor-controller `
  mon.profil `
  ".\Mon-Controleur.ctrl2"
```

La conception de la bibliothèque communautaire et de son mécanisme de contribution est décrite dans `docs/LIBRARY_GITHUB_DESIGN.md`.
