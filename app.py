from flask import Flask
from flask_cors import CORS
from flask_security import Security, SQLAlchemyUserDatastore

from config import (
    SECRET_KEY, SECURITY_PASSWORD_SALT, AUTH_ENABLED,
    WEBAUTHN_RP_NAME, WEBAUTHN_RP_ID, WEBAUTHN_ORIGIN
)
from routes import init_routes


def create_app(database_url=None):
    """Application factory pattern for better testing and configuration.

    Args:
        database_url: Optional database URL override. If not provided, uses config default.
    """
    app = Flask(__name__)

    # Core Flask config
    app.config["SECRET_KEY"] = SECRET_KEY

    # Flask-Security configuration
    app.config["SECURITY_PASSWORD_SALT"] = SECURITY_PASSWORD_SALT

    # Session cookie settings
    app.config["REMEMBER_COOKIE_SAMESITE"] = "strict"
    app.config["SESSION_COOKIE_SAMESITE"] = "strict"

    # Disable CSRF for API endpoints (we use CORS instead)
    # Re-enable if you need form-based submissions with CSRF
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECURITY_CSRF_PROTECT_MECHANISMS"] = []
    app.config["SECURITY_CSRF_IGNORE_UNAUTH_ENDPOINTS"] = True

    # User registration settings
    app.config["SECURITY_REGISTERABLE"] = True
    app.config["SECURITY_SEND_REGISTER_EMAIL"] = False  # No email verification

    # Unified signin enables passwordless authentication
    app.config["SECURITY_UNIFIED_SIGNIN"] = True
    app.config["SECURITY_PASSWORD_REQUIRED"] = False  # Allow passkey-only registration

    # Disable email/SMS signin methods (we only want passkey)
    app.config["SECURITY_US_ENABLED_METHODS"] = ["authenticator"]  # Only passkey/authenticator

    # WebAuthn/Passkey configuration
    app.config["SECURITY_WEBAUTHN"] = True
    app.config["SECURITY_WAN_ALLOW_AS_FIRST_FACTOR"] = True  # Passkeys can be primary auth
    app.config["SECURITY_WAN_ALLOW_AS_MULTI_FACTOR"] = True  # Passkeys can be 2FA
    app.config["SECURITY_WAN_ALLOW_AS_VERIFY"] = ["first", "secondary"]
    app.config["SECURITY_WAN_ALLOW_USER_HINTS"] = True

    # WebAuthn Relying Party settings
    app.config["SECURITY_WAN_RP_NAME"] = WEBAUTHN_RP_NAME
    app.config["SECURITY_WAN_RP_ID"] = WEBAUTHN_RP_ID
    app.config["SECURITY_WAN_ORIGIN"] = WEBAUTHN_ORIGIN

    # Login/logout redirects
    app.config["SECURITY_POST_LOGIN_VIEW"] = "/conversations"
    app.config["SECURITY_POST_LOGOUT_VIEW"] = "/login"
    app.config["SECURITY_POST_REGISTER_VIEW"] = "/conversations"
    app.config["SECURITY_UNAUTHORIZED_VIEW"] = "/login"

    # Use custom login template
    app.config["SECURITY_LOGIN_USER_TEMPLATE"] = "security/login.html"
    app.config["SECURITY_REGISTER_USER_TEMPLATE"] = "security/register.html"

    # Enable CORS for all routes
    CORS(app)

    # Initialize PostgreSQL database
    print("Initializing PostgreSQL database")
    from db.database import create_tables, get_session
    try:
        create_tables(database_url=database_url)
    except Exception as e:
        print(f"Database table creation warning: {e}")

    # Initialize Flask-Security (only if auth is enabled)
    if AUTH_ENABLED:
        from db.models.models import User, Role, WebAuthn
        from db.database import SessionFactory

        # Create the user datastore
        user_datastore = SQLAlchemyUserDatastore(SessionFactory, User, Role, webauthn_model=WebAuthn)

        # Initialize security extension
        security = Security(app, user_datastore)

        # Store datastore on app for access in routes
        app.user_datastore = user_datastore
        app.security = security

    # Initialize routes
    init_routes(app)

    return app


# Create the app instance
app = create_app()

# === Main ===
if __name__ == "__main__":
    import os
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=5001, debug=debug_mode)
