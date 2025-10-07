import re
from datetime import datetime, timedelta

from flask import render_template, request, Response, jsonify
import markdown

from forms import SearchForm
from controllers.conversation_controller import ConversationController, UploadController
from config import COLLECTION_NAME, DEFAULT_EMBEDDING_MODEL, SECRET_KEY


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

    @app.route("/api/conversation/<conversation_id>", methods=["GET"])
    def api_conversation(conversation_id):
        return conversation_controller.api_conversation(conversation_id)

    @app.route("/stats")
    def stats():
        return conversation_controller.stats()

    @app.route("/api/stats")
    def api_stats():
        return conversation_controller.api_stats()

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
    
    @app.route("/export_to_openwebui/<doc_id>", methods=["POST"])
    def export_to_openwebui(doc_id):
        """Export a conversation to OpenWebUI"""
        return conversation_controller.export_to_openwebui(doc_id)

    @app.route("/api/rag/query", methods=["POST"])
    def api_rag_query():
        """RAG query endpoint for OpenWebUI integration"""
        try:
            data = request.get_json()
            query_text = data.get('query', '')
            n_results = data.get('n_results', 5)
            search_type = data.get('search_type', 'semantic')
            
            if not query_text:
                return jsonify({"error": "Query text is required"}), 400
                
            # Query the RAG service
            search_results = conversation_controller.search_model.conversation_model.search(
                query_text=query_text,
                n_results=n_results,
                keyword_search=(search_type == "keyword")
            )
            
            # Format results for OpenWebUI
            formatted_results = []
            if search_results.get("documents") and search_results["documents"][0]:
                for i, (doc, meta, dist) in enumerate(zip(
                    search_results["documents"][0], 
                    search_results["metadatas"][0], 
                    search_results["distances"][0]
                )):
                    # Extract a preview of the content
                    preview = doc[:500] + "..." if len(doc) > 500 else doc
                    
                    formatted_results.append({
                        "id": meta.get("id", f"result-{i}"),
                        "title": meta.get("title", "Untitled"),
                        "content": doc,
                        "preview": preview,
                        "source": meta.get("source", "unknown"),
                        "distance": dist,
                        "relevance": 1.0 - dist,  # Convert distance to relevance score
                        "metadata": meta
                    })
            
            return jsonify({
                "query": query_text,
                "search_type": search_type,
                "results": formatted_results
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/clear_db", methods=["POST"])
    def clear_database():
        """Clear the entire database"""
        return conversation_controller.clear_database()
    
    @app.route("/api/rag/health", methods=["GET"])
    def api_rag_health():
        """Health check endpoint for RAG service"""
        try:
            # Get basic stats from the conversation model
            doc_count = conversation_controller.search_model.conversation_model.get_count()
            
            return jsonify({
                "status": "healthy",
                "collection_name": COLLECTION_NAME,
                "document_count": doc_count,
                "embedding_model": DEFAULT_EMBEDDING_MODEL
            })
        except Exception as e:
            return jsonify({"status": "unhealthy", "error": str(e)}), 500
