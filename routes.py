import re
from datetime import datetime, timedelta
from functools import wraps

from flask import render_template, request, Response, jsonify, redirect, url_for, current_app
import markdown

from forms import SearchForm
from controllers.conversation_controller import ConversationController
from controllers.postgres_controller import get_postgres_controller
from controllers.rag_controller import get_rag_controller
from config import SECRET_KEY, AUTH_ENABLED
import os


def get_auth_required():
    """Get the appropriate auth decorator based on AUTH_ENABLED setting."""
    if AUTH_ENABLED:
        from flask_security import auth_required
        return auth_required()
    else:
        # Return a no-op decorator when auth is disabled
        def no_auth(f):
            return f
        return no_auth


def check_first_user_setup():
    """Check if this is the first user setup and redirect to registration if needed."""
    if not AUTH_ENABLED:
        return None

    from db.database import get_session_context
    from db.models.models import User

    with get_session_context() as session:
        user_count = session.query(User).count()
        if user_count == 0:
            return redirect(url_for('security.register'))
    return None


def init_routes(app):
    """Initialize all Flask routes using MVC pattern"""

    # PostgreSQL controller for API endpoints
    postgres_controller = get_postgres_controller()
    # Legacy controller for web UI (uses postgres adapter internally)
    conversation_controller = ConversationController()

    # First-user setup check middleware
    @app.before_request
    def before_request_handler():
        """Check for first-user setup before each request."""
        # Skip auth checks for static files and security endpoints
        if request.endpoint and (
            request.endpoint.startswith('static') or
            request.endpoint.startswith('security.') or
            request.endpoint == 'setup_check'
        ):
            return None

        # Check if we need first-user setup
        redirect_response = check_first_user_setup()
        if redirect_response:
            return redirect_response

        return None

    # =========================================================================
    # Public routes (no auth required)
    # =========================================================================

    @app.route("/api/setup/status", methods=["GET"])
    def setup_check():
        """Check if the application needs first-user setup."""
        if not AUTH_ENABLED:
            return jsonify({"setup_required": False, "auth_enabled": False})

        from db.database import get_session_context
        from db.models.models import User

        with get_session_context() as session:
            user_count = session.query(User).count()
            return jsonify({
                "setup_required": user_count == 0,
                "auth_enabled": True,
                "user_count": user_count
            })

    @app.route("/api/rag/health", methods=["GET"])
    def api_rag_health():
        """Health check endpoint for RAG service (public for monitoring)."""
        return jsonify(postgres_controller.rag_health())

    @app.route("/api/auth/webauthn-login", methods=["POST"])
    def api_webauthn_login():
        """Login user after WebAuthn credential verification."""
        if not AUTH_ENABLED:
            return jsonify({"error": "Auth not enabled"}), 400

        from flask_security import login_user
        from db.database import db_session
        from db.models.models import User
        import base64

        data = request.get_json() or {}

        try:
            credential_data = data.get('credential', {})
            user_handle = credential_data.get('response', {}).get('userHandle')

            if not user_handle:
                return jsonify({"error": "No user handle in credential"}), 401

            # Decode user handle (base64url)
            user_handle_padded = user_handle + '=' * (4 - len(user_handle) % 4) if len(user_handle) % 4 else user_handle
            user_handle_decoded = base64.urlsafe_b64decode(user_handle_padded).decode('utf-8')

            # Find user by fs_webauthn_user_handle
            user = db_session.query(User).filter_by(fs_webauthn_user_handle=user_handle_decoded).first()

            if not user:
                return jsonify({"error": "User not found for handle: " + user_handle_decoded}), 401

            # Login the user with remember=True for persistent session
            login_user(user, remember=True)

            return jsonify({
                "meta": {"code": 200},
                "response": {
                    "user": {"email": user.email},
                    "post_login_url": "/conversations"
                }
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    # =========================================================================
    # Protected routes (require authentication when AUTH_ENABLED)
    # =========================================================================

    @app.route("/", methods=["GET", "POST"])
    @get_auth_required()
    def index():
        """Redirect to conversations view"""
        return conversation_controller.index_with_postgres_adapter(postgres_controller)

    @app.route("/upload", methods=["GET", "POST"])
    @get_auth_required()
    def upload():
        return postgres_controller.upload()

    @app.route("/api/search", methods=["GET"])
    @get_auth_required()
    def api_search():
        return jsonify(postgres_controller.api_search())

    @app.route("/api/conversations", methods=["GET"])
    @get_auth_required()
    def api_conversations():
        return jsonify(postgres_controller.get_conversations())

    @app.route("/api/conversations/list", methods=["GET"])
    @get_auth_required()
    def api_conversations_paginated():
        """Paginated conversations endpoint for lazy loading"""
        return jsonify(postgres_controller.get_conversations_paginated())

    @app.route("/api/conversation/<conversation_id>", methods=["GET"])
    @get_auth_required()
    def api_conversation(conversation_id):
        return jsonify(postgres_controller.get_conversation(conversation_id))

    @app.route("/api/conversation/<conversation_id>/save", methods=["POST"])
    @get_auth_required()
    def api_toggle_save_conversation(conversation_id):
        """Toggle saved/bookmarked status of a conversation"""
        result, status_code = postgres_controller.toggle_save_conversation(conversation_id)
        return jsonify(result), status_code

    @app.route("/api/conversations/saved", methods=["GET"])
    @get_auth_required()
    def api_saved_conversations():
        """Get all saved/bookmarked conversations"""
        return jsonify(postgres_controller.get_saved_conversations())

    @app.route("/settings")
    @get_auth_required()
    def settings():
        return postgres_controller.get_settings_page()

    @app.route("/api/settings", methods=["GET", "POST"])
    @get_auth_required()
    def api_settings():
        return jsonify(postgres_controller.handle_settings(request))

    @app.route("/api/license/status", methods=["GET"])
    @get_auth_required()
    def api_license_status():
        return jsonify(postgres_controller.get_license_status())

    @app.route("/api/embedding/status")
    @get_auth_required()
    def embedding_status():
        return jsonify(postgres_controller.get_embedding_status())

    @app.route("/stats")
    @get_auth_required()
    def stats():
        return conversation_controller.stats_with_postgres_adapter(postgres_controller)

    @app.route("/api/stats")
    @get_auth_required()
    def api_stats():
        return jsonify(postgres_controller.get_stats())

    @app.route("/api/collection/count", methods=["GET"])
    @get_auth_required()
    def api_collection_count():
        return jsonify(postgres_controller.get_collection_count())

    @app.route("/conversations", methods=["GET", "POST"])
    @app.route("/conversations/<int:page>", methods=["GET", "POST"])
    @get_auth_required()
    def conversations(page=1):
        """Display all documents in a list with filtering, pagination, and search"""
        return conversation_controller.conversations_with_postgres_adapter(page, postgres_controller)

    @app.route("/moments")
    @get_auth_required()
    def moments():
        """Display key moments/highlights from conversations"""
        return render_template("moments.html")

    @app.route("/topics")
    @get_auth_required()
    def topics():
        """Display topics extracted from conversations"""
        return render_template("topics.html")

    @app.route("/saved")
    @get_auth_required()
    def saved():
        """Display saved/bookmarked conversations"""
        return render_template("saved.html")

    @app.route("/insights")
    @get_auth_required()
    def insights():
        """Display insights and analytics about conversations"""
        return render_template("insights.html")

    @app.route("/view/<doc_id>")
    @get_auth_required()
    def view_conversation(doc_id):
        """View a single conversation"""
        return conversation_controller.view_conversation_with_postgres_adapter(doc_id, postgres_controller)

    @app.route("/export/<doc_id>")
    @get_auth_required()
    def export_conversation(doc_id):
        """Export a conversation as markdown"""
        return postgres_controller.export_conversation(doc_id)

    @app.route("/export_to_openwebui/<doc_id>", methods=["POST"])
    @get_auth_required()
    def export_to_openwebui(doc_id):
        """Export a conversation to OpenWebUI"""
        result = postgres_controller.export_to_openwebui(doc_id)
        return jsonify(result)

    @app.route("/api/conversation/<doc_id>", methods=["DELETE"])
    @get_auth_required()
    def delete_conversation(doc_id):
        """Delete a conversation and all its associated data"""
        result = postgres_controller.delete_conversation(doc_id)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    @app.route("/api/export/openwebui/<doc_id>", methods=["POST"])
    @get_auth_required()
    def api_export_to_openwebui(doc_id):
        """API endpoint for exporting conversation to OpenWebUI"""
        return jsonify(postgres_controller.export_to_openwebui(doc_id))

    @app.route("/api/check_openwebui_conversation/<conversation_id>", methods=["GET"])
    @get_auth_required()
    def check_openwebui_conversation(conversation_id):
        """Check if conversation exists in OpenWebUI"""
        result = postgres_controller.check_conversation_exists_in_openwebui(conversation_id)
        return jsonify(result)

    @app.route("/api/rag/query", methods=["POST"])
    @get_auth_required()
    def api_rag_query():
        """RAG query endpoint with contextual window expansion for OpenWebUI integration."""
        try:
            rag_controller = get_rag_controller(postgres_controller)
            result = rag_controller.handle_rag_query()

            # Return 400 for validation errors
            if "error" in result:
                return jsonify(result), 400

            return jsonify(result)
        except Exception as e:
            import logging
            logging.error(f"RAG query failed: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/clear_db", methods=["POST"])
    @get_auth_required()
    def clear_database():
        """Clear the entire database"""
        return jsonify(postgres_controller.clear_database())

    @app.route("/api/clear", methods=["DELETE"])
    @get_auth_required()
    def api_clear_database():
        """API endpoint to clear the database"""
        return jsonify(postgres_controller.clear_database())

    @app.route("/api/sync/openwebui", methods=["POST"])
    @get_auth_required()
    def api_sync_openwebui():
        """Trigger OpenWebUI sync"""
        return jsonify(postgres_controller.trigger_openwebui_sync())

    @app.route("/api/sync/status", methods=["GET"])
    @get_auth_required()
    def api_sync_status():
        """Get sync status and statistics"""
        return jsonify(postgres_controller.get_sync_status())

    @app.route("/api/watch-folder/status", methods=["GET"])
    @get_auth_required()
    def api_watch_folder_status():
        """Get watch folder status"""
        return jsonify(postgres_controller.get_watch_folder_status())

    @app.route("/api/watch-folder/test", methods=["POST"])
    @get_auth_required()
    def api_watch_folder_test():
        """Test if a folder path is valid and writable"""
        return jsonify(postgres_controller.test_watch_folder(request))
