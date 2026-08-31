from datetime import date, timedelta
from app import create_app, db
from app.models import User, Category, Task, Settings

def test_phase4_dashboard_and_tasks():
    print("=== STARTING PHASE 4 AUTOMATED TEST SUITE ===")
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # 1. Test unauthenticated redirects
    print("1. Testing unauthenticated route protection...")
    for endpoint in ["/dashboard", "/tasks", "/archive", "/settings"]:
        r = client.get(endpoint)
        assert r.status_code == 302, f"Unprotected endpoint: {endpoint}"
        assert "/login" in r.headers["Location"]
    print("   -> All protected routes safely redirected unauthenticated guests to /login.")

    # 2. Setup test users
    print("2. Setting up isolated test users in SQLite...")
    with app.app_context():
        user_a = User.query.filter_by(email="usera@taskflow.dev").first()
        if not user_a:
            user_a = User(full_name="User Alpha", email="usera@taskflow.dev", email_verified=True)
            user_a.set_password("pass123")
            db.session.add(user_a)
            db.session.flush()
            user_a.init_default_data()
            db.session.commit()
        else:
            user_a.email_verified = True
            db.session.commit()

        user_b = User.query.filter_by(email="userb@taskflow.dev").first()
        if not user_b:
            user_b = User(full_name="User Beta", email="userb@taskflow.dev", email_verified=True)
            user_b.set_password("pass123")
            db.session.add(user_b)
            db.session.flush()
            user_b.init_default_data()
            db.session.commit()
        else:
            user_b.email_verified = True
            db.session.commit()

        user_a_id = user_a.id
        user_b_id = user_b.id

        # Clean existing tasks for test isolation
        Task.query.filter(Task.user_id.in_([user_a_id, user_b_id])).delete()
        db.session.commit()

        # Seed initial tasks for User A: 3 total (1 completed, 2 active: 1 high priority, 1 medium)
        cat_work_a = Category.query.filter_by(user_id=user_a_id, name="Work").first()
        cat_pers_a = Category.query.filter_by(user_id=user_a_id, name="Personal").first()

        t1 = Task(user_id=user_a_id, category_id=cat_work_a.id, title="Task Alpha 1", priority="high", status="todo", due_date=date.today())
        t2 = Task(user_id=user_a_id, category_id=cat_pers_a.id, title="Task Alpha 2", priority="medium", status="todo", due_date=date.today() + timedelta(days=1))
        t3 = Task(user_id=user_a_id, category_id=cat_work_a.id, title="Task Alpha 3 Completed", priority="low", status="completed")
        t3.mark_completed()

        # Task for User B
        cat_work_b = Category.query.filter_by(user_id=user_b_id, name="Work").first()
        t_b = Task(user_id=user_b_id, category_id=cat_work_b.id, title="User B Secret Task", priority="high", status="todo")

        cat_work_a_id = cat_work_a.id
        cat_pers_a_id = cat_pers_a.id
        cat_work_b_id = cat_work_b.id

        db.session.add_all([t1, t2, t3, t_b])
        db.session.commit()
        t1_id, t2_id, t3_id, tb_id = t1.id, t2.id, t3.id, t_b.id

    # 3. Log in as User A
    print("3. Logging in as User Alpha...")
    r_login = client.post("/login", data={"email": "usera@taskflow.dev", "password": "pass123"}, follow_redirects=True)
    assert r_login.status_code == 200
    assert "User Alpha" in r_login.get_data(as_text=True)

    # 4. Test Dashboard Dynamic Calculations
    print("4. Testing Dashboard Dynamic Calculations for User Alpha...")
    r_dash = client.get("/dashboard")
    assert r_dash.status_code == 200
    content = r_dash.get_data(as_text=True)
    # Total active tasks = 3, completed = 1, remaining = 2, completion rate = round(1/3*100) = 33%
    assert "33%" in content, "Completion rate calculation mismatch!"
    assert "1 completed" in content
    assert "2 remaining" in content
    assert "Task Alpha 1" in content
    assert "User B Secret Task" not in content, "Cross-user data leakage on dashboard!"
    print("   -> Dashboard calculations verified: 33% completion, 1 completed, 2 remaining, strict user isolation.")

    # 5. Test Tasks Page and Filtering
    print("5. Testing /tasks and Filter Controls...")
    r_tasks = client.get("/tasks")
    assert r_tasks.status_code == 200
    t_content = r_tasks.get_data(as_text=True)
    assert "Task Alpha 1" in t_content
    assert "Task Alpha 2" in t_content
    assert "User B Secret Task" not in t_content

    # Filter by priority high
    r_high = client.get("/tasks?priority=high")
    assert "Task Alpha 1" in r_high.get_data(as_text=True)
    assert "Task Alpha 2" not in r_high.get_data(as_text=True)

    # Search query filter
    r_search = client.get("/tasks?q=Alpha+2")
    assert "Task Alpha 2" in r_search.get_data(as_text=True)
    assert "Task Alpha 1" not in r_search.get_data(as_text=True)

    # Quick filter today
    r_today = client.get("/tasks?quick=today")
    assert "Task Alpha 1" in r_today.get_data(as_text=True)
    print("   -> Filtering by priority, search query, and quick filter verified.")

    # 6. Test Task Creation
    print("6. Testing POST /tasks/create...")
    r_create = client.post("/tasks/create", data={
        "title": "Newly Created Automated Task",
        "description": "Integration test task description",
        "priority": "high",
        "category_id": cat_work_a_id,
        "due_date": date.today().isoformat()
    }, follow_redirects=True)
    assert r_create.status_code == 200
    assert "Task created successfully" in r_create.get_data(as_text=True)
    assert "Newly Created Automated Task" in r_create.get_data(as_text=True)
    print("   -> Task creation persisted and displayed.")

    with app.app_context():
        new_task = Task.query.filter_by(title="Newly Created Automated Task").first()
        assert new_task is not None
        assert new_task.user_id == user_a_id
        new_task_id = new_task.id

    # 7. Test Task Completion & Uncompletion
    print("7. Testing Task Completion and Uncompletion...")
    r_comp = client.post(f"/tasks/{t1_id}/complete", follow_redirects=True)
    assert r_comp.status_code == 200
    with app.app_context():
        t1_chk = Task.query.get(t1_id)
        assert t1_chk.status == "completed"
        assert t1_chk.completed_at is not None

    r_uncomp = client.post(f"/tasks/{t1_id}/uncomplete", follow_redirects=True)
    assert r_uncomp.status_code == 200
    with app.app_context():
        t1_chk = Task.query.get(t1_id)
        assert t1_chk.status == "todo"
        assert t1_chk.completed_at is None
    print("   -> Complete and uncomplete status transitions verified.")

    # 8. Test Task Archiving
    print("8. Testing Task Archiving...")
    r_arch = client.post(f"/tasks/{new_task_id}/archive", follow_redirects=True)
    assert r_arch.status_code == 200
    with app.app_context():
        t_arch = Task.query.get(new_task_id)
        assert t_arch.archived_at is not None

    # Archived task should not be in active /tasks list
    r_tasks_after_arch = client.get("/tasks")
    assert "Newly Created Automated Task" not in r_tasks_after_arch.get_data(as_text=True)
    print("   -> Archiving verified (timestamp set, excluded from active task list).")

    # 9. Test Task Deletion
    print("9. Testing Task Deletion...")
    r_del = client.post(f"/tasks/{new_task_id}/delete", follow_redirects=True)
    assert r_del.status_code == 200
    with app.app_context():
        assert Task.query.get(new_task_id) is None
    print("   -> Task deletion verified.")

    # 10. Test Security & Ownership Checks (User A attacking User B's task)
    print("10. Testing Cross-User Security & Authorization Defense...")
    r_bad_update = client.post(f"/tasks/{tb_id}/update", data={"title": "Hacked Title"})
    assert r_bad_update.status_code == 403, "User A was allowed to modify User B's task!"

    r_bad_complete = client.post(f"/tasks/{tb_id}/complete")
    assert r_bad_complete.status_code == 403, "User A was allowed to complete User B's task!"

    r_bad_archive = client.post(f"/tasks/{tb_id}/archive")
    assert r_bad_archive.status_code == 403, "User A was allowed to archive User B's task!"

    r_bad_delete = client.post(f"/tasks/{tb_id}/delete")
    assert r_bad_delete.status_code == 403, "User A was allowed to delete User B's task!"
    print("   -> All unauthorized access attempts blocked with HTTP 403 Forbidden.")

    print("=== ALL PHASE 4 TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_phase4_dashboard_and_tasks()
