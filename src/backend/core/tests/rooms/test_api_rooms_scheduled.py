"""Rooms of planned meetings, created on first entry (SCHEDULED_ROOMS_URL)."""

# pylint: disable=redefined-outer-name,unused-argument
import json
import uuid
from datetime import timedelta
from unittest import mock

from django.utils import timezone

import pytest
import requests
import responses
from rest_framework.test import APIClient

from core.factories import RoomFactory, UserFactory
from core.models import ResourceAccess, RoleChoices, Room

pytestmark = pytest.mark.django_db

LOOKUP_URL = "http://platform.test/scheduled-meeting"
ROOM_URL = "http://platform.test/scheduled-meeting-room"
CHECK_URL = "http://platform.test/room-creation-check"
SLUG = "abc-defg-hij"
ORG = uuid.uuid4()


@pytest.fixture(autouse=True)
def scheduled_enabled(settings):
    """Enable the feature, with the creation check."""
    settings.SCHEDULED_ROOMS_URL = LOOKUP_URL
    settings.SCHEDULED_ROOMS_ROOM_URL = ROOM_URL
    settings.ROOM_CREATION_CHECK_URL = CHECK_URL
    settings.ROOM_CREATION_CHECK_TOKEN = "check-token"
    settings.ALLOW_UNREGISTERED_ROOMS = False


def meeting(**overrides):
    """Answer of the platform for a meeting starting in 5 minutes."""
    now = timezone.now()
    body = {
        "exists": True,
        "organization_id": str(ORG),
        "organizer_sub": None,
        "status": "scheduled",
        "starts_at": (now + timedelta(minutes=5)).isoformat(),
        "ends_at": (now + timedelta(minutes=65)).isoformat(),
        "room_id": None,
        "user_may_open": True,
        "refused_reason": None,
    }
    body.update(overrides)
    return body


def minutes(delta):
    """ISO date `delta` minutes from now."""
    return (timezone.now() + timedelta(minutes=delta)).isoformat()


def organizer():
    """A user of the organization of the meeting."""
    return UserFactory(organization_id=ORG)


def enter(user=None, slug=SLUG):
    """First entry: get the room by its slug."""
    client = APIClient()
    if user is not None:
        client.force_login(user)
    return client.get(f"/api/v1.0/rooms/{slug}/")


def mock_platform(lookup=None, check=None, **kwargs):
    """Register the three platform routes."""
    responses.post(LOOKUP_URL, json=lookup or meeting(), **kwargs)
    responses.post(CHECK_URL, json=check or {"allowed": True})
    responses.post(ROOM_URL, json={"bound": True})


def calls(url):
    """Requests received by a platform route."""
    return [call.request for call in responses.calls if call.request.url == url]


# Creation


@responses.activate
def test_first_entry_creates_the_room_of_the_organization():
    """The room takes the slug and the organization of the meeting; the user owns it."""
    user = organizer()
    mock_platform()

    response = enter(user)

    assert response.status_code == 200
    room = Room.objects.get(slug=SLUG)
    assert room.organization_id == ORG
    assert response.json()["id"] == str(room.id)
    assert response.json()["livekit"]["room"] == str(room.id)
    assert ResourceAccess.objects.get(resource=room).user == user
    assert ResourceAccess.objects.get(resource=room).role == RoleChoices.OWNER
    sent = json.loads(calls(LOOKUP_URL)[0].body)
    assert sent == {"slug": SLUG, "user_sub": user.sub}
    assert calls(LOOKUP_URL)[0].headers["Authorization"] == "Bearer check-token"
    assert json.loads(calls(CHECK_URL)[0].body) == {
        "organization_id": str(ORG),
        "user_sub": user.sub,
    }
    assert json.loads(calls(ROOM_URL)[0].body) == {
        "slug": SLUG,
        "room_id": str(room.id),
    }


@responses.activate
def test_the_organizer_also_owns_the_room_when_an_administrator_opens_it():
    """The organizer, known to Meet by its sub, becomes owner too."""
    host = organizer()
    admin = organizer()
    mock_platform(lookup=meeting(organizer_sub=host.sub))

    assert enter(admin).status_code == 200

    owners = ResourceAccess.objects.filter(
        resource__room__slug=SLUG, role=RoleChoices.OWNER
    )
    assert {access.user for access in owners} == {host, admin}


@responses.activate
def test_second_entry_does_not_ask_the_platform_again():
    """Idempotent: the room exists, the following entries are upstream ones."""
    user = organizer()
    mock_platform()
    enter(user)
    lookups = len(calls(LOOKUP_URL))

    response = enter(user)

    assert response.status_code == 200
    assert Room.objects.filter(slug=SLUG).count() == 1
    assert len(calls(LOOKUP_URL)) == lookups
    assert len(calls(CHECK_URL)) == 1


