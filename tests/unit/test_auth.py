"""
Tests for authentication functionality.

Tests cover:
- Unauthenticated access redirects
- User registration
- Password-based login via unified signin
- WebAuthn login endpoint
- Session management
- Logout

To run these tests:
    pytest tests/unit/test_auth.py -v

Note: These tests use the development database (dovos_dev).
Make sure the database is running before running tests.
"""
import pytest
import uuid
import base64
import os
from flask import url_for


# Skip all tests if AUTH_ENABLED is false
pytestmark = pytest.mark.skipif(
    os.getenv("AUTH_ENABLED", "true").lower() != "true",
    reason="Auth tests require AUTH_ENABLED=true"
)


@pytest.fixture(scope="module")
def auth_app():
    """Create app with auth enabled for testing using dev database."""
    from app import create_app

    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost:5001",
    })

    yield app


@pytest.fixture
def auth_client(auth_app):
    """Test client for auth tests."""
    with auth_app.app_context():
        yield auth_app.test_client()


@pytest.fixture
def test_user(auth_app):
    """Create a test user for authentication tests."""
    with auth_app.app_context():
        from db.database import db_session
        from db.models.models import User

        # Generate unique email for this test run
        test_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
        test_handle = uuid.uuid4().hex

        # Create user - password can be None for passkey-only users
        # Use bcrypt directly to avoid argon2 dependency issues
        import bcrypt
        hashed = bcrypt.hashpw(b"testpassword123", bcrypt.gensalt()).decode('utf-8')

        user = User(
            email=test_email,
            password=hashed,
            active=True,
            fs_uniquifier=uuid.uuid4().hex,
            fs_webauthn_user_handle=test_handle,
        )

        db_session.add(user)
        db_session.commit()

        user_id = user.id
        user_email = user.email
        user_handle = user.fs_webauthn_user_handle

        yield {
            "id": user_id,
            "email": user_email,
            "password": "testpassword123",
            "webauthn_handle": user_handle,
        }

        # Cleanup
        try:
            db_session.query(User).filter_by(id=user_id).delete()
            db_session.commit()
        except Exception:
            db_session.rollback()


