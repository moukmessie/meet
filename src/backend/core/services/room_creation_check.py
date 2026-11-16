"""Ask an external service whether a user may create a room.

Used by multi-organization deployments: before creating a room, Meet asks a
platform that manages organizations, plans and quotas. The check is disabled
when ROOM_CREATION_CHECK_URL is empty (default).

The check fails closed: no organization, a refusal, an error or a timeout of
the platform all refuse the creation. Existing rooms are never affected.
"""

import logging

from django.conf import settings

import requests
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class RoomCreationRefused(PermissionDenied):
    """The user is not allowed to create a room."""

    default_detail = "You are not allowed to create a room."
    default_code = "room_creation_refused"


def ensure_room_creation_allowed(user):
    """Raise RoomCreationRefused unless the external platform allows the creation."""
    url = settings.ROOM_CREATION_CHECK_URL
    if not url:
        return

    if user.organization_id is None:
        raise RoomCreationRefused(
            "You must belong to an organization to create a room.",
            code="no_organization",
        )

    try:
        response = requests.post(
            url,
            json={"organization_id": str(user.organization_id), "user_sub": user.sub},
            headers={"Authorization": f"Bearer {settings.ROOM_CREATION_CHECK_TOKEN}"},
            timeout=settings.ROOM_CREATION_CHECK_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning("Room creation check failed: %s", type(error).__name__)
        raise RoomCreationRefused(
            "Room creation is temporarily unavailable, please try again later.",
            code="check_unavailable",
        ) from error

    if not isinstance(result, dict) or result.get("allowed") is not True:
        reason = result.get("reason") if isinstance(result, dict) else None
        raise RoomCreationRefused(code=str(reason or "refused"))
