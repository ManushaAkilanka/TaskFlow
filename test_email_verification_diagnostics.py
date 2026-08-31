import os
import time
from unittest.mock import patch
import smtplib
from app import create_app, db
from app.models import User, Task, Category, Settings
from app.auth_tokens import (
    generate_email_verification_token,
    verify_email_verification_token,
    generate_password_reset_token,
    verify_password_reset_token
)
from app.mailer import send_email, mask_email, send_verification_email, send_password_reset_email


def test_email_verification_diagnostics():
    print("=== STARTING COMPREHENSIVE EMAIL DELIVERY & MULTI-USER ISOLATION TESTS ===")

    # ----------------------------------------------------
    # 1. TEST EMAIL MASKING HELPER
    # ----------------------------------------------------
    print("1. Testing Email Masking Helper...")
    assert mask_email("manushaakilanka53@gmail.com") == "m*******@gmail.com"
    assert mask_email("alex@example.com") == "a*******@example.com"
    assert mask_email("a@b.com") == "*@b.com"
    assert mask_email("") == "***"
    assert mask_email(None) == "***"
    print("   -> Email masking utility verified.")

    # ----------------------------------------------------
    # 2. TEST SMTP CONFIGURATION & ERROR HANDLING
    # ----------------------------------------------------
    print("2. Testing SMTP Error & Failure Handling...")
    
    # 2a. Dev Fallback (when SMTP not configured)
    with patch.dict(os.environ, {"MAIL_SERVER": "", "MAIL_USERNAME": "", "MAIL_PASSWORD": ""}):
        result = send_email("test@example.com", "Test Subject", "Test Body")
        assert result is True, "Dev fallback should return True"
        print("   -> Dev fallback when SMTP not configured: PASSED")

    # 2b. SMTP Authentication Failure
    with patch.dict(os.environ, {
        "MAIL_SERVER": "smtp.gmail.com",
        "MAIL_PORT": "587",
        "MAIL_USE_TLS": "true",
        "MAIL_USERNAME": "test@gmail.com",
        "MAIL_PASSWORD": "wrongpassword"
    }):
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_instance = mock_smtp_cls.return_value
            mock_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
            result = send_email("recipient@example.com", "Test", "Body")
            assert result is False, "send_email should return False on SMTPAuthenticationError"
            print("   -> SMTP Authentication Failure (535) handled safely, returned False: PASSED")

    # 2c. SMTP Connection Failure
    with patch.dict(os.environ, {
        "MAIL_SERVER": "invalid.smtp.host",
        "MAIL_PORT": "587",
        "MAIL_USE_TLS": "true",
        "MAIL_USERNAME": "test@gmail.com",
        "MAIL_PASSWORD": "password"
    }):
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.side_effect = smtplib.SMTPConnectError(421, b"Connection refused")
            result = send_email("recipient@example.com", "Test", "Body")
            assert result is False, "send_email should return False on SMTPConnectError"
            print("   -> SMTP Connection Failure handled safely, returned False: PASSED")

    # 2d. Successful SMTP Send
    with patch.dict(os.environ, {
        "MAIL_SERVER": "smtp.gmail.com",
        "MAIL_PORT": "587",
        "MAIL_USE_TLS": "true",
        "MAIL_USERNAME": "test@gmail.com",
        "MAIL_PASSWORD": "password"
    }):
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_instance = mock_smtp_cls.return_value
            result = send_email("recipient@example.com", "Test", "Body")
            assert result is True, "send_email should return True on successful transmission"
            print("   -> Successful SMTP Send handled cleanly, returned True: PASSED")

    # ----------------------------------------------------
    # 3. TEST FLASK APP INTEGRATION WITH SMTP SUCCESS & FAILURE
    # ----------------------------------------------------
    print("3. Testing Signup & Resend UI with SMTP Failure vs Success...")
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key-email-diagnostics"
    })
    with app.app_context():
        db.create_all()

    client = app.test_client()

    # 3a. Signup when email delivery fails
    with patch("app.auth.send_verification_email", return_value=False):
        ts = int(time.time())
        fail_email = f"fail_user_{ts}@taskflow.dev"
        r_fail = client.post("/signup", data={
            "full_name": "Delivery Fail User",
            "email": fail_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        }, follow_redirects=True)
        assert r_fail.status_code == 200
        html_text = r_fail.get_data(as_text=True)
        # Must show the safe error warning, NOT false success
        assert "couldn&#39;t send the verification email" in html_text or "couldn't send the verification email" in html_text
        print("   -> False-success prevented on signup failure: UI safely warned user.")

    # 3b. Resend when email delivery fails
    with patch("app.auth.send_verification_email", return_value=False):
        r_resend_fail = client.post("/resend-verification", data={"email": fail_email}, follow_redirects=True)
        assert r_resend_fail.status_code == 200
        html_resend = r_resend_fail.get_data(as_text=True)
        assert "couldn&#39;t send the verification email" in html_resend or "couldn't send the verification email" in html_resend
        print("   -> False-success prevented on resend failure: UI safely warned user.")

    # ----------------------------------------------------
    # 4. MULTI-USER ISOLATION: USER A & USER B
    # ----------------------------------------------------
    print("4. Testing Multi-User Isolation for Verification & Password Reset...")
    user_a_email = f"user_a_{int(time.time())}@taskflow.dev"
    user_b_email = f"user_b_{int(time.time())}@taskflow.dev"
    password_a = "PasswordA123!"
    password_b = "PasswordB123!"

    # Create User A
    with patch("app.auth.send_verification_email", return_value=True):
        client.post("/signup", data={
            "full_name": "User Alpha",
            "email": user_a_email,
            "password": password_a,
            "confirm_password": password_a
        }, follow_redirects=True)

    # Create User B
    with patch("app.auth.send_verification_email", return_value=True):
        client.post("/signup", data={
            "full_name": "User Beta",
            "email": user_b_email,
            "password": password_b,
            "confirm_password": password_b
        }, follow_redirects=True)

    with app.app_context():
        user_a = User.query.filter_by(email=user_a_email).first()
        user_b = User.query.filter_by(email=user_b_email).first()
        assert user_a is not None
        assert user_b is not None
        assert user_a.id != user_b.id
        assert user_a.email_verified is False
        assert user_b.email_verified is False

        # Generate token for User A
        token_a = generate_email_verification_token(user_a.email, app.config["SECRET_KEY"])
        # Generate token for User B
        token_b = generate_email_verification_token(user_b.email, app.config["SECRET_KEY"])

    # 4a. Verify User A with Token A
    r_ver_a = client.get(f"/verify-email/{token_a}", follow_redirects=True)
    assert r_ver_a.status_code == 200
    assert "verified successfully" in r_ver_a.get_data(as_text=True)

    with app.app_context():
        u_a = User.query.filter_by(email=user_a_email).first()
        u_b = User.query.filter_by(email=user_b_email).first()
        assert u_a.email_verified is True
        assert u_b.email_verified is False, "User B must NOT be verified by User A's token!"
        print("   -> User A verified; User B strictly remains unverified.")

    # 4b. Verify User B cannot be verified by Token A (already verified account or mismatch)
    # Now verify User B with Token B
    r_ver_b = client.get(f"/verify-email/{token_b}", follow_redirects=True)
    assert r_ver_b.status_code == 200
    assert "verified successfully" in r_ver_b.get_data(as_text=True)

    with app.app_context():
        u_b = User.query.filter_by(email=user_b_email).first()
        assert u_b.email_verified is True
        print("   -> User B verified independently with Token B.")

    # 4c. Cross-User Password Reset Isolation
    print("5. Testing Cross-User Password Reset Isolation...")
    with app.app_context():
        u_a = User.query.filter_by(email=user_a_email).first()
        u_b = User.query.filter_by(email=user_b_email).first()
        reset_token_a = generate_password_reset_token(u_a, app.config["SECRET_KEY"])
        reset_token_b = generate_password_reset_token(u_b, app.config["SECRET_KEY"])

        # Token A must only decode to User A
        verified_user_a = verify_password_reset_token(reset_token_a, app.config["SECRET_KEY"])
        assert verified_user_a.id == u_a.id
        assert verified_user_a.email == u_a.email

        # Token B must only decode to User B
        verified_user_b = verify_password_reset_token(reset_token_b, app.config["SECRET_KEY"])
        assert verified_user_b.id == u_b.id
        assert verified_user_b.email == u_b.email

    # Reset User A's password using Token A
    r_reset_a = client.post(f"/reset-password/{reset_token_a}", data={
        "password": "NewPasswordA!99",
        "confirm_password": "NewPasswordA!99"
    }, follow_redirects=True)
    assert r_reset_a.status_code == 200
    assert "password has been reset successfully" in r_reset_a.get_data(as_text=True)

    # Token A must now be invalidated (single-use) because password hash changed
    with app.app_context():
        invalidated_a = verify_password_reset_token(reset_token_a, app.config["SECRET_KEY"])
        assert invalidated_a is None, "Reset token must be single-use and invalidated immediately!"

    # User B's password must NOT have been changed
    with app.app_context():
        u_b = User.query.filter_by(email=user_b_email).first()
        assert u_b.check_password(password_b) is True
        print("   -> Password reset strictly isolated: User A updated, User B unaffected, Token A single-use.")

    # ----------------------------------------------------
    # 6. EXPIRED AND INVALID TOKEN REJECTION
    # ----------------------------------------------------
    print("6. Testing Token Expiration & Tampering Defense...")
    with app.app_context():
        # Expired verification token (max_age=-1)
        exp_ver_token = generate_email_verification_token("test@example.com", app.config["SECRET_KEY"])
        assert verify_email_verification_token(exp_ver_token, app.config["SECRET_KEY"], max_age=-1) is None
        
        # Expired password reset token
        u_b = User.query.filter_by(email=user_b_email).first()
        exp_reset_token = generate_password_reset_token(u_b, app.config["SECRET_KEY"])
        assert verify_password_reset_token(exp_reset_token, app.config["SECRET_KEY"], max_age=-1) is None
        print("   -> Expired verification & reset tokens safely rejected.")

    print("\n=== ALL EMAIL DELIVERY & MULTI-USER ISOLATION TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    test_email_verification_diagnostics()
