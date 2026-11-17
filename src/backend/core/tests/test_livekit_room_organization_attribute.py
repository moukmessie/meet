"""LiveKit tokens carry the organization of the room (`room_organization_id`)."""

# pylint: disable=unused-argument
import uuid
from unittest import mock

from django.conf import settings

import jwt
import pytest
from rest_framework.test import APIClient

from core import utils
from core.factories import RoomFactory, UserFactory
from core.models import RoomAccessLevel

pytestmark = pytest.mark.django_db

ORG = uuid.uuid4()


def attributes(token):
    """Participant attributes of a LiveKit access token."""
    return jwt.decode(
        token, settings.LIVEKIT_CONFIGURATION["api_secret"], algorithms=["HS256"]
    )["attributes"]


def test_generate_token_room_organization_attribute():
    """The attribute is set when given, omitted otherwise."""
    user = UserFactory()
    token = utils.generate_token(room="r", user=user, room_organization_id=str(ORG))
    assert attributes(token)["room_organization_id"] == str(ORG)
    assert "room_organization_id" not in attributes(
        utils.generate_token(room="r", user=user)
    )


def test_generate_token_attributes_not_updatable_by_participant():
    """Participants cannot overwrite their attributes, so consumers can trust them."""
    token = utils.generate_token(room="r", user=UserFactory(), room_organization_id="x")
    payload = jwt.decode(
        token, settings.LIVEKIT_CONFIGURATION["api_secret"], algorithms=["HS256"]
    )
    assert payload["video"].get("canUpdateOwnMetadata", False) is False


@pytest.mark.parametrize("user", [None, "member", "outsider"])
def test_retrieve_room_token_has_room_organization(user):
    """Whoever joins, the attribute is the organization of the room."""
    room = RoomFactory(access_level=RoomAccessLevel.PUBLIC, organization_id=ORG)
    client = APIClient()
    if user is not None:
        organization = ORG if user == "member" else uuid.uuid4()
        client.force_login(UserFactory(organization_id=organization))
    response = client.get(f"/api/v1.0/rooms/{room.id}/")
    token = response.json()["livekit"]["token"]
    assert attributes(token)["room_organization_id"] == str(ORG)


def test_retrieve_room_without_organization_has_no_attribute():
    """No organization on the room: the attribute is omitted."""
    room = RoomFactory(access_level=RoomAccessLevel.PUBLIC, organization_id=None)
    response = APIClient().get(f"/api/v1.0/rooms/{room.id}/")
    assert "room_organization_id" not in attributes(response.json()["livekit"]["token"])


def test_lobby_token_has_room_organization():
    """The token issued through the lobby carries the attribute too."""
    room = RoomFactory(access_level=RoomAccessLevel.TRUSTED, organization_id=ORG)
    client = APIClient()
    client.force_login(UserFactory(organization_id=ORG))
    with mock.patch.object(utils, "notify_participants", return_value=None):
        response = client.post(
            f"/api/v1.0/rooms/{room.id}/request-entry/", {"username": "someone"}
        )
    assert response.json()["status"] == "accepted"
    token = response.json()["livekit"]["token"]
    assert attributes(token)["room_organization_id"] == str(ORG)
