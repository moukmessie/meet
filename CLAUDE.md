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

## Conventions (celles de l'amont)

- Commits au format gitmoji, vérifié par gitlint : `<gitmoji>(<scope>) <sujet en minuscules>`, par exemple `✨(backend) restrict trusted rooms to the user organization`. Pas de trailer `Co-Authored-By`.
- Tests backend : `make test-back` (pytest). Lint : `make lint-back` (ruff).
- Aucun secret dans le dépôt.

## Agent

`.claude/agents/meet-patch-maintainer.md` : écriture des patchs et montées de version.
