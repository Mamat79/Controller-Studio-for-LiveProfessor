# Indépendance du produit et inspirations

## FAIT_VERIFIE — frontière avec EC4 LiveProfessor Bridge

- Le dépôt historique `FaderFox EC4` a été audité en lecture seule et est resté propre.
- L'audit initial a trouvé 39 fichiers suivis déjà repris à l'identique dans le dépôt SiLeMI/O, principalement le mode de compatibilité, ses tests et sa documentation technique.
- Le protocole EC4, le lecteur/écrivain JUCE ValueTree et le moteur AutoMap réutilisables appartiennent désormais à `silemio_control_hub`.
- Le paquet source `ec4lpbridge` ne contient plus que les composants historiques et des imports de compatibilité vers le nouveau cœur pour les trois briques extraites.
- `pyproject.toml` n'installe que `silemio_control_hub*` et n'expose aucun lanceur historique. `ec4lpbridge` sert uniquement de référence de migration et de régression dans le dépôt de développement.
- La CI construit le wheel et échoue si un chemin `ec4lpbridge/` apparaît dans l'archive distribuable.
- Aucun fichier Python de `src/silemio_control_hub` ne peut importer `ec4lpbridge`. Le test `test_independence_boundary.py` analyse l'AST de tout le paquet et échoue si cette règle est enfreinte.
- Les nouvelles maps générées portent la marque `SiLeMI/O AutoMap`. Les anciennes maps `EC4 AutoMap` restent reconnues afin de ne pas rendre les projets existants illisibles.

Les anciens installateurs, scripts de désinstallation, chaînes de packaging, README produit et configuration racine n'ont pas été importés dans le produit actif. Ils portent l'identité et les chemins de l'ancien logiciel et n'apportent rien au cœur universel.

## FAIT_VERIFIE — Producely Dialr

Les pages publiques de Producely décrivent :

- un scan des plug-ins VST3 ;
- un profil déjà disponible lors de l'ouverture du plug-in ;
- une distribution de profils par un service cloud partagé ;
- une distribution automatique de profils par le service cloud ;
- une disposition cohérente des paramètres destinée à développer la mémoire musculaire ;
- une expérience sans wrapper de plug-in et sans mapping manuel obligatoire.

Sources consultées le 9 août 2026 :

- <https://producely.com/>
- <https://producely.com/pages/why-we-built-dialr>
- <https://producely.com/pages/designed-for-muscle-memory>

La documentation publique consultée ne décrit pas assez précisément l'algorithme de reconnaissance, les données envoyées au cloud ni la manière dont la DAW signale le plug-in sélectionné. Ces points restent donc inconnus et ne doivent pas être présentés comme reproduits.

## PROPOSITION — architecture inspirée, mais indépendante

SiLeMI/O doit conserver trois niveaux séparés et visibles :

1. `Raw` : ordre technique des paramètres fourni par l'hôte, sans prétendre comprendre leur fonction.
2. `Suggested` : proposition déterministe issue de règles sémantiques et d'un profil communautaire compatible.
3. `User` : corrections validées localement par l'utilisateur, toujours prioritaires et exportables pour contribution.

Cette résolution locale est maintenant implémentée. Elle n'accepte un profil que si le format, l'identifiant stable et l'empreinte de paramètres correspondent exactement. La version du plug-in devient une contrainte supplémentaire lorsqu'elle est connue.

L'identité d'un plug-in doit combiner les identifiants exposés par l'hôte, son format, sa version et une empreinte de sa liste de paramètres. Une correspondance incertaine ne doit jamais écraser un profil utilisateur.

Le futur catalogue GitHub doit télécharger des profils déclaratifs signés ou vérifiés, les valider avant installation, conserver la dernière version saine et rester facultatif pour l'exécution hors ligne.

## PROCHAIN BANC DE TEST — Behringer X-Touch Compact

Le X-Touch Compact physiquement disponible sera le premier exemple matériel distinct de l'EC4. La validation suivra cet ordre :

1. inventorier les ports, le mode et le firmware observés ;
2. capturer sans effet de bord les messages des encodeurs, poussoirs et faders ;
3. vérifier les retours LED et motorisés séparément ;
4. construire un profil provisoire, puis le comparer aux captures ;
5. générer son `.ctrl2` ;
6. tester l'AutoMap uniquement sur une copie d'un projet LiveProfessor ;
7. publier le profil comme `verified` seulement après reproduction du test matériel.

## HYPOTHESE

Le X-Touch Compact devrait exercer davantage de capacités du modèle universel que l'EC4, notamment les faders et les retours matériels. Les messages exacts, les modes et les limites restent à mesurer sur l'appareil disponible avant toute conclusion.
