# Fork de La Suite Meet : jeu de patchs multi-tenant

Ce dépôt est un fork **public** de [suitenumerique/meet](https://github.com/suitenumerique/meet)
(licence MIT). Il porte un petit jeu de patchs qui rend une instance Meet utilisable par
plusieurs organisations (tenants). Une plateforme externe gère les organisations, les
offres et les quotas ; l'identité vient de Keycloak (claim `organization`).

**Dépôt public : n'y mets aucune information interne** (adresses, noms d'hôtes ou de
conteneurs, chemins de secrets, configuration d'infrastructure, stratégie commerciale).
Ces informations vivent dans des dépôts privés.

## Branches

- `main` : miroir de `upstream/main`, **jamais modifié**. Remote `upstream` : `https://github.com/suitenumerique/meet.git`.
- `patched/vX.Y.Z` : part du tag amont `vX.Y.Z`. Elle contient les patchs (un commit par patch) et les fichiers propres au fork (`CLAUDE.md`, `.claude/`, CI de l'image patchée).

## Patchs

| N° | Patch | Documentation |
|----|-------|---------------|
| 1 | Organisation de l'utilisateur (claim OIDC) et de la salle | `docs/features/room-limits.md` |
| 2 | Salles `trusted` limitées à l'organisation de la salle | `docs/fork-frontend-patch.md` |
| 3 | Contrôle de création de salle par une plateforme externe (échec fermé) | `docs/features/room-limits.md` |
| 5 | Limites de salle d'un service externe appliquées aux jetons (échec ouvert) | `docs/features/room-limits.md` |
| 6 | Frontend : bannière de fin de réunion, refus traduits, neutralisation des marques | `docs/fork-frontend-patch.md` |
| 7 | Salles de réunions planifiées, créées à la première entrée (échec fermé) | `docs/features/scheduled-rooms.md` |
| 8 | Création de salle par l'API désactivable et niveau d'accès renforcé seulement | `docs/features/room-policy.md` |

Migrations du fork : elles gardent leurs noms (`0030_user_organization_id`, `0031_room_organization_id`,
`0032_backfill_room_organization_id`) pour ne pas être rejouées sur une base déjà migrée. Elles forment une
branche parallèle de celle de l'amont ; une migration de fusion (`0033_merge_fork_and_upstream`) réunit les
deux feuilles. À chaque montée de version amont : `makemigrations --check` doit ne rien détecter et
`showmigrations core` ne doit montrer qu'une feuille ; sinon ajouter ou mettre à jour la migration de fusion.

## CI du fork

`.github/workflows/fork-patched-ci.yml` : lint et tests backend sur les PR et les pushs
des branches `patched/**` (les workflows amont ne voient pas les branches contenant un
`/`), puis image backend patchée `ghcr.io/moukmessie/meet-backend` (tag `sha-…`, et
`vX.Y.Z-patched.N` sur les tags), digest dans le résumé du job. Le frontend est
vérifié (format, lint, tests, build) puis publié de la même façon sous
`ghcr.io/moukmessie/meet-frontend` (cible `frontend-production`, `Dockerfile` dans
`src/frontend/`). Le frontend est construit avec `VITE_APP_TITLE=Meet` et une API de
même origine.

Contrôles amont sans objet pour le fork : `check-changelog` (pas d'entrée de
CHANGELOG pour les patchs, pour faciliter le rebase) et `lint-spell-mistakes` (signale
le français de ce fichier).

## Conventions (celles de l'amont)

- Commits au format gitmoji, vérifié par gitlint : `<gitmoji>(<scope>) <sujet en minuscules>`, par exemple `✨(backend) restrict trusted rooms to the user organization`. Pas de trailer `Co-Authored-By`.
- Tests backend : `make test-back` (pytest). Lint : `make lint-back` (ruff).
- Aucun secret dans le dépôt.

## Agent

`.claude/agents/meet-patch-maintainer.md` : écriture des patchs et montées de version.
