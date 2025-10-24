import re
from datetime import datetime, timedelta

from flask import render_template, request, Response, jsonify
import markdown

from forms import SearchForm
from controllers.conversation_controller import ConversationController, UploadController
from controllers.postgres_controller import get_postgres_controller
from config import COLLECTION_NAME, DEFAULT_EMBEDDING_MODEL, SECRET_KEY, USE_PG_SINGLE_STORE
import os


def init_routes(app, archive):
    """Initialize all Flask routes using MVC pattern"""
    
    # Check feature flag for PostgreSQL backend
    use_postgres = USE_PG_SINGLE_STORE
    
    if use_postgres:
        # Use PostgreSQL controller for API endpoints
        postgres_controller = get_postgres_controller()
        # Still use legacy controller for web UI
        conversation_controller = ConversationController()
        upload_controller = UploadController()
    else:
        # Use legacy controllers
        conversation_controller = ConversationController()
        upload_controller = UploadController()

    @app.route("/", methods=["GET", "POST"])
    def index():
        """Redirect to conversations view"""
        if use_postgres:
            return conversation_controller.index_with_postgres_adapter(postgres_controller)
        else:
            return conversation_controller.index()

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        if use_postgres:
            return postgres_controller.upload()
        else:
            return upload_controller.upload()

    @app.route("/api/search", methods=["GET"])
    def api_search():
        if use_postgres:
            return jsonify(postgres_controller.api_search())
        else:
            return upload_controller.api_search()

    @app.route("/api/conversations", methods=["GET"])
    def api_conversations():
        if use_postgres:
            return jsonify(postgres_controller.get_conversations())
        else:
            return conversation_controller.api_conversations()

    @app.route("/api/conversation/<conversation_id>", methods=["GET"])
    def api_conversation(conversation_id):
        if use_postgres:
            return jsonify(postgres_controller.get_conversation(conversation_id))
        else:
            return conversation_controller.api_conversation(conversation_id)

    @app.route("/settings")
    def settings():
        if use_postgres:
            return postgres_controller.get_settings_page()
        else:
            return conversation_controller.settings()
    
    @app.route("/api/settings", methods=["GET", "POST"])
    def api_settings():
        if use_postgres:
            return jsonify(postgres_controller.handle_settings(request))
        else:
            return jsonify({"error": "Settings not available in legacy mode"}), 501
    
    @app.route("/stats")
    def stats():
        if use_postgres:
            return conversation_controller.stats_with_postgres_adapter(postgres_controller)
        else:
            return conversation_controller.stats()

    @app.route("/api/stats")
    def api_stats():
        if use_postgres:
            return jsonify(postgres_controller.get_stats())
        else:
            return conversation_controller.api_stats()
    
    @app.route("/api/collection/count", methods=["GET"])
    def api_collection_count():
        if use_postgres:
            return jsonify(postgres_controller.get_collection_count())
        else:
            # Legacy implementation would go here if needed
            try:
                count = conversation_controller.search_model.conversation_model.get_count()
                return jsonify({"count": count})
            except Exception as e:
                return jsonify({"error": str(e), "count": 0})

    @app.route("/conversations", methods=["GET", "POST"])
    @app.route("/conversations/<int:page>", methods=["GET", "POST"])
    def conversations(page=1):
        """Display all documents in a list with filtering, pagination, and search"""
        if use_postgres:
            # Use PostgreSQL backend with legacy UI by creating adapter-based controller
            return conversation_controller.conversations_with_postgres_adapter(page, postgres_controller)
        else:
            return conversation_controller.conversations(page)

    @app.route("/view/<doc_id>")
    def view_conversation(doc_id):
        """View a single conversation"""
        if use_postgres:
            return conversation_controller.view_conversation_with_postgres_adapter(doc_id, postgres_controller)
        else:
            return conversation_controller.view_conversation(doc_id)

    @app.route("/export/<doc_id>")
    def export_conversation(doc_id):
        """Export a conversation as markdown"""
        if use_postgres:
            from flask import jsonify
            return jsonify({"error": "Export not yet implemented for PostgreSQL mode"}), 501
        else:
            return conversation_controller.export_conversation(doc_id)
    
    @app.route("/export_to_openwebui/<doc_id>", methods=["POST"])
    def export_to_openwebui(doc_id):
        """Export a conversation to OpenWebUI"""
        if use_postgres:
            result = postgres_controller.export_to_openwebui(doc_id)
            # Result is always a dict from postgres_controller
            return jsonify(result)
        else:
            # Result from conversation_controller is already (response, status_code) tuple
            return conversation_controller.export_to_openwebui(doc_id)
    
    @app.route("/api/export/openwebui/<doc_id>", methods=["POST"])
    def api_export_to_openwebui(doc_id):
        """API endpoint for exporting conversation to OpenWebUI"""
        if use_postgres:
            return jsonify(postgres_controller.export_to_openwebui(doc_id))
        else:
            return jsonify(conversation_controller.export_to_openwebui(doc_id))

    @app.route("/api/rag/query", methods=["POST"])
    def api_rag_query():
        """RAG query endpoint with contextual window expansion for OpenWebUI integration."""
        try:
            data = request.get_json()
            query_text = data.get('query', '')
            
            if not query_text:
                return jsonify({"error": "Query text is required"}), 400
            
            # Check if contextual retrieval is requested (new behavior)
            context_window = data.get('context_window')
            use_contextual = context_window is not None or data.get('use_contextual', False)
            
            if use_postgres and use_contextual:
                # New contextual retrieval with window expansion
                from db.services.contextual_retrieval_service import ContextualRetrievalService
                from db.repositories.unit_of_work import get_unit_of_work
                from config import (
                    RAG_DEFAULT_WINDOW_SIZE,
                    RAG_MAX_WINDOW_SIZE,
                    RAG_ADAPTIVE_WINDOWING,
                    RAG_DEDUPLICATE_MESSAGES,
                    RAG_DEFAULT_TOP_K_WINDOWS,
                    RAG_DEFAULT_MAX_TOKENS,
                    RAG_PROXIMITY_DECAY_LAMBDA,
                    RAG_APPLY_RECENCY_BONUS
                )
                
                # Parse and validate parameters
                top_k_windows = min(data.get('n_results', RAG_DEFAULT_TOP_K_WINDOWS), RAG_DEFAULT_TOP_K_WINDOWS * 2)
                context_window = min(context_window or RAG_DEFAULT_WINDOW_SIZE, RAG_MAX_WINDOW_SIZE)
                adaptive_context = data.get('adaptive_context', RAG_ADAPTIVE_WINDOWING)
                asymmetric_before = data.get('asymmetric_before')
                asymmetric_after = data.get('asymmetric_after')
                deduplicate = data.get('deduplicate', RAG_DEDUPLICATE_MESSAGES)
                max_tokens = data.get('max_tokens', RAG_DEFAULT_MAX_TOKENS)
                include_markers = data.get('include_markers', True)
                
                # Validate parameters
                if asymmetric_before and asymmetric_before > RAG_MAX_WINDOW_SIZE:
                    return jsonify({"error": f"asymmetric_before must be <= {RAG_MAX_WINDOW_SIZE}"}), 400
                if asymmetric_after and asymmetric_after > RAG_MAX_WINDOW_SIZE:
                    return jsonify({"error": f"asymmetric_after must be <= {RAG_MAX_WINDOW_SIZE}"}), 400
                
                with get_unit_of_work() as uow:
                    contextual_service = ContextualRetrievalService(uow)
                    
                    windows = contextual_service.retrieve_with_context(
                        query=query_text,
                        top_k_windows=top_k_windows,
                        context_window=context_window,
                        adaptive_context=adaptive_context,
                        asymmetric_before=asymmetric_before,
                        asymmetric_after=asymmetric_after,
                        deduplicate=deduplicate,
                        max_tokens=max_tokens if max_tokens and max_tokens > 0 else None,
                        include_markers=include_markers,
                        proximity_decay_lambda=RAG_PROXIMITY_DECAY_LAMBDA,
                        apply_recency_bonus=RAG_APPLY_RECENCY_BONUS
                    )
                    
                    # Format results for OpenWebUI
                    formatted_results = []
                    for window in windows:
                        meta = window.metadata
                        
                        # Extract preview from content (first 500 chars)
                        preview = window.content[:500] + "..." if len(window.content) > 500 else window.content
                        
                        formatted_results.append({
                            "id": meta.conversation_id,
                            "window_id": meta.window_id,
                            "title": meta.conversation_title,
                            "content": window.content,
                            "preview": preview,
                            "source": "postgres_contextual",
                            "relevance": meta.aggregated_score,
                            "metadata": {
                                "conversation_id": meta.conversation_id,
                                "matched_message_id": meta.matched_message_id,
                                "window_size": meta.window_size,
                                "match_position": meta.match_position,
                                "before_count": meta.before_count,
                                "after_count": meta.after_count,
                                "base_score": meta.base_score,
                                "aggregated_score": meta.aggregated_score,
                                "roles": meta.roles,
                                "token_estimate": meta.token_estimate,
                                "retrieval_params": meta.retrieval_params
                            }
                        })
                    
                    return jsonify({
                        "query": query_text,
                        "retrieval_mode": "contextual",
                        "context_window": context_window,
                        "adaptive_context": adaptive_context,
                        "results": formatted_results
                    })
            
            # Legacy behavior (backward compatible)
            elif use_postgres:
                return jsonify(postgres_controller.rag_query())
            else:
                # Legacy ChromaDB implementation
                n_results = data.get('n_results', 5)
                search_type = data.get('search_type', 'semantic')
                
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
                            "relevance": 1.0 - dist,
                            "metadata": meta
                        })
                
                return jsonify({
                    "query": query_text,
                    "search_type": search_type,
                    "results": formatted_results
                })
                
        except Exception as e:
            import logging
            logging.error(f"RAG query failed: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/clear_db", methods=["POST"])
    def clear_database():
        """Clear the entire database"""
        if use_postgres:
            return jsonify(postgres_controller.clear_database())
        else:
            return conversation_controller.clear_database()
    
    @app.route("/api/clear", methods=["DELETE"])
    def api_clear_database():
        """API endpoint to clear the database"""
        if use_postgres:
            return jsonify(postgres_controller.clear_database())
        else:
            return jsonify(conversation_controller.clear_database())
    
    @app.route("/api/rag/health", methods=["GET"])
    def api_rag_health():
        """Health check endpoint for RAG service"""
        if use_postgres:
            return jsonify(postgres_controller.rag_health())
        else:
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
