"""Trusted rooms limited to the room organization (TRUSTED_ACCESS_SAME_ORGANIZATION)."""

# pylint: disable=redefined-outer-name,unused-argument
import importlib
import uuid
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth.models import AnonymousUser

import pytest
from rest_framework.test import APIClient

from core import utils
from core.factories import RoomFactory, UserFactory, UserResourceAccessFactory
from core.models import ApplicationScope, RoleChoices, Room, RoomAccessLevel
from core.tests.test_external_api_rooms import generate_test_token

pytestmark = pytest.mark.django_db

ORG_A = uuid.uuid4()
ORG_B = uuid.uuid4()


@pytest.fixture
def same_organization(settings):
    """Enable the organization restriction of trusted rooms."""
    settings.TRUSTED_ACCESS_SAME_ORGANIZATION = True


def client_for(user):
    """API client logged in as the user."""
    client = APIClient()
    client.force_login(user)
    return client


# Rule


def test_is_trusted_for_disabled_any_authenticated_user():
    """Upstream behaviour by default: any authenticated user is trusted."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    assert room.is_trusted_for(UserFactory(organization_id=ORG_B))
    assert room.is_trusted_for(UserFactory(organization_id=None))
    assert not room.is_trusted_for(AnonymousUser())


@pytest.mark.parametrize(
    "room_org,user_org,expected",
    [
        (ORG_A, ORG_A, True),
        (ORG_A, ORG_B, False),
        (ORG_A, None, False),
        (None, ORG_A, False),
        (None, None, False),
    ],
)
def test_is_trusted_for_same_organization(
    same_organization, room_org, user_org, expected
):
    """Only members of the room organization are trusted; unknown means no."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=room_org)
    assert room.is_trusted_for(UserFactory(organization_id=user_org)) is expected


@pytest.mark.parametrize(
    "access_level", [RoomAccessLevel.PUBLIC, RoomAccessLevel.RESTRICTED]
)
def test_is_trusted_for_other_access_levels(same_organization, access_level):
    """The rule only concerns trusted rooms."""
    room = RoomFactory(access_level=access_level, organization_id=ORG_A)
    assert not room.is_trusted_for(UserFactory(organization_id=ORG_A))


def test_is_trusted_for_anonymous(same_organization):
    """Anonymous users are never trusted."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    assert not room.is_trusted_for(AnonymousUser())


# Room retrieval (LiveKit token)


def test_retrieve_same_organization_gets_token(same_organization):
    """A member of the room organization joins directly."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    response = client_for(UserFactory(organization_id=ORG_A)).get(
        f"/api/v1.0/rooms/{room.id}/"
    )
    assert response.status_code == 200
    assert "livekit" in response.json()


@pytest.mark.parametrize("user_org", [ORG_B, None])
def test_retrieve_other_organization_gets_no_token(same_organization, user_org):
    """Negative test: a user of tenant B gets no token for a trusted room of tenant A."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    response = client_for(UserFactory(organization_id=user_org)).get(
        f"/api/v1.0/rooms/{room.id}/"
    )
    assert response.status_code == 200
    assert "livekit" not in response.json()
    assert "pin_code" not in response.json()


def test_retrieve_other_organization_with_role_gets_token(same_organization):
    """A user explicitly given a role on the room joins directly, whatever the org."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    user = UserFactory(organization_id=ORG_B)
    UserResourceAccessFactory(resource=room, user=user, role=RoleChoices.MEMBER)
    response = client_for(user).get(f"/api/v1.0/rooms/{room.id}/")
    assert response.status_code == 200
    assert "livekit" in response.json()


def test_retrieve_room_without_organization_gets_no_token(same_organization):
    """Fail closed: a trusted room without organization trusts nobody."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=None)
    response = client_for(UserFactory(organization_id=ORG_A)).get(
        f"/api/v1.0/rooms/{room.id}/"
    )
    assert "livekit" not in response.json()


def test_retrieve_disabled_other_organization_gets_token():
    """Without the setting, upstream behaviour is kept."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    response = client_for(UserFactory(organization_id=ORG_B)).get(
        f"/api/v1.0/rooms/{room.id}/"
    )
    assert "livekit" in response.json()


def test_retrieve_public_room_other_organization_gets_token(same_organization):
    """Public rooms stay open to everyone."""
    room = RoomFactory(access_level=RoomAccessLevel.PUBLIC, organization_id=ORG_A)
    response = client_for(UserFactory(organization_id=ORG_B)).get(
        f"/api/v1.0/rooms/{room.id}/"
    )
    assert "livekit" in response.json()