@responses.activate
def test_simultaneous_first_entries_create_a_single_room():
    """The loser of the race reads the room of the winner."""
    first, second = organizer(), organizer()
    mock_platform()
    real_check = __import__(
        "core.services.scheduled_rooms", fromlist=["x"]
    ).ensure_room_creation_allowed

    def other_request_wins(user):
        real_check(user)
        # Between the check and the creation, the other entry creates the room.
        RoomFactory(name=SLUG, organization_id=ORG)

    with mock.patch(
        "core.services.scheduled_rooms.ensure_room_creation_allowed",
        side_effect=other_request_wins,
    ):
        response = enter(first)

    assert response.status_code == 200
    assert Room.objects.filter(slug=SLUG).count() == 1
    assert response.json()["id"] == str(Room.objects.get(slug=SLUG).id)
    assert enter(second).status_code == 200
    assert Room.objects.filter(slug=SLUG).count() == 1


@responses.activate
def test_the_platform_is_not_told_when_the_room_creation_fails():
    """No room, no announcement."""
    mock_platform(check={"allowed": False, "reason": "concurrent_rooms_limit"})

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == "concurrent_rooms_limit"
    assert not Room.objects.exists()
    assert calls(ROOM_URL) == []


@responses.activate
def test_announcement_failure_does_not_prevent_the_entry():
    """The room is created even if the platform cannot be told about it."""
    responses.post(LOOKUP_URL, json=meeting())
    responses.post(CHECK_URL, json={"allowed": True})
    responses.post(ROOM_URL, body=requests.ConnectionError())

    assert enter(organizer()).status_code == 200
    assert Room.objects.filter(slug=SLUG).exists()


# Time window


@responses.activate
@pytest.mark.parametrize("start", [15 - 1, 0, -30])
def test_room_opens_within_the_window(start):
    """From 15 minutes before the start until the end."""
    mock_platform(lookup=meeting(starts_at=minutes(start), ends_at=minutes(start + 60)))

    assert enter(organizer()).status_code == 200


@responses.activate
def test_too_early_is_refused_and_nothing_is_created():
    """Negative test: more than 15 minutes before the start."""
    mock_platform(lookup=meeting(starts_at=minutes(20), ends_at=minutes(80)))

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == "scheduled_meeting_not_started"
    assert not Room.objects.exists()
    assert calls(CHECK_URL) == []


@responses.activate
def test_early_entry_tolerance_is_configurable(settings):
    """The tolerance before the start is a setting."""
    settings.SCHEDULED_ROOMS_EARLY_ENTRY_MINUTES = 30
    mock_platform(lookup=meeting(starts_at=minutes(20), ends_at=minutes(80)))

    assert enter(organizer()).status_code == 200


@responses.activate
def test_after_the_end_is_refused():
    """Negative test: nothing is tolerated after the end."""
    mock_platform(lookup=meeting(starts_at=minutes(-90), ends_at=minutes(-1)))

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == "scheduled_meeting_ended"
    assert not Room.objects.exists()


# State and access


@responses.activate
def test_canceled_meeting_is_refused():
    """Negative test: a canceled meeting never opens, whoever asks."""
    mock_platform(lookup=meeting(status="canceled"))

    for user in (organizer(), None):
        response = enter(user)
        assert response.status_code == 403
        assert response.json()["code"] == "scheduled_meeting_canceled"
    assert not Room.objects.exists()


@responses.activate
@pytest.mark.parametrize(
    "refused_reason", ["scheduling_not_available", "tenant_inactive"]
)
def test_refusal_decided_by_the_platform(refused_reason):
    """Plan without scheduling or inactive organization: the platform says so."""
    mock_platform(lookup=meeting(refused_reason=refused_reason))

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == refused_reason
    assert not Room.objects.exists()


@responses.activate
def test_anonymous_user_cannot_open_the_room():
    """Negative test: a guest waits for the organizer."""
    mock_platform()

    response = enter(None)

    assert response.status_code == 403
    assert response.json()["code"] == "scheduled_meeting_not_opened"
    assert not Room.objects.exists()
    assert calls(CHECK_URL) == []


@responses.activate
def test_member_who_may_not_open_is_refused():
    """The platform decides (organizer or administrator only)."""
    mock_platform(lookup=meeting(user_may_open=False))

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == "scheduled_meeting_not_opened"
    assert not Room.objects.exists()


