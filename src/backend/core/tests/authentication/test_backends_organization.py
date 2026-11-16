"""Organization of the user, copied from the OIDC 'organization' claim."""

import uuid

import pytest

from core.authentication.backends import OIDCAuthenticationBackend, get_organization_id
from core.factories import UserFactory

pytestmark = pytest.mark.django_db

ORG_ID = uuid.uuid4()


def login(monkeypatch, user_info):
    """Run the claims part of the OIDC login with the given user info."""
    monkeypatch.setattr(
        OIDCAuthenticationBackend, "get_userinfo", lambda *args: user_info
    )
    return OIDCAuthenticationBackend().get_or_create_user(
        access_token="test-token", id_token=None, payload=None
    )


@pytest.mark.parametrize(
    "claim, expected",
    [
        ({"acme": {"id": str(ORG_ID)}}, ORG_ID),
        (None, None),
        ({}, None),
        # several organizations: no organization rights
        ({"a": {"id": str(ORG_ID)}, "b": {"id": str(uuid.uuid4())}}, None),
        # unexpected formats
        (["acme"], None),
        ("acme", None),
        ({"acme": {}}, None),
        ({"acme": "id"}, None),
        ({"acme": {"id": "not-a-uuid"}}, None),
    ],
)
def test_get_organization_id(claim, expected):
    """Only one organization with a valid id is accepted."""
    assert get_organization_id(claim) == expected


def test_new_user_gets_the_organization(monkeypatch):
    """The organization of a new user is copied from the claim."""
    user = login(
        monkeypatch,
        {
            "sub": "new-sub",
            "email": "a@example.com",
            "organization": {"acme": {"id": str(ORG_ID)}},
        },
    )
    user.refresh_from_db()
    assert user.organization_id == ORG_ID


def test_organization_is_updated_at_each_login(monkeypatch):
    """A user moved to another organization gets the new one at the next login."""
    user = UserFactory(organization_id=uuid.uuid4())
    login(
        monkeypatch,
        {
            "sub": user.sub,
            "email": user.email,
            "organization": {"acme": {"id": str(ORG_ID)}},
        },
    )
    user.refresh_from_db()
    assert user.organization_id == ORG_ID


def test_organization_is_cleared_when_the_claim_disappears(monkeypatch):
    """A user removed from the organization loses it at the next login."""
    user = UserFactory(organization_id=ORG_ID)
    login(monkeypatch, {"sub": user.sub, "email": user.email})
    user.refresh_from_db()
    assert user.organization_id is None


def test_several_organizations_do_not_refuse_the_login(monkeypatch):
    """The user can still join meetings as a guest, without organization."""
    claim = {"a": {"id": str(ORG_ID)}, "b": {"id": str(uuid.uuid4())}}
    user = login(
        monkeypatch, {"sub": "multi", "email": "m@example.com", "organization": claim}
    )
    user.refresh_from_db()
    assert user.organization_id is None
