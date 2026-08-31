import click
from datetime import datetime, date, timedelta, timezone
from flask import Blueprint
from app import db
from app.models import User, Category, Task, Settings

cli_bp = Blueprint("cli", __name__)


def utc_now():
    return datetime.now(timezone.utc)


@cli_bp.cli.command("init-db")
def init_db():
    """Initializes the SQLite database tables."""
    db.create_all()
    click.echo("Initialized SQLite database tables in instance/taskflow.db.")


@cli_bp.cli.command("seed-db")
def seed_db():
    """Seeds the database with realistic development data for testing."""
    db.create_all()

    demo_email = "jane.doe@example.com"
    user = User.query.filter_by(email=demo_email).first()
    if not user:
        click.echo("Creating default demo user 'jane.doe@example.com'...")
        user = User(
            full_name="Jane Doe",
            email=demo_email,
            bio="Senior Python Developer focusing on automation and infrastructure.",
            avatar=None,
            email_verified=True,
            email_verified_at=utc_now()
        )
        user.set_password("taskflow123")
        db.session.add(user)
        db.session.flush()
        user.init_default_data()
        db.session.commit()

    # Call demo tasks seeder on user
    _seed_tasks_for_user(user)


@cli_bp.cli.command("seed-demo-tasks")
@click.option("--email", default="jane.doe@example.com", help="Email of user to seed demo tasks for.")
def seed_demo_tasks(email):
    """Safely and idempotently adds realistic demo tasks to the specified user's account."""
    user = User.query.filter_by(email=email).first()
    if not user:
        # Fallback to first active user if specified email not found
        user = User.query.first()
        if not user:
            click.echo(f"Error: User '{email}' not found and no users exist in database.")
            return
        click.echo(f"User '{email}' not found. Using primary account '{user.email}' instead.")

    _seed_tasks_for_user(user)


def _seed_tasks_for_user(user):
    """Helper to populate realistic tasks across all categories and states idempotently."""
    work_cat = Category.query.filter_by(user_id=user.id, name="Work").first()
    personal_cat = Category.query.filter_by(user_id=user.id, name="Personal").first()
    univ_cat = Category.query.filter_by(user_id=user.id, name="University").first()

    # If categories missing, provision defaults
    if not work_cat or not personal_cat or not univ_cat:
        user.init_default_data()
        db.session.commit()
        work_cat = Category.query.filter_by(user_id=user.id, name="Work").first()
        personal_cat = Category.query.filter_by(user_id=user.id, name="Personal").first()
        univ_cat = Category.query.filter_by(user_id=user.id, name="University").first()

    now = utc_now()
    today_date = date.today()

    demo_tasks_specs = [
        # WORK TASKS
        {
            "title": "Prepare weekly project report",
            "description": "Consolidate sprint velocity and deliverable metrics for stakeholders.",
            "category": work_cat,
            "priority": "high",
            "status": "todo",
            "due_date": today_date,
            "completed_at": None,
            "archived_at": None
        },
        {
            "title": "Review client requirements",
            "description": "Analyze RFC specifications for upcoming OAuth2 API integration.",
            "category": work_cat,
            "priority": "medium",
            "status": "todo",
            "due_date": today_date + timedelta(days=1),
            "completed_at": None,
            "archived_at": None
        },
        {
            "title": "Fix authentication bug in token renewal",
            "description": "BUG-204 Resolve race condition when refreshing OAuth tokens.",
            "category": work_cat,
            "priority": "high",
            "status": "completed",
            "due_date": today_date - timedelta(days=1),
            "completed_at": now - timedelta(hours=2),
            "archived_at": None
        },
        {
            "title": "Update project documentation",
            "description": "DOCS-492 Complete endpoint reference updates for TaskFlow Developer Edition.",
            "category": work_cat,
            "priority": "medium",
            "status": "completed",
            "due_date": today_date,
            "completed_at": now - timedelta(hours=3),
            "archived_at": now - timedelta(hours=3)  # Archived Today
        },
        {
            "title": "Deploy staging build v2.4.1-rc",
            "description": "TECH-88 Verified staging release pipeline.",
            "category": work_cat,
            "priority": "low",
            "status": "completed",
            "due_date": today_date - timedelta(days=1),
            "completed_at": now - timedelta(days=1, hours=4),
            "archived_at": now - timedelta(days=1, hours=4)  # Archived Yesterday
        },
        # PERSONAL TASKS
        {
            "title": "Buy groceries",
            "description": "Fresh produce, coffee beans, almond milk, and whole grains.",
            "category": personal_cat,
            "priority": "low",
            "status": "todo",
            "due_date": today_date + timedelta(days=2),
            "completed_at": None,
            "archived_at": None
        },
        {
            "title": "Plan weekend activities",
            "description": "Reserve mountain trail permits and hiking equipment.",
            "category": personal_cat,
            "priority": "medium",
            "status": "todo",
            "due_date": today_date + timedelta(days=4),
            "completed_at": None,
            "archived_at": None
        },
        {
            "title": "Pay utility bill",
            "description": "Monthly internet and electricity service invoices.",
            "category": personal_cat,
            "priority": "high",
            "status": "completed",
            "due_date": today_date - timedelta(days=2),
            "completed_at": now - timedelta(days=4),
            "archived_at": now - timedelta(days=4)  # Archived Older
        },
        {
            "title": "Schedule vehicle service",
            "description": "Annual safety inspection and synthetic oil change.",
            "category": personal_cat,
            "priority": "low",
            "status": "todo",
            "due_date": today_date + timedelta(days=7),
            "completed_at": None,
            "archived_at": None
        },
        # UNIVERSITY TASKS
        {
            "title": "Complete database assignment",
            "description": "Implement B-Tree indexing and query optimizer benchmarks.",
            "category": univ_cat,
            "priority": "high",
            "status": "todo",
            "due_date": today_date + timedelta(days=1),
            "completed_at": None,
            "archived_at": None
        },
        {
            "title": "Review lecture notes",
            "description": "Distributed systems consensus algorithms (Raft and Paxos).",
            "category": univ_cat,
            "priority": "medium",
            "status": "todo",
            "due_date": today_date + timedelta(days=3),
            "completed_at": None,
            "archived_at": None
        },
        {
            "title": "Prepare presentation slides",
            "description": "Cap-theorem tradeoffs presentation for computer science seminar.",
            "category": univ_cat,
            "priority": "medium",
            "status": "completed",
            "due_date": today_date - timedelta(days=1),
            "completed_at": now - timedelta(hours=6),
            "archived_at": None
        },
    ]

    added_count = 0
    for spec in demo_tasks_specs:
        # Check if task already exists by user_id and title to ensure idempotency
        existing = Task.query.filter_by(user_id=user.id, title=spec["title"]).first()
        if not existing:
            task = Task(
                user_id=user.id,
                category_id=spec["category"].id if spec["category"] else None,
                title=spec["title"],
                description=spec["description"],
                priority=spec["priority"],
                status=spec["status"],
                due_date=spec["due_date"],
                completed_at=spec["completed_at"],
                archived_at=spec["archived_at"]
            )
            db.session.add(task)
            added_count += 1

    db.session.commit()
    click.echo(f"Successfully seeded {added_count} realistic demo tasks for account: {user.email}")


@cli_bp.cli.command("reset-db")
def reset_db():
    """Drops all tables and recreates empty tables in SQLite."""
    db.drop_all()
    db.create_all()
    click.echo("Reset SQLite database (dropped all tables and recreated).")
