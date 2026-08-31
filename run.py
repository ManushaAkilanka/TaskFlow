import os
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    # DEVELOPMENT ONLY: debug=True enables the Werkzeug debugger and auto-reloader.
    # NEVER run with debug=True in production. Use a production WSGI server
    # (e.g., gunicorn run:app) instead of this development entry point.
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=True)
