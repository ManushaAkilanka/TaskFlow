import json
from datetime import datetime, date, timedelta, timezone
from app import create_app, db
from app.models import User, Category, Task, Settings

def test_phase5_archive_and_settings():
    print("=== STARTING PHASE 5 AUTOMATED TEST SUITE ===")
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # 1. Unauthenticated Route Redirection
    print("1. Testing unauthenticated route protection...")
    for endpoint in ["/archive", "/settings", "/settings/export"]:
        r = client.get(endpoint)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
    print("   -> Unauthenticated /archive and /settings safely redirected to /login.")

    # 2. Setup Test Users & Scoped Archive Data
    print("2. Setting up isolated test users in SQLite...")
    now_utc = datetime.now(timezone.utc)
    with app.app_context():
        user_p5 = User.query.filter_by(email="p5_user@taskflow.dev").first()
        if not user_p5:
            user_p5 = User(full_name="Phase5 Developer", email="p5_user@taskflow.dev", bio="Original Bio", email_verified=True)
            user_p5.set_password("pass123")
            db.session.add(user_p5)
            db.session.flush()
            user_p5.init_default_data()
            db.session.commit()
        else:
            user_p5.email_verified = True
            db.session.commit()

        user_other = User.query.filter_by(email="other_p5@taskflow.dev").first()
        if not user_other:
            user_other = User(full_name="Other Developer", email="other_p5@taskflow.dev", email_verified=True)
            user_other.set_password("pass123")
            db.session.add(user_other)
            db.session.flush()
            user_other.init_default_data()
            db.session.commit()
        else:
            user_other.email_verified = True
            db.session.commit()

        user_id = user_p5.id
        other_id = user_other.id

        # Clean existing tasks for user_p5
        Task.query.filter(Task.user_id.in_([user_id, other_id])).delete()
        db.session.commit()

        work_cat = Category.query.filter_by(user_id=user_id, name="Work").first()

        # Task 1: Archived Today
        t_today = Task(
            user_id=user_id,
            category_id=work_cat.id,
            title="Archived Task Today",
            status="completed",
            completed_at=now_utc - timedelta(hours=2),
            archived_at=now_utc - timedelta(hours=2)
        )
        # Task 2: Archived Yesterday
        t_yesterday = Task(
            user_id=user_id,
            category_id=work_cat.id,
            title="Archived Task Yesterday",
            status="completed",
            completed_at=now_utc - timedelta(days=1, hours=3),
            archived_at=now_utc - timedelta(days=1, hours=3)
        )
        # Task 3: Archived Older (e.g. 5 days ago)
        t_older = Task(
            user_id=user_id,
            category_id=work_cat.id,
            title="Archived Task Older",
            status="completed",
            completed_at=now_utc - timedelta(days=5),
            archived_at=now_utc - timedelta(days=5)
        )
        # Task 4: Active task (not archived)
        t_active = Task(
            user_id=user_id,
            category_id=work_cat.id,
            title="Active Unarchived Task",
            status="todo"
        )
        # Task 5: Other user's archived task
        t_other_arch = Task(
            user_id=other_id,
            title="Other User Secret Archive",
            status="completed",
            archived_at=now_utc
        )

        db.session.add_all([t_today, t_yesterday, t_older, t_active, t_other_arch])
        db.session.commit()

        t_today_id = t_today.id
        t_yesterday_id = t_yesterday.id
        t_older_id = t_older.id
        t_other_arch_id = t_other_arch.id

    # 3. Log in as Phase5 Developer
    print("3. Logging in as Phase5 Developer...")
    r_login = client.post("/login", data={"email": "p5_user@taskflow.dev", "password": "pass123"}, follow_redirects=True)
    assert r_login.status_code == 200

    # 4. Test Archive Display and Grouping
    print("4. Testing /archive Display and Dynamic Date Grouping...")
    r_arch = client.get("/archive")
    assert r_arch.status_code == 200
    arch_html = r_arch.get_data(as_text=True)

    # Verify archived tasks exist
    assert "Archived Task Today" in arch_html
    assert "Archived Task Yesterday" in arch_html
    assert "Archived Task Older" in arch_html

    # Verify active task does NOT appear in archive
    assert "Active Unarchived Task" not in arch_html, "Active task leaked into Archive page!"

    # Verify cross-user isolation
    assert "Other User Secret Archive" not in arch_html, "Other user's archived task leaked into Archive!"

    # Verify date headings
    assert "Today" in arch_html
    assert "Yesterday" in arch_html
    assert "Older" in arch_html
    print("   -> Archive dynamic date grouping and strict user isolation verified.")

    # 5. Test Search Filtering in Archive
    print("5. Testing Archive Search Query...")
    r_search = client.get("/archive?q=Yesterday")
    search_html = r_search.get_data(as_text=True)
    assert "Archived Task Yesterday" in search_html
    assert "Archived Task Today" not in search_html
    print("   -> Archive search filtering verified.")

    # 6. Test Task Restore
    print("6. Testing POST /tasks/<id>/restore...")
    r_restore = client.post(f"/tasks/{t_today_id}/restore", follow_redirects=True)
    assert r_restore.status_code == 200
    assert "Task restored to active tasks" in r_restore.get_data(as_text=True)

    with app.app_context():
        t_chk = db.session.get(Task, t_today_id)
        assert t_chk.archived_at is None, "Restored task still has archived_at timestamp!"

    # Verify restored task appears in /tasks active list
    r_tasks_chk = client.get("/tasks")
    assert "Archived Task Today" in r_tasks_chk.get_data(as_text=True)
    print("   -> Task restoration verified: returned to active tasks list.")

    # 7. Test Cross-User Restore and Delete Defense
    print("7. Testing Cross-User Restore & Delete Authorization Defense...")
    r_bad_rest = client.post(f"/tasks/{t_other_arch_id}/restore")
    assert r_bad_rest.status_code == 403, "User was allowed to restore another user's task!"

    r_bad_del = client.post(f"/tasks/{t_other_arch_id}/delete")
    assert r_bad_del.status_code == 403, "User was allowed to delete another user's task!"
    print("   -> Unauthorized restore and delete attempts blocked with HTTP 403 Forbidden.")

    # 8. Test Settings Page Viewing
    print("8. Testing GET /settings...")
    r_settings = client.get("/settings")
    assert r_settings.status_code == 200
    set_html = r_settings.get_data(as_text=True)
    assert "Phase5 Developer" in set_html
    assert "p5_user@taskflow.dev" in set_html
    assert "Original Bio" in set_html
    assert "Environment" in set_html
    assert "System Data" in set_html
    print("   -> Settings page rendered with user profile and preferences.")

    # 9. Test Profile Information Update
    print("9. Testing POST /settings (Profile Update)...")
    r_prof_update = client.post("/settings", data={
        "form_type": "profile",
        "full_name": "Updated Dev Name",
        "email": "p5_user@taskflow.dev",
        "bio": "Updated Infrastructure Engineer Bio",
        "avatar": "https://example.com/avatar.png"
    }, follow_redirects=True)
    assert r_prof_update.status_code == 200
    assert "Profile information updated successfully" in r_prof_update.get_data(as_text=True)

    with app.app_context():
        u_chk = db.session.get(User, user_id)
        assert u_chk.full_name == "Updated Dev Name"
        assert u_chk.bio == "Updated Infrastructure Engineer Bio"
        assert u_chk.avatar == "https://example.com/avatar.png"
    print("   -> Profile updates persisted directly to SQLite.")

    # 10. Test Preferences Update
    print("10. Testing POST /settings (Preferences Update)...")
    r_pref_update = client.post("/settings", data={
        "form_type": "preferences",
        "appearance": "light",
        # notifications_enabled unchecked (omitted from form)
        "system_alerts_enabled": "on"
    }, follow_redirects=True)
    assert r_pref_update.status_code == 200
    assert "Preferences updated successfully" in r_pref_update.get_data(as_text=True)

    with app.app_context():
        u_settings = db.session.get(User, user_id).settings
        assert u_settings.notifications_enabled is False
        assert u_settings.system_alerts_enabled is True
        assert u_settings.appearance == "light"
    print("   -> Preferences toggles updated and saved to SQLite.")

    # 11. Test Export Settings JSON
    print("11. Testing GET /settings/export...")
    r_export = client.get("/settings/export")
    assert r_export.status_code == 200
    export_json = r_export.get_json()
    assert export_json["user"]["full_name"] == "Updated Dev Name"
    assert export_json["settings"]["notifications_enabled"] is False
    assert len(export_json["categories"]) == 3
    print("   -> Configuration JSON export verified.")

    # 12. Test Settings Persistence Across App Restart
    print("12. Testing Settings persistence across app restart...")
    app_restarted = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
    with app_restarted.app_context():
        persisted_user = db.session.get(User, user_id)
        assert persisted_user.full_name == "Updated Dev Name"
        assert persisted_user.settings.notifications_enabled is False
        assert persisted_user.settings.system_alerts_enabled is True
    print("   -> SQLite persistence verified across restart.")

    # 13. Test Clear Archive
    print("13. Testing POST /tasks/archive/clear...")
    r_clear = client.post("/tasks/archive/clear", follow_redirects=True)
    assert r_clear.status_code == 200
    assert "Archive cleared" in r_clear.get_data(as_text=True)

    with app.app_context():
        assert Task.query.filter(Task.user_id == user_id, Task.archived_at.is_not(None)).count() == 0
        # Active task must still exist
        assert Task.query.filter(Task.user_id == user_id, Task.archived_at.is_(None)).count() >= 1
        # Other user's archived task must NOT be deleted
        assert db.session.get(Task, t_other_arch_id) is not None
    print("   -> Clear archive deleted only current user's archived tasks.")

    print("=== ALL PHASE 5 TESTS COMPLETED AND PASSED! ===")

if __name__ == "__main__":
    test_phase5_archive_and_settings()