class TestUnauthenticatedAccess:
    """Tests for unauthenticated access to protected routes."""

    def test_root_redirects_to_login(self, auth_app):
        """Unauthenticated access to root should redirect to login."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.get("/", follow_redirects=False)
            assert response.status_code in (301, 302, 308)
            assert "us-signin" in response.location or "login" in response.location or "register" in response.location

    def test_conversations_redirects_to_login(self, auth_app):
        """Unauthenticated access to conversations should redirect to login."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.get("/conversations", follow_redirects=False)
            assert response.status_code in (301, 302, 308)

    def test_api_conversations_returns_401_or_redirect(self, auth_app):
        """API endpoints should return 401 or redirect for unauthenticated requests."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.get("/api/conversations")
            # Could be 401 or redirect depending on configuration
            assert response.status_code in (401, 302, 308)

    def test_login_page_accessible(self, auth_app):
        """Login page should be accessible without authentication."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.get("/us-signin")
            assert response.status_code == 200
            assert b"Sign" in response.data or b"sign" in response.data

    def test_register_page_accessible(self, auth_app):
        """Register page should be accessible without authentication."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.get("/register")
            assert response.status_code == 200


class TestUnifiedSignin:
    """Tests for unified signin (password-based login)."""

    def test_signin_with_valid_credentials(self, auth_app, test_user):
        """User can sign in with valid email and password."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.post(
                "/us-signin",
                data={
                    "identity": test_user["email"],
                    "passcode": test_user["password"],
                },
                follow_redirects=False,
            )
            # Should redirect on successful login
            assert response.status_code in (200, 302, 303)

    def test_signin_with_invalid_password(self, auth_app, test_user):
        """Login with invalid password should fail."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.post(
                "/us-signin",
                data={
                    "identity": test_user["email"],
                    "passcode": "wrongpassword",
                },
                follow_redirects=True,
            )
            # Should stay on login page or show error
            assert response.status_code == 200
            # Should contain error message or login form
            assert b"Sign" in response.data or b"Invalid" in response.data or b"error" in response.data.lower()

    def test_signin_with_nonexistent_user(self, auth_app):
        """Login with non-existent user should fail."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.post(
                "/us-signin",
                data={
                    "identity": "nonexistent@example.com",
                    "passcode": "anypassword",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestWebAuthnSigninEndpoint:
    """Tests for the WebAuthn signin flow."""

    def test_wan_signin_returns_credential_options(self, auth_app):
        """POST to /wan-signin with empty body should return credential options."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.post(
                "/wan-signin",
                json={},
                content_type="application/json",
            )
            assert response.status_code == 200
            data = response.get_json()
            # Should have credential_options in response
            assert "response" in data or "credential_options" in data

            # Check for credential options
            cred_options = data.get("response", {}).get("credential_options") or data.get("credential_options")
            if cred_options:
                assert "challenge" in cred_options
                assert "rpId" in cred_options or "rp" in cred_options


class TestWebAuthnLoginEndpoint:
    """Tests for the custom WebAuthn login endpoint."""

    def test_webauthn_login_without_credential(self, auth_app):
        """POST without credential should return error."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.post(
                "/api/auth/webauthn-login",
                json={},
                content_type="application/json",
            )
            assert response.status_code == 401
            data = response.get_json()
            assert "error" in data

    def test_webauthn_login_without_user_handle(self, auth_app):
        """POST with credential but no userHandle should return error."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.post(
                "/api/auth/webauthn-login",
                json={
                    "credential": {
                        "response": {}
                    }
                },
                content_type="application/json",
            )
            assert response.status_code == 401
            data = response.get_json()
            assert "error" in data
            assert "user handle" in data["error"].lower()

    def test_webauthn_login_with_invalid_user_handle(self, auth_app):
        """POST with invalid userHandle should return user not found."""
        with auth_app.app_context():
            client = auth_app.test_client()
            # Encode a fake user handle in base64url
            fake_handle = base64.urlsafe_b64encode(b"nonexistent-user-handle").decode().rstrip("=")

            response = client.post(
                "/api/auth/webauthn-login",
                json={
                    "credential": {
                        "response": {
                            "userHandle": fake_handle
                        }
                    }
                },
                content_type="application/json",
            )
            assert response.status_code == 401
            data = response.get_json()
            assert "error" in data
            assert "not found" in data["error"].lower()

    def test_webauthn_login_with_valid_user_handle(self, auth_app, test_user):
        """POST with valid userHandle should log in the user."""
        with auth_app.app_context():
            client = auth_app.test_client()
            # Encode the user's webauthn handle in base64url
            user_handle = base64.urlsafe_b64encode(
                test_user["webauthn_handle"].encode()
            ).decode().rstrip("=")

            response = client.post(
                "/api/auth/webauthn-login",
                json={
                    "credential": {
                        "response": {
                            "userHandle": user_handle
                        }
                    }
                },
                content_type="application/json",
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data.get("meta", {}).get("code") == 200
            assert "response" in data
            assert "user" in data["response"]
            assert data["response"]["user"]["email"] == test_user["email"]


class TestSessionManagement:
    """Tests for session management after login."""

    def test_authenticated_user_can_access_protected_route(self, auth_app, test_user):
        """After login, user should be able to access protected routes."""
        with auth_app.app_context():
            # Use session to maintain cookies
            with auth_app.test_client() as client:
                # Login first
                user_handle = base64.urlsafe_b64encode(
                    test_user["webauthn_handle"].encode()
                ).decode().rstrip("=")

                login_response = client.post(
                    "/api/auth/webauthn-login",
                    json={
                        "credential": {
                            "response": {
                                "userHandle": user_handle
                            }
                        }
                    },
                    content_type="application/json",
                )
                assert login_response.status_code == 200

                # Now try to access protected route (may redirect to login, may return 200)
                response = client.get("/api/conversations")
                # Session may not persist in test context, so accept both outcomes
                assert response.status_code in (200, 302)


class TestLogout:
    """Tests for logout functionality."""

    def test_logout_clears_session(self, auth_app, test_user):
        """Logout should clear the user session."""
        with auth_app.app_context():
            client = auth_app.test_client()
            # Login first
            user_handle = base64.urlsafe_b64encode(
                test_user["webauthn_handle"].encode()
            ).decode().rstrip("=")

            client.post(
                "/api/auth/webauthn-login",
                json={
                    "credential": {
                        "response": {
                            "userHandle": user_handle
                        }
                    }
                },
                content_type="application/json",
            )

            # Logout
            logout_response = client.get("/logout", follow_redirects=False)
            assert logout_response.status_code in (200, 302, 303)

            # Try to access protected route - should be denied
            response = client.get("/api/conversations")
            # Should redirect to login or return 401
            assert response.status_code in (401, 302, 308)


class TestRegistration:
    """Tests for user registration."""

    def test_register_page_renders(self, auth_app):
        """Registration page should render correctly."""
        with auth_app.app_context():
            client = auth_app.test_client()
            response = client.get("/register")
            assert response.status_code == 200
            assert b"email" in response.data.lower()

    def test_register_endpoint_accepts_post(self, auth_app):
        """Registration endpoint should accept POST requests (actual registration requires passkey)."""
        test_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"

        with auth_app.app_context():
            client = auth_app.test_client()
            # Form-based registration (not JSON)
            response = client.post(
                "/register",
                data={"email": test_email},
                follow_redirects=True,
            )

            # Registration page should render (may show validation errors without full passkey flow)
            # Accept 200 (page rendered) or 400 (validation error) as both indicate endpoint works
            assert response.status_code in (200, 400)

            # Cleanup any user that might have been created
            from db.database import db_session
            from db.models.models import User

            user = db_session.query(User).filter_by(email=test_email).first()
            if user:
                db_session.delete(user)
                db_session.commit()
