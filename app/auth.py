import os
import re
import secrets
import json
import urllib.request
import urllib.parse
from urllib.parse import urlsplit
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, utc_now
from app.auth_tokens import (
    generate_email_verification_token,
    verify_email_verification_token,
    generate_password_reset_token,
    verify_password_reset_token
)
from app.mailer import send_verification_email, send_password_reset_email

auth_bp = Blueprint("auth", __name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_safe_redirect_url(target):
    """Ensures redirect URL is on the same host."""
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc or not test_url.netloc


# =========================================================
# MANUAL AUTHENTICATION
# =========================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("auth/login.html", email=email), 400

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("auth/login.html", email=email), 400

        user = User.query.filter_by(email=email).first()

        # Security-conscious authentication check (prevents email enumeration)
        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", email=email), 401

        # Email Verification Check
        if not user.email_verified:
            flash("Please verify your email before signing in. Check your inbox or request a new verification link below.", "error")
            return render_template("auth/login.html", email=email, unverified=True), 403

        login_user(user)

        next_page = request.args.get("next")
        if next_page and is_safe_redirect_url(next_page):
            return redirect(next_page)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        # Validation
        if not full_name:
            flash("Full Name is required.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 400

        if len(full_name) > 100:
            flash("Full Name must be under 100 characters.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 400

        if not email or not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 400

        if len(email) > 120:
            flash("Email address is too long.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 400

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 400

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 400

        # Check existing user
        if User.query.filter_by(email=email).first():
            flash("An account with this email address already exists.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 409

        try:
            # Create unverified user and default provisions in atomic transaction
            user = User(
                full_name=full_name,
                email=email,
                avatar=None,
                email_verified=False,
                email_verified_at=None
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            # Provision default categories (Personal, Work, University) & Settings
            user.init_default_data()
            db.session.commit()

            # Generate Email Verification Token and Send Email
            token = generate_email_verification_token(user.email, current_app.config["SECRET_KEY"])
            verify_url = url_for("auth.verify_email", token=token, _external=True)
            email_sent = send_verification_email(user.email, verify_url)

            if email_sent:
                flash("Account created! Please check your email to verify your account before signing in.", "success")
            else:
                flash("Account created, but we couldn't send the verification email right now. Please try again later.", "error")
            return redirect(url_for("auth.verify_email_pending", email=user.email))

        except Exception as e:
            db.session.rollback()
            flash("An unexpected error occurred during account creation. Please try again.", "error")
            return render_template("auth/signup.html", full_name=full_name, email=email), 500

    return render_template("auth/signup.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("auth.login"))


# =========================================================
# EMAIL VERIFICATION
# =========================================================

@auth_bp.route("/verify-email-pending")
def verify_email_pending():
    email = request.args.get("email", "")
    return render_template("auth/verify_email_pending.html", email=email)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    email = verify_email_verification_token(token, current_app.config["SECRET_KEY"])
    if not email:
        flash("The verification link is invalid or has expired. Please request a new verification link below.", "error")
        return redirect(url_for("auth.resend_verification"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Invalid verification request.", "error")
        return redirect(url_for("auth.login"))

    if user.email_verified:
        flash("Your email is already verified. Please sign in.", "info")
        return redirect(url_for("auth.login"))

    user.email_verified = True
    user.email_verified_at = utc_now()
    db.session.commit()

    flash("Your email has been verified successfully! You can now sign in to your TaskFlow account.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if not email or not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("auth/resend_verification.html", email=email), 400

        user = User.query.filter_by(email=email).first()
        if user and not user.email_verified:
            token = generate_email_verification_token(user.email, current_app.config["SECRET_KEY"])
            verify_url = url_for("auth.verify_email", token=token, _external=True)
            email_sent = send_verification_email(user.email, verify_url)
            if not email_sent:
                flash("We couldn't send the verification email right now. Please try again later.", "error")
                return redirect(url_for("auth.resend_verification", email=email))

        # Generic message prevents email enumeration
        flash("If an unverified account exists for that email, a fresh verification link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/resend_verification.html", email=request.args.get("email", ""))


# =========================================================
# FORGOT PASSWORD & PASSWORD RESET
# =========================================================

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if not email or not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "error")
            return render_template("auth/forgot_password.html", email=email), 400

        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_password_reset_token(user, current_app.config["SECRET_KEY"])
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            email_sent = send_password_reset_email(user.email, reset_url)
            if not email_sent:
                flash("We couldn't send the password reset email right now. Please try again later.", "error")
                return redirect(url_for("auth.forgot_password"))

        # Generic response prevents account enumeration
        flash("If an account exists for that email, we have sent password reset instructions.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    user = verify_password_reset_token(token, current_app.config["SECRET_KEY"])
    if not user:
        flash("The password reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("auth/reset_password.html", token=token), 400

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/reset_password.html", token=token), 400

        user.set_password(password)
        db.session.commit()

        flash("Your password has been reset successfully! Please sign in with your new password.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)


# =========================================================
# GITHUB OAUTH
# =========================================================

@auth_bp.route("/login/github")
def github_login():
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET")

    if not client_id or not client_secret:
        flash("GitHub sign-in is not configured. Please configure GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.", "info")
        return redirect(url_for("auth.login"))

    state = secrets.token_hex(16)
    session["oauth_state"] = state
    redirect_uri = url_for("auth.github_callback", _external=True)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "user:email",
        "state": state
    }
    github_auth_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
    return redirect(github_auth_url)


@auth_bp.route("/login/github/callback")
def github_callback():
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET")

    if not client_id or not client_secret:
        flash("GitHub sign-in is not configured.", "error")
        return redirect(url_for("auth.login"))

    error = request.args.get("error")
    if error:
        flash(f"GitHub authentication was cancelled or encountered an error ({error}).", "error")
        return redirect(url_for("auth.login"))

    state = request.args.get("state")
    saved_state = session.pop("oauth_state", None)
    if not state or state != saved_state:
        flash("OAuth state verification failed. Please try again.", "error")
        return redirect(url_for("auth.login"))

    code = request.args.get("code")
    if not code:
        flash("Missing authorization code from GitHub.", "error")
        return redirect(url_for("auth.login"))

    try:
        # Exchange code for access token
        token_url = "https://github.com/login/oauth/access_token"
        token_data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=token_data, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_json = json.loads(resp.read().decode("utf-8"))

        access_token = token_json.get("access_token")
        if not access_token:
            flash("Failed to obtain access token from GitHub.", "error")
            return redirect(url_for("auth.login"))

        # Fetch GitHub User Identity
        user_req = urllib.request.Request("https://api.github.com/user", headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "TaskFlow-App",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            gh_user = json.loads(resp.read().decode("utf-8"))

        github_id = str(gh_user.get("id"))
        full_name = gh_user.get("name") or gh_user.get("login") or "GitHub User"
        avatar_url = gh_user.get("avatar_url")
        email = gh_user.get("email")

        # If email is private on GitHub profile, fetch from emails endpoint
        if not email:
            email_req = urllib.request.Request("https://api.github.com/user/emails", headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "TaskFlow-App",
                "Accept": "application/json"
            })
            with urllib.request.urlopen(email_req, timeout=10) as resp:
                emails_list = json.loads(resp.read().decode("utf-8"))
                for em in emails_list:
                    if em.get("primary") and em.get("verified"):
                        email = em.get("email")
                        break
                if not email and emails_list:
                    email = emails_list[0].get("email")

        if not email:
            flash("Could not retrieve a verified email address from your GitHub account.", "error")
            return redirect(url_for("auth.login"))

        email = email.strip().lower()

        # Find existing user by github_id or email
        user = User.query.filter((User.github_id == github_id) | (User.email == email)).first()

        if user:
            if not user.github_id:
                user.github_id = github_id
            if not user.email_verified:
                user.email_verified = True
                user.email_verified_at = utc_now()
            if not user.avatar and avatar_url:
                user.avatar = avatar_url
            db.session.commit()
        else:
            # Create new user
            user = User(
                full_name=full_name,
                email=email,
                avatar=avatar_url,
                github_id=github_id,
                email_verified=True,
                email_verified_at=utc_now()
            )
            user.set_password(secrets.token_urlsafe(32))  # Secure dummy password
            db.session.add(user)
            db.session.flush()
            user.init_default_data()
            db.session.commit()

        login_user(user)
        flash(f"Welcome, {user.full_name}!", "success")
        return redirect(url_for("main.dashboard"))

    except Exception as e:
        flash(f"GitHub sign-in encountered an error: {str(e)}", "error")
        return redirect(url_for("auth.login"))


# =========================================================
# GOOGLE OAUTH
# =========================================================

@auth_bp.route("/login/google")
def google_login():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        flash("Google sign-in is not configured. Please configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.", "info")
        return redirect(url_for("auth.login"))

    state = secrets.token_hex(16)
    session["oauth_state"] = state
    redirect_uri = url_for("auth.google_callback", _external=True)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return redirect(google_auth_url)


@auth_bp.route("/login/google/callback")
def google_callback():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        flash("Google sign-in is not configured.", "error")
        return redirect(url_for("auth.login"))

    error = request.args.get("error")
    if error:
        flash(f"Google authentication was cancelled or encountered an error ({error}).", "error")
        return redirect(url_for("auth.login"))

    state = request.args.get("state")
    saved_state = session.pop("oauth_state", None)
    if not state or state != saved_state:
        flash("OAuth state verification failed. Please try again.", "error")
        return redirect(url_for("auth.login"))

    code = request.args.get("code")
    if not code:
        flash("Missing authorization code from Google.", "error")
        return redirect(url_for("auth.login"))

    try:
        # Exchange code for token
        token_url = "https://oauth2.googleapis.com/token"
        redirect_uri = url_for("auth.google_callback", _external=True)
        token_data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=token_data, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_json = json.loads(resp.read().decode("utf-8"))

        access_token = token_json.get("access_token")
        if not access_token:
            flash("Failed to obtain access token from Google.", "error")
            return redirect(url_for("auth.login"))

        # Fetch Google Userinfo
        user_req = urllib.request.Request("https://openidconnect.googleapis.com/v1/userinfo", headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            g_user = json.loads(resp.read().decode("utf-8"))

        google_id = str(g_user.get("sub"))
        email = g_user.get("email")
        full_name = g_user.get("name") or "Google User"
        avatar_url = g_user.get("picture")

        if not email:
            flash("Could not retrieve a verified email address from your Google account.", "error")
            return redirect(url_for("auth.login"))

        email = email.strip().lower()

        # Find existing user by google_id or email
        user = User.query.filter((User.google_id == google_id) | (User.email == email)).first()

        if user:
            if not user.google_id:
                user.google_id = google_id
            if not user.email_verified:
                user.email_verified = True
                user.email_verified_at = utc_now()
            if not user.avatar and avatar_url:
                user.avatar = avatar_url
            db.session.commit()
        else:
            # Create new user
            user = User(
                full_name=full_name,
                email=email,
                avatar=avatar_url,
                google_id=google_id,
                email_verified=True,
                email_verified_at=utc_now()
            )
            user.set_password(secrets.token_urlsafe(32))  # Secure dummy password
            db.session.add(user)
            db.session.flush()
            user.init_default_data()
            db.session.commit()

        login_user(user)
        flash(f"Welcome, {user.full_name}!", "success")
        return redirect(url_for("main.dashboard"))

    except Exception as e:
        flash(f"Google sign-in encountered an error: {str(e)}", "error")
        return redirect(url_for("auth.login"))
