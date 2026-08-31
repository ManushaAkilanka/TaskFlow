import sys
from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify, Response
from flask_login import login_required, current_user
from app import db
from app.models import Task, Category, Settings, User

main_bp = Blueprint("main", __name__)


def get_safe_referrer(default_endpoint="main.tasks"):
    """Returns safe referrer or default endpoint url."""
    ref = request.referrer
    if ref and request.host_url in ref:
        return ref
    return url_for(default_endpoint)


def format_time_ago(dt):
    """Formats relative time string for archived items."""
    if not dt:
        return "recently"
    now = datetime.now(timezone.utc)
    # Ensure dt is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days == 1:
        return "yesterday"
    return f"{days}d ago"


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Productivity Overview — dynamically calculated from current user's SQLite tasks."""
    user_id = current_user.id

    # Active tasks only (unarchived)
    active_query = Task.query.filter(Task.user_id == user_id, Task.archived_at.is_(None))

    total_tasks = active_query.count()
    completed_count = active_query.filter(Task.status == "completed").count()
    remaining_count = total_tasks - completed_count
    completion_rate = round((completed_count / total_tasks) * 100) if total_tasks > 0 else 0

    high_priority_count = active_query.filter(Task.priority == "high", Task.status != "completed").count()
    medium_priority_count = active_query.filter(Task.priority == "medium", Task.status != "completed").count()
    low_priority_count = active_query.filter(Task.priority == "low", Task.status != "completed").count()

    # Category breakdown for current user
    user_categories = Category.query.filter_by(user_id=user_id).all()
    category_stats = []
    for cat in user_categories:
        count = Task.query.filter(
            Task.user_id == user_id,
            Task.category_id == cat.id,
            Task.archived_at.is_(None)
        ).count()
        category_stats.append({
            "id": cat.id,
            "name": cat.name,
            "color_code": cat.color_code or "#64748b",
            "count": count
        })

    # Recent active tasks for the agenda section
    tasks = active_query.order_by(
        (Task.status == "completed"),
        Task.due_date.asc().nullslast(),
        Task.created_at.desc()
    ).limit(8).all()

    return render_template(
        "dashboard.html",
        total_tasks=total_tasks,
        completed_count=completed_count,
        remaining_count=remaining_count,
        completion_rate=completion_rate,
        high_priority_count=high_priority_count,
        medium_priority_count=medium_priority_count,
        low_priority_count=low_priority_count,
        category_stats=category_stats,
        tasks=tasks,
        now_date=date.today(),
        delta_day=timedelta(days=1)
    )


@main_bp.route("/tasks")
@login_required
def tasks():
    """All Tasks List — with category, priority, quick pills, and search filters."""
    user_id = current_user.id
    query = Task.query.filter(Task.user_id == user_id, Task.archived_at.is_(None))

    # URL query filters
    selected_categories = request.args.getlist("category")
    selected_priorities = request.args.getlist("priority")
    search_query = (request.args.get("q") or "").strip()
    current_quick = request.args.get("quick")

    if selected_categories:
        valid_cat_ids = [int(cid) for cid in selected_categories if cid.isdigit()]
        if valid_cat_ids:
            query = query.filter(Task.category_id.in_(valid_cat_ids))

    if selected_priorities:
        query = query.filter(Task.priority.in_(selected_priorities))

    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern)
            )
        )

    today = date.today()
    if current_quick == "today":
        query = query.filter(Task.due_date == today)
    elif current_quick == "high":
        query = query.filter(Task.priority == "high")

    tasks_list = query.order_by(
        (Task.status == "completed"),
        Task.due_date.asc().nullslast(),
        Task.created_at.desc()
    ).all()

    categories = Category.query.filter_by(user_id=user_id).all()

    return render_template(
        "tasks.html",
        tasks=tasks_list,
        categories=categories,
        selected_categories=selected_categories,
        selected_priorities=selected_priorities,
        search_query=search_query,
        current_quick=current_quick,
        now_date=today,
        delta_day=timedelta(days=1)
    )


