from flask import Flask
from flask_cors import CORS

from config import SECRET_KEY, USE_PG_SINGLE_STORE
from routes import init_routes

def create_app():
    """Application factory pattern for better testing and configuration"""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["USE_PG_SINGLE_STORE"] = USE_PG_SINGLE_STORE
    
    # Enable CORS for all routes
    CORS(app)
    
    # Initialize data layer based on feature flag
    if app.config["USE_PG_SINGLE_STORE"]:
        print("🚀 Using PostgreSQL single-store architecture")
        # Initialize database tables
        from db.database import create_tables
        try:
            create_tables()
        except Exception as e:
            print(f"⚠️ Database table creation warning: {e}")
        archive = None  # Placeholder - will implement in next steps
    else:
        print("📚 Using legacy ChromaDB + SQLite architecture")
        from models.conversation_model import ConversationModel
        archive = ConversationModel()
    
    # Initialize routes
    init_routes(app, archive)
    
    return app

# Create the app instance
app = create_app()

# === Main ===
if __name__ == "__main__":
    app.run(port=5001,debug=True)