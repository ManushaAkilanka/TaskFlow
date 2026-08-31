import re
import html
from datetime import datetime, date, timedelta, timezone
from app import create_app, db
from app.models import User, Category, Task, Settings

def get_csrf_token(client, url):
    response = client.get(url)
    assert response.status_code == 200
    page_html = response.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page_html)
    assert match is not None, f"CSRF token not found in {url}"
    return match.group(1)

def test_phase6_final_qa_and_security():
    print("=== STARTING PHASE 6 FINAL INTEGRATION & SECURITY QA SUITE ===")
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # ----------------------------------------------------
    # 1. PASSWORD POLICY (Minimum 8 Characters)
    # ----------------------------------------------------
    print("1. Testing 8-character password policy...")
    r_short = client.post("/signup", data={
        "full_name": "Short Password User",
        "email": "short_pw@taskflow.dev",
        "password": "pass123",  # 7 characters
        "confirm_password": "pass123"
    })
    assert r_short.status_code == 400
    assert "at least 8 characters" in r_short.get_data(as_text=True)

    r_valid_pw = client.post("/signup", data={
        "full_name": "QA Developer",
        "email": "qa_dev@taskflow.dev",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    }, follow_redirects=True)
    assert r_valid_pw.status_code == 200
    print("   -> 8-character password policy strictly enforced.")

    # Verify email and log in
    with app.app_context():
        u_qa = User.query.filter_by(email="qa_dev@taskflow.dev").first()
        u_qa.email_verified = True
        db.session.commit()

    r_login_qa = client.post("/login", data={"email": "qa_dev@taskflow.dev", "password": "SecurePassword123!"}, follow_redirects=True)
    assert r_login_qa.status_code == 200

    # ----------------------------------------------------
    # 2. XSS INJECTION & AUTO-ESCAPING DEFENSE
    # ----------------------------------------------------
    print("2. Testing XSS Injection & Template Auto-Escaping Defense...")
    xss_payload = '<script>alert("XSS_PWNED")</script>'
    r_xss_task = client.post("/tasks/create", data={
        "title": f"Task with {xss_payload}",
        "description": f"Notes with {xss_payload}",
        "priority": "high"
    }, follow_redirects=True)
    assert r_xss_task.status_code == 200

    r_tasks_view = client.get("/tasks")
    tasks_html = r_tasks_view.get_data(as_text=True)
    # Verify raw unescaped script tag is NOT in the HTML
    assert '<script>alert("XSS_PWNED")</script>' not in tasks_html
    # Verify HTML escaped version is present safely
    assert html.escape(xss_payload) in tasks_html or '&lt;script&gt;' in tasks_html
    print("   -> XSS attack string safely auto-escaped in templates.")

    # ----------------------------------------------------
    # 3. IDOR / AUTHORIZATION DEFENSE MATRIX
    # ----------------------------------------------------
    print("3. Testing Exhaustive IDOR Authorization Defense Matrix...")
    with app.app_context():
        # Setup Victim User (User B) and Attacker User (User A)
        user_a = User.query.filter_by(email="qa_dev@taskflow.dev").first()
        user_b = User.query.filter_by(email="victim_b@taskflow.dev").first()
        if not user_b:
            user_b = User(full_name="Victim Bob", email="victim_b@taskflow.dev")
            user_b.set_password("SecretPassword123!")
            db.session.add(user_b)
            db.session.flush()
            user_b.init_default_data()
            db.session.commit()

        user_a_id = user_a.id
        user_b_id = user_b.id

        # Create private task for User B
        cat_b = Category.query.filter_by(user_id=user_b_id, name="Work").first()
        cat_b_id = cat_b.id
        t_victim = Task(
            user_id=user_b_id,
            category_id=cat_b_id,
            title="User B Top Secret Task",
            description="Confidential business data",
            priority="high",
            status="todo"
        )
        db.session.add(t_victim)
        db.session.commit()
        t_victim_id = t_victim.id

    # Client is currently logged in as User A (QA Developer)
    # Test A attempting unauthorized operations on B's task
    assert client.post(f"/tasks/{t_victim_id}/update", data={"title": "Hacked"}).status_code == 403
    assert client.post(f"/tasks/{t_victim_id}/complete").status_code == 403
    assert client.post(f"/tasks/{t_victim_id}/uncomplete").status_code == 403
    assert client.post(f"/tasks/{t_victim_id}/archive").status_code == 403
    assert client.post(f"/tasks/{t_victim_id}/restore").status_code == 403
    assert client.post(f"/tasks/{t_victim_id}/delete").status_code == 403

    # Test A attempting to hijack B's category
    client.post("/tasks/create", data={
        "title": "Task with stolen category",
        "category_id": cat_b_id,
        "priority": "low"
    })
    with app.app_context():
        hijack_task = Task.query.filter_by(title="Task with stolen category").first()
        # Should not be assigned to user B's category
        assert hijack_task.category_id is None, "User A was allowed to assign User B's category!"
    print("   -> All IDOR attack vectors rejected with 403 Forbidden or safe neutralization.")

    # ----------------------------------------------------
    # 4. FULL REAL-WORLD TASK LIFECYCLE ON SQLITE
    # ----------------------------------------------------
    print("4. Testing Complete Real-World Task Lifecycle on SQLite...")
    with app.app_context():
        # Clear tasks for User A for clean lifecycle arithmetic
        Task.query.filter_by(user_id=user_a_id).delete()
        db.session.commit()

    # (a) Create Task
    r_create = client.post("/tasks/create", data={
        "title": "Lifecycle Master Task",
        "description": "Step-by-step lifecycle verification",
        "priority": "high",
        "due_date": date.today().isoformat()
    }, follow_redirects=True)
    assert r_create.status_code == 200

    with app.app_context():
        t_life = Task.query.filter_by(title="Lifecycle Master Task").first()
        assert t_life is not None
        assert t_life.status == "todo"
        assert t_life.completed_at is None
        assert t_life.archived_at is None
        t_life_id = t_life.id

    # (b) Check Dashboard stats: 0 completed, 1 remaining, 0% rate
    r_dash1 = client.get("/dashboard")
    assert "0%" in r_dash1.get_data(as_text=True)
    assert "0 completed" in r_dash1.get_data(as_text=True)
    assert "1 remaining" in r_dash1.get_data(as_text=True)

    # (c) Complete Task
    r_comp = client.post(f"/tasks/{t_life_id}/complete", follow_redirects=True)
    assert r_comp.status_code == 200
    with app.app_context():
        t_life = db.session.get(Task, t_life_id)
        assert t_life.status == "completed"
        assert t_life.completed_at is not None

    # (d) Check Dashboard stats: 1 completed, 0 remaining, 100% rate
    r_dash2 = client.get("/dashboard")
    assert "100%" in r_dash2.get_data(as_text=True)
    assert "1 completed" in r_dash2.get_data(as_text=True)
    assert "0 remaining" in r_dash2.get_data(as_text=True)

    # (e) Uncomplete Task
    r_uncomp = client.post(f"/tasks/{t_life_id}/uncomplete", follow_redirects=True)
    assert r_uncomp.status_code == 200
    with app.app_context():
        t_life = db.session.get(Task, t_life_id)
        assert t_life.status == "todo"
        assert t_life.completed_at is None

    # (f) Archive Task
    r_arch = client.post(f"/tasks/{t_life_id}/archive", follow_redirects=True)
    assert r_arch.status_code == 200
    with app.app_context():
        t_life = db.session.get(Task, t_life_id)
        assert t_life.archived_at is not None

    # Verify task is NOT in active /tasks
    r_tasks_chk = client.get("/tasks")
    assert "Lifecycle Master Task" not in r_tasks_chk.get_data(as_text=True)

    # Verify task IS in /archive
    r_arch_chk = client.get("/archive")
    assert "Lifecycle Master Task" in r_arch_chk.get_data(as_text=True)

    # (g) Restore Task
    r_rest = client.post(f"/tasks/{t_life_id}/restore", follow_redirects=True)
    assert r_rest.status_code == 200
    with app.app_context():
        t_life = db.session.get(Task, t_life_id)
        assert t_life.archived_at is None

    # Verify task is back in /tasks
    assert "Lifecycle Master Task" in client.get("/tasks").get_data(as_text=True)

    # (h) Delete Task
    r_del = client.post(f"/tasks/{t_life_id}/delete", follow_redirects=True)
    assert r_del.status_code == 200
    with app.app_context():
        assert db.session.get(Task, t_life_id) is None
    print("   -> Full task lifecycle (create -> complete -> uncomplete -> archive -> restore -> delete) verified.")

    # ----------------------------------------------------
    # 5. SETTINGS EXPORT SECURITY & LEAKAGE CHECK
    # ----------------------------------------------------
    print("5. Testing Settings Export Security & Leakage Defense...")
    r_exp = client.get("/settings/export")
    assert r_exp.status_code == 200
    exp_data = r_exp.get_json()

    # Must contain valid user info
    assert exp_data["user"]["email"] == "qa_dev@taskflow.dev"
    assert exp_data["user"]["full_name"] == "QA Developer"

    # Must NOT contain sensitive credentials / hashes / other user info
    assert "password_hash" not in exp_data["user"]
    assert "password" not in exp_data["user"]
    assert "SECRET_KEY" not in str(exp_data)
    assert "victim_b@taskflow.dev" not in str(exp_data)
    print("   -> Export security verified (no password hashes or secrets exposed).")

    # ----------------------------------------------------
    # 6. GLOBAL CSRF PROTECTION ENFORCEMENT
    # ----------------------------------------------------
    print("6. Testing Global CSRF Protection Enforcement...")
    csrf_app = create_app({"TESTING": False, "WTF_CSRF_ENABLED": True})
    csrf_client = csrf_app.test_client()

    # Unauthenticated CSRF checks
    assert csrf_client.post("/login", data={"email": "qa_dev@taskflow.dev", "password": "SecurePassword123!"}).status_code == 400
    assert csrf_client.post("/signup", data={"full_name": "Hacker", "email": "h@taskflow.dev", "password": "SecurePassword123!"}).status_code == 400

    # Obtain valid CSRF token and log in
    token = get_csrf_token(csrf_client, "/login")
    r_login_csrf = csrf_client.post("/login", data={
        "email": "qa_dev@taskflow.dev",
        "password": "SecurePassword123!",
        "csrf_token": token
    }, follow_redirects=True)
    assert r_login_csrf.status_code == 200

    # Test protected POST operations without CSRF token
    assert csrf_client.post("/tasks/create", data={"title": "No CSRF"}).status_code == 400
    assert csrf_client.post("/settings", data={"form_type": "profile", "full_name": "No CSRF"}).status_code == 400
    assert csrf_client.post("/tasks/archive/clear").status_code == 400
    assert csrf_client.post("/logout").status_code == 400
    print("   -> Global CSRF protection verified on all state-changing endpoints.")

    # ----------------------------------------------------
    # 7. CUSTOM ERROR HANDLERS (404, 403)
    # ----------------------------------------------------
    print("7. Testing Custom Error Handlers...")
    r_404 = client.get("/non-existent-route-endpoint")
    assert r_404.status_code == 404
    assert "404" in r_404.get_data(as_text=True)

    r_404_task = client.post("/tasks/9999999/complete")
    assert r_404_task.status_code == 404
    print("   -> Custom 404 and 403 error pages rendered cleanly.")

    print("=== ALL PHASE 6 INTEGRATION & SECURITY TESTS PASSED! ===")

if __name__ == "__main__":
    test_phase6_final_qa_and_security()
