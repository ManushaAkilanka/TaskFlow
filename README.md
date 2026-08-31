# TaskFlow

A modern, full-featured personal task management web application built with Python and Flask. TaskFlow features secure multi-user authentication, email verification, password recovery, OAuth integration, task and category management, priority tracking, archiving, and a clean responsive dashboard — with dual database support (SQLite locally and PostgreSQL in production).

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [Database Architecture](#database-architecture)
- [Authentication & Security](#authentication--security)
- [Email Verification & Delivery](#email-verification--delivery)
- [Password Reset](#password-reset)
- [OAuth Configuration](#oauth-configuration)
- [Demo Data & Seeding](#demo-data--seeding)
- [Testing Suite](#testing-suite)
- [Production Deployment (Render)](#production-deployment-render)
- [Security Best Practices](#security-best-practices)
- [Future Improvements](#future-improvements)

---

## Overview

TaskFlow is designed to help individuals and developers organize their daily workload with high efficiency. It enforces strict per-user data isolation, protects against common web vulnerabilities (CSRF, XSS, IDOR), and supports multiple authentication workflows (manual password hashing, GitHub OAuth, and Google OAuth).

---

## Features

### Authentication & User Management
- **Manual Registration & Login:** Password hashing with Werkzeug (PBKDF2-SHA256).
- **Mandatory Email Verification:** Cryptographically signed, time-limited verification tokens via `itsdangerous`.
- **Password Recovery:** Secure, single-use password reset links that auto-invalidate upon password modification.
- **OAuth Providers:** One-click sign-in via GitHub and Google OAuth with graceful fallback when unconfigured.
- **Session Management:** Flask-Login session authentication with secure cookies.

### Task Management
- **CRUD Operations:** Create, edit, update status, and delete tasks.
- **Workflow Statuses:** `To Do`, `In Progress`, and `Completed`.
- **Priority Levels:** `High`, `Medium`, and `Low` with visual indicator badges.
- **Due Dates & Timestamps:** Optional due dates, completion timestamps (`completed_at`), and archive timestamps (`archived_at`).
- **Archiving & Restoration:** Archive completed tasks to clean up your board and restore or permanently delete them at any time.

### Categorization & Customization
- **Personal Categories:** Color-coded category tags (`Work`, `Personal`, `University`, etc.).
- **User Settings:** Theme preference toggles (Light/Dark mode) and notification settings.
- **Configuration Export:** Export your profile, settings, and task statistics as a JSON payload.

---

## Technology Stack

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Language** | Python | `>= 3.10` (Recommended: `3.13`) | Core programming language |
| **Web Framework** | Flask | `>= 3.0.0` | Application routing and factory architecture |
| **ORM** | Flask-SQLAlchemy | `>= 3.1.0` | Database ORM and relational models |
| **Authentication** | Flask-Login | `>= 0.6.3` | User session and access control |
| **Forms & CSRF** | Flask-WTF / WTForms | `>= 1.2.1` | CSRF protection across all state-changing endpoints |
| **Token Signing** | itsdangerous | `>= 2.1.0` | URL-safe cryptographic token serialization |
| **Email Validation** | email-validator | `>= 2.1.0` | RFC-compliant email address validation |
| **Environment** | python-dotenv | `>= 1.0.0` | Local `.env` file management |
| **Production WSGI** | Gunicorn | `>= 21.2.0` | Production HTTP WSGI server for UNIX/Linux platforms |
| **PostgreSQL Driver**| psycopg2-binary | `>= 2.9.9` | PostgreSQL database adapter for production |
| **Database** | SQLite / PostgreSQL | Built-in / Managed | SQLite for local dev, PostgreSQL for cloud deployment |

---

## Project Structure

```text
TaskFlow/
│
├── app/
│   ├── __init__.py          # Application Factory (create_app), extensions, ProxyFix
│   ├── auth.py              # Authentication blueprint (login, signup, verify, OAuth, reset)
│   ├── auth_tokens.py       # Cryptographic token generator & verifier (itsdangerous)
│   ├── cli.py               # Flask CLI commands (init-db, seed-db, seed-demo-tasks)
│   ├── mailer.py            # Safe SMTP mailer with diagnostic logging & email masking
│   ├── models.py            # SQLAlchemy models (User, Category, Task, Settings)
│   ├── routes.py            # Main application blueprint (dashboard, tasks, archive, settings)
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── app.css      # Core application styling & dashboard themes
│   │   │   └── auth.css     # Authentication views styling
│   │   └── js/              # Frontend interactivity scripts
│   │
│   └── templates/
│       ├── auth/            # Auth templates (login, signup, verify_email, forgot_password, etc.)
│       ├── errors/          # Custom error handlers (403.html, 404.html, 500.html)
│       ├── base.html        # Shared navigation, sidebar, and layout wrapper
│       ├── dashboard.html   # Main productivity overview dashboard
│       ├── tasks.html       # Active task listing, filters, and modals
│       ├── archive.html     # Archived tasks management and date grouping
│       └── settings.html    # Profile management, appearance toggles, and data export
│
├── instance/
│   └── .gitkeep             # Preserves instance directory structure (SQLite databases gitignored)
│
├── run.py                   # WSGI application entrypoint for development and Gunicorn
├── requirements.txt         # Production and development dependencies
├── render.yaml              # Render Cloud Blueprint deployment specification
├── .env.example             # Safe template of all environment variables with placeholders
├── .gitignore               # Strict exclusion rules for secrets, databases, and artifacts
├── .python-version          # Python 3.13 specification
├── README.md                # Project documentation
│
├── test_phase2.py           # Model schema, relations, and persistence tests
├── test_phase3.py           # Authentication, form validation, and CSRF tests
├── test_phase4.py           # Dashboard stats, task lifecycle, and filtering tests
├── test_phase5.py           # Archive date grouping, settings, and restore tests
├── test_phase6.py           # Integration security, XSS auto-escaping, and IDOR matrix tests
├── test_phase7_auth_features.py            # Verification, password reset, and OAuth fallback tests
└── test_email_verification_diagnostics.py   # SMTP delivery diagnostic and multi-user tests
```

---

## Local Development

### 1. Clone the repository
```bash
git clone https://github.com/your-username/TaskFlow.git
cd TaskFlow
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure local environment variables
```bash
cp .env.example .env
```
Generate a secure local secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Edit `.env` and assign `SECRET_KEY`.

### 5. Initialize database & run
```bash
# Initialize SQLite database (instance/taskflow.db)
flask --app run:app cli init-db

# Run development server
python run.py
```
Open your browser at `http://127.0.0.1:5000`.

---

## Environment Variables

All environment variables are optional for local development (defaults are provided), but required variables must be configured for production.

| Variable Name | Purpose | Example / Format | Required in Production? |
| :--- | :--- | :--- | :---: |
| `SECRET_KEY` | Signs session cookies and CSRF tokens | `8bf249d85b531...` (64-char hex) | **Yes** |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` | **Yes (for PostgreSQL)** |
| `APP_BASE_URL` | Public application URL | `https://taskflow.onrender.com` | Optional (Auto-detected) |
| `MAIL_SERVER` | SMTP server host | `smtp.gmail.com` | Optional (Console fallback if unset) |
| `MAIL_PORT` | SMTP port | `587` (STARTTLS) or `465` (SSL) | Optional |
| `MAIL_USE_TLS` | Enable STARTTLS | `true` | Optional |
| `MAIL_USERNAME` | SMTP authentication username | `your-email@gmail.com` | Optional |
| `MAIL_PASSWORD` | SMTP password / App Password | `16-character Google App Password` | Optional |
| `MAIL_DEFAULT_SENDER`| Outgoing email From address | `your-email@gmail.com` | Optional |
| `GITHUB_CLIENT_ID` | GitHub OAuth Client ID | `Ov23li...` | Optional |
| `GITHUB_CLIENT_SECRET`| GitHub OAuth Client Secret | `3599e25...` | Optional |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `57151...apps.googleusercontent.com` | Optional |
| `GOOGLE_CLIENT_SECRET`| Google OAuth Client Secret | `GOCSPX-...` | Optional |

---

## Database Architecture

TaskFlow features dual-database compatibility handled seamlessly through SQLAlchemy:

* **Local Development:** Uses SQLite stored locally in `instance/taskflow.db`. No separate database server installation needed.
* **Production Deployment:** Supports managed PostgreSQL (e.g. Render PostgreSQL, Supabase, Neon) simply by defining the `DATABASE_URL` environment variable.

The schema comprises four core relational models:
1. **`User`**: Account identity, hashed passwords, verification state, and OAuth identifiers (`github_id`, `google_id`).
2. **`Category`**: User-scoped task categories with color hex codes (`#2563eb`, `#16a34a`, etc.).
3. **`Task`**: Tasks associated with a user and category, featuring priority, status, and lifecycle timestamps.
4. **`Settings`**: Per-user theme preferences and notification configurations.

---

## Authentication & Security

TaskFlow implements security-first best practices:

* **CSRF Protection:** Every state-changing form includes a dynamic, signed CSRF token validated by Flask-WTF.
* **Password Security:** Passwords require a minimum of 8 characters and are hashed using PBKDF2-SHA256 via Werkzeug. Plaintext passwords are never stored or logged.
* **Multi-User Isolation (IDOR Defense):** Every database query for tasks, categories, or settings strictly filters by `current_user.id`. Unauthorized access attempts are rejected with `403 Forbidden`.
* **XSS Defense:** Jinja2 auto-escapes all dynamic parameters in HTML templates.
* **Safe Redirects:** Login `next` redirects validate that target URLs reside on the same host to prevent open-redirect phishing.

---

## Email Verification & Delivery

* When a new account signs up, an account is created with `email_verified = False`.
* A cryptographically signed token is generated with a 24-hour expiration time.
* If SMTP credentials are configured in `.env`, the verification email is dispatched over TLS.
* If SMTP is unconfigured during local development, the system falls back to logging the message in the console without failing.
* The safe mailer logs transmission steps (connecting, TLS handshake, authenticating, dispatching) while strictly masking email addresses (e.g., `m*******@gmail.com`) and never logging passwords or secret tokens.

---

## Password Reset

* Users who forget their password can request a reset link from `/forgot-password`.
* The reset token binds both the `user_id` and a cryptographic hash signature of the current password hash.
* When the user changes their password, the signature changes, making the token **single-use** and immediately invalidating old links.

---

## OAuth Configuration

### GitHub OAuth Setup
1. Visit [GitHub Developer Settings](https://github.com/settings/developers) → **New OAuth App**.
2. Set **Homepage URL** to: `http://127.0.0.1:5000/` (Local) or `https://your-app.onrender.com/` (Production).
3. Set **Authorization callback URL** to: `http://127.0.0.1:5000/login/github/callback` (Local) or `https://your-app.onrender.com/login/github/callback` (Production).
4. Add `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` to your environment.

### Google OAuth Setup
1. Visit [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → **Create Credentials** → **OAuth 2.0 Client ID**.
2. Select **Web application**.
3. Add **Authorized redirect URIs**: `http://127.0.0.1:5000/login/google/callback` (Local) or `https://your-app.onrender.com/login/google/callback` (Production).
4. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to your environment.

---

## Demo Data & Seeding

TaskFlow provides a convenient CLI seeder to populate realistic test data:

```bash
# Seed demo user (jane.doe@example.com / taskflow123) and sample tasks
flask --app run:app cli seed-db

# Add sample tasks to a specific existing user
flask --app run:app cli seed-demo-tasks --email your-email@example.com
```

> ⚠️ **Note:** The seed password `taskflow123` is for local development only and must never be used in production.

---

## Testing Suite

Run the full automated test suite:

```bash
# Phase 2: Schema & Models
python test_phase2.py

# Phase 3: Auth & Forms
python test_phase3.py

# Phase 4: Tasks & Dashboard
python test_phase4.py

# Phase 5: Archive & Settings
python test_phase5.py

# Phase 6: Integration & Security
python test_phase6.py

# Phase 7: Verification & OAuth Fallback
python test_phase7_auth_features.py

# Email Delivery Diagnostics & Multi-User Isolation
python test_email_verification_diagnostics.py
```

---

## Production Deployment (Render)

### Option A: One-Click Blueprint Deployment (Recommended)
1. Push your repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com/), select **Blueprints** → **New Blueprint Instance**.
3. Connect your TaskFlow repository. Render will detect `render.yaml` and provision both the Web Service and a Managed PostgreSQL database automatically.

### Option B: Manual Web Service Setup on Render
1. Create a **New Web Service** connected to your GitHub repository.
2. Configure settings:
   - **Environment:** `Python`
   - **Python Version:** `3.13.0`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn run:app`
3. Under **Environment Variables**, add:
   - `SECRET_KEY`: Long random string
   - `DATABASE_URL`: Your PostgreSQL connection string (or Render Managed Database)
   - `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`, etc.

---

## Security Best Practices

1. **Never commit `.env`:** The repository's `.gitignore` excludes `.env`, `instance/*.db`, and sensitive files.
2. **Use App Passwords for Gmail:** Use a 16-character Google App Password with 2-Step Verification enabled.
3. **Always Run Behind WSGI:** In production, use Gunicorn (`gunicorn run:app`) rather than Flask's built-in development server.
4. **Enforce HTTPS:** Render and modern cloud hosts provide automatic TLS termination.

---

## Future Improvements

- Task tags and multi-label filtering
- Drag-and-drop Kanban board view
- Recurring task scheduling
- Team collaboration and shared task spaces
