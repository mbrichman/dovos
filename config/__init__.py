"""
Configuration package for Dovos application.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === CONFIG ===
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")

# PostgreSQL Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dovos_dev")
PGAPPNAME = os.getenv("PGAPPNAME", "dovos-api")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# OpenWebUI Configuration
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")

# RAG Context Configuration
RAG_DEFAULT_WINDOW_SIZE = int(os.getenv("RAG_WINDOW_SIZE", "3"))
RAG_MAX_WINDOW_SIZE = int(os.getenv("RAG_MAX_WINDOW_SIZE", "10"))
RAG_ADAPTIVE_WINDOWING = os.getenv("RAG_ADAPTIVE_WINDOWING", "true").lower() == "true"
RAG_DEDUPLICATE_MESSAGES = os.getenv("RAG_DEDUPLICATE_MESSAGES", "true").lower() == "true"
RAG_DEFAULT_TOP_K_WINDOWS = int(os.getenv("RAG_DEFAULT_TOP_K_WINDOWS", "8"))
RAG_DEFAULT_MAX_TOKENS = int(os.getenv("RAG_DEFAULT_MAX_TOKENS", "0"))  # 0 = no limit
RAG_PROXIMITY_DECAY_LAMBDA = float(os.getenv("RAG_PROXIMITY_DECAY_LAMBDA", "0.3"))
RAG_APPLY_RECENCY_BONUS = os.getenv("RAG_APPLY_RECENCY_BONUS", "false").lower() == "true"

# Import synonym functionality
from .synonyms import SEARCH_SYNONYMS, get_synonyms, add_synonym_mapping

__all__ = [
    'SECRET_KEY',
    'DATABASE_URL',
    'PGAPPNAME',
    'EMBEDDING_MODEL',
    'EMBEDDING_DIM',
    'OPENWEBUI_URL',
    'OPENWEBUI_API_KEY',
    'SEARCH_SYNONYMS',
    'get_synonyms',
    'add_synonym_mapping',
    'RAG_DEFAULT_WINDOW_SIZE',
    'RAG_MAX_WINDOW_SIZE',
    'RAG_ADAPTIVE_WINDOWING',
    'RAG_DEDUPLICATE_MESSAGES',
    'RAG_DEFAULT_TOP_K_WINDOWS',
    'RAG_DEFAULT_MAX_TOKENS',
    'RAG_PROXIMITY_DECAY_LAMBDA',
    'RAG_APPLY_RECENCY_BONUS'
]
