from pathlib import Path

# === CONFIG ===
COLLECTION_NAME = "chat_history"
PERSIST_DIR = "./chroma_storage"
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SECRET_KEY = "your-secret-key-change-this-in-production"

# Create storage dir if it doesn't exist
Path(PERSIST_DIR).mkdir(exist_ok=True)