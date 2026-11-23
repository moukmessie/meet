# Création de salle et niveau d'accès

Deux réglages facultatifs, désactivés par défaut (comportement amont), pour les
déploiements où les salles sont créées par un autre système et où l'accès ne doit
pouvoir qu'être renforcé.

## Réglages

| Variable                        | Description                                                                                              | Défaut  |
| ------------------------------- | -------------------------------------------------------------------------------------------------------- | ------- |
| `ROOM_CREATION_API_ENABLED`     | Faux : `POST /api/v1.0/rooms/` répond `403` avec `code: room_creation_disabled`. Aucune salle n'est créée. | `true`  |
| `ROOM_ACCESS_LEVEL_HARDEN_ONLY` | Vrai : l'API refuse d'assouplir le niveau d'accès d'une salle (`public` < `trusted` < `restricted`).     | `false` |

`ALLOW_UNREGISTERED_ROOMS=False` reste le réglage amont qui empêche d'entrer dans une
salle inconnue.

## Comportement

- Création refusée : réponse `403` `{"detail": "...", "code": "room_creation_disabled"}`.
  Un utilisateur non authentifié reçoit toujours `401`. Les salles existantes ne sont pas touchées.
- Une salle dont l'identifiant est inconnu reste « introuvable » (`404`) à la récupération :
  le refus ne concerne que `POST /rooms/`.
- Niveau d'accès : `PUT`/`PATCH` vers un niveau plus strict ou identique est accepté ; vers un
  niveau plus souple, `403` avec `code: access_level_loosening_refused`, la salle est inchangée.
  Les autres champs ne sont pas concernés.
- L'interface (panneau d'administration de la réunion) n'offre que le niveau courant et les
  niveaux plus stricts quand `ROOM_ACCESS_LEVEL_HARDEN_ONLY` est vrai. Les deux réglages sont
  exposés au frontend par `GET /api/v1.0/config/` (`room_creation_api_enabled`,
  `room_access_level_harden_only`).
- Messages : `room_creation_disabled` et `access_level_loosening_refused` sont traduits
  (en, fr, de, es, nl), dans un ton neutre qui invite à revenir au portail de création.

## API externe

L'API de ressource (`rooms:create`, jeton OIDC de service) n'est pas concernée par ces
réglages : ne pas l'exposer publiquement (au niveau de l'Ingress ou du proxy).

## Retour arrière

Remettre `ROOM_CREATION_API_ENABLED=true` et `ROOM_ACCESS_LEVEL_HARDEN_ONLY=false`
(ou supprimer les variables) : le comportement redevient celui de l'amont, sans migration.

## Tests

`src/backend/core/tests/rooms/test_api_rooms_policy.py` (positifs et négatifs) et
`src/frontend/src/features/rooms/utils/accessLevel.test.ts`.
