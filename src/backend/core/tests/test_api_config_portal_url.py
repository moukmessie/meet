"""Tests for the `portal_url` entry of the frontend configuration."""

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_config_portal_url_is_empty_by_default():
    """Without PORTAL_URL the frontend keeps the upstream behaviour."""
    response = APIClient().get("/api/v1.0/config/")

    assert response.status_code == 200
    assert response.json()["portal_url"] is None


def test_config_exposes_portal_url(settings):
    """The frontend reads the portal address from /config/."""
    settings.FRONTEND_CONFIGURATION = {
        **settings.FRONTEND_CONFIGURATION,
        "portal_url": "https://portal.example.com",
    }

    response = APIClient().get("/api/v1.0/config/")

    assert response.status_code == 200
    assert response.json()["portal_url"] == "https://portal.example.com"
