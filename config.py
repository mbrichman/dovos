import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === CONFIG ===
COLLECTION_NAME = "chat_history"
PERSIST_DIR = "./chroma_storage"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SECRET_KEY = "your-secret-key-change-this-in-production"

# Feature Flags
USE_PG_SINGLE_STORE = os.getenv("USE_POSTGRES", "false").lower() in ("true", "1", "yes")

# PostgreSQL Configuration (for new single-store architecture)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/dovos_dev")
PGAPPNAME = os.getenv("PGAPPNAME", "dovos-api")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# OpenWebUI Configuration
OPENWEBUI_URL = "http://100.116.198.80:3000"
OPENWEBUI_API_KEY = "sk-44016316021243d0b0a00ba36aa0c22e"

# Create storage dir if it doesn't exist (legacy path)
Path(PERSIST_DIR).mkdir(exist_ok=True)
