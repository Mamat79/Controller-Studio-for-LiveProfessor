# Reconnaissance et profils de plug-ins

## Parcours V.2026

L’onglet **Plug-ins / Plugin Studio** propose le parcours principal :

1. choisir un projet `.rack2` en lecture seule ;
2. lancer l’analyse non bloquante ;
3. sélectionner un type de plug-in regroupant toutes ses instances ;
4. créer ou modifier le profil local de ses paramètres ;
5. enregistrer une nouvelle version avec sauvegarde automatique de la précédente ;
6. transmettre le projet à AutoMap.

Le parcours en ligne de commande reste disponible :

```powershell
python -m silemio_control_hub inspect-liveprofessor-plugins ".\Projet.rack2"
```

La commande inspecte les plug-ins d'un projet LiveProfessor sans exiger qu'un contrôleur soit déjà configuré. Pour chaque instance, elle renvoie le nom observé, l'UID d'instance, le format, l'identifiant technique, le nombre de paramètres et leur empreinte SHA-256.

## FAIT_VERIFIE

- L'identité de correspondance combine le format, l'identifiant stable fourni par l'hôte et une empreinte ordonnée des identifiants de paramètres.
- Le nom affiché du plug-in et les libellés localisés ne participent pas à l'empreinte.
- Une version déclarée dans un profil doit correspondre exactement à la version observée. Un profil sans contrainte de version peut rester compatible tant que l'identité et l'empreinte correspondent.
- La priorité de résolution est fixe : `User`, puis `Suggested`, puis `Raw`.
- `Raw` est généré localement à partir de l'observation et ne peut pas être chargé depuis un fichier téléchargé.
- Un profil `User` doit avoir le statut `local`. Un profil communautaire ou vérifié est nécessairement `Suggested`.
- Un profil peut préciser les noms, libellés courts, unités, rôles, types et niveaux d'importance d'une partie des paramètres. Les paramètres absents restent en `Raw`.
- Un champ inconnu, un paramètre dupliqué ou une référence à un paramètre absent est refusé.
- L’importance est utilisée par AutoMap pour ordonner uniquement les paramètres encore libres. Les affectations manuelles, apprises et préservées restent prioritaires.
- L’enregistrement local est atomique ; un remplacement explicite crée une sauvegarde hors du dossier actif des profils.

Le contrat JSON est défini dans `plugin-profile-schema-v1.json`.

## LIMITES_OBSERVEES

Un projet `.rack2` fournit actuellement à SiLeMI/O l'identifiant de type du plug-in et des paramètres indexés, mais pas leurs noms stables. Dans cette source, l'empreinte distingue donc surtout la structure indexée et le nombre de paramètres. Elle ne peut pas détecter à elle seule une réorganisation interne qui conserverait exactement le même nombre de paramètres.

L'UID affiché par la commande identifie une instance dans le projet. Il ne doit pas servir d'identité universelle du produit.

La détection du plug-in sélectionné en temps réel par LiveProfessor et le scan direct des installations VST3 ne sont pas encore implémentés.

## PROCHAINE ETAPE

Faire évoluer les profils communautaires depuis les retours réels, puis utiliser les types et rôles pour proposer des boutons/toggles plus intelligents. Une contribution GitHub reste une action distincte et explicite : aucun profil local n’est publié automatiquement.
