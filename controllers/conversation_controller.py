"""Refactored ConversationController using service layer

This controller follows SOLID principles by delegating business logic to
specialized services. It handles only routing and HTTP concerns.
"""

from flask import render_template, request, redirect, url_for
from forms import SearchForm
from db.services.conversation_format_service import ConversationFormatService


class ConversationController:
    """Controller for handling conversation web UI routes"""
    
    def __init__(self, format_service=None):
        """Initialize controller with optional service injection
        
        Args:
            format_service: ConversationFormatService instance (or None for default)
        """
        self.format_service = format_service or ConversationFormatService()
    
    def index_with_postgres_adapter(self, postgres_controller):
        """Index page using PostgreSQL backend
        
        Args:
            postgres_controller: PostgreSQL controller instance
        
        Returns:
            Flask Response (redirect to conversations)
        """
        # Handle search query redirects
        if request.args.get("q"):
            return redirect(url_for("conversations", **request.args))
        elif request.method == "POST":
            search_form = SearchForm()
            if search_form.validate_on_submit():
                return redirect(url_for("conversations", q=search_form.query.data))
        
        # Default: redirect to conversations
        return redirect(url_for("conversations"))
    
    def conversations_with_postgres_adapter(self, page, postgres_controller):
        """Display conversations using PostgreSQL backend
        
        Args:
            page: Page number (unused with lazy loading)
            postgres_controller: PostgreSQL controller instance
        
        Returns:
            Flask Response (rendered template)
        """
        # Initialize form and parameters
        search_form = SearchForm()
        search_triggered = False
        query = None
        
        # Handle search query
        if request.method == "POST":
            if search_form.validate_on_submit():
                query = search_form.query.data
                search_triggered = True
        elif request.method == "GET" and request.args.get("q"):
            query = request.args.get("q")
            search_form.query.data = query
            search_triggered = True
        
        # Get filter parameters
        source_filter = request.args.get("source", "all")
        date_filter = request.args.get("date", "all")
        sort_order = request.args.get("sort", "newest")
        
        # Get conversations from postgres controller
        if search_triggered and query:
            items = self._get_search_results(
                postgres_controller,
                query,
                search_form
            )
        else:
            items = self._get_conversations_list(
                postgres_controller,
                source_filter,
                date_filter,
                sort_order
            )
        
        # Render template (no server-side pagination - client handles lazy loading)
        return render_template(
            "conversations.html",
            conversations=items,
            source_filter=source_filter,
            date_filter=date_filter,
            sort_order=sort_order,
            search_form=search_form,
            search_triggered=search_triggered,
            query=query,
        )
    
    def view_conversation_with_postgres_adapter(self, doc_id, postgres_controller):
        """View a single conversation using PostgreSQL backend
        
        Args:
            doc_id: Conversation UUID
            postgres_controller: PostgreSQL controller instance
        
        Returns:
            Flask Response (rendered template or error)
        """
        try:
            from uuid import UUID
            from db.repositories.unit_of_work import get_unit_of_work
            import markdown
            
            # Parse UUID
            try:
                conv_uuid = UUID(doc_id)
            except ValueError:
                return "Invalid conversation ID", 400
            
            # Get conversation and messages from database
            with get_unit_of_work() as uow:
                conversation = uow.conversations.get_by_id(conv_uuid)
                if not conversation:
                    return "Conversation not found", 404
                
                db_messages = uow.messages.get_by_conversation(conv_uuid)
                if not db_messages:
                    return "No messages found in conversation", 404
                
                # Sort messages by sequence/timestamp
                db_messages.sort(key=lambda m: (
                    m.message_metadata.get('sequence', 999999) if m.message_metadata else 999999,
                    m.created_at
                ))
                
                # Extract source and determine assistant name
                source = self.format_service.extract_source_from_messages(db_messages)
                assistant_name = self.format_service._determine_assistant_name(None, source)
                
                # Format messages for view
                messages = self.format_service.format_db_messages_for_view(db_messages)
                
                # Build conversation metadata
                conversation_meta = {
                    'title': conversation.title,
                    'source': source,
                    'message_count': len(messages),
                    'earliest_ts': conversation.created_at.strftime('%Y-%m-%d %H:%M:%S') if conversation.created_at else None
                }
                
                conversation_obj = {'meta': conversation_meta}
                
                # Use appropriate template based on source
                if source.lower() == 'docx':
                    return render_template(
                        "view_document.html",
                        conversation=conversation_obj,
                        messages=messages,
                        doc_id=doc_id
                    )
                else:
                    return render_template(
                        "view.html",
                        conversation=conversation_obj,
                        messages=messages,
                        assistant_name=assistant_name,
                        doc_id=doc_id
                    )
        
        except Exception as e:
            # Log error without using print()
            import logging
            logging.error(f"Error viewing conversation: {e}", exc_info=True)
            return "Conversation not found", 404
    
    def stats_with_postgres_adapter(self, postgres_controller):
        """Display statistics using PostgreSQL backend

        Args:
            postgres_controller: PostgreSQL controller instance

        Returns:
            Flask Response (rendered template)
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Get statistics from PostgreSQL backend
            stats_data = postgres_controller.get_stats()
            logger.info(f"Stats data from postgres: {stats_data}")

            # Get source breakdown
            all_conversations = postgres_controller.get_conversations()
            source_counts = self.format_service.calculate_source_breakdown(all_conversations)

            # Format stats for template
            total_conversations = int(stats_data.get('total_conversations', 0))
            total_messages = int(stats_data.get('total_messages', 0))
            total_embeddings = int(stats_data.get('total_embeddings', 0))
            embedding_coverage = float(stats_data.get('embedding_coverage_percent') or 0)

            formatted_stats = {
                'total': total_conversations,
                'total_conversations': total_conversations,
                'total_messages': total_messages,
                'total_embeddings': total_embeddings,
                'embedding_coverage_percent': embedding_coverage,
                'sources': source_counts,
                'timeline': stats_data.get('timeline', []),
                'date_range': {
                    'earliest': stats_data.get('earliest_ts', ''),
                    'latest': stats_data.get('latest_ts', '')
                } if stats_data.get('earliest_ts') else None,
                'collection_info': {
                    'dimensions': 384,  # MiniLM uses 384 dimensions
                    'last_updated': stats_data.get('last_updated', '')
                } if stats_data.get('last_updated') else None,
                'collection_name': stats_data.get('collection_name', 'chat_history'),
                'embedding_model': stats_data.get('embedding_model', 'all-MiniLM-L6-v2'),
                'status': stats_data.get('status', 'healthy')
            }

            logger.info(f"Formatted stats: total_conversations={total_conversations}, total_messages={total_messages}")
            return render_template("stats.html", stats=formatted_stats)

        except Exception as e:
            # Return empty stats rather than error
            logger.error(f"Error getting PostgreSQL stats: {e}", exc_info=True)
            return render_template("stats.html", stats={
                'total': 0,
                'total_conversations': 0,
                'total_messages': 0,
                'total_embeddings': 0,
                'embedding_coverage_percent': 0,
                'sources': {},
                'timeline': [],
                'collection_name': 'chat_history',
                'embedding_model': 'all-MiniLM-L6-v2'
            })
    
    # ===== Private helper methods =====
    # (Formatting methods have been moved to ConversationFormatService)
    
    def _get_search_results(self, postgres_controller, query, search_form):
        """Get and format search results from postgres controller
        
        Args:
            postgres_controller: PostgreSQL controller instance
            query: Search query string
            search_form: SearchForm instance
        
        Returns:
            List of formatted result items
        """
        try:
            from werkzeug.datastructures import ImmutableMultiDict
            
            # Build search parameters
            original_args = request.args
            new_args = dict(original_args)
            new_args['q'] = query
            new_args['n'] = '20'
            
            # Get search type from form or URL
            if request.method == "POST" and search_form.search_type.data:
                search_type = search_form.search_type.data
            else:
                search_type = request.args.get('search_type', 'auto')
            
            new_args['search_type'] = search_type
            
            # Temporarily replace request.args
            request.args = ImmutableMultiDict(new_args)
            
            # Get search results
            search_results = postgres_controller.api_search()
            
            # Restore original args
            request.args = original_args
            
            # Format results using format service
            return self.format_service.format_postgres_search_results(search_results.get('results', []))
        
        except Exception as e:
            import logging
            logging.error(f"Error in PostgreSQL search: {e}")
            return []
    
    def _get_conversations_list(self, postgres_controller, source_filter, date_filter, sort_order):
        """Get and format conversations list from postgres controller
        
        Args:
            postgres_controller: PostgreSQL controller instance
            source_filter: Source filter value
            date_filter: Date filter value
            sort_order: Sort order value
        
        Returns:
            List of formatted conversation items
        """
        try:
            from werkzeug.datastructures import ImmutableMultiDict
            
            original_args = request.args
            
            # Build filter parameters
            new_args = {
                'page': '1',
                'limit': '30',
                'source': source_filter,
                'date': date_filter,
                'sort': sort_order
            }
            
            # Temporarily replace request.args
            request.args = ImmutableMultiDict(new_args)
            
            # Get conversations
            result = postgres_controller.get_conversations_paginated()
            
            # Restore original args
            request.args = original_args
            
            # Format results
            return self.format_service.format_postgres_list_results(result.get('conversations', []))
        
        except Exception as e:
            import logging
            logging.error(f"Error getting PostgreSQL conversations: {e}")
            return []
    
