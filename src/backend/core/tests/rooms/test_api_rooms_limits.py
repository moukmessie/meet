"""Room limits read from an external service (ROOM_LIMITS_URL)."""

# pylint: disable=redefined-outer-name,unused-argument
import logging
import uuid

from django.conf import settings

import jwt
import pytest
import requests
import responses
from rest_framework.test import APIClient

from core.factories import RoomFactory, UserFactory
from core.models import RoomAccessLevel

pytestmark = pytest.mark.django_db

LIMITS_URL = "http://platform.test/room-limits"
ORG = uuid.uuid4()
QUOTA = {
    "limit": 6000,
    "used": 6000,
    "remaining": 0,
    "resets_at": "2026-12-01T00:00:00Z",
}


@pytest.fixture
def limits_enabled(settings):
    """Enable the room limits."""
    settings.ROOM_LIMITS_URL = LIMITS_URL
    settings.ROOM_LIMITS_TOKEN = "limits-token"


def get_room(room):
    """Retrieve a room as an anonymous user (public room)."""
    return APIClient().get(f"/api/v1.0/rooms/{room.id}/")


def room_payload(response):
    """LiveKit token claims of a retrieve response."""
    token = response.json()["livekit"]["token"]
    return jwt.decode(
        token, settings.LIVEKIT_CONFIGURATION["api_secret"], algorithms=["HS256"]
    )


def public_room(**kwargs):
    """A public room of the test organization."""
    return RoomFactory(access_level=RoomAccessLevel.PUBLIC, **kwargs)


@responses.activate
def test_max_participants_in_token_room_config(limits_enabled):
    """The limit goes to the room configuration of the token, with the auth header."""
    responses.post(
        LIMITS_URL,
        json={"max_participants": 25, "entry_refused_reason": None, "quota": None},
    )

    response = get_room(public_room(organization_id=ORG))

    assert response.status_code == 200
    assert room_payload(response)["roomConfig"]["maxParticipants"] == 25
    call = responses.calls[0].request
    assert call.headers["Authorization"] == "Bearer limits-token"
    assert call.body == f'{{"organization_id": "{ORG}"}}'.encode()


@responses.activate
def test_null_max_participants_adds_no_room_config(limits_enabled):
    """No limit: the token is identical to the default one."""
    responses.post(
        LIMITS_URL,
        json={"max_participants": None, "entry_refused_reason": None, "quota": None},
    )

    response = get_room(public_room(organization_id=ORG))

    assert response.status_code == 200
    assert "roomConfig" not in room_payload(response)


@responses.activate
def test_dedicated_token_falls_back_to_creation_check_token(settings):
    """Without a dedicated token, the room creation check token is reused."""
    settings.ROOM_LIMITS_URL = LIMITS_URL
    settings.ROOM_LIMITS_TOKEN = None
    settings.ROOM_CREATION_CHECK_TOKEN = "shared-token"
    responses.post(LIMITS_URL, json={"max_participants": None})

    get_room(public_room(organization_id=ORG))

    assert responses.calls[0].request.headers["Authorization"] == "Bearer shared-token"


@responses.activate
def test_entry_refused(limits_enabled):
    """Negative test: monthly minutes exhausted, no token at all."""
    responses.post(
        LIMITS_URL,
        json={
            "max_participants": None,
            "entry_refused_reason": "monthly_minutes_exhausted",
            "quota": QUOTA,
        },
    )

    response = get_room(public_room(organization_id=ORG))

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "monthly_minutes_exhausted"
    assert body["quota"] == QUOTA
    assert "quota" in body["detail"]
    assert "livekit" not in body


@responses.activate
@pytest.mark.parametrize(
    "mock_response",
    [
        {"status": 404, "json": {"detail": "no"}},
        {"status": 500},
        {"status": 503, "json": {"entry_refused_reason": "monthly_minutes_exhausted"}},
        {"status": 403, "json": {"entry_refused_reason": "monthly_minutes_exhausted"}},
        {"status": 200, "body": "not json"},
        {"status": 200, "json": ["unexpected"]},
        {"body": requests.exceptions.ConnectionError("down")},
        {"body": requests.exceptions.Timeout("slow")},
    ],
)
def test_fails_open(limits_enabled, mock_response, caplog):
    """Negative test: any non-200 answer, error or bad body gives a limitless token."""
    responses.post(LIMITS_URL, **mock_response)

    with caplog.at_level(logging.WARNING, logger="core.services.room_limits"):
        response = get_room(public_room(organization_id=ORG))

    assert response.status_code == 200
    assert "roomConfig" not in room_payload(response)
    assert "Room limits unavailable" in caplog.text


@responses.activate
@pytest.mark.parametrize("value", [0, -3, True, "12", 1.5])
def test_invalid_max_participants_is_ignored(limits_enabled, value):
    """A malformed limit is not applied."""
    responses.post(LIMITS_URL, json={"max_participants": value})

    response = get_room(public_room(organization_id=ORG))

    assert response.status_code == 200
    assert "roomConfig" not in room_payload(response)


@responses.activate
@pytest.mark.parametrize("url", [None, ""])
def test_disabled_without_url(settings, url):
    """Empty setting: no call, upstream behavior."""
    settings.ROOM_LIMITS_URL = url
    responses.post(
        LIMITS_URL, json={"entry_refused_reason": "monthly_minutes_exhausted"}
    )

    response = get_room(public_room(organization_id=ORG))

    assert response.status_code == 200
    assert "roomConfig" not in room_payload(response)
    assert len(responses.calls) == 0


@responses.activate
def test_room_without_organization_makes_no_call(limits_enabled):
    """Rooms without organization are never limited."""
    responses.post(
        LIMITS_URL, json={"entry_refused_reason": "monthly_minutes_exhausted"}
    )

    response = get_room(public_room(organization_id=None))

    assert response.status_code == 200
    assert "roomConfig" not in room_payload(response)
    assert len(responses.calls) == 0


@responses.activate
def test_authenticated_member_is_limited_too(limits_enabled):
    """The limit applies whoever joins."""
    responses.post(LIMITS_URL, json={"max_participants": 5})
    client = APIClient()
    client.force_login(UserFactory(organization_id=ORG))
    room = public_room(organization_id=ORG)

    response = client.get(f"/api/v1.0/rooms/{room.id}/")

    assert room_payload(response)["roomConfig"]["maxParticipants"] == 5
