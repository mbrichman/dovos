from flask import Flask

from config import SECRET_KEY
from chat_archive import ChatArchive
from routes import init_routes

# Create global archive instance
archive = ChatArchive()

# === Flask App ===
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

# Initialize routes
init_routes(app, archive)

# === Main ===
if __name__ == "__main__":
    app.run(debug=True)