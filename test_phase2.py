import os
from datetime import date
from app import create_app, db
from app.models import User, Category, Task, Settings

def test_phase2_database_and_models():
    print("=== STARTING PHASE 2 VERIFICATION ===")
    app = create_app()

    with app.app_context():
        # 1. Verify instance database path
        db_path = os.path.join(app.instance_path, "taskflow.db")
        print(f"1. Database path: {db_path}")
        assert os.path.exists(db_path), "Database file does not exist!"
        print("   -> SQLite database file verified.")

        # 2. Verify all 4 tables exist
        tables = list(db.metadata.tables.keys())
        print(f"2. Tables in metadata: {tables}")
        for expected in ["users", "categories", "tasks", "settings"]:
            assert expected in tables, f"Missing table: {expected}"
        print("   -> All 4 tables (users, categories, tasks, settings) verified.")

        # Clean slate for testing
        db.drop_all()
        db.create_all()

        # 3. Test User model and password hashing
        user = User(
            full_name="Test User",
            email="test@example.com",
            bio="Software Tester"
        )
        user.set_password("SecurePassword!123")
        assert user.password_hash != "SecurePassword!123", "Password stored as plaintext!"
        assert user.check_password("SecurePassword!123") is True, "Password verification failed!"
        assert user.check_password("WrongPassword") is False, "Invalid password matched!"
        db.session.add(user)
        db.session.commit()
        print(f"3. User model created: ID={user.id}, Email={user.email}")
        print("   -> Secure Werkzeug password hashing verified.")

        # 4. Test default data provisioning (Categories + Settings)
        categories = user.init_default_data()
        db.session.commit()
        print(f"4. Provisioned {len(categories)} categories and settings.")
        
        user_categories = user.categories.all()
        cat_names = [c.name for c in user_categories]
        print(f"   -> User categories: {cat_names}")
        assert "Work" in cat_names
        assert "Personal" in cat_names
        assert "University" in cat_names

        assert user.settings is not None
        assert user.settings.appearance == "light"
        assert user.settings.notifications_enabled is True
        assert user.settings.system_alerts_enabled is True
        print(f"   -> Settings verified: appearance={user.settings.appearance}, notifications={user.settings.notifications_enabled}")

        # 5. Test Task model & relationships
        work_cat = Category.query.filter_by(user_id=user.id, name="Work").first()
        task1 = Task(
            user_id=user.id,
            category_id=work_cat.id,
            title="Complete Phase 2",
            description="Verify models and SQLite database",
            priority="high",
            status="in_progress",
            due_date=date.today()
        )
        db.session.add(task1)
        db.session.commit()
        print(f"5. Task created: ID={task1.id}, Title='{task1.title}', Priority={task1.priority}")
        assert task1.user.id == user.id
        assert task1.category.name == "Work"
        assert user.tasks.count() == 1
        assert work_cat.tasks.count() == 1

        # Test task methods
        task1.mark_completed()
        assert task1.status == "completed"
        assert task1.completed_at is not None
        task1.archive()
        assert task1.archived_at is not None
        db.session.commit()
        print("   -> Task completion, completed_at, and archived_at timestamps verified.")

        # 6. Test Data Isolation & Cascade Deletion
        user2 = User(
            full_name="Second User",
            email="user2@example.com"
        )
        user2.set_password("Password2")
        db.session.add(user2)
        db.session.commit()
        user2.init_default_data()
        db.session.commit()

        # Verify user 2 cannot see user 1's tasks
        assert user2.tasks.count() == 0
        print("6. User data isolation verified (User 2 has 0 tasks while User 1 has 1 task).")

        # Cascade delete test
        db.session.delete(user)
        db.session.commit()
        assert Task.query.filter_by(id=task1.id).first() is None
        assert Settings.query.filter_by(user_id=user.id).first() is None
        assert Category.query.filter_by(user_id=user.id).count() == 0
        print("   -> Cascade delete on User deletion verified.")

    # 7. Test CLI seed mechanism
    print("7. Testing CLI seed mechanism...")
    runner = app.test_cli_runner()
    result = runner.invoke(args=["cli", "seed-db"])
    print(f"   -> Seed output: {result.output.strip()}")
    assert result.exit_code == 0, f"Seed failed: {result.output}"

    with app.app_context():
        demo_user = User.query.filter_by(email="jane.doe@example.com").first()
        assert demo_user is not None
        assert demo_user.tasks.count() >= 7
        assert demo_user.categories.count() == 3
        assert demo_user.settings is not None
        print(f"   -> Seed verification: Demo user '{demo_user.full_name}' has {demo_user.tasks.count()} tasks, {demo_user.categories.count()} categories, and settings configured.")

    # 8. Test Data Persistence across new application instance
    print("8. Testing persistence across app restart...")
    app_restarted = create_app()
    with app_restarted.app_context():
        persisted_user = User.query.filter_by(email="jane.doe@example.com").first()
        assert persisted_user is not None
        assert persisted_user.tasks.count() >= 7
        print("   -> Database persistence across app restart verified.")

    print("=== ALL PHASE 2 TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_phase2_database_and_models()
