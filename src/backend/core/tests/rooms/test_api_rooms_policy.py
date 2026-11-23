"""
Test rooms API endpoints in the Meet core app: optional creation and access level
restrictions (ROOM_CREATION_API_ENABLED, ROOM_ACCESS_LEVEL_HARDEN_ONLY).
"""

from unittest import mock

import pytest
from rest_framework.test import APIClient

from ...factories import RoomFactory, UserFactory
from ...models import Room, RoomAccessLevel

pytestmark = pytest.mark.django_db


def _client(user):
    client = APIClient()
    client.force_login(user)
    return client


def test_api_rooms_create_enabled_by_default():
    """The creation endpoint works as upstream with the default settings."""
    response = _client(UserFactory()).post("/api/v1.0/rooms/", {"name": "My room"})
    assert response.status_code == 201
    assert Room.objects.filter(slug="my-room").exists()


def test_api_rooms_create_disabled(settings):
    """An authenticated user gets a 403 with a code and no room is created."""
    settings.ROOM_CREATION_API_ENABLED = False

    response = _client(UserFactory()).post("/api/v1.0/rooms/", {"name": "My room"})

    assert response.status_code == 403
    assert response.json()["code"] == "room_creation_disabled"
    assert not Room.objects.exists()


def test_api_rooms_create_disabled_anonymous(settings):
    """Anonymous users are still refused first (401), nothing is created."""
    settings.ROOM_CREATION_API_ENABLED = False

    response = APIClient().post("/api/v1.0/rooms/", {"name": "My room"})

    assert response.status_code == 401
    assert not Room.objects.exists()


def test_api_rooms_create_disabled_unknown_slug_stays_not_found(settings):
    """Disabling creation does not turn an unknown slug into a creation refusal."""
    settings.ROOM_CREATION_API_ENABLED = False
    settings.ALLOW_UNREGISTERED_ROOMS = False

    response = _client(UserFactory()).get("/api/v1.0/rooms/unknown-room/")

    assert response.status_code == 404
    assert "code" not in response.json()


def test_api_rooms_create_disabled_keeps_existing_rooms(settings):
    """Existing rooms stay readable when creation is disabled."""
    settings.ROOM_CREATION_API_ENABLED = False
    room = RoomFactory(access_level=RoomAccessLevel.RESTRICTED)
    user = UserFactory()
    room.accesses.create(user=user, role="owner")

    response = _client(user).get(f"/api/v1.0/rooms/{room.id}/")

    assert response.status_code == 200


def test_api_config_exposes_policy_settings(settings):
    """The frontend configuration tells whether the policies are on."""
    response = APIClient().get("/api/v1.0/config/")
    assert response.json()["room_creation_api_enabled"] is True
    assert response.json()["room_access_level_harden_only"] is False

    settings.ROOM_CREATION_API_ENABLED = False
    settings.ROOM_ACCESS_LEVEL_HARDEN_ONLY = True
    response = APIClient().get("/api/v1.0/config/")
    assert response.json()["room_creation_api_enabled"] is False
    assert response.json()["room_access_level_harden_only"] is True


def _owned_room(access_level):
    user = UserFactory()
    room = RoomFactory(access_level=access_level)
    room.accesses.create(user=user, role="owner")
    return user, room


@pytest.mark.parametrize(
    "old,new",
    [
        ("public", "trusted"),
        ("public", "restricted"),
        ("trusted", "restricted"),
        ("restricted", "restricted"),
    ],
)
@mock.patch("core.services.room_management.RoomManagement.sync_room_metadata")
def test_api_rooms_access_level_harden_only_accepts_hardening(
    _sync, old, new, settings
):
    """A stricter (or identical) access level is accepted."""
    settings.ROOM_ACCESS_LEVEL_HARDEN_ONLY = True
    user, room = _owned_room(old)

    response = _client(user).patch(
        f"/api/v1.0/rooms/{room.id}/", {"access_level": new}, format="json"
    )

    assert response.status_code == 200
    room.refresh_from_db()
    assert room.access_level == new


@pytest.mark.parametrize(
    "old,new",
    [
        ("restricted", "trusted"),
        ("restricted", "public"),
        ("trusted", "public"),
    ],
)
def test_api_rooms_access_level_harden_only_refuses_loosening(old, new, settings):
    """A looser access level is refused with a code and the room is unchanged."""
    settings.ROOM_ACCESS_LEVEL_HARDEN_ONLY = True
    user, room = _owned_room(old)

    response = _client(user).patch(
        f"/api/v1.0/rooms/{room.id}/", {"access_level": new}, format="json"
    )

    assert response.status_code == 403
    assert response.json()["code"] == "access_level_loosening_refused"
    room.refresh_from_db()
    assert room.access_level == old


def test_api_rooms_access_level_harden_only_refuses_loosening_on_put(settings):
    """PUT cannot be used to loosen the access level either."""
    settings.ROOM_ACCESS_LEVEL_HARDEN_ONLY = True
    user, room = _owned_room("restricted")

    response = _client(user).put(
        f"/api/v1.0/rooms/{room.id}/",
        {"name": room.name, "access_level": "public"},
        format="json",
    )

    assert response.status_code == 403
    room.refresh_from_db()
    assert room.access_level == "restricted"


def test_api_rooms_access_level_harden_only_allows_other_fields(settings):
    """Updates that do not touch the access level are not affected."""
    settings.ROOM_ACCESS_LEVEL_HARDEN_ONLY = True
    user, room = _owned_room("restricted")

    response = _client(user).patch(
        f"/api/v1.0/rooms/{room.id}/", {"configuration": {}}, format="json"
    )

    assert response.status_code == 200


@mock.patch("core.services.room_management.RoomManagement.sync_room_metadata")
def test_api_rooms_access_level_loosening_allowed_by_default(_sync):
    """With the default settings the access level can be loosened (upstream)."""
    user, room = _owned_room("restricted")

    response = _client(user).patch(
        f"/api/v1.0/rooms/{room.id}/", {"access_level": "public"}, format="json"
    )

    assert response.status_code == 200
    room.refresh_from_db()
    assert room.access_level == "public"
