"""
Greena — Email Service.

Transactional email for the auth system: verification, password reset, welcome,
password-changed and email-changed notices.

Design:
  * Greena OWNS the verification engine — token generation, hashing, expiry,
    single-use, rate limiting and audit live in auth_service. This module is
    only the transport + the branded templates.
  * Transport is behind an ``EmailProvider`` abstraction so a future provider
    (SES, Mailgun, Resend, a different SMTP host) can be added without touching
    authentication logic. The active provider is chosen from EMAIL_PROVIDER.
  * SMTP runs on a worker thread (asyncio.to_thread) — transactional volume, no
    async-SMTP dependency to audit.
  * Delivery NEVER raises into a request. A signup must not fail because the mail
    host is briefly unreachable; the failure is logged and the user can resend.
"""

import asyncio
import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from app.config import settings

logger = logging.getLogger(__name__)


# ── Provider abstraction ──────────────────────────────────────────────────────

class EmailProvider(ABC):
    """A transport that can deliver one message. Implementations must not raise
    on delivery failure — return False instead (see module docstring)."""

    @abstractmethod
    async def send(self, to: str, subject: str, html: str, text: str) -> bool: ...


def _from_header() -> tuple[str, str]:
    """Display name + address for the From header.

    Some hosts (Gmail, and Zoho for non-alias addresses) require the From
    address to be the authenticated mailbox, so the configured display name is
    kept but the address falls back to SMTP_USER for SMTP transports.
    """
    display, address = parseaddr(settings.EMAIL_FROM)
    if settings.SMTP_USER:
        address = settings.SMTP_USER
    return display or "Greena", address


class SMTPProvider(EmailProvider):
    """Delivers over SMTP with STARTTLS (587) or implicit TLS (465)."""

    def _send_sync(self, message: EmailMessage) -> None:
        if settings.SMTP_STARTTLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT,
                              timeout=settings.SMTP_TIMEOUT_SECONDS) as smtp:
                smtp.ehlo(); smtp.starttls(); smtp.ehlo()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT,
                                  timeout=settings.SMTP_TIMEOUT_SECONDS) as smtp:
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(message)

    async def send(self, to: str, subject: str, html: str, text: str) -> bool:
        display, address = _from_header()
        message = EmailMessage()
        message["Subject"] = subject
        message["To"] = to
        message["From"] = formataddr((display, address))
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        try:
            await asyncio.to_thread(self._send_sync, message)
            logger.info("Email sent to %s: %r", to, subject)
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error(
                "SMTP authentication failed for %s on %s — check SMTP_PASSWORD is a "
                "valid app password and that SMTP sending is enabled for the mailbox.",
                settings.SMTP_USER, settings.SMTP_HOST,
            )
            return False
        except Exception as exc:
            logger.error("Email to %s failed (%s): %s", to, subject, exc)
            return False


class ConsoleProvider(EmailProvider):
    """Development transport: logs the message instead of sending it. Lets the
    whole auth surface run with no mail account configured."""

    async def send(self, to: str, subject: str, html: str, text: str) -> bool:
        logger.info("[email:console] to=%s subject=%r\n%s", to, subject, text)
        return True


def _select_provider() -> EmailProvider:
    # Every non-console provider currently ships over SMTP (Zoho, Gmail, generic).
    # SES/Mailgun/Resend HTTP providers slot in here without changing callers.
    if settings.EMAIL_PROVIDER == "console" or not settings.SMTP_USER:
        return ConsoleProvider()
    return SMTPProvider()


# Chosen once at import; cheap and stateless, and env is fixed for the process.
provider: EmailProvider = _select_provider()


