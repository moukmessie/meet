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
