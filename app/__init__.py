import os
from dotenv import load_dotenv
from flask import Flask, render_template, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Automatically load environment variables from .env if present
load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(test_config=None):
    """Application Factory for TaskFlow."""
    app = Flask(__name__, instance_relative_config=True)

    # Database Configuration (supports DATABASE_URL for Render PostgreSQL, falls back to local SQLite)
    raw_db_uri = os.environ.get("DATABASE_URL")
    if raw_db_uri:
        # Handle Render/Heroku postgres:// scheme for SQLAlchemy compatibility
        if raw_db_uri.startswith("postgres://"):
            raw_db_uri = raw_db_uri.replace("postgres://", "postgresql://", 1)
        db_uri = raw_db_uri
    else:
        # Ensure the instance folder exists for local SQLite database
        os.makedirs(app.instance_path, exist_ok=True)
        db_path = os.path.join(app.instance_path, "taskflow.db")
        db_uri = f"sqlite:///{db_path}"

    # Default Configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-taskflow-key-change-in-prod"),
        SQLALCHEMY_DATABASE_URI=db_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    # Support reverse proxy headers (Render, Nginx, load balancers)
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    except Exception:
        pass

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    # Register models & blueprints
    from app import models  # noqa: F401
    from app.cli import cli_bp
    from app.auth import auth_bp
    from app.routes import main_bp

    app.register_blueprint(cli_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Custom Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.route("/favicon.ico")
    def favicon():
        return Response("", status=204, mimetype="image/x-icon")

    # Automatically create tables if not existing and apply non-destructive column upgrades
    with app.app_context():
        db.create_all()
    models.upgrade_db_schema(app)

    return app