@responses.activate
def test_user_of_another_organization_is_refused_even_if_the_platform_agrees():
    """Negative test: the signed organization of the user must match the meeting."""
    mock_platform()

    for other in (UserFactory(organization_id=uuid.uuid4()), UserFactory()):
        response = enter(other)
        assert response.status_code == 403
        assert response.json()["code"] == "scheduled_meeting_not_opened"
    assert not Room.objects.exists()


@responses.activate
def test_guest_enters_once_the_room_exists():
    """After the opening, the link works as for any room (no more platform call)."""
    mock_platform()
    enter(organizer())
    lookups = len(calls(LOOKUP_URL))

    response = enter(None)

    assert response.status_code == 200
    assert len(calls(LOOKUP_URL)) == lookups


# Quota and platform failures


@responses.activate
def test_creation_check_refusal_is_reported_with_its_code():
    """Quota and limits are those of the creation check."""
    mock_platform(
        check={
            "allowed": False,
            "reason": "monthly_minutes_exhausted",
            "quota": {"limit": 300, "used": 300, "remaining": 0},
        }
    )

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == "monthly_minutes_exhausted"
    assert response.json()["quota"]["remaining"] == 0
    assert not Room.objects.exists()


@responses.activate
def test_creation_check_unavailable_fails_closed():
    """The creation stays fail closed."""
    responses.post(LOOKUP_URL, json=meeting())
    responses.post(CHECK_URL, status=500)

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == "check_unavailable"
    assert not Room.objects.exists()


@responses.activate
@pytest.mark.parametrize(
    "mock_response",
    [
        {"status": 500},
        {"status": 404},
        {"body": "not json"},
        {"json": ["exists"]},
        {"json": {}},
        {"json": {"exists": "yes"}},
        {"json": {"exists": True}},
        {"json": meeting(status="done")},
        {"json": meeting(starts_at="tomorrow")},
        {"json": meeting(organization_id="not-a-uuid")},
        {"body": requests.ConnectTimeout()},
        {"body": requests.ConnectionError()},
    ],
)
def test_lookup_unavailable_fails_closed_for_a_user(mock_response):
    """Negative test: no answer, no room."""
    responses.post(LOOKUP_URL, **mock_response)

    response = enter(organizer())

    assert response.status_code == 403
    assert response.json()["code"] == "check_unavailable"
    assert not Room.objects.exists()
    assert calls(CHECK_URL) == []


@responses.activate
def test_lookup_unavailable_keeps_upstream_behavior_for_anonymous():
    """An anonymous user cannot create anything: plain not found."""
    responses.post(LOOKUP_URL, status=500)

    assert enter(None).status_code == 404


# Unchanged behavior


@responses.activate
def test_slug_unknown_to_the_platform_is_not_found():
    """Unknown to Meet and to the platform: upstream 404."""
    responses.post(LOOKUP_URL, json={"exists": False})

    assert enter(organizer()).status_code == 404
    assert not Room.objects.exists()


@responses.activate
@pytest.mark.parametrize(
    "slug",
    ["standup", "ABC-defg-hij-k", "abcd-efg-hij", "abc_defg_hij", "abc-defg-hi1"],
)
def test_other_slugs_never_reach_the_platform(slug):
    """Only identifiers of the reserved format are looked up."""
    assert enter(organizer(), slug=slug).status_code == 404
    assert len(responses.calls) == 0


@responses.activate
def test_uuid_never_reaches_the_platform():
    """Rooms can also be read by id."""
    assert enter(organizer(), slug=str(uuid.uuid4())).status_code == 404
    assert len(responses.calls) == 0


@responses.activate
def test_disabled_without_url(settings):
    """Without URL the behavior is upstream's, with no call."""
    settings.SCHEDULED_ROOMS_URL = None

    assert enter(organizer()).status_code == 404
    assert len(responses.calls) == 0


@responses.activate
def test_existing_room_is_untouched():
    """A room already in Meet never goes through the platform."""
    room = RoomFactory(name=SLUG, organization_id=None)

    response = enter(organizer())

    assert response.status_code == 200
    assert response.json()["id"] == str(room.id)
    assert len(responses.calls) == 0
    room.refresh_from_db()
    assert room.organization_id is None


@responses.activate
def test_unregistered_rooms_setting_is_still_honored(settings):
    """Unknown to the platform: the upstream unregistered room, id-less."""
    settings.ALLOW_UNREGISTERED_ROOMS = True
    responses.post(LOOKUP_URL, json={"exists": False})

    response = enter(organizer())

    assert response.status_code == 200
    assert response.json()["id"] is None
    assert not Room.objects.exists()
