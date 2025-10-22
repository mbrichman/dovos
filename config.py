import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === CONFIG ===
SECRET_KEY = "your-secret-key-change-this-in-production"

# Legacy config (kept for backward compatibility during migration)
COLLECTION_NAME = "chat_history"  # unused
PERSIST_DIR = "./chroma_storage"  # unused
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # unused

# Feature Flags
USE_PG_SINGLE_STORE = True  # PostgreSQL is now the only supported backend

# PostgreSQL Configuration (for new single-store architecture)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dovos_dev")
PGAPPNAME = os.getenv("PGAPPNAME", "dovos-api")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# OpenWebUI Configuration
OPENWEBUI_URL = "http://100.116.198.80:3000"
OPENWEBUI_API_KEY = "sk-44016316021243d0b0a00ba36aa0c22e"
