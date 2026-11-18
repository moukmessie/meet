"""Room limits applied to the lobby: entry requests and admission."""

# pylint: disable=W0621,W0613
import uuid
from unittest import mock

from django.conf import settings as django_settings

import jwt
import pytest
import requests
import responses
from rest_framework.test import APIClient

from core import utils
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
REFUSED = {
    "max_participants": None,
    "entry_refused_reason": "monthly_minutes_exhausted",
    "quota": QUOTA,
}
ALLOWED = {"max_participants": 5, "entry_refused_reason": None, "quota": None}


@pytest.fixture(autouse=True)
def limits_enabled(settings):
    """Enable the room limits and silence lobby notifications."""
    settings.ROOM_LIMITS_URL = LIMITS_URL
    settings.ROOM_LIMITS_TOKEN = "limits-token"
    with mock.patch.object(utils, "notify_participants", return_value=None):
        yield


def trusted_room(**kwargs):
    """A trusted room (anonymous users go through the lobby)."""
    return RoomFactory(access_level=RoomAccessLevel.TRUSTED, **kwargs)


def request_entry(room, client=None, **data):
    """Request entry to a room."""
    return (client or APIClient()).post(
        f"/api/v1.0/rooms/{room.id}/request-entry/", {"username": "guest", **data}
    )


def assert_refused(response):
    """The refusal is the one of the token generation."""
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "monthly_minutes_exhausted"
    assert body["quota"] == QUOTA
    assert "quota" in body["detail"]
    assert "livekit" not in body


def claims(response):
    """LiveKit token claims of a request-entry response."""
    return jwt.decode(
        response.json()["livekit"]["token"],
        django_settings.LIVEKIT_CONFIGURATION["api_secret"],
        algorithms=["HS256"],
    )


@responses.activate
def test_anonymous_refused_before_waiting():
    """Negative test: quota used up, the anonymous user is refused, not queued."""
    responses.post(LIMITS_URL, json=REFUSED)
    room = trusted_room(organization_id=ORG)

    response = request_entry(room)

    assert_refused(response)
    waiting = APIClient().get(f"/api/v1.0/rooms/{room.id}/waiting-participants/")
    assert waiting.status_code in (401, 403)
    owner = UserFactory()
    room.accesses.create(user=owner, role="owner")
    client = APIClient()
    client.force_login(owner)
    assert (
        client.get(f"/api/v1.0/rooms/{room.id}/waiting-participants/").json()[
            "participants"
        ]
        == []
    )


@responses.activate
def test_authenticated_refused_the_same_way():
    """An authenticated user of another organization is refused too."""
    responses.post(LIMITS_URL, json=REFUSED)
    room = trusted_room(organization_id=ORG)
    client = APIClient()
    client.force_login(UserFactory(organization_id=ORG))

    assert_refused(request_entry(room, client))


@responses.activate
def test_anonymous_waits_under_quota():
    """Under quota the anonymous user waits as before."""
    responses.post(LIMITS_URL, json=ALLOWED)
    room = trusted_room(organization_id=ORG)

    response = request_entry(room)

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    assert response.json()["livekit"] is None


@responses.activate
def test_polling_is_refused_when_quota_runs_out_while_waiting():
    """Negative test: the quota used up during the wait stops the polling."""
    responses.post(LIMITS_URL, json=ALLOWED)
    room = trusted_room(organization_id=ORG)
    first = request_entry(room)
    assert first.json()["status"] == "waiting"

    responses.replace(responses.POST, LIMITS_URL, json=REFUSED)
    assert_refused(request_entry(room, participant_id=first.json()["id"]))


@responses.activate
@pytest.mark.parametrize(
    "mock_response",
    [
        {"status": 500},
        {"status": 404, "json": {}},
        {"status": 200, "body": "not json"},
        {"body": requests.exceptions.ConnectionError("down")},
        {"body": requests.exceptions.Timeout("slow")},
    ],
)
def test_service_unavailable_fails_open(mock_response):
    """Unavailable service: the anonymous user waits, as without the feature."""
    responses.post(LIMITS_URL, **mock_response)
    room = trusted_room(organization_id=ORG)

    response = request_entry(room)

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"


@responses.activate
def test_room_without_organization_makes_no_call():
    """Upstream behavior: no organization, no call, the user waits."""
    room = trusted_room(organization_id=None)

    response = request_entry(room)

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    assert len(responses.calls) == 0


@responses.activate
def test_disabled_without_url_makes_no_call(settings):
    """Feature disabled: no call."""
    settings.ROOM_LIMITS_URL = ""
    room = trusted_room(organization_id=ORG)

    assert request_entry(room).json()["status"] == "waiting"
    assert len(responses.calls) == 0


def admit(room, participant_id):
    """The owner of the room admits a waiting participant."""
    owner = UserFactory()
    room.accesses.create(user=owner, role="owner")
    client = APIClient()
    client.force_login(owner)
    response = client.post(
        f"/api/v1.0/rooms/{room.id}/enter/",
        {"participant_id": participant_id, "allow_entry": True},
    )
    assert response.status_code == 200


@responses.activate
def test_admission_token_carries_max_participants():
    """The token delivered after admission goes through room-limits."""
    responses.post(LIMITS_URL, json=ALLOWED)
    room = trusted_room(organization_id=ORG)
    first = request_entry(room)
    signed_id = first.json()["id"]
    raw_id = signed_id.split(":")[0]

    admit(room, raw_id)
    response = request_entry(room, participant_id=signed_id)

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert claims(response)["roomConfig"]["maxParticipants"] == 5


@responses.activate
def test_admission_cannot_bypass_quota():
    """Negative test: an admitted participant gets no token once the quota is used up."""
    responses.post(LIMITS_URL, json=ALLOWED)
    room = trusted_room(organization_id=ORG)
    first = request_entry(room)
    signed_id = first.json()["id"]

    admit(room, signed_id.split(":")[0])
    responses.replace(responses.POST, LIMITS_URL, json=REFUSED)

    assert_refused(request_entry(room, participant_id=signed_id))