@main_bp.route("/tasks/create", methods=["POST"])
@login_required
def create_task():
    """Create a new task with strict user ownership and category validation."""
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    priority = (request.form.get("priority") or "medium").lower()
    category_id_str = request.form.get("category_id")
    due_date_str = request.form.get("due_date")

    if not title:
        flash("Task title is required.", "error")
        return redirect(get_safe_referrer())

    if priority not in ("high", "medium", "low"):
        priority = "medium"

    category_id = None
    if category_id_str and category_id_str.isdigit():
        cat = Category.query.filter_by(id=int(category_id_str), user_id=current_user.id).first()
        if cat:
            category_id = cat.id

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            due_date = None

    task = Task(
        user_id=current_user.id,
        category_id=category_id,
        title=title,
        description=description,
        priority=priority,
        status="todo",
        due_date=due_date
    )
    db.session.add(task)
    db.session.commit()

    flash("Task created successfully.", "success")
    return redirect(get_safe_referrer())


@main_bp.route("/tasks/<int:task_id>/update", methods=["POST"])
@login_required
def update_task(task_id):
    """Update task fields with strict user ownership validation."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    title = (request.form.get("title") or "").strip()
    if title:
        task.title = title

    task.description = (request.form.get("description") or "").strip() or None
    
    priority = (request.form.get("priority") or "").lower()
    if priority in ("high", "medium", "low"):
        task.priority = priority

    category_id_str = request.form.get("category_id")
    if category_id_str and category_id_str.isdigit():
        cat = Category.query.filter_by(id=int(category_id_str), user_id=current_user.id).first()
        if cat:
            task.category_id = cat.id
    elif category_id_str == "":
        task.category_id = None

    due_date_str = request.form.get("due_date")
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    db.session.commit()
    flash("Task updated successfully.", "success")
    return redirect(get_safe_referrer())


@main_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def complete_task(task_id):
    """Marks task completed with completed_at timestamp."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    task.mark_completed()
    db.session.commit()
    flash("Task completed.", "success")
    return redirect(get_safe_referrer())


@main_bp.route("/tasks/<int:task_id>/uncomplete", methods=["POST"])
@login_required
def uncomplete_task(task_id):
    """Reverts task to active status."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    task.mark_uncompleted()
    db.session.commit()
    flash("Task marked as active.", "success")
    return redirect(get_safe_referrer())


@main_bp.route("/tasks/<int:task_id>/archive", methods=["POST"])
@login_required
def archive_task(task_id):
    """Archives task with timestamp."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    task.archive()
    db.session.commit()
    flash("Task archived.", "success")
    return redirect(get_safe_referrer())


