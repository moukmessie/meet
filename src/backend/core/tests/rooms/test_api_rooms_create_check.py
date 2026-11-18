"""Room creation checked by an external platform (ROOM_CREATION_CHECK_URL)."""

# pylint: disable=redefined-outer-name,unused-argument
import json
import uuid

import pytest
import requests
import responses
from rest_framework.test import APIClient

from core.factories import UserFactory
from core.models import ApplicationScope, Room
from core.tests.test_external_api_rooms import generate_test_token

pytestmark = pytest.mark.django_db

CHECK_URL = "http://platform.test/room-creation-check"


@pytest.fixture
def check_enabled(settings):
    """Enable the room creation check."""
    settings.ROOM_CREATION_CHECK_URL = CHECK_URL
    settings.ROOM_CREATION_CHECK_TOKEN = "check-token"


def create_room(user):
    """Create a room with the frontend API."""
    client = APIClient()
    client.force_login(user)
    return client.post("/api/v1.0/rooms/", {"name": "my room"})


def create_room_external(user):
    """Create a room with the external API."""
    token = generate_test_token(user, [ApplicationScope.ROOMS_CREATE])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client.post("/external-api/v1.0/rooms/", {}, format="json")


CREATE = pytest.mark.parametrize("create", [create_room, create_room_external])


@CREATE
def test_check_disabled_by_default(create):
    """Without URL, rooms are created as upstream, organization or not."""
    response = create(UserFactory())
    assert response.status_code == 201


@CREATE
@responses.activate
def test_allowed_creation(check_enabled, create):
    """The platform receives the organization and allows the creation."""
    org_id = uuid.uuid4()
    user = UserFactory(organization_id=org_id)
    responses.post(CHECK_URL, json={"allowed": True})

    response = create(user)

    assert response.status_code == 201
    call = responses.calls[0].request
    assert call.headers["Authorization"] == "Bearer check-token"
    assert json.loads(call.body) == {
        "organization_id": str(org_id),
        "user_sub": user.sub,
    }


@CREATE
@responses.activate
def test_user_without_organization_is_refused(check_enabled, create):
    """Negative test: no organization, no room, and no call to the platform."""
    response = create(UserFactory())

    assert response.status_code == 403
    assert Room.objects.exists() is False
    assert len(responses.calls) == 0


@CREATE
@responses.activate
def test_refused_by_the_platform(check_enabled, create):
    """Negative test: quota reached."""
    responses.post(
        CHECK_URL, json={"allowed": False, "reason": "concurrent_rooms_limit"}
    )

    response = create(UserFactory(organization_id=uuid.uuid4()))

    assert response.status_code == 403
    assert Room.objects.exists() is False


@CREATE
@responses.activate
@pytest.mark.parametrize(
    "mock_response",
    [
        {"status": 500},
        {"status": 404},
        {"body": "not json"},
        {"json": ["allowed"]},
        {"json": {}},
        {"json": {"allowed": "yes"}},
        {"body": requests.ConnectTimeout()},
        {"body": requests.ConnectionError()},
    ],
)
def test_platform_failure_refuses_the_creation(check_enabled, create, mock_response):
    """Fail closed: errors, timeouts and unexpected answers refuse the creation."""
    responses.post(CHECK_URL, **mock_response)

    response = create(UserFactory(organization_id=uuid.uuid4()))

    assert response.status_code == 403
    assert Room.objects.exists() is False


@responses.activate
def test_refusal_body_carries_code_and_quota(check_enabled):
    """The 403 body gives the reason as code and the quota, next to the detail."""
    quota = {
        "limit": 600,
        "used": 600,
        "remaining": 0,
        "resets_at": "2026-12-01T00:00:00Z",
    }
    responses.post(
        CHECK_URL,
        json={"allowed": False, "reason": "monthly_minutes_exhausted", "quota": quota},
    )

    response = create_room(UserFactory(organization_id=uuid.uuid4()))

    assert response.status_code == 403
    assert response.json() == {
        "detail": "You are not allowed to create a room.",
        "code": "monthly_minutes_exhausted",
        "quota": quota,
    }


@responses.activate
def test_refusal_without_quota_has_no_quota_key(check_enabled):
    """Without quota from the platform, the body has no quota key."""
    responses.post(
        CHECK_URL, json={"allowed": False, "reason": "concurrent_rooms_limit"}
    )

    response = create_room(UserFactory(organization_id=uuid.uuid4()))

    assert response.status_code == 403
    assert response.json()["code"] == "concurrent_rooms_limit"
    assert "quota" not in response.json()


@responses.activate
@pytest.mark.parametrize(
    "answer",
    [
        {"allowed": False},
        {"allowed": False, "reason": ""},
        {"allowed": False, "reason": 42},
        {"allowed": False, "reason": "Not a <code>"},
        {"allowed": False, "reason": "x" * 200},
        {"allowed": False, "reason": "refused", "quota": "bad"},
    ],
)
def test_unknown_or_malformed_reason_falls_back_to_refused(check_enabled, answer):
    """Negative test: a malformed reason or quota is not forwarded."""
    responses.post(CHECK_URL, json=answer)

    response = create_room(UserFactory(organization_id=uuid.uuid4()))

    assert response.status_code == 403
    assert response.json()["code"] == "refused"
    assert "quota" not in response.json()


@responses.activate
def test_unavailable_platform_gives_check_unavailable_code(check_enabled):
    """An unavailable platform gives the check_unavailable code."""
    responses.post(CHECK_URL, status=500)

    response = create_room(UserFactory(organization_id=uuid.uuid4()))

    assert response.status_code == 403
    assert response.json()["code"] == "check_unavailable"


def test_no_organization_gives_no_organization_code(check_enabled):
    """A user without organization gets the no_organization code."""
    response = create_room(UserFactory())

    assert response.status_code == 403
    assert response.json()["code"] == "no_organization"
