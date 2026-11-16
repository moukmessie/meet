---
name: meet-patch-maintainer
description: Maintenance du jeu de patchs multi-tenant de La Suite Meet (organisation sur le User, trusted limité à l'organisation, quota à la création, organisation dans le jeton LiveKit) et des montées de version amont. À utiliser pour écrire ou modifier un patch, évaluer une nouvelle version de Meet ou préparer la branche patched/vX.Y.Z suivante.
---

Tu maintiens le **jeu de patchs** de ce fork. L'amont sort 3 à 4 versions par mois :
les patchs doivent rester **petits, isolés (un commit par patch) et testés**.

## Les patchs

1. **Organisation de l'utilisateur** : `OIDCAuthenticationBackend.get_extra_claims` (`src/backend/core/authentication/backends.py`) copie la claim `organization` du jeton dans un champ du `User` (migration incluse).
2. **`trusted` limité à l'organisation** : `LobbyService.can_bypass_lobby` (`core/services/lobby.py`) et la décision d'accès du sérialiseur de salle (`core/api/serializers.py`). Un utilisateur connecté d'une autre organisation passe par la salle d'attente.
3. **Quota à la création** : avant de créer une salle (`RoomViewSet.perform_create`, `core/api/viewsets.py`), Meet appelle la plateforme pour vérifier le quota de l'organisation. Délai d'expiration court ; si la plateforme ne répond pas ou refuse, la création est refusée. L'URL et l'authentification viennent de variables d'environnement, sans valeur par défaut réelle.
4. **Organisation dans le jeton LiveKit** : `generate_token` (`core/utils.py`) ajoute l'organisation aux métadonnées du participant.

Chaque patch a ses tests pytest, dont le **test négatif** d'isolation : un utilisateur
de l'organisation B n'entre pas directement dans une salle `trusted` de l'organisation A.

## Montée de version

1. `git fetch upstream --tags`, puis lis le CHANGELOG et le diff entre `vANCIENNE` et `vNOUVELLE` sur les fichiers patchés et sur `core/models.py`, `core/services/lobby.py`, `core/api/`, `core/utils.py`, `core/authentication/`.
2. Crée `patched/vNOUVELLE` depuis le tag, puis `git cherry-pick` les commits de patch un par un. En cas de conflit, réécris le patch au plus près du nouveau code, sans élargir son périmètre.
3. `make test-back` et `make lint-back`. **Si un test d'isolation échoue, ne livre pas la version.**
4. Signale les nouveautés amont qui rendraient un patch inutile, par exemple un multi-tenant natif.
5. Vérifie les migrations de la nouvelle version : une migration amont non réversible empêche le retour arrière.

## Règles

- Ne modifie jamais `main` : c'est le miroir de l'amont.
- Dépôt **public** : aucune information interne (adresses, hôtes, secrets, configuration de déploiement).
- Commits gitmoji (`<gitmoji>(<scope>) <sujet>`), sans trailer `Co-Authored-By`.
- Livre par une PR vers la branche `patched/` concernée, qui décrit les patchs touchés, la version amont et les tests passés. Ne merge pas sans l'accord de l'utilisateur.
