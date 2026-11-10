"""WhatsApp notifications.

Providers (set WHATSAPP_PROVIDER):
  console — log the message instead of sending (default; good for local dev and demos)
  meta    — send through the Meta WhatsApp Cloud API
"""
import logging
import re
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)
GRAPH_URL = "https://graph.facebook.com/v20.0/{phone_number_id}/messages"


class WhatsAppError(RuntimeError):
    pass


def normalize_phone(raw: str, default_country_code: str = "254") -> str:
    """Turn '0712 345 678' or '+254-712-345678' into '254712345678'."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        digits = default_country_code + digits[1:]
    if not 10 <= len(digits) <= 15:
        raise ValueError(f"'{raw}' doesn't look like a valid phone number.")
    return digits


def click_to_chat_link(phone: str, message: str) -> str:
    """Free fallback: a wa.me link that opens WhatsApp with the message pre-filled."""
    return f"https://wa.me/{phone}?text={quote(message)}"


def send_message(to: str, body: str, config) -> dict:
    provider = config.get("WHATSAPP_PROVIDER", "console")

    if provider == "console":
        log.info("[WhatsApp → %s] %s", to, body)
        return {"provider": "console", "to": to}

    if provider == "meta":
        token = config.get("WHATSAPP_TOKEN")
        phone_number_id = config.get("WHATSAPP_PHONE_NUMBER_ID")
        if not token or not phone_number_id:
            raise WhatsAppError("WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID must be set.")
        resp = requests.post(
            GRAPH_URL.format(phone_number_id=phone_number_id),
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body},
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            raise WhatsAppError(f"WhatsApp API error {resp.status_code}: {resp.text}")
        return resp.json()

    raise WhatsAppError(f"Unknown WHATSAPP_PROVIDER '{provider}'.")
