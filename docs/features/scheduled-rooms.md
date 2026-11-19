# Salles de réunions planifiées

Pour les déploiements multi-organisations, une plateforme externe peut planifier des
réunions et **réserver un identifiant de salle** (`abc-defg-hij`) pour chacune. Meet ne
connaît pas encore cet identifiant : à la première entrée, il interroge la plateforme et crée la
salle si la réunion est valable. Rien n'est créé à la planification.

## Réglages

| Variable                              | Description                                                                                         | Défaut |
| ------------------------------------- | --------------------------------------------------------------------------------------------------- | ------ |
| `SCHEDULED_ROOMS_URL`                 | URL de recherche d'une réunion par identifiant. Vide : fonction désactivée, comportement amont.     |        |
| `SCHEDULED_ROOMS_ROOM_URL`            | URL où Meet annonce la salle créée. Facultative : vide, rien n'est annoncé.                         |        |
| `SCHEDULED_ROOMS_TIMEOUT`             | Délai d'attente du service, en secondes.                                                            | `2.0`  |
| `SCHEDULED_ROOMS_EARLY_ENTRY_MINUTES` | Minutes avant le début pendant lesquelles la salle peut être ouverte. Rien n'est toléré après la fin. | `15`   |

Le jeton est celui du contrôle de création de salle (`ROOM_CREATION_CHECK_TOKEN`, en-tête
`Authorization: Bearer`). Le contrôle de création (`ROOM_CREATION_CHECK_URL`) s'applique à
l'ouverture de la salle : quotas et limites restent ceux de la plateforme.

## Où c'est appliqué

`GET /rooms/<identifiant>/` (récupération de la salle, première requête de toute entrée). Pour
une salle inconnue de Meet **dont l'identifiant a le format `abc-defg-hij`** (les autres
identifiants et les UUID ne déclenchent aucun appel), Meet appelle la plateforme. Une salle déjà
présente dans Meet ne déclenche aucun appel.

## Contrat du service

### Recherche (`SCHEDULED_ROOMS_URL`)

`POST` JSON :

```json
{ "slug": "abc-defg-hij", "user_sub": "<sub de l'utilisateur>" }
```

(`user_sub` vide pour un anonyme.) Réponse `200` :

```json
{ "exists": false }
```

ou

```json
{
  "exists": true,
  "organization_id": "<uuid>",
  "organizer_sub": "<sub>",
  "status": "scheduled",
  "starts_at": "2026-12-01T09:00:00+00:00",
  "ends_at": "2026-12-01T10:00:00+00:00",
  "room_id": null,
  "user_may_open": true,
  "refused_reason": null,
  "name": "Atelier",
  "access_level": "trusted",
  "configuration": { "can_publish_sources": ["microphone", "camera"], "everyone_can_mute": true },
  "cohost_subs": ["<sub>"]
}
```

Ni titre, ni description, ni adresse e-mail : seul le nécessaire à la décision est échangé.
`status` : `scheduled` ou `canceled`. `user_may_open` : décision de la plateforme (qui peut
ouvrir la salle). `refused_reason` : motif de refus décidé par la plateforme (offre, organisation
inactive).

### Réglages de la salle

Les champs `access_level`, `configuration`, `cohost_subs` et `name` sont facultatifs et validés
par Meet. Les préférences par défaut de l'utilisateur (`default_room_access_level`,
`default_room_configuration`) sont **ignorées** : c'est la réunion qui décide.

