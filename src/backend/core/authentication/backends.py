"""Authentication Backends for the Meet core app."""

import logging
import uuid

from django.conf import settings
from django.core.exceptions import (
    SuspiciousOperation,
    ValidationError,
)
from django.utils.translation import gettext_lazy as _

from lasuite.marketing.tasks import create_or_update_contact
from lasuite.oidc_login.backends import (
    OIDCAuthenticationBackend as LaSuiteOIDCAuthenticationBackend,
)
from rest_framework.authentication import SessionAuthentication

from core.models import User
from core.validators import sub_validator

logger = logging.getLogger(__name__)


def get_organization_id(claim):
    """Return the organization id found in the OIDC 'organization' claim.

    The expected format is the one of the Keycloak "Organization Membership"
    mapper with the organization id enabled: {"<alias>": {"id": "<uuid>"}}.
    Only the id identifies the organization, the alias may change.

    A user without organization, with several organizations or with a claim
    in an unexpected format gets None: the login is not refused, but the user
    has no organization.
    """
    if not claim:
        return None
    if not isinstance(claim, dict) or len(claim) != 1:
        logger.warning(
            "Ignoring 'organization' claim: expected exactly one organization"
        )
        return None
    (value,) = claim.values()
    try:
        return uuid.UUID(str(value["id"]))
    except (TypeError, KeyError, ValueError):
        logger.warning("Ignoring 'organization' claim: invalid organization id")
        return None


class OIDCAuthenticationBackend(LaSuiteOIDCAuthenticationBackend):
    """Custom OpenID Connect (OIDC) Authentication Backend.

    This class overrides the default OIDC Authentication Backend to accommodate differences
    in the User and Identity models, and handles signed and/or encrypted UserInfo response.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Organization id read from the last user info (see get_organization_id)
        self._organization_id = None

    def get_extra_claims(self, user_info):
        """
        Return extra claims from user_info.

        Args:
          user_info (dict): The user information dictionary.

        Returns:
          dict: A dictionary of extra claims.

        """
        # Kept aside: applied in post_get_or_create_user, even when it becomes empty
        self._organization_id = get_organization_id(user_info.get("organization"))
        return {
            # Get user's full name from OIDC fields defined in settings
            "full_name": self.compute_full_name(user_info),
            "short_name": user_info.get(settings.OIDC_USERINFO_SHORTNAME_FIELD),
        }

    def post_get_or_create_user(self, user, claims, is_new_user):
        """
        Post-processing after user creation or retrieval.

        Args:
          user (User): The user instance.
          claims (dict): The claims dictionary.
          is_new_user (bool): Indicates if the user was newly created.

        Returns:
        - None

        """
        if user.organization_id != self._organization_id:
            user.organization_id = self._organization_id
            user.save(update_fields=["organization_id"])

        email = claims["email"]
        if is_new_user and email and settings.SIGNUP_NEW_USER_TO_MARKETING_EMAIL:
            self.signup_to_marketing_email(email)

    @staticmethod
    def signup_to_marketing_email(email):
        """Add the user to the newsletter list on sign-in.

        Uses the team's standard Brevo integration, dispatching the contact
        creation/update as an asynchronous task to keep authentication fast.
        """
        create_or_update_contact.delay(
            email=email,
            attributes={"VISIO_SOURCE": ["SIGNIN"]},
        )

    def get_existing_user(self, sub, email):
        """Fetch existing user by sub or email."""

        sub = str(sub)

        try:
            sub_validator(sub)
        except ValidationError as err:
            raise SuspiciousOperation(
                "User info contained an invalid sub claim"
            ) from err

        try:
            return User.objects.get(sub=sub)
        except User.DoesNotExist:
            if email and settings.OIDC_FALLBACK_TO_EMAIL_FOR_IDENTIFICATION:
                try:
                    return User.objects.get(email__iexact=email)
                except User.DoesNotExist:
                    pass
                except User.MultipleObjectsReturned as e:
                    raise SuspiciousOperation(
                        "Multiple user accounts share a common email."
                    ) from e
        return None


class SessionAuthenticationWith401(SessionAuthentication):
    """
    Identical to DRF's SessionAuthentication, but returns a WWW-Authenticate
    header so unauthenticated requests get a 401 instead of a 403.

    The scheme is deliberately NOT 'Basic' — that would trigger the browser's
    native login popup. 'Session' is ignored by the browser's auth UI but is
    still truthy, so DRF keeps the status at 401.
    """

    def authenticate_header(self, request):
        return "Session"
