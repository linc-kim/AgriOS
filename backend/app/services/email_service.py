"""
Greena — Email Service.

Sends transactional email over SMTP (Gmail in production), or logs it to the
console when no provider is configured.

Uses stdlib smtplib on a worker thread rather than adding an async SMTP
dependency: the volume here is transactional (verification, password reset,
welcome), not bulk, and asyncio.to_thread keeps the event loop free without
introducing another package to audit and pin.

Delivery never raises into a request. A signup must not fail because Gmail is
briefly unreachable — the account is created, the failure is logged, and the
user can request a new verification link. Callers get a bool if they care.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from app.config import settings

logger = logging.getLogger(__name__)


# ── Transport ─────────────────────────────────────────────────────────────────

def _send_sync(message: EmailMessage) -> None:
    """Blocking SMTP send. Runs on a worker thread."""
    if settings.SMTP_STARTTLS:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT,
                          timeout=settings.SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    else:
        # Implicit TLS (port 465).
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT,
                              timeout=settings.SMTP_TIMEOUT_SECONDS) as smtp:
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)


def _build_message(to: str, subject: str, html: str, text: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["To"] = to

    # Gmail rewrites the From address to the authenticated account unless the
    # address is a verified alias, so the configured display name is kept but
    # the address falls back to SMTP_USER to avoid a mismatch that trips spam
    # filters (and, on some providers, a hard rejection).
    display, address = parseaddr(settings.EMAIL_FROM)
    if settings.EMAIL_PROVIDER == "smtp" and settings.SMTP_USER:
        address = settings.SMTP_USER
    message["From"] = formataddr((display or "Greena", address))

    message.set_content(text)
    message.add_alternative(html, subtype="html")
    return message


async def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """
    Send one email. Returns True if it was handed to the provider.

    Never raises — see the module docstring.
    """
    if not to:
        logger.warning("Email skipped: no recipient for %r", subject)
        return False

    if settings.EMAIL_PROVIDER == "console" or not settings.SMTP_USER:
        # Development path: the whole auth surface works with no mail account.
        logger.info(
            "[email:console] to=%s subject=%r\n%s",
            to, subject, text,
        )
        return True

    try:
        message = _build_message(to, subject, html, text)
        await asyncio.to_thread(_send_sync, message)
        logger.info("Email sent to %s: %r", to, subject)
        return True
    except smtplib.SMTPAuthenticationError:
        # The single most likely misconfiguration: a Google account password
        # instead of an App Password, or 2FA not enabled on the account.
        logger.error(
            "SMTP authentication failed for %s — Gmail requires an App Password "
            "(Google Account → Security → 2-Step Verification → App passwords), "
            "not the account password.",
            settings.SMTP_USER,
        )
        return False
    except Exception as exc:
        logger.error("Email to %s failed (%s): %s", to, subject, exc)
        return False


# ── Templates ─────────────────────────────────────────────────────────────────
#
# Inline styles only: Gmail strips <style> blocks, so a stylesheet would render
# as unstyled text in the client most of these users are on.

_BRAND = "#076524"


def _layout(heading: str, body_html: str, cta_label: str = "", cta_url: str = "") -> str:
    button = (
        f'<a href="{cta_url}" style="display:inline-block;background:{_BRAND};color:#ffffff;'
        f'text-decoration:none;padding:12px 24px;border-radius:8px;font-weight:600;'
        f'margin:20px 0;">{cta_label}</a>'
        if cta_label and cta_url else ""
    )
    fallback = (
        f'<p style="color:#6b7280;font-size:13px;line-height:1.6;">'
        f'If the button does not work, paste this into your browser:<br>'
        f'<span style="color:{_BRAND};word-break:break-all;">{cta_url}</span></p>'
        if cta_url else ""
    )
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f6f8f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f8f6;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:16px;padding:32px;">
        <tr><td>
          <p style="margin:0 0 24px;font-size:20px;font-weight:700;color:{_BRAND};">Greena</p>
          <h1 style="margin:0 0 16px;font-size:22px;color:#111827;">{heading}</h1>
          {body_html}
          {button}
          {fallback}
          <hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0 16px;">
          <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.6;">
            Greena — the operating system for your farm.<br>
            You received this because someone used this address to sign up. If that was not you, ignore this email.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _p(text: str) -> str:
    return f'<p style="margin:0 0 12px;color:#374151;font-size:15px;line-height:1.6;">{text}</p>'


# ── Flows ─────────────────────────────────────────────────────────────────────

async def send_verification_email(to: str, name: str, token: str) -> bool:
    url = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={token}"
    hours = settings.EMAIL_VERIFY_TOKEN_HOURS
    greeting = f"Hi {name}," if name else "Hi,"
    html = _layout(
        "Confirm your email",
        _p(greeting) + _p(
            "Confirm this address to finish setting up your Greena account."
        ) + _p(f"This link expires in {hours} hours."),
        "Confirm email", url,
    )
    text = (
        f"{greeting}\n\n"
        f"Confirm your email to finish setting up your Greena account:\n{url}\n\n"
        f"This link expires in {hours} hours.\n\n"
        "If you did not sign up for Greena, ignore this email.\n"
    )
    return await send_email(to, "Confirm your Greena email", html, text)


async def send_password_reset_email(to: str, name: str, token: str) -> bool:
    url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    hours = settings.PASSWORD_RESET_TOKEN_HOURS
    greeting = f"Hi {name}," if name else "Hi,"
    html = _layout(
        "Reset your password",
        _p(greeting) + _p(
            "We received a request to reset your Greena password. "
            "Choose a new one using the button below."
        ) + _p(
            f"This link expires in {hours} hour{'s' if hours != 1 else ''} and can be used once."
        ),
        "Reset password", url,
    )
    text = (
        f"{greeting}\n\n"
        f"Reset your Greena password:\n{url}\n\n"
        f"This link expires in {hours} hour(s) and can be used once.\n\n"
        "If you did not request this, ignore this email — your password is unchanged.\n"
    )
    return await send_email(to, "Reset your Greena password", html, text)


async def send_welcome_email(to: str, name: str) -> bool:
    url = settings.FRONTEND_URL.rstrip("/")
    greeting = f"Welcome, {name}!" if name else "Welcome to Greena!"
    html = _layout(
        greeting,
        _p("Your Greena account is ready.")
        + _p("Greena keeps your whole operation in one place — flocks, daily logs, "
             "feed, health, finances and reports — and ARIA answers questions using "
             "your own farm data.")
        + _p("Start by adding your first farm and flock."),
        "Open Greena", url,
    )
    text = (
        f"{greeting}\n\n"
        "Your Greena account is ready.\n\n"
        "Greena keeps your whole operation in one place — flocks, daily logs, feed, "
        "health, finances and reports — and ARIA answers questions using your own "
        "farm data.\n\n"
        f"Start by adding your first farm and flock:\n{url}\n"
    )
    return await send_email(to, "Welcome to Greena", html, text)
