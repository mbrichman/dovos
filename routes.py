import re
from datetime import datetime, timedelta

from flask import render_template, request, Response, jsonify
import markdown

from forms import SearchForm
from controllers.conversation_controller import ConversationController
from controllers.postgres_controller import get_postgres_controller
from controllers.rag_controller import get_rag_controller
from config import SECRET_KEY
import os


def init_routes(app):
    """Initialize all Flask routes using MVC pattern"""
    
    # PostgreSQL controller for API endpoints
    postgres_controller = get_postgres_controller()
    # Legacy controller for web UI (uses postgres adapter internally)
    conversation_controller = ConversationController()

    @app.route("/", methods=["GET", "POST"])
    def index():
        """Redirect to conversations view"""
        return conversation_controller.index_with_postgres_adapter(postgres_controller)

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        return postgres_controller.upload()

    @app.route("/api/search", methods=["GET"])
    def api_search():
        return jsonify(postgres_controller.api_search())

    @app.route("/api/conversations", methods=["GET"])
    def api_conversations():
        return jsonify(postgres_controller.get_conversations())
    
    @app.route("/api/conversations/list", methods=["GET"])
    def api_conversations_paginated():
        """Paginated conversations endpoint for lazy loading"""
        return jsonify(postgres_controller.get_conversations_paginated())

    @app.route("/api/conversation/<conversation_id>", methods=["GET"])
    def api_conversation(conversation_id):
        return jsonify(postgres_controller.get_conversation(conversation_id))

    @app.route("/settings")
    def settings():
        return postgres_controller.get_settings_page()
    
    @app.route("/api/settings", methods=["GET", "POST"])
    def api_settings():
        return jsonify(postgres_controller.handle_settings(request))
    
    @app.route("/stats")
    def stats():
        return conversation_controller.stats_with_postgres_adapter(postgres_controller)

    @app.route("/api/stats")
    def api_stats():
        return jsonify(postgres_controller.get_stats())
    
    @app.route("/api/collection/count", methods=["GET"])
    def api_collection_count():
        return jsonify(postgres_controller.get_collection_count())

    @app.route("/conversations", methods=["GET", "POST"])
    @app.route("/conversations/<int:page>", methods=["GET", "POST"])
    def conversations(page=1):
        """Display all documents in a list with filtering, pagination, and search"""
        return conversation_controller.conversations_with_postgres_adapter(page, postgres_controller)

    @app.route("/view/<doc_id>")
    def view_conversation(doc_id):
        """View a single conversation"""
        return conversation_controller.view_conversation_with_postgres_adapter(doc_id, postgres_controller)

    @app.route("/export/<doc_id>")
    def export_conversation(doc_id):
        """Export a conversation as markdown"""
        return postgres_controller.export_conversation(doc_id)
    
    @app.route("/export_to_openwebui/<doc_id>", methods=["POST"])
    def export_to_openwebui(doc_id):
        """Export a conversation to OpenWebUI"""
        result = postgres_controller.export_to_openwebui(doc_id)
        return jsonify(result)
    
    @app.route("/api/conversation/<doc_id>", methods=["DELETE"])
    def delete_conversation(doc_id):
        """Delete a conversation and all its associated data"""
        result = postgres_controller.delete_conversation(doc_id)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    
    @app.route("/api/export/openwebui/<doc_id>", methods=["POST"])
    def api_export_to_openwebui(doc_id):
        """API endpoint for exporting conversation to OpenWebUI"""
        return jsonify(postgres_controller.export_to_openwebui(doc_id))

    @app.route("/api/rag/query", methods=["POST"])
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
    def clear_database():
        """Clear the entire database"""
        return jsonify(postgres_controller.clear_database())
    
    @app.route("/api/clear", methods=["DELETE"])
    def api_clear_database():
        """API endpoint to clear the database"""
        return jsonify(postgres_controller.clear_database())
    
    @app.route("/api/rag/health", methods=["GET"])
    def api_rag_health():
        """Health check endpoint for RAG service"""
        return jsonify(postgres_controller.rag_health())
