import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def mask_email(email: str) -> str:
    """Masks an email address for safe logging (e.g., m*******@gmail.com)."""
    if not email or "@" not in email:
        return "***"
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 1:
            masked_local = "*"
        else:
            masked_local = local[0] + "*******"
        return f"{masked_local}@{domain}"
    except Exception:
        return "***"


def send_email(to_email: str, subject: str, body_text: str, body_html: str = None, email_type: str = "Email") -> bool:
    """
    Sends an email using configured SMTP settings with safe diagnostic logging.
    Returns True if successfully handed to the SMTP server (or in dev fallback mode),
    or False if SMTP delivery fails.
    
    Supported Environment Variables:
      - MAIL_SERVER
      - MAIL_PORT (default 587)
      - MAIL_USE_TLS (default True)
      - MAIL_USERNAME
      - MAIL_PASSWORD
      - MAIL_DEFAULT_SENDER (default: MAIL_USERNAME or 'noreply@taskflow.dev')
    """
    mail_server = os.environ.get("MAIL_SERVER")
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")
    mail_port_str = os.environ.get("MAIL_PORT", "587")
    mail_use_tls = os.environ.get("MAIL_USE_TLS", "true").lower() in ("true", "1", "yes")
    default_sender = os.environ.get("MAIL_DEFAULT_SENDER") or mail_username or "noreply@taskflow.dev"

    # -----------------------------------------------------------------
    # Case 1: SMTP is configured -> Attempt Real Transmission
    # -----------------------------------------------------------------
    if mail_server and mail_username and mail_password:
        try:
            mail_port = int(mail_port_str)
        except ValueError:
            print(f"[MAIL] Configuration error: Invalid MAIL_PORT '{mail_port_str}'.", file=sys.stderr)
            return False

        print(f"[MAIL] {email_type} requested", file=sys.stdout)
        print(f"[MAIL] Recipient: {mask_email(to_email)}", file=sys.stdout)
        print(f"[MAIL] SMTP host: {mail_server}", file=sys.stdout)
        print(f"[MAIL] SMTP port: {mail_port}", file=sys.stdout)
        print(f"[MAIL] TLS: {'enabled' if mail_use_tls else 'disabled'}", file=sys.stdout)
        print(f"[MAIL] Sender: {mask_email(default_sender)}", file=sys.stdout)
        print(f"[MAIL] Connecting...", file=sys.stdout)

        server = None
        try:
            server = smtplib.SMTP(mail_server, mail_port, timeout=15)
            print(f"[MAIL] Connected", file=sys.stdout)

            if mail_use_tls:
                server.ehlo()
                server.starttls()
                server.ehlo()

            print(f"[MAIL] Authenticating...", file=sys.stdout)
            server.login(mail_username, mail_password)
            print(f"[MAIL] Authentication successful", file=sys.stdout)

            print(f"[MAIL] Sending {email_type.lower()}...", file=sys.stdout)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = default_sender
            msg["To"] = to_email

            part1 = MIMEText(body_text, "plain")
            msg.attach(part1)

            if body_html:
                part2 = MIMEText(body_html, "html")
                msg.attach(part2)

            server.sendmail(default_sender, [to_email], msg.as_string())
            print(f"[MAIL] SMTP accepted message", file=sys.stdout)
            return True

        except smtplib.SMTPAuthenticationError as e:
            err_msg = e.smtp_error.decode('utf-8', errors='replace') if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
            print(f"[MAIL] SMTP authentication failed: SMTPAuthenticationError {e.smtp_code} ({err_msg})", file=sys.stderr)
            return False
        except (smtplib.SMTPConnectError, TimeoutError, ConnectionRefusedError, OSError) as e:
            print(f"[MAIL] SMTP connection failed: {type(e).__name__} ({e})", file=sys.stderr)
            return False
        except smtplib.SMTPException as e:
            print(f"[MAIL] SMTP send failed: {type(e).__name__} ({e})", file=sys.stderr)
            return False
        except Exception as e:
            print(f"[MAIL] Unexpected email delivery error: {type(e).__name__} ({e})", file=sys.stderr)
            return False
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass

    # -----------------------------------------------------------------
    # Case 2: Local Development Fallback (SMTP not configured)
    # -----------------------------------------------------------------
    print(f"[MAIL] (Dev Mode) SMTP not configured — logging to console", file=sys.stdout)
    print(f"[MAIL] Recipient: {mask_email(to_email)}", file=sys.stdout)
    print("\n" + "=" * 65, file=sys.stdout)
    print(f"[TASKFLOW DEV EMAIL] Outgoing Message to: {to_email}", file=sys.stdout)
    print(f"Subject: {subject}", file=sys.stdout)
    print("-" * 65, file=sys.stdout)
    print(body_text.strip(), file=sys.stdout)
    print("=" * 65 + "\n", file=sys.stdout)
    return True


def send_verification_email(to_email: str, verify_url: str) -> bool:
    """Sends account email verification link."""
    subject = "Verify your TaskFlow Account"
    body_text = f"""Hello,

Thank you for signing up for TaskFlow!

Please verify your email address by visiting the link below:
{verify_url}

This link will expire in 24 hours.

If you did not create a TaskFlow account, please ignore this email.

Best regards,
The TaskFlow Team
"""
    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #0f172a; padding: 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px;">
    <h2 style="color: #1d4ed8; margin-top: 0;">TaskFlow</h2>
    <p>Hello,</p>
    <p>Thank you for signing up for TaskFlow! Please click the button below to verify your email address:</p>
    <div style="margin: 24px 0;">
      <a href="{verify_url}" style="background: #1e3a8a; color: #ffffff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Verify Email Address</a>
    </div>
    <p style="font-size: 13px; color: #64748b;">Or copy and paste this link into your browser:<br><a href="{verify_url}" style="color: #1d4ed8;">{verify_url}</a></p>
    <p style="font-size: 12px; color: #94a3b8; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 12px;">This link will expire in 24 hours. If you did not create an account, you can safely ignore this email.</p>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, body_text, body_html, email_type="Verification email")


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Sends password reset link."""
    subject = "Reset your TaskFlow Password"
    body_text = f"""Hello,

We received a request to reset the password for your TaskFlow account.

Please visit the link below to set a new password:
{reset_url}

This link will expire in 1 hour and can only be used once.

If you did not request a password reset, please ignore this email.

Best regards,
The TaskFlow Team
"""
    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #0f172a; padding: 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px;">
    <h2 style="color: #1d4ed8; margin-top: 0;">TaskFlow</h2>
    <p>Hello,</p>
    <p>We received a request to reset the password for your TaskFlow account. Click the button below to choose a new password:</p>
    <div style="margin: 24px 0;">
      <a href="{reset_url}" style="background: #1e3a8a; color: #ffffff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Reset Password</a>
    </div>
    <p style="font-size: 13px; color: #64748b;">Or copy and paste this link into your browser:<br><a href="{reset_url}" style="color: #1d4ed8;">{reset_url}</a></p>
    <p style="font-size: 12px; color: #94a3b8; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 12px;">This link will expire in 1 hour and is single-use. If you did not request this, you can safely ignore this email.</p>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, body_text, body_html, email_type="Password reset email")

