import os
from datetime import datetime, timezone
import sqlite3
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

# Ensure SQLite enforces foreign key constraints and sets a safe timeout
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def utc_now():
    """Returns current UTC datetime."""
    return datetime.now(timezone.utc)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.String(255), nullable=True)
    
    # Email Verification & OAuth Fields
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    github_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    google_id = db.Column(db.String(100), unique=True, nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    categories = db.relationship(
        "Category", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    tasks = db.relationship(
        "Task", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    settings = db.relationship(
        "Settings", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """Hashes and sets the user's password using Werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies a plaintext password against the stored secure hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def init_default_data(self):
        """Creates default categories and settings for a new user."""
        default_categories = [
            {"name": "Work", "color_code": "#2563eb"},
            {"name": "Personal", "color_code": "#16a34a"},
            {"name": "University", "color_code": "#d97706"},
        ]
        created_categories = []
        for cat in default_categories:
            category = Category(
                user_id=self.id,
                name=cat["name"],
                color_code=cat["color_code"]
            )
            db.session.add(category)
            created_categories.append(category)

        # Default settings
        if not self.settings:
            user_settings = Settings(
                user_id=self.id,
                appearance="light",
                notifications_enabled=True,
                system_alerts_enabled=True
            )
            db.session.add(user_settings)

        return created_categories

    def __repr__(self):
        return f"<User {self.id}: {self.email}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    color_code = db.Column(db.String(20), nullable=True, default="#64748b")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    tasks = db.relationship(
        "Task", backref="category", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Category {self.id}: {self.name} (User {self.user_id})>"


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default="medium", nullable=False)  # high, medium, low
    status = db.Column(db.String(20), default="todo", nullable=False)      # todo, in_progress, completed
    due_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def mark_completed(self):
        """Marks task completed with completed_at timestamp."""
        self.status = "completed"
        self.completed_at = utc_now()

    def mark_uncompleted(self):
        """Reverts task to active status."""
        self.status = "todo"
        self.completed_at = None

    def archive(self):
        """Archives the task."""
        self.archived_at = utc_now()

    def restore(self):
        """Restores an archived task."""
        self.archived_at = None

    def __repr__(self):
        return f"<Task {self.id}: {self.title} (Status: {self.status})>"


class Settings(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    appearance = db.Column(db.String(20), default="light", nullable=False)
    notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    system_alerts_enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self):
        return f"<Settings for User {self.user_id}>"


def upgrade_db_schema(app):
    """Safely and non-destructively adds new columns to SQLite tables if missing."""
    with app.app_context():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        # Only run SQLite PRAGMA migrations on SQLite databases
        if not db_uri.startswith("sqlite:///"):
            return

        db_path = db_uri[len("sqlite:///"):]
        if not os.path.exists(db_path):
            db.create_all()
            return

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA table_info(users)")
            existing_cols = {row[1] for row in cur.fetchall()}

            if "email_verified" not in existing_cols:
                cur.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 1 NOT NULL")
            if "email_verified_at" not in existing_cols:
                cur.execute("ALTER TABLE users ADD COLUMN email_verified_at DATETIME")
            if "github_id" not in existing_cols:
                cur.execute("ALTER TABLE users ADD COLUMN github_id VARCHAR(100)")
            if "google_id" not in existing_cols:
                cur.execute("ALTER TABLE users ADD COLUMN google_id VARCHAR(100)")

            conn.commit()
        except Exception as e:
            print(f"[Schema Upgrade Notice] {e}")
        finally:
            conn.close()
