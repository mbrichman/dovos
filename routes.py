import re
from datetime import datetime, timedelta

from flask import render_template, request, Response
import markdown

from forms import SearchForm
from controllers.conversation_controller import ConversationController, UploadController


def init_routes(app, archive):
    """Initialize all Flask routes using MVC pattern"""
    
    # Create controller instances
    conversation_controller = ConversationController()
    upload_controller = UploadController()

    @app.route("/", methods=["GET", "POST"])
    def index():
        """Redirect to conversations view"""
        return conversation_controller.index()

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        return upload_controller.upload()

    @app.route("/api/search", methods=["GET"])
    def api_search():
        return upload_controller.api_search()

    @app.route("/api/conversations", methods=["GET"])
    def api_conversations():
        return conversation_controller.api_conversations()

    @app.route("/stats")
    def stats():
        return conversation_controller.stats()

    @app.route("/conversations", methods=["GET", "POST"])
    @app.route("/conversations/<int:page>", methods=["GET", "POST"])
    def conversations(page=1):
        """Display all documents in a list with filtering, pagination, and search"""
        return conversation_controller.conversations(page)

    @app.route("/view/<doc_id>")
    def view_conversation(doc_id):
        """View a single conversation"""
        return conversation_controller.view_conversation(doc_id)

    @app.route("/export/<doc_id>")
    def export_conversation(doc_id):
        """Export a conversation as markdown"""
        return conversation_controller.export_conversation(doc_id)

    @app.route("/clear_db", methods=["POST"])
    def clear_database():
        """Clear the entire database"""
        return conversation_controller.clear_database()