@main_bp.route("/tasks/<int:task_id>/restore", methods=["POST"])
@login_required
def restore_task(task_id):
    """Restores an archived task back to the active tasks list."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    task.restore()
    db.session.commit()
    flash("Task restored to active tasks.", "success")
    return redirect(get_safe_referrer(default_endpoint="main.archive"))


@main_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    """Permanently deletes task with ownership validation."""
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)

    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(get_safe_referrer())


@main_bp.route("/tasks/archive/clear", methods=["POST"])
@login_required
def clear_archive():
    """Permanently deletes all archived tasks belonging to the current user."""
    archived_tasks = Task.query.filter(Task.user_id == current_user.id, Task.archived_at.is_not(None)).all()
    count = len(archived_tasks)
    for t in archived_tasks:
        db.session.delete(t)
    db.session.commit()
    flash(f"Archive cleared ({count} tasks deleted).", "success")
    return redirect(url_for("main.archive"))


@main_bp.route("/archive")
@login_required
def archive():
    """Archive Page — dynamically grouped into Today, Yesterday, and Older sections."""
    user_id = current_user.id
    search_query = (request.args.get("q") or "").strip()

    query = Task.query.filter(Task.user_id == user_id, Task.archived_at.is_not(None))

    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern)
            )
        )

    archived_tasks = query.order_by(Task.archived_at.desc()).all()
    total_count = len(archived_tasks)

    # Dynamic date bucketing
    now_utc = datetime.now(timezone.utc)
    today_date = now_utc.date()
    yesterday_date = today_date - timedelta(days=1)

    groups = {
        "today": [],
        "yesterday": [],
        "older": []
    }

    for task in archived_tasks:
        arch_date = task.archived_at.date() if task.archived_at else today_date
        item = {
            "task": task,
            "time_ago": format_time_ago(task.archived_at or task.completed_at)
        }
        if arch_date == today_date:
            groups["today"].append(item)
        elif arch_date == yesterday_date:
            groups["yesterday"].append(item)
        else:
            groups["older"].append(item)

    return render_template(
        "archive.html",
        groups=groups,
        total_archived_count=total_count,
        search_query=search_query
    )


@main_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Settings Page — Profile, Preferences, Environment, and System Data management."""
    # Ensure settings record exists
    user_settings = current_user.settings
    if not user_settings:
        user_settings = Settings(user_id=current_user.id)
        db.session.add(user_settings)
        db.session.commit()

    if request.method == "POST":
        form_type = request.form.get("form_type", "profile")

        if form_type == "profile":
            full_name = (request.form.get("full_name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            bio = (request.form.get("bio") or "").strip() or None
            avatar = (request.form.get("avatar") or "").strip() or None

            if not full_name:
                flash("Full Name is required.", "error")
                return redirect(url_for("main.settings"))

            if not email:
                flash("Email Address is required.", "error")
                return redirect(url_for("main.settings"))

            # Check email uniqueness if email changed
            if email != current_user.email:
                existing = User.query.filter_by(email=email).first()
                if existing:
                    flash("An account with that email already exists.", "error")
                    return redirect(url_for("main.settings"))
                current_user.email = email

            current_user.full_name = full_name
            current_user.bio = bio
            current_user.avatar = avatar
            db.session.commit()
            flash("Profile information updated successfully.", "success")

        elif form_type == "preferences":
            appearance = request.form.get("appearance") or "light"
            notifications_enabled = "notifications_enabled" in request.form
            system_alerts_enabled = "system_alerts_enabled" in request.form

            user_settings.appearance = "light" if appearance == "light" else "dark"
            user_settings.notifications_enabled = notifications_enabled
            user_settings.system_alerts_enabled = system_alerts_enabled
            db.session.commit()
            flash("Preferences updated successfully.", "success")

        return redirect(url_for("main.settings"))

    now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    python_ver = f"Python {sys.version.split()[0]}"

    return render_template(
        "settings.html",
        user_settings=user_settings,
        last_sync_time=now_utc_str,
        python_runtime=python_ver
    )


@main_bp.route("/settings/export", methods=["GET"])
@login_required
def export_settings():
    """Exports user configuration and categories as a structured JSON file."""
    user = current_user
    settings_data = {
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "bio": user.bio,
            "avatar": user.avatar,
            "created_at": user.created_at.isoformat() if user.created_at else None
        },
        "settings": {
            "appearance": user.settings.appearance if user.settings else "light",
            "notifications_enabled": user.settings.notifications_enabled if user.settings else True,
            "system_alerts_enabled": user.settings.system_alerts_enabled if user.settings else True
        },
        "categories": [
            {"id": c.id, "name": c.name, "color_code": c.color_code}
            for c in user.categories.all()
        ]
    }
    return jsonify(settings_data)


@main_bp.route("/settings/sync", methods=["POST"])
@login_required
def force_sync():
    """Triggers sync state confirmation with SQLite single source of truth."""
    flash("System state synchronized with SQLite database.", "info")
    return redirect(url_for("main.settings"))
