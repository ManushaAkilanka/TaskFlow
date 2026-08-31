import os
import time
from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch
from flask import url_for
from app import create_app, db
from app.models import User, Category, Task, Settings
from app.auth_tokens import (
    generate_email_verification_token,
    verify_email_verification_token,
    generate_password_reset_token,
    verify_password_reset_token
)

def test_phase7_authentication_features():
    print("=== STARTING PHASE 7 AUTHENTICATION, EMAIL VERIFICATION & OAUTH TEST SUITE ===")
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key-phase-7"
    })

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # ----------------------------------------------------
    # 1. MANUAL SIGNUP & EMAIL VERIFICATION LIFECYCLE
    # ----------------------------------------------------
    print("1. Testing Manual Signup & Email Verification...")
    test_email = f"verified_dev_{int(time.time())}@taskflow.dev"
    password = "SecurePassword123!"

    # Signup
    r_signup = client.post("/signup", data={
        "full_name": "Verification Tester",
        "email": test_email,
        "password": password,
        "confirm_password": password
    }, follow_redirects=True)
    assert r_signup.status_code == 200
    assert "Verify your email" in r_signup.get_data(as_text=True) or "check your email" in r_signup.get_data(as_text=True)

    with app.app_context():
        u = User.query.filter_by(email=test_email).first()
        assert u is not None
        assert u.email_verified is False
        assert u.email_verified_at is None
        user_id = u.id

    # Try login before verification -> Must be rejected with 403
    r_unver_login = client.post("/login", data={"email": test_email, "password": password})
    assert r_unver_login.status_code == 403
    assert "verify your email" in r_unver_login.get_data(as_text=True).lower()
    print("   -> Unverified user login blocked with status 403.")

    # Generate token and verify email
    with app.app_context():
        token = generate_email_verification_token(test_email, app.config["SECRET_KEY"])
        assert verify_email_verification_token(token, app.config["SECRET_KEY"]) == test_email

    r_verify = client.get(f"/verify-email/{token}", follow_redirects=True)
    assert r_verify.status_code == 200
    assert "verified successfully" in r_verify.get_data(as_text=True)

    with app.app_context():
        u_ver = db.session.get(User, user_id)
        assert u_ver.email_verified is True
        assert u_ver.email_verified_at is not None

    # Now login must succeed
    r_login_ok = client.post("/login", data={"email": test_email, "password": password}, follow_redirects=True)
    assert r_login_ok.status_code == 200
    assert "Verification Tester" in r_login_ok.get_data(as_text=True)
    print("   -> Email verified successfully and user logged in.")

    # Test invalid / expired verification token
    r_bad_token = client.get("/verify-email/invalid-tampered-token", follow_redirects=True)
    assert r_bad_token.status_code == 200
    assert "invalid or has expired" in r_bad_token.get_data(as_text=True)
    print("   -> Tampered email token safely rejected.")

    # ----------------------------------------------------
    # 2. RESEND VERIFICATION
    # ----------------------------------------------------
    print("2. Testing Resend Verification...")
    client.post("/logout")
    r_resend_view = client.get("/resend-verification")
    assert r_resend_view.status_code == 200
    assert "Resend Verification Email" in r_resend_view.get_data(as_text=True)

    # Post resend for existing and non-existing email (generic message prevents account enumeration)
    r_resend_post = client.post("/resend-verification", data={"email": test_email}, follow_redirects=True)
    assert r_resend_post.status_code == 200
    assert "verification link has been sent" in r_resend_post.get_data(as_text=True)

    r_resend_anon = client.post("/resend-verification", data={"email": "nobody@taskflow.dev"}, follow_redirects=True)
    assert r_resend_anon.status_code == 200
    assert "verification link has been sent" in r_resend_anon.get_data(as_text=True)
    print("   -> Resend verification functional and protected against account enumeration.")

    # ----------------------------------------------------
    # 3. FORGOT PASSWORD & PASSWORD RESET LIFECYCLE
    # ----------------------------------------------------
    print("3. Testing Password Reset Workflow...")
    # Forgot password page
    r_fp_view = client.get("/forgot-password")
    assert r_fp_view.status_code == 200
    assert "Reset Password" in r_fp_view.get_data(as_text=True)

    # Submit email for reset (generic message prevents account enumeration)
    r_fp_post = client.post("/forgot-password", data={"email": test_email}, follow_redirects=True)
    assert r_fp_post.status_code == 200
    assert "sent password reset instructions" in r_fp_post.get_data(as_text=True)

    r_fp_anon = client.post("/forgot-password", data={"email": "nobody@taskflow.dev"}, follow_redirects=True)
    assert r_fp_anon.status_code == 200
    assert "sent password reset instructions" in r_fp_anon.get_data(as_text=True)

    # Generate valid reset token
    with app.app_context():
        u_target = db.session.get(User, user_id)
        reset_token = generate_password_reset_token(u_target, app.config["SECRET_KEY"])
        assert verify_password_reset_token(reset_token, app.config["SECRET_KEY"]) is not None

    # View reset password page
    r_reset_view = client.get(f"/reset-password/{reset_token}")
    assert r_reset_view.status_code == 200
    assert "Choose New Password" in r_reset_view.get_data(as_text=True)

    # Submit invalid new password (< 8 chars)
    r_short_reset = client.post(f"/reset-password/{reset_token}", data={"password": "short", "confirm_password": "short"})
    assert r_short_reset.status_code == 400
    assert "at least 8 characters" in r_short_reset.get_data(as_text=True)

    # Submit valid new password
    new_password = "BrandNewPassword2026!"
    r_reset_done = client.post(f"/reset-password/{reset_token}", data={
        "password": new_password,
        "confirm_password": new_password
    }, follow_redirects=True)
    assert r_reset_done.status_code == 200
    assert "password has been reset successfully" in r_reset_done.get_data(as_text=True)

    # Verify old password is rejected and new password is accepted
    r_old_login = client.post("/login", data={"email": test_email, "password": password})
    assert r_old_login.status_code == 401

    r_new_login = client.post("/login", data={"email": test_email, "password": new_password}, follow_redirects=True)
    assert r_new_login.status_code == 200
    assert "Verification Tester" in r_new_login.get_data(as_text=True)
    print("   -> Password reset verified: old password rejected, new password authenticated.")

    # Verify single-use token invalidation: Reusing the same reset token must be rejected!
    client.post("/logout")
    with app.app_context():
        assert verify_password_reset_token(reset_token, app.config["SECRET_KEY"]) is None
    r_reuse_token = client.get(f"/reset-password/{reset_token}", follow_redirects=True)
    assert r_reuse_token.status_code == 200
    assert "invalid or has expired" in r_reuse_token.get_data(as_text=True)
    print("   -> Single-use token invalidation verified.")

    # ----------------------------------------------------
    # 4. GITHUB & GOOGLE OAUTH ROUTE HANDLING
    # ----------------------------------------------------
    print("4. Testing GitHub & Google OAuth endpoints...")
    from unittest.mock import patch
    # Unconfigured GitHub OAuth
    with patch.dict(os.environ, {"GITHUB_CLIENT_ID": "", "GITHUB_CLIENT_SECRET": "", "GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
        r_gh_unconf = client.get("/login/github", follow_redirects=True)
        assert r_gh_unconf.status_code == 200
        assert "GitHub sign-in is not configured" in r_gh_unconf.get_data(as_text=True)

        # Unconfigured Google OAuth
        r_g_unconf = client.get("/login/google", follow_redirects=True)
        assert r_g_unconf.status_code == 200
        assert "Google sign-in is not configured" in r_g_unconf.get_data(as_text=True)
        print("   -> Missing OAuth credentials handled gracefully without application crashes.")

    # ----------------------------------------------------
    # 5. DEMO TASKS SEEDING CLI VERIFICATION
    # ----------------------------------------------------
    print("5. Testing Demo Tasks Seeder CLI...")
    runner = app.test_cli_runner()
    res1 = runner.invoke(args=["cli", "seed-demo-tasks", "--email", test_email])
    assert res1.exit_code == 0
    assert "Successfully seeded" in res1.output

    # Check that demo tasks were created across categories and priorities
    with app.app_context():
        tasks = Task.query.filter_by(user_id=user_id).all()
        assert len(tasks) >= 10
        priorities = {t.priority for t in tasks}
        assert "high" in priorities
        assert "medium" in priorities
        assert "low" in priorities

        # Check archived tasks exist
        archived_tasks = [t for t in tasks if t.archived_at is not None]
        assert len(archived_tasks) >= 2

    # Verify idempotency (second run adds 0 duplicates)
    res2 = runner.invoke(args=["cli", "seed-demo-tasks", "--email", test_email])
    assert res2.exit_code == 0
    assert "0 realistic demo tasks" in res2.output
    print("   -> Demo tasks seeder populated realistic data across categories/priorities and is strictly idempotent.")

    print("=== ALL PHASE 7 AUTHENTICATION & SECURITY TESTS COMPLETED AND PASSED! ===")

if __name__ == "__main__":
    test_phase7_authentication_features()