# Lobby


def request_entry(user, room):
    """Ask to enter the room through the lobby."""
    with mock.patch.object(utils, "notify_participants", return_value=None):
        return client_for(user).post(
            f"/api/v1.0/rooms/{room.id}/request-entry/", {"username": "someone"}
        )


def test_request_entry_other_organization_waits(same_organization):
    """Negative test: a user of tenant B waits in the lobby of a trusted room of tenant A."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    response = request_entry(UserFactory(organization_id=ORG_B), room)
    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    assert response.json()["livekit"] is None


def test_request_entry_same_organization_accepted(same_organization):
    """A member of the room organization bypasses the lobby."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    response = request_entry(UserFactory(organization_id=ORG_A), room)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["livekit"]["token"]


# In-meeting capabilities


@mock.patch(
    "core.services.participants_management.ParticipantsManagement.check_if_in_meeting",
    return_value=True,
)
def test_capability_other_organization_present_forbidden(mock_check, same_organization):
    """A user of another organization admitted in the meeting cannot manage the lobby."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    response = client_for(UserFactory(organization_id=ORG_B)).get(
        f"/api/v1.0/rooms/{room.id}/waiting-participants/"
    )
    assert response.status_code == 403
    mock_check.assert_not_called()


@mock.patch(
    "core.services.participants_management.ParticipantsManagement.check_if_in_meeting",
    return_value=True,
)
def test_capability_same_organization_present_allowed(mock_check, same_organization):
    """A member of the room organization present in the meeting manages the lobby."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG_A)
    response = client_for(UserFactory(organization_id=ORG_A)).get(
        f"/api/v1.0/rooms/{room.id}/waiting-participants/"
    )
    assert response.status_code == 200


# Creation


def test_create_room_sets_organization():
    """The room takes the organization of its creator (frontend API)."""
    response = client_for(UserFactory(organization_id=ORG_A)).post(
        "/api/v1.0/rooms/", {"name": "my room"}
    )
    assert response.status_code == 201
    assert Room.objects.get(pk=response.json()["id"]).organization_id == ORG_A


def test_create_room_external_sets_organization():
    """The room takes the organization of its creator (external API)."""
    user = UserFactory(organization_id=ORG_A)
    token = generate_test_token(user, [ApplicationScope.ROOMS_CREATE])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = client.post("/external-api/v1.0/rooms/", {}, format="json")
    assert response.status_code == 201
    assert Room.objects.get(pk=response.json()["id"]).organization_id == ORG_A


def test_organization_not_writable_through_api():
    """The organization cannot be chosen or changed by the client."""
    user = UserFactory(organization_id=ORG_A)
    client = client_for(user)
    response = client.post(
        "/api/v1.0/rooms/", {"name": "my room", "organization_id": str(ORG_B)}
    )
    room = Room.objects.get(pk=response.json()["id"])
    assert room.organization_id == ORG_A

    client.patch(
        f"/api/v1.0/rooms/{room.id}/",
        {"organization_id": str(ORG_B)},
        format="json",
    )
    room.refresh_from_db()
    assert room.organization_id == ORG_A


# Backfill of existing rooms (migration 0032)


def test_backfill_room_organization_id():
    """Rooms get their owners' organization only when it is unambiguous."""
    backfill = importlib.import_module(
        "core.migrations.0032_backfill_room_organization_id"
    ).backfill_room_organization_id

    def room_owned_by(*organizations, room_org=None):
        room = RoomFactory(organization_id=room_org)
        for organization in organizations:
            UserResourceAccessFactory(
                resource=room,
                user=UserFactory(organization_id=organization),
                role=RoleChoices.OWNER,
            )
        return room

    single = room_owned_by(ORG_A)
    shared = room_owned_by(ORG_A, ORG_A)
    with_unknown = room_owned_by(ORG_A, None)
    conflicting = room_owned_by(ORG_A, ORG_B)
    no_org = room_owned_by(None)
    already_set = room_owned_by(ORG_A, room_org=ORG_B)
    member_only = RoomFactory(organization_id=None)
    UserResourceAccessFactory(
        resource=member_only,
        user=UserFactory(organization_id=ORG_A),
        role=RoleChoices.MEMBER,
    )

    backfill(django_apps, None)

    def org(room):
        room.refresh_from_db()
        return room.organization_id

    assert org(single) == ORG_A
    assert org(shared) == ORG_A
    assert org(with_unknown) == ORG_A
    assert org(conflicting) is None
    assert org(no_org) is None
    assert org(already_set) == ORG_B
    assert org(member_only) is None