| Champ | Règle de Meet |
| ----- | ------------- |
| `access_level` | `trusted` ou `restricted`. **`public` n'est jamais accordé** : toute autre valeur (`public`, inconnue, absente, mal typée) donne `restricted`, avec un avertissement journalisé. |
| `configuration` | Validée avec le schéma de l'API (`can_publish_sources`, `everyone_can_mute` ; clés inconnues refusées). Invalide : ignorée (`{}`) et journalisée, la salle est tout de même créée. |
| `cohost_subs` | 10 `sub` au plus, chaînes de 255 caractères au plus ; sinon la liste entière est ignorée. Un co-animateur reçoit le rôle **administrateur** de la salle (il modère, il n'en est pas propriétaire) s'il est déjà connu de Meet **et** si l'organisation de sa claim est celle de la réunion. Un `sub` inconnu de Meet (jamais connecté à la salle) n'obtient rien. |
| `name` | Lu mais **non appliqué** : l'identifiant d'une salle est dérivé de son nom (`slug`), il doit rester l'identifiant réservé. Le nom d'affichage n'apparaît pas dans la salle. |

### Annonce de la salle (`SCHEDULED_ROOMS_ROOM_URL`)

Après la création, `POST {"slug": "...", "room_id": "<uuid de la salle>"}`. L'identifiant de salle
est le nom de la salle LiveKit : la plateforme s'en sert pour rattacher les sessions LiveKit
(webhooks) à la réunion. Idempotent ; un échec est journalisé et n'empêche pas l'entrée.

## Décision de Meet

Dans cet ordre, pour un identifiant connu de la plateforme :

| Situation                                                                 | Réponse `403`, `code`                   |
| ------------------------------------------------------------------------- | --------------------------------------- |
| Réunion annulée (quel que soit l'utilisateur)                             | `scheduled_meeting_canceled`            |
| Fin de la réunion passée                                                  | `scheduled_meeting_ended`               |
| Motif de refus de la plateforme (`refused_reason`)                        | ce motif (`scheduling_not_available`…)  |
| Plus de `SCHEDULED_ROOMS_EARLY_ENTRY_MINUTES` avant le début              | `scheduled_meeting_not_started`         |
| Anonyme, `user_may_open` faux, ou organisation signée différente de celle de la réunion | `scheduled_meeting_not_opened` |
| Refus du contrôle de création (quota, limites, rôle)                      | le motif du contrôle (`monthly_minutes_exhausted`…) |
| Plateforme injoignable, réponse illisible ou en erreur (utilisateur connecté) | `check_unavailable`                 |

Sinon la salle est créée : nom et identifiant = celui réservé, `organization_id` = celui de la
réunion (la salle est donc de l'organisation, patch 1), niveau d'accès et configuration de
la réunion (voir « Réglages de la salle »), l'utilisateur en propriétaire (l'organisateur aussi, s'il est connu de Meet
par son `sub`). La salle existe ensuite comme toute salle : les invités entrent avec le lien selon son
niveau d'accès (salle d'attente comprise) et les limites de salle s'appliquent à chaque jeton
(patch 5).

Un invité qui arrive avant l'ouverture reçoit `scheduled_meeting_not_opened` (ou
`scheduled_meeting_not_started` trop tôt) : il réessaie une fois la salle ouverte.

## Idempotence et concurrence

Deux premières entrées simultanées créent une seule salle : l'unicité de l'identifiant rejette la
seconde création, qui relit alors la salle de la première (sans second appel d'annonce).
Les entrées suivantes ne passent plus par la plateforme.

## Échecs

- La **création échoue fermé** : plateforme injoignable, délai dépassé, réponse illisible, contrôle
  de création indisponible ou refus : aucune salle n'est créée. Pour un utilisateur connecté, la
  réponse est `403 check_unavailable` ; pour un anonyme (qui ne pourrait rien créer), le
  comportement amont (`404`) est conservé.
- L'**entrée** dans une salle existante reste celle de Meet : elle échoue ouvert comme les limites
  de salle (voir `room-limits.md`).
- Un identifiant inconnu de la plateforme garde le comportement amont : `404`, ou salle non
  enregistrée si `ALLOW_UNREGISTERED_ROOMS` est actif.

## Limites connues

- **Durcissement en direct** : le niveau d'accès choisi par la réunion est le niveau initial. En
  direct, le comportement amont n'est pas modifié : un propriétaire ou administrateur de la salle
  peut changer le niveau d'accès dans les deux sens, y compris vers `public`. « Durcir seulement »
  et « jamais `public` » après l'ouverture demandent un patch distinct sur la mise à jour de la
  salle, non réalisé ici.
- Un co-animateur qui ne s'est jamais connecté à Meet n'a pas le rôle (son compte Meet n'existe
  pas encore) : l'organisateur peut le promouvoir dans la salle.
- L'ouverture par la récupération de la salle n'est pas limitée par le débit de création de salle
  (`ROOM_CREATION_THROTTLE_RATES`) : le nombre de salles par utilisateur est borné par les réunions
  planifiées de la plateforme.
- Si l'annonce de la salle échoue, la plateforme ne rattache pas les sessions LiveKit à la réunion.
- La fenêtre horaire est évaluée avec l'horloge de Meet : les horloges doivent être synchronisées
  (quelques secondes de dérive sont sans effet avec la tolérance).

## Retour arrière

Vider `SCHEDULED_ROOMS_URL` : plus aucun appel, comportement amont. Les salles déjà créées
restent des salles ordinaires.

## Tests

`src/backend/core/tests/rooms/test_api_rooms_scheduled.py` (accès, idempotence, concurrence, fenêtre
horaire, annulation, quota, plateforme injoignable, identifiants hors format, réglages de la
réunion, repli `restricted`, co-animateurs) et
`src/frontend/src/api/apiRefusal.test.ts` (messages dans les cinq langues).