async def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Send one email through the active provider. Never raises."""
    if not to:
        logger.warning("Email skipped: no recipient for %r", subject)
        return False
    return await provider.send(to, subject, html, text)


# Background sending. Auth flows must NOT await email — an SMTP send can take
# seconds (or, where a host blocks outbound SMTP, the full timeout), and a signup
# or reset must never be delayed or failed by it. `fire()` schedules the coroutine
# on the running loop and returns immediately; a reference is held so the task is
# not garbage-collected before it runs.
_bg_tasks: set = set()


def fire(coro) -> None:
    """Run an email coroutine in the background. Never blocks or raises."""
    try:
        task = asyncio.create_task(coro)
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
    except RuntimeError:
        # No running event loop (e.g. a sync context / test) — close the coroutine
        # so it doesn't warn, and skip. The caller's flow is unaffected.
        coro.close()


# ── Branded templates ─────────────────────────────────────────────────────────
#
# Inline styles only (Gmail and others strip <style> blocks). Table-based layout
# with a fluid max-width for mobile. Image-free logo lockup so nothing breaks
# when a client blocks remote images by default.

_BRAND = "#076524"
_BRAND_DARK = "#054a1b"
_INK = "#111827"
_MUTED = "#6b7280"


def _logo() -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:34px;height:34px;background:{_BRAND};border-radius:9px;'
        'text-align:center;vertical-align:middle;color:#ffffff;font-size:18px;'
        'font-weight:800;font-family:Arial,sans-serif;">G</td>'
        '<td style="padding-left:10px;font-size:20px;font-weight:700;'
        f'color:{_BRAND};font-family:Arial,sans-serif;letter-spacing:-0.02em;">Greena</td>'
        '</tr></table>'
    )


def _button(label: str, url: str) -> str:
    if not (label and url):
        return ""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr><td '
        f'style="border-radius:10px;background:{_BRAND};">'
        f'<a href="{url}" style="display:inline-block;padding:13px 26px;font-size:15px;'
        f'font-weight:600;color:#ffffff;text-decoration:none;font-family:Arial,sans-serif;">'
        f'{label}</a></td></tr></table>'
    )


def _layout(heading: str, body_html: str, *, cta_label: str = "", cta_url: str = "",
            security_note: str = "If you didn't request this, you can safely ignore this email.") -> str:
    fallback = (
        f'<p style="color:{_MUTED};font-size:13px;line-height:1.6;margin:8px 0 0;">'
        f'If the button doesn\'t work, copy and paste this link into your browser:<br>'
        f'<span style="color:{_BRAND};word-break:break-all;">{cta_url}</span></p>'
        if cta_url else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light only"></head>
<body style="margin:0;padding:0;background:#f4f7f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7f4;padding:28px 14px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #eaeeea;">
        <tr><td style="padding:28px 32px 8px;">{_logo()}</td></tr>
        <tr><td style="padding:8px 32px 0;">
          <h1 style="margin:0 0 14px;font-size:22px;line-height:1.3;color:{_INK};">{heading}</h1>
          {body_html}
          {_button(cta_label, cta_url)}
          {fallback}
        </td></tr>
        <tr><td style="padding:24px 32px 28px;">
          <hr style="border:none;border-top:1px solid #edf0ed;margin:8px 0 16px;">
          <p style="margin:0 0 8px;color:{_MUTED};font-size:12px;line-height:1.6;">{security_note}</p>
          <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.6;">
            Greena — the operating system for your farm.<br>Nairobi, Kenya · support@greena.app
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _p(text: str) -> str:
    return f'<p style="margin:0 0 12px;color:#374151;font-size:15px;line-height:1.65;">{text}</p>'


# ── Flows ─────────────────────────────────────────────────────────────────────

async def send_verification_email(to: str, name: str, token: str) -> bool:
    url = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={token}"
    hours = settings.EMAIL_VERIFY_TOKEN_HOURS
    greeting = f"Hi {name}," if name else "Hi,"
    html = _layout(
        "Confirm your email",
        _p(greeting) + _p("Confirm this address to finish setting up your Greena account.")
        + _p(f"This link expires in {hours} hours and can be used once."),
        cta_label="Confirm email", cta_url=url,
    )
    text = (f"{greeting}\n\nConfirm your email to finish setting up your Greena account:\n{url}\n\n"
            f"This link expires in {hours} hours.\n\nIf you didn't sign up for Greena, ignore this email.\n")
    return await send_email(to, "Confirm your Greena email", html, text)


async def send_password_reset_email(to: str, name: str, token: str) -> bool:
    url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    hours = settings.PASSWORD_RESET_TOKEN_HOURS
    s = "s" if hours != 1 else ""
    greeting = f"Hi {name}," if name else "Hi,"
    html = _layout(
        "Reset your password",
        _p(greeting) + _p("We received a request to reset your Greena password. Choose a new one below.")
        + _p(f"This link expires in {hours} hour{s} and can be used once."),
        cta_label="Reset password", cta_url=url,
        security_note="If you didn't request this, you can ignore this email — your password won't change.",
    )
    text = (f"{greeting}\n\nReset your Greena password:\n{url}\n\n"
            f"This link expires in {hours} hour{s} and can be used once.\n\n"
            "If you didn't request this, ignore this email — your password is unchanged.\n")
    return await send_email(to, "Reset your Greena password", html, text)


async def send_welcome_email(to: str, name: str) -> bool:
    url = settings.FRONTEND_URL.rstrip("/")
    greeting = f"Welcome, {name}!" if name else "Welcome to Greena!"
    html = _layout(
        greeting,
        _p("Your Greena account is ready.")
        + _p("Greena keeps your whole operation in one place — animals, daily logs, feed, "
             "health, finances and reports across poultry, birds, rabbits, goats, sheep, "
             "pigs and more — and ARIA answers questions using your own farm data.")
        + _p("Set up your first farm to start your <strong>14-day Greena Premium trial</strong> — "
             "every feature, free for 14 days."),
        cta_label="Set up my farm", cta_url=url,
        security_note="You're receiving this because you created a Greena account.",
    )
    text = (f"{greeting}\n\nYour Greena account is ready.\n\n"
            "Greena keeps your whole operation in one place — animals, daily logs, feed, health, "
            "finances and reports across poultry, birds, rabbits, goats, sheep, pigs and more — "
            "and ARIA answers questions using your own farm data.\n\n"
            "Set up your first farm to start your 14-day Greena Premium trial — every feature, "
            f"free for 14 days:\n{url}\n")
    return await send_email(to, "Welcome to Greena", html, text)


async def send_password_changed_email(to: str, name: str) -> bool:
    """Confirmation that the password was changed — a security signal so an
    unexpected change is noticed."""
    url = f"{settings.FRONTEND_URL.rstrip('/')}/forgot-password"
    greeting = f"Hi {name}," if name else "Hi,"
    html = _layout(
        "Your password was changed",
        _p(greeting) + _p("This is a confirmation that the password on your Greena account was "
                          "just changed, and you've been signed out of your other sessions.")
        + _p("If this was you, no action is needed."),
        cta_label="Reset it again", cta_url=url,
        security_note="If this <strong>wasn't</strong> you, reset your password immediately and contact support@greena.app.",
    )
    text = (f"{greeting}\n\nThe password on your Greena account was just changed, and you've been "
            "signed out of your other sessions.\n\nIf this was you, no action is needed.\n\n"
            f"If this wasn't you, reset your password now:\n{url}\nand contact support@greena.app.\n")
    return await send_email(to, "Your Greena password was changed", html, text)


async def send_email_changed_email(to: str, name: str, new_email: str) -> bool:
    """Notify the OLD address that an email change was requested — sent to the
    previous address so a hijacked change is visible to the real owner."""
    greeting = f"Hi {name}," if name else "Hi,"
    html = _layout(
        "Your email address is changing",
        _p(greeting) + _p(f"We received a request to change the email on your Greena account to "
                          f"<strong>{new_email}</strong>.")
        + _p("If this was you, you can ignore this message once the new address is confirmed."),
        security_note="If you didn't request this, contact support@greena.app right away — your account may be at risk.",
    )
    text = (f"{greeting}\n\nWe received a request to change the email on your Greena account to "
            f"{new_email}.\n\nIf this was you, no action is needed. If not, contact "
            "support@greena.app right away.\n")
    return await send_email(to, "Your Greena email address is changing", html, text)
