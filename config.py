from pathlib import Path

# === CONFIG ===
COLLECTION_NAME = "chat_history"
PERSIST_DIR = "./chroma_storage"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SECRET_KEY = "your-secret-key-change-this-in-production"

# OpenWebUI Configuration
OPENWEBUI_URL = "http://100.116.198.80:3000"
OPENWEBUI_API_KEY = "sk-44016316021243d0b0a00ba36aa0c22e"

# Create storage dir if it doesn't exist
Path(PERSIST_DIR).mkdir(exist_ok=True)