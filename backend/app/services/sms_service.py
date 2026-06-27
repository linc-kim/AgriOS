"""
AGRIOS — SMS Service (Africa's Talking)
Sprint 7: Implements all SMS notification types from Engineering Constitution Appendix C.

SMS types (all from Engineering Constitution, Appendix C):
  OTP                  — already in auth service
  Farm invite          — sent on member invite
  Vaccination reminder — 3 days before next_due_date
  Vaccination overdue  — 1 day after next_due_date
  Daily log reminder   — 20:00 EAT if farm unlogged today
  Disease alert        — admin publishes, all farms in county
  Weekly summary       — every Friday at 18:00 EAT

All SMS is fire-and-forget. Failures are logged, not raised.
AT_ENVIRONMENT = "sandbox" in development (no real SMS sent).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_at_sms():
    """Lazy-load Africa's Talking SDK and return configured SMS instance."""
    try:
        import africastalking  # type: ignore
        from app.config import settings

        africastalking.initialize(
            username=settings.AT_USERNAME,
            api_key=settings.AT_API_KEY,
        )
        return africastalking.SMS
    except ImportError:
        logger.warning("africastalking package not installed — SMS disabled")
        return None
    except Exception as e:
        logger.error(f"Africa's Talking init failed: {e}")
        return None


async def send_sms(phone: str, message: str, sender_id: Optional[str] = None) -> bool:
    """
    Send a single SMS via Africa's Talking.
    Returns True on success, False on failure.
    Fire-and-forget — callers should not depend on return value for business logic.

    Phone format: E.164 e.g. "+254712345678"
    """
    from app.config import settings

    sms = _get_at_sms()
    if not sms:
        logger.info(f"[SMS MOCK] To {phone}: {message}")
        return False

    try:
        response = sms.send(
            message=message,
            recipients=[phone],
            sender_id=sender_id or settings.AT_SENDER_ID,
        )
        logger.info(f"SMS sent to {phone}: {response}")
        return True
    except Exception as e:
        logger.error(f"SMS send failed to {phone}: {e}")
        return False


async def send_bulk_sms(phones: list[str], message: str) -> int:
    """Send the same message to multiple recipients. Returns count of successes."""
    sms = _get_at_sms()
    if not sms:
        logger.info(f"[SMS MOCK BULK] To {len(phones)} recipients: {message}")
        return 0

    from app.config import settings

    try:
        response = sms.send(
            message=message,
            recipients=phones,
            sender_id=settings.AT_SENDER_ID,
        )
        # Count successful sends
        recipients = response.get("SMSMessageData", {}).get("Recipients", [])
        success_count = sum(1 for r in recipients if r.get("status") == "Success")
        logger.info(f"Bulk SMS: {success_count}/{len(phones)} delivered")
        return success_count
    except Exception as e:
        logger.error(f"Bulk SMS failed: {e}")
        return 0


# ── Template Functions ────────────────────────────────────────────────────────

async def sms_vaccination_reminder(
    phone: str, vaccine_name: str, flock_name: str, due_date: str
) -> bool:
    """Vaccination reminder — 3 days before next_due_date."""
    msg = (
        f"Reminder: {vaccine_name} due for {flock_name} on {due_date}. "
        f"Log it on AGRIOS."
    )
    return await send_sms(phone, msg)


async def sms_vaccination_overdue(
    phone: str, vaccine_name: str, flock_name: str, due_date: str
) -> bool:
    """Vaccination overdue — 1 day after next_due_date."""
    msg = (
        f"Overdue: {vaccine_name} for {flock_name} was due {due_date}. "
        f"Please vaccinate immediately. Log on AGRIOS."
    )
    return await send_sms(phone, msg)


async def sms_daily_log_reminder(
    phone: str, flock_name: str
) -> bool:
    """Daily log reminder — 20:00 EAT if unlogged today."""
    msg = (
        f"AGRIOS: {flock_name} has not been logged today. "
        f"Please log daily data now."
    )
    return await send_sms(phone, msg)


async def sms_disease_alert(
    phones: list[str], disease_name: str, county: str, guidance: str
) -> int:
    """Disease alert — admin publishes, all farms in county receive."""
    msg = (
        f"AGRIOS Alert: {disease_name} reported in {county}. "
        f"{guidance} Check AGRIOS for details."
    )
    return await send_bulk_sms(phones, msg)


async def sms_weekly_summary(
    phone: str, farm_name: str, survival_rate: float, flock_count: int
) -> bool:
    """Weekly summary — every Friday at 18:00 EAT."""
    msg = (
        f"AGRIOS Weekly: {farm_name} had {survival_rate:.1f}% survival rate this week. "
        f"{flock_count} active flock(s). View your report on AGRIOS."
    )
    return await send_sms(phone, msg)


async def sms_farm_invite(
    phone: str, farm_name: str
) -> bool:
    """Farm member invite notification."""
    msg = (
        f"You have been invited to join {farm_name} on AGRIOS. "
        f"Open the AGRIOS app to accept."
    )
    return await send_sms(phone, msg)
