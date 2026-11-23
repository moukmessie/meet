# Patch frontend du fork

Ce document décrit le patch frontend du fork (branche `patched/vX.Y.Z`).

## Bannière de fin de réunion (`meetingEnding`)

- La plateforme envoie, via l'API serveur de LiveKit, un message de données **sans
  topic** à tous les participants, au format des notifications de Meet :
  `{"type": "meetingEnding", "data": {"seconds_left": <entier>, "reason": "duration_limit" | "monthly_limit" | "concurrent_limit"}}`.
- Réception : paquets de données de LiveKit (voir « Authenticité »), sans topic ; les
  autres valeurs de `type` sont ignorées et ne gênent
  pas les écouteurs existants. L'instant de fin est l'instant de réception plus
  `seconds_left`. Les payloads invalides, `seconds_left` non entier, négatif ou supérieur
  à 24 h, et les raisons inconnues sont ignorés.
- Authenticité : seuls les messages **émis par l'API serveur** de LiveKit
  (`RoomService.SendData`) sont acceptés, pour qu'un participant ne puisse pas forger la
  bannière. Le critère est lu sur le **paquet brut** (`room.engine`, événement
  `EngineEvent.DataPacketReceived`) : le serveur LiveKit pose l'identité de l'émetteur
  (`participantIdentity`, `participantSid`) sur tout paquet relayé depuis un client, sans
  que le client puisse l'écraser, et les laisse vides pour un paquet `SendData`. Le
  paramètre `participant` de `RoomEvent.DataReceived` ne convient **pas** : il vaut
  `undefined` pour un message serveur, mais aussi pour un message client reçu avant que
  l'émetteur soit enregistré dans `room.remoteParticipants` (mesuré : environ 3 s après
  sa connexion), d'où une fenêtre de forge après chaque arrivée.
  Limites : `room.engine` est une API interne de livekit-client (à revérifier à chaque
  montée de version ; le test avec un vrai `Room` échoue si le comportement change, et
  sans moteur le hook n'accepte rien) ; le critère suppose un serveur LiveKit qui
  estampille l'émetteur (vérifié avec livekit-server 1.13.11). Le format du message n'a
  pas changé.
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
| `scheduled_meeting_not_started` | Réunion planifiée pas encore commencée |
| `scheduled_meeting_not_opened` | L'organisateur n'a pas encore ouvert la réunion |
| `scheduled_meeting_canceled` | Réunion annulée |
| `scheduled_meeting_ended` | Réunion terminée |
| `scheduling_not_available` | Planification non incluse dans l'offre |

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

## Portail (`PORTAL_URL`)

Quand une plateforme externe porte l'accueil, la création et les comptes, Meet n'est plus
que la salle. Le réglage `PORTAL_URL` (variable d'environnement du backend, exposé au
frontend par `GET /config/` sous la clé `portal_url`) active ce mode.

- **Vide (défaut) : comportement amont inchangé.** Rien n'est masqué ni redirigé.
- Valeur acceptée : une adresse `http(s)` ; seule son origine est retenue (chemin, requête et
  fragment sont ignorés). Toute autre valeur (`javascript:`, `data:`, adresse relative…) est
  traitée comme vide.
- **Sorties de la salle** : quitter la salle, être retiré, doublon de session, salle fermée
  par le serveur (réunion terminée, limite atteinte) et déconnexion pour inactivité
  redirigent vers le portail : `<portail>/` pour un membre connecté, `<portail>/feedback`
  pour un invité anonyme. La cible est **fixe** (origine de la configuration + chemin
  constant) : elle n'est jamais lue dans l'URL de la page ni dans ses paramètres, donc
  aucune redirection ouverte. Les coupures réseau gardent la reconnexion habituelle.
- **En-tête** : le logo ramène à `<portail>/` (la confirmation de sortie reste demandée
  dans une salle) ; plus aucun bouton « Se connecter » (en-tête, réglages, enregistrement).
- **Écrans masqués** (redirection vers `<portail>/`) : accueil (donc création et « plus
  tard »), `/feedback` de Meet, routes du SDK (`/sdk/*`). La salle, les mentions légales
  et le test de connexion restent servis.
- **Réglages masqués** : onglets Compte, Transcription et Enregistrement du dialogue de
  réglages de la salle ; onglet Salles du dialogue d'en-tête (le dialogue simple reste).
- **Téléphonie** : numéro d'appel et code PIN ne sont plus affichés (fenêtre d'invitation
  et informations de la salle).
- Langue de la salle : celle du navigateur, inchangée.
- Code : `src/frontend/src/features/portal/` (calcul de la cible, route masquée, hooks),
  `PORTAL_URL` dans `FRONTEND_CONFIGURATION` (`src/backend/meet/settings.py`).
- Tests : `portalUrl.test.ts` et `routes.test.ts` (Vitest), `test_api_config_portal_url.py` (pytest).

Retour arrière : retirer `PORTAL_URL` de l'environnement du backend (le mode amont revient
sans redéploiement du frontend) ; le patch lui-même se retire en annulant son commit.

Limite connue : ce patch masque les écrans, il n'empêche pas la création de salle côté
serveur (voir le patch de contrôle de création, `docs/features/room-limits.md`).
