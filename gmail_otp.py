"""
Gmail IMAP OTP reader.

Polls the inbox for a VFS OTP email that arrived after a given timestamp,
extracts the 6-digit code, and marks the email as read.

Requires a Gmail App Password (not the regular account password).
Generate one at: https://myaccount.google.com/apppasswords
"""
import imaplib
import email
import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, OTP_WAIT_SECONDS

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

# VFS Global sends OTP emails from this address
VFS_SENDER = "donotreply@vfsglobal.com"


def fetch_latest_otp(triggered_at: datetime, timeout: int = OTP_WAIT_SECONDS) -> Optional[str]:
    """
    Poll Gmail IMAP for a VFS OTP email received after `triggered_at`.

    Args:
        triggered_at: UTC datetime captured just before the OTP was requested.
        timeout:      Maximum seconds to wait before giving up.

    Returns:
        6-digit OTP string, or None if not found within the timeout.
    """
    deadline = time.monotonic() + timeout
    poll_interval = 5  # seconds between IMAP checks

    logging.info(f"Polling Gmail for OTP (timeout={timeout}s)…")

    while time.monotonic() < deadline:
        otp = _try_fetch_otp(triggered_at)
        if otp:
            logging.info(f"OTP retrieved: {otp}")
            return otp
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sleep_for = min(poll_interval, remaining)
        logging.debug(f"OTP not yet received. Retrying in {sleep_for:.0f}s…")
        time.sleep(sleep_for)

    logging.error("OTP not received within timeout.")
    return None


def _try_fetch_otp(triggered_at: datetime) -> Optional[str]:
    """Single IMAP fetch attempt. Returns OTP string or None."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        # SINCE filter uses date only (not time) — we verify exact recency below
        since_date = triggered_at.strftime("%d-%b-%Y")
        search_criteria = f'(UNSEEN FROM "{VFS_SENDER}" SINCE "{since_date}")'
        status, data = mail.search(None, search_criteria)

        if status != "OK" or not data[0]:
            mail.logout()
            return None

        msg_ids = data[0].split()
        # Process newest first
        for msg_id in reversed(msg_ids):
            status, msg_data = mail.fetch(msg_id, "(RFC822 INTERNALDATE)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Verify the email arrived AFTER our trigger timestamp
            date_str = msg.get("Date", "")
            try:
                from email.utils import parsedate_to_datetime
                msg_dt = parsedate_to_datetime(date_str)
                if msg_dt.tzinfo is None:
                    msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                if msg_dt < triggered_at:
                    continue  # Skip older emails
            except Exception:
                pass  # If parsing fails, try the email anyway

            body = _extract_body(msg)
            otp = _extract_otp(body)
            if otp:
                # Mark as read
                mail.store(msg_id, "+FLAGS", "\\Seen")
                mail.logout()
                return otp

        mail.logout()
    except imaplib.IMAP4.error as exc:
        logging.warning(f"IMAP error: {exc}")
    except Exception as exc:
        logging.warning(f"Unexpected error reading Gmail: {exc}")

    return None


def _extract_body(msg: email.message.Message) -> str:
    """Extract plaintext body from an email.message.Message."""
    body_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode("utf-8", errors="replace"))
    return "\n".join(body_parts)


def _extract_otp(text: str) -> Optional[str]:
    """
    Extract a 6-digit OTP from email text.
    VFS Global typically formats it as: "Your OTP is: 123456" or just a
    standalone 6-digit number on its own line.
    """
    # Look for labelled patterns first (most reliable)
    patterns = [
        r'(?:OTP|one.?time.?password|verification code|kod)[^\d]{0,20}(\d{6})',
        r'(\d{6})\s*(?:is your|kodunuz)',
        r'\b(\d{6})\b',  # Fallback: any 6-digit number
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None
