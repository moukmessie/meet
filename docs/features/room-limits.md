# Limites de salle fournies par un service externe

Pour les déploiements multi-organisations, Meet peut lire les limites d'une salle
auprès d'un service externe (plateforme gérant les offres et les quotas) et les
appliquer au jeton d'accès LiveKit.

## Réglages

| Variable                    | Description                                                                                        | Défaut |
| --------------------------- | -------------------------------------------------------------------------------------------------- | ------ |
| `ROOM_LIMITS_URL`           | URL du service. Vide : fonction désactivée, comportement amont inchangé.                           |        |
| `ROOM_LIMITS_TOKEN`         | Jeton porté dans `Authorization: Bearer`. S'il est vide, `ROOM_CREATION_CHECK_TOKEN` est réutilisé. |        |
| `ROOM_LIMITS_TIMEOUT`       | Délai d'attente du service, en secondes.                                                           | `2.0`  |

Comme les autres jetons secrets, `ROOM_LIMITS_TOKEN` accepte la variante `_FILE`.

## Contrat du service

Pour chaque jeton délivré, et chaque demande d'entrée, pour une salle qui a une organisation (aucun appel sinon),
Meet envoie un `POST` JSON :

```json
{ "organization_id": "<uuid>" }
```

Le service répond `200` avec toujours ces trois clés :

```json
{
  "max_participants": 25,
  "entry_refused_reason": null,
  "quota": { "limit": 6000, "used": 120, "remaining": 5880, "resets_at": "2026-12-01T00:00:00Z" }
}
```

- `max_participants` entier strictement positif : placé dans `roomConfig.max_participants`
  du jeton d'accès. LiveKit l'applique à la création de la salle (première connexion).
  `null` : aucune limite ajoutée.
- `entry_refused_reason` non nul : aucun jeton, réponse HTTP `403` avec
  `{"detail": "<message en français>", "code": "<raison>", "quota": {...}}`
  (par exemple `monthly_minutes_exhausted`).

## Où le contrôle est appliqué

Le contrôle se fait à un seul endroit : `Room.livekit_token_kwargs`, qui appelle
`get_room_limits` et lève `RoomEntryRefused` (HTTP 403). Il est évalué :

- à la récupération de la salle (`GET /rooms/<id>/`), quand un jeton est délivré
  (salle publique, utilisateur de confiance, membre) ;
- à chaque `POST /rooms/<id>/request-entry/`, **avant** toute mise en attente
  (`LobbyService.request_entry`), pour les utilisateurs anonymes comme
  authentifiés ;
- à chaque interrogation suivante de `request-entry` (toutes les 3 s côté
  frontend), y compris celle qui délivre le jeton après l'admission d'un
  participant par un modérateur.

Une salle sans organisation ne déclenche aucun appel.

Historique : avant ce correctif, un anonyme sur une salle `trusted` n'a pas de jeton
à la récupération de la salle (il doit passer par la salle d'attente) et
`request-entry` ne consultait room-limits que lorsqu'un jeton était délivré. Il
recevait donc `200 {"status": "waiting"}` et attendait sans message, alors qu'un
utilisateur connecté recevait le `403`. Le refus a maintenant lieu à la demande
d'entrée.

### Admission depuis la salle d'attente

`POST /rooms/<id>/enter/` ne fait que changer le statut du participant en cache,
il ne délivre aucun jeton. Le jeton est délivré à l'interrogation suivante de
`request-entry` (statut `accepted`), qui passe par `livekit_token_kwargs` : il porte
donc `max_participants`, et si le quota est épuisé entre-temps le participant admis
reçoit le même `403` sans jeton. L'admission ne contourne ni la limite ni le quota
(tests `test_api_rooms_lobby_limits.py`).

Coût : un appel au service par interrogation de `request-entry` pour une salle avec
organisation ; le service doit répondre vite (délai `ROOM_LIMITS_TIMEOUT`, échec
ouvert).

## Échec ouvert

Seule une réponse `200` explicite peut refuser une entrée. Toute autre réponse (404,
5xx), un délai dépassé, une erreur réseau ou un corps illisible délivre le jeton sans
limite et journalise un avertissement (`Room limits unavailable`). Contrairement au
contrôle de création de salle, qui échoue fermé, une panne du service ne bloque donc
pas les réunions.

## Retour arrière

Vider `ROOM_LIMITS_URL` désactive la fonction : plus aucun appel, jetons identiques à
l'amont.

## Refus de création de salle

Le refus du contrôle de création renvoie `403` avec
`{"detail": "...", "code": "<raison>", "quota": {...}}`. `code` est la raison renvoyée
par le service (`refused` si elle est absente ou n'a pas la forme `[a-z][a-z0-9_]*`),
`check_unavailable` si le service est indisponible, `no_organization` sans organisation.
`quota` n'est présent que si le service le fournit.
