import os
import re
from app import create_app, db
from app.models import User, Category, Settings

def get_csrf_token(client, url):
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None, f"CSRF token not found in {url}"
    return match.group(1)

def test_phase3_authentication():
    print("=== STARTING PHASE 3 FUNCTIONAL & AUTHENTICATION TESTS ===")
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,  # We also test explicit form validation
    })

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # 1. Test GET routes
    print("1. Testing GET /login, /signup, /forgot-password...")
    r_login = client.get("/login")
    assert r_login.status_code == 200
    assert "Sign in to TaskFlow" in r_login.get_data(as_text=True)
    assert "TaskFlow: Login" in r_login.get_data(as_text=True)
    assert "Continue with GitHub" in r_login.get_data(as_text=True)
    assert "Continue with Google" in r_login.get_data(as_text=True)

    r_signup = client.get("/signup")
    assert r_signup.status_code == 200
    assert "Create an account" in r_signup.get_data(as_text=True)
    assert "TaskFlow: Sign Up" in r_signup.get_data(as_text=True)
    assert "Create Account" in r_signup.get_data(as_text=True)

    r_forgot = client.get("/forgot-password")
    assert r_forgot.status_code == 200
    assert "Reset Password" in r_forgot.get_data(as_text=True)
    print("   -> All GET routes returned 200 OK with matching template titles and elements.")

    # 2. Test Signup Form Validations
    print("2. Testing Signup Form Validations...")
    # Empty Name
    r = client.post("/signup", data={"full_name": "", "email": "test@example.com", "password": "password123", "confirm_password": "password123"})
    assert r.status_code == 400
    assert "Full Name is required" in r.get_data(as_text=True)

    # Invalid Email
    r = client.post("/signup", data={"full_name": "Test User", "email": "not-an-email", "password": "password123", "confirm_password": "password123"})
    assert r.status_code == 400
    assert "valid email" in r.get_data(as_text=True)

    # Password too short (< 8 chars)
    r = client.post("/signup", data={"full_name": "Test User", "email": "test@example.com", "password": "pass12", "confirm_password": "pass12"})
    assert r.status_code == 400
    assert "at least 8 characters" in r.get_data(as_text=True)

    # Password mismatch
    r = client.post("/signup", data={"full_name": "Test User", "email": "test@example.com", "password": "password123", "confirm_password": "mismatch"})
    assert r.status_code == 400
    assert "Passwords do not match" in r.get_data(as_text=True)
    print("   -> Signup input validation passed (name, email, password length, mismatch).")

    # 3. Test Successful Signup & Default Provisioning
    print("3. Testing Successful User Registration...")
    import time
    signup_email = f"alex_{int(time.time())}@taskflow.dev"
    r = client.post("/signup", data={
        "full_name": "Alex Coder",
        "email": signup_email,
        "password": "SecurePassword!99",
        "confirm_password": "SecurePassword!99"
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Verify your email" in r.get_data(as_text=True) or "check your email" in r.get_data(as_text=True)
    print("   -> Registration succeeded and prompted for email verification.")

    with app.app_context():
        user = User.query.filter_by(email=signup_email).first()
        assert user is not None
        assert user.check_password("SecurePassword!99") is True
        assert user.password_hash != "SecurePassword!99"
        assert user.email_verified is False
        
        # Verify default categories
        cat_names = [c.name for c in user.categories.all()]
        assert "Work" in cat_names
        assert "Personal" in cat_names
        assert "University" in cat_names
        print(f"   -> Provisioned default categories in SQLite: {cat_names}")

        # Verify settings
        assert user.settings is not None
        assert user.settings.appearance == "light"
        assert user.settings.notifications_enabled is True
        print(f"   -> Provisioned default settings in SQLite: appearance={user.settings.appearance}")

    # 4. Test Duplicate Email Prevention (Unauthenticated client)
    print("4. Testing Duplicate Email Signup...")
    unauth_client = app.test_client()
    r = unauth_client.post("/signup", data={
        "full_name": "Another Alex",
        "email": signup_email,
        "password": "SecurePassword!99",
        "confirm_password": "SecurePassword!99"
    })
    assert r.status_code == 409
    assert "already exists" in r.get_data(as_text=True)
    print("   -> Duplicate email prevented with status 409.")

    # 5. Test Unverified Login Rejection
    print("5. Testing Unverified Login Rejection...")
    r_unver = client.post("/login", data={"email": signup_email, "password": "SecurePassword!99"}, follow_redirects=True)
    assert r_unver.status_code == 403
    assert "verify your email" in r_unver.get_data(as_text=True).lower()
    print("   -> Unverified login correctly rejected with status 403.")

    # 6. Verify User Email and Test Authenticated Login
    print("6. Verifying User Email...")
    with app.app_context():
        u = User.query.filter_by(email=signup_email).first()
        u.email_verified = True
        db.session.commit()

    # 7. Test Login Failures (Generic Security Message)
    print("7. Testing Login Security...")
    # Wrong password
    r_bad_pw = client.post("/login", data={"email": signup_email, "password": "WrongPassword"})
    assert r_bad_pw.status_code == 401
    assert "Invalid email or password" in r_bad_pw.get_data(as_text=True)

    # Non-existent email
    r_bad_user = client.post("/login", data={"email": "nonexistent@taskflow.dev", "password": "SomePassword"})
    assert r_bad_user.status_code == 401
    assert "Invalid email or password" in r_bad_user.get_data(as_text=True)
    print("   -> Generic 'Invalid email or password' returned for both invalid credentials and non-existent users.")

    # 8. Test Successful Login
    print("8. Testing Successful Login...")
    r_login_ok = client.post("/login", data={"email": signup_email, "password": "SecurePassword!99"}, follow_redirects=True)
    assert r_login_ok.status_code == 200
    assert "Alex Coder" in r_login_ok.get_data(as_text=True)
    print("   -> Authenticated session created successfully.")

    # 8b. Test Logout
    r_logout = client.post("/logout", follow_redirects=True)
    assert r_logout.status_code == 200
    assert "signed out successfully" in r_logout.get_data(as_text=True)

    # 9. Test CSRF Protection
    print("9. Testing CSRF Protection with active WTF CSRF...")
    csrf_app = create_app({"TESTING": False, "WTF_CSRF_ENABLED": True})
    csrf_client = csrf_app.test_client()
    
    # Attempt POST without CSRF token
    r_no_csrf = csrf_client.post("/login", data={"email": signup_email, "password": "SecurePassword!99"})
    assert r_no_csrf.status_code == 400
    print("   -> POST without CSRF token blocked with status 400.")

    # Extract CSRF token from page and submit
    token = get_csrf_token(csrf_client, "/login")
    r_with_csrf = csrf_client.post("/login", data={"email": signup_email, "password": "SecurePassword!99", "csrf_token": token}, follow_redirects=True)
    assert r_with_csrf.status_code == 200
    print("   -> POST with valid CSRF token succeeded.")

    print("=== ALL PHASE 3 TESTS COMPLETED AND PASSED! ===")

if __name__ == "__main__":
    test_phase3_authentication()
