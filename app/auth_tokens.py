from itsdangerous import URLSafeTimedSerializer
from app.models import User

def get_serializer(secret_key: str) -> URLSafeTimedSerializer:
    """Returns a URLSafeTimedSerializer initialized with the application's SECRET_KEY."""
    return URLSafeTimedSerializer(secret_key)


def generate_email_verification_token(email: str, secret_key: str) -> str:
    """Generates a cryptographically signed, timestamped email verification token."""
    serializer = get_serializer(secret_key)
    return serializer.dumps(email, salt="taskflow-email-verification-salt")


def verify_email_verification_token(token: str, secret_key: str, max_age: int = 86400) -> str:
    """
    Verifies an email verification token.
    Default validity: 24 hours (86,400 seconds).
    Returns the email string if valid, or None if invalid or expired.
    """
    serializer = get_serializer(secret_key)
    try:
        email = serializer.loads(
            token,
            salt="taskflow-email-verification-salt",
            max_age=max_age
        )
        return email
    except Exception:
        return None


def generate_password_reset_token(user: User, secret_key: str) -> str:
    """
    Generates a secure password reset token.
    Includes user ID and a tail signature of the current password hash.
    This guarantees that the token is single-use and immediately invalidated once the password is changed.
    """
    serializer = get_serializer(secret_key)
    hash_tail = (user.password_hash or "")[-12:]
    payload = {
        "user_id": user.id,
        "hash_tail": hash_tail
    }
    return serializer.dumps(payload, salt="taskflow-password-reset-salt")


def verify_password_reset_token(token: str, secret_key: str, max_age: int = 3600):
    """
    Verifies a password reset token.
    Default validity: 1 hour (3,600 seconds).
    Returns the User model instance if valid and unused, or None if invalid/expired/already used.
    """
    serializer = get_serializer(secret_key)
    try:
        data = serializer.loads(
            token,
            salt="taskflow-password-reset-salt",
            max_age=max_age
        )
        user_id = data.get("user_id")
        hash_tail = data.get("hash_tail")
        if not user_id:
            return None

        user = User.query.get(user_id)
        if not user:
            return None

        # Verify password hash has not changed since token generation
        current_tail = (user.password_hash or "")[-12:]
        if current_tail != hash_tail:
            return None

        return user
    except Exception:
        return None
