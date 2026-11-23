"""Optional restrictions on how rooms are created and how their access changes.

Both are off by default, which is the upstream behavior:

- ROOM_CREATION_API_ENABLED=False refuses the room creation endpoint, for
  deployments where rooms are only created by another system.
- ROOM_ACCESS_LEVEL_HARDEN_ONLY=True lets the API change the access level of a
  room only towards a stricter one (public < trusted < restricted).

Refusals are 403 responses whose body carries a machine-readable ``code`` next
to the human ``detail``, so that clients can show a translated message.
"""

from django.conf import settings

from rest_framework.exceptions import PermissionDenied

ACCESS_LEVEL_RANK = {"public": 0, "trusted": 1, "restricted": 2}


class _CodedPermissionDenied(PermissionDenied):
    """A 403 whose body is {"detail": ..., "code": ...}."""

    default_code = "refused"

    def __init__(self, detail=None):
        super().__init__(detail=detail, code=self.default_code)
        self.detail = {"detail": str(self.detail), "code": self.default_code}


class RoomCreationDisabled(_CodedPermissionDenied):
    """Rooms cannot be created through the API."""

    default_detail = "Rooms cannot be created from here."
    default_code = "room_creation_disabled"


class AccessLevelLoosening(_CodedPermissionDenied):
    """The access level of a room can only be made stricter."""

    default_detail = "The access level of a room can only be made stricter."
    default_code = "access_level_loosening_refused"


def ensure_room_creation_enabled():
    """Raise RoomCreationDisabled when the creation endpoint is turned off."""
    if not settings.ROOM_CREATION_API_ENABLED:
        raise RoomCreationDisabled()


def ensure_access_level_not_loosened(old_level, new_level):
    """Raise AccessLevelLoosening if the policy is on and the change loosens access."""
    if not settings.ROOM_ACCESS_LEVEL_HARDEN_ONLY:
        return
    if ACCESS_LEVEL_RANK.get(new_level, 0) < ACCESS_LEVEL_RANK.get(old_level, 0):
        raise AccessLevelLoosening()
