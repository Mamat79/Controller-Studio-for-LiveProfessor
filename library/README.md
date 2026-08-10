# Controller Studio public library

[Français](#français) · [English](#english)

## Français

Cette bibliothèque déclarative et versionnée alimente directement [Controller Studio for LiveProfessor](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor). Elle se trouve dans le même dépôt que le logiciel afin de rendre les mises à jour, la revue et les contributions faciles à retrouver.

```text
library/manifest-v1.json
library/schemas/
library/controllers/<fabricant>/<modèle>/<version>/profile.json
library/plugin-profiles/<fabricant>/<plug-in>/<version>/profile.json
```

- `builtin` : profil livré avec Controller Studio ;
- `verified` : profil testé selon une procédure reproductible ;
- `community` : profil valide construit depuis une documentation ou une contribution communautaire.

Les profils de plug-ins partagés utilisent la couche `suggested`. La couche `user` reste locale et prioritaire dans Controller Studio.

### Proposer un contrôleur

Dans l’application, sélectionnez le profil dans `Banque de contrôleurs`, puis cliquez sur `Proposer à la bibliothèque…`. Controller Studio valide le JSON, le copie dans le presse-papiers et ouvre automatiquement le formulaire GitHub à compléter.

Une contribution peut aussi être ajoutée par pull request : créez un nouveau dossier de version, régénérez le manifeste, lancez les trois validateurs ci-dessous et décrivez la documentation ainsi que les essais matériels utilisés.

```powershell
python library/scripts/update_manifest.py
python library/scripts/validate_library.py
python library/scripts/validate_schemas.py
```

L’application ne télécharge que le manifeste et les profils JSON référencés. Elle vérifie leurs empreintes SHA-256 et n’exécute aucun code provenant de la bibliothèque.

## English

This versioned declarative library directly feeds [Controller Studio for LiveProfessor](https://github.com/Mamat79/Controller-Studio-for-LiveProfessor). Keeping it in the same repository as the application makes updates, reviews, and contributions easy to find.

- `builtin`: bundled with Controller Studio;
- `verified`: tested through a reproducible procedure;
- `community`: valid profile built from documentation or a community contribution.

Shared plug-in profiles use the `suggested` layer. The local `user` layer remains authoritative inside Controller Studio.

### Submit a controller

In the application, select the profile in `Controller bank`, then click `Submit to the library…`. Controller Studio validates the JSON, copies it to the clipboard, and opens the correct GitHub form.

Contributors may also open a pull request: add a new version directory, regenerate the manifest, run the three validators shown above, and document the source material and hardware tests.

The application only downloads the manifest and referenced JSON profiles. It verifies SHA-256 hashes and never executes code from the library.
