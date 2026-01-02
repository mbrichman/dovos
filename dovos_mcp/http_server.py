#!/usr/bin/env python3
"""
DovOS MCP HTTP Server

HTTP/SSE-based MCP server for network communication between Docker containers.
OpenWebUI connects to this server over HTTP instead of stdio.

Run with: uvicorn dovos_mcp.http_server:app --host 0.0.0.0 --port 8001
"""

import sys
import os
import logging
from typing import Any, Sequence
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import Response
import uvicorn

from db.database import get_session_context
from db.services.search_service import SearchService, SearchConfig
from db.repositories.conversation_repository import ConversationRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp_server = Server("dovos")

# Global service instance
search_service: SearchService = None


def initialize_services():
    """Initialize services on startup."""
    global search_service
    logger.info("Initializing DovOS MCP HTTP Server...")
    search_service = SearchService(SearchConfig())
    logger.info("Services initialized successfully")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="search_conversations",
            description=(
                "Search DovOS conversation archive using hybrid semantic + keyword search. "
                "Returns conversation IDs, titles, and relevant snippets (NOT full content). "
                "BEST PRACTICE: Start with broad searches, review results, then do follow-up searches "
                "based on what you learn. Use different search_mode values for different needs. "
                "Always fetch_conversation to read full content before drawing conclusions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (natural language or keywords)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10, max: 50)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "search_mode": {
                        "type": "string",
                        "enum": ["hybrid", "vector", "fulltext"],
                        "description": "Search mode: 'hybrid' (semantic+keyword, default), 'vector' (semantic only), 'fulltext' (keyword only)",
                        "default": "hybrid"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="fetch_conversation",
            description=(
                "Fetch complete conversation content by ID. "
                "Returns all messages in chronological order with roles (user/assistant/system). "
                "BEST PRACTICE: Fetch multiple conversations (2-5) to get comprehensive coverage. "
                "Use after search_conversations to read full details of promising results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "UUID of the conversation to fetch (from search_conversations results)"
                    }
                },
                "required": ["conversation_id"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""
    if name == "search_conversations":
        return await handle_search(arguments)
    elif name == "fetch_conversation":
        return await handle_fetch(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_search(arguments: dict) -> Sequence[TextContent]:
    """Handle search_conversations tool call."""
    try:
        query = arguments.get("query")
        limit = arguments.get("limit", 10)
        search_mode = arguments.get("search_mode", "hybrid")

        if not query:
            return [TextContent(
                type="text",
                text="Error: 'query' parameter is required"
            )]

        # Validate limit
        limit = max(1, min(50, limit))

        logger.info(f"Searching conversations: query='{query}', mode={search_mode}, limit={limit}")

        # Configure search based on mode
        # All search methods return Tuple[List[SearchResult], Dict[str, Any]]
        if search_mode == "vector":
            results, _ = search_service.search_vector_only(query, limit=limit)
        elif search_mode == "fulltext":
            results, _ = search_service.search_fts_only(query, limit=limit)
        else:  # hybrid
            results, _ = search_service.search(query, limit=limit)

        if not results:
            return [TextContent(
                type="text",
                text=f"No conversations found matching query: '{query}'"
            )]

        # Format results for LLM consumption
        output_lines = [
            f"Found {len(results)} conversation(s) matching '{query}':\n"
        ]

        for i, result in enumerate(results, 1):
            conversation_id = result.conversation_id
            title = result.conversation_title or "Untitled"
            score = result.combined_score
            snippet = result.content or "No preview available"

            output_lines.append(f"{i}. **{title}**")
            output_lines.append(f"   - ID: `{conversation_id}`")
            output_lines.append(f"   - Score: {score:.3f}")
            output_lines.append(f"   - Preview: {snippet[:200]}{'...' if len(snippet) > 200 else ''}")
            output_lines.append("")

        output_lines.append(f"\nUse fetch_conversation with a conversation ID to read full content.")

        return [TextContent(
            type="text",
            text="\n".join(output_lines)
        )]

    except Exception as e:
        logger.error(f"Search error: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error during search: {str(e)}"
        )]


async def handle_fetch(arguments: dict) -> Sequence[TextContent]:
    """Handle fetch_conversation tool call."""
    try:
        conversation_id_str = arguments.get("conversation_id")

        if not conversation_id_str:
            return [TextContent(
                type="text",
                text="Error: 'conversation_id' parameter is required"
            )]

        # Parse UUID
        try:
            conversation_id = UUID(conversation_id_str)
        except ValueError:
            return [TextContent(
                type="text",
                text=f"Error: Invalid UUID format: '{conversation_id_str}'"
            )]

        logger.info(f"Fetching conversation: {conversation_id}")

        # Fetch conversation with messages using session context
        with get_session_context() as session:
            conversation_repo = ConversationRepository(session)
            conversation = conversation_repo.get_with_messages(conversation_id)

            if not conversation:
                return [TextContent(
                    type="text",
                    text=f"Error: Conversation not found: {conversation_id}"
                )]

            # Format conversation for LLM consumption
            title = conversation.title or "Untitled"
            created_at = conversation.created_at.strftime("%Y-%m-%d %H:%M:%S") if conversation.created_at else "Unknown"
            message_count = len(conversation.messages)

            output_lines = [
                f"# {title}\n",
                f"**Conversation ID:** `{conversation_id}`",
                f"**Created:** {created_at}",
                f"**Messages:** {message_count}\n",
                "---\n"
            ]

            # Add messages
            for msg in conversation.messages:
                role = msg.role.upper() if msg.role else "UNKNOWN"
                content = msg.content or ""
                msg_time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else ""

                output_lines.append(f"**{role}** ({msg_time})")
                output_lines.append(content)
                output_lines.append("")

            return [TextContent(
                type="text",
                text="\n".join(output_lines)
            )]

    except Exception as e:
        logger.error(f"Fetch error: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error fetching conversation: {str(e)}"
        )]


# SSE transport instance
sse_transport = SseServerTransport("/messages/")


async def handle_sse(request: Request) -> Response:
    """Handle SSE connection for MCP communication."""
    async with sse_transport.connect_sse(
        request.scope,
        request.receive,
        request._send,
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )
    return Response()


async def health_check(request: Request) -> Response:
    """Health check endpoint."""
    return Response(
        content='{"status": "ok", "service": "dovos-mcp"}',
        media_type="application/json"
    )


# Create Starlette app
app = Starlette(
    debug=False,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/health", endpoint=health_check),
        Mount("/messages", app=sse_transport.handle_post_message),
    ],
    on_startup=[initialize_services]
)


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
