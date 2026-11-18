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

Pour chaque jeton délivré pour une salle qui a une organisation (aucun appel sinon),
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

## Échec ouvert

Seule une réponse `200` explicite peut refuser une entrée. Toute autre réponse (404,
5xx), un délai dépassé, une erreur réseau ou un corps illisible délivre le jeton sans
limite et journalise un avertissement (`Room limits unavailable`). Contrairement au
contrôle de création de salle, qui échoue fermé, une panne du service ne bloque donc
pas les réunions.

## Retour arrière

Vider `ROOM_LIMITS_URL` désactive la fonction : plus aucun appel, jetons identiques à
l'amont.
