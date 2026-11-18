# Patch frontend du fork

Ce document décrit le patch frontend du fork (branche `patched/vX.Y.Z`).

## Bannière de fin de réunion (`meetingEnding`)

- La plateforme envoie, via l'API serveur de LiveKit, un message de données **sans
  topic** à tous les participants, au format des notifications de Meet :
  `{"type": "meetingEnding", "data": {"seconds_left": <entier>, "reason": "duration_limit" | "monthly_limit" | "concurrent_limit"}}`.
- Réception : événement `RoomEvent.DataReceived` de LiveKit, comme les autres
  notifications de la salle ; les autres valeurs de `type` sont ignorées et ne gênent
  pas les écouteurs existants. L'instant de fin est l'instant de réception plus
  `seconds_left`. Seuls les messages **émis par le serveur** (sans participant
  émetteur) sont acceptés : un participant ne peut pas forger la bannière. Les payloads
  invalides, `seconds_left` non entier, négatif ou supérieur à 24 h, et les raisons
  inconnues sont ignorés.
- Affichage : bannière `role="status"` (`aria-live="polite"`) avec un compte à rebours à
  la minute (« La réunion se termine dans 4 min », « … dans moins d'une minute »,
  « … maintenant ») et un message propre à chaque raison. Le texte ne change qu'une fois
  par minute pour ne pas surcharger les lecteurs d'écran.
- Code : `src/frontend/src/features/meetingEnding/`. Textes : clés `meetingEnding.*` de
  `locales/<langue>/rooms.json`.

## Message de refus (HTTP 403)

Quand l'API refuse la création ou l'entrée avec `403 {detail, code, quota}`, le frontend
affiche un message traduit. Chemins couverts : création depuis l'accueil (message
d'alerte sous le bouton), récupération de la salle et écran de connexion (écran d'erreur
avec bouton de retour), écran d'entrée (`Lobby`) : un 403 lors de la récupération de la
salle ou de `request-entry` affiche le refus au lieu de la salle d'attente, et **arrête
l'interrogation** de `request-entry` (statut client `refused`).

Le message traduit du code est **toujours** préféré à `detail` (qui n'est pas traduit) ;
`detail` ne sert que de repli pour un code inconnu, puis un message générique.

| Code | Message |
|------|---------|
| `monthly_minutes_exhausted` | Quota mensuel épuisé, avec la date de renouvellement (`quota.resets_at`, fuseau Europe/Paris) |
| `concurrent_rooms_limit`, `concurrent_limit` | Nombre maximal de réunions simultanées atteint |
| `no_organization`, `unknown_organization` | Appartenance à une organisation reconnue requise |
| `tenant_suspended`, `tenant_closed` | Compte de l'organisation suspendu ou clôturé |
| `no_active_subscription` | Aucun abonnement actif |
| `check_unavailable` | Création temporairement indisponible |
| `entry_refused` | Entrée refusée |
| `room_creation_refused`, `refused` | Création non autorisée |

Code : `src/frontend/src/api/apiRefusal.ts`, clés `error.refusal.*` de `rooms.json`
(cinq langues ; un test vérifie que chaque code a une traduction dans chacune).

Côté backend, le refus de création (`RoomCreationRefused`) renvoie aussi `code` (la raison
de la plateforme, `refused` si elle est absente ou mal formée, `check_unavailable` si la
plateforme est indisponible, `no_organization` sans organisation) et `quota` quand la
plateforme le fournit, en plus de `detail`.

Non traité : le refus d'un participant par la limite `max_participants` de LiveKit. Le
`DisconnectReason` de livekit-client 2.21 n'a pas de valeur « salle pleine » (seulement
`JOIN_FAILURE`, trop générique) : le message « Disconnected » reste générique.

## Libellé de l'accès « de confiance »

« Ouvrir aux personnes de confiance » devient « Ouvrir aux membres de l'organisation »
(clé `admin.access.levels.trusted` de `rooms.json`, cinq langues), avec sa description.

## Retrait des marques et textes institutionnels

Retiré du frontend :

- Pied de page : logo Marianne et devise (`marianne.svg`, `devise.svg`, déjà absents du
  dépôt), mention « gouvernement », bloc « Direction interministérielle du numérique »,
  liens `legifrance.gouv.fr`, `info.gouv.fr`, `service-public.fr`, `data.gouv.fr`,
  lien « Données personnelles et cookie » vers un document institutionnel, mention de
  licence Etalab, police « Marianne ». Le pied de page est désormais neutre : mentions
  légales, conditions d'utilisation, accessibilité, test de configuration, fiche
  technique configurable (`technical_documentation_url`) et lien vers le dépôt du code
  du logiciel. Il reste activé par l'option de configuration existante
  `FRONTEND_USE_FRENCH_GOV_FOOTER` (nom conservé pour ne pas toucher au backend).
- Bouton et liens ProConnect : composant `ProConnectButton`, images
  `proconnect-button*.svg`, textes `login.proconnect*`, option `use_proconnect_button`
  côté frontend. Le bouton de connexion est toujours le bouton standard.
- Logo `logo-suite-numerique.png` (non utilisé).
- Pages légales entièrement réécrites en texte neutre : mentions légales (éditeur DINUM,
  SIRET, directrice de publication, hébergeur, licence Etalab), déclaration
  d'accessibilité (adresse, courriels, Défenseur des droits, RGAA) et conditions
  d'utilisation (Visio, administrations de l'État, DINUM, ProConnect). Les trois
  textes renvoient à « l'exploitant du service » : **l'exploitant doit fournir ses
  propres informations légales** avant une mise en production.
- Textes « Visio » de l'interface du SDK (`sdk.json`) et commentaires de code citant la
  DINUM.
- Police « Marianne » dans le primitif de lien.

Conservé volontairement :

- `LICENSE.md`, `LICENSES/` et les attributions amont (licence MIT) ; la page légale et
  le pied de page citent la licence MIT et le dépôt amont.
- Le logo du produit (`public/assets/logo.svg`) et les icônes, qui sont ceux du logiciel
  amont : à remplacer par ceux de la plateforme si besoin.
- Le répertoire `docker/dinum-frontend/` (image de thème institutionnelle, hors image du
  fork, non construite par la CI du fork).

## Image du frontend

La CI du fork publie `ghcr.io/moukmessie/meet-frontend` (tag `sha-<court>`, digest dans
le résumé du job), construite depuis `src/frontend/Dockerfile`, cible
`frontend-production`, avec `VITE_APP_TITLE=Meet` et l'API en même origine.
