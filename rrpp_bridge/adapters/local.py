from __future__ import annotations

from typing import Any

from ..models import NormalizedEvent

MAX_BODY_LENGTH = 20_000


def normalize(payload: dict[str, Any]) -> NormalizedEvent:
    values: dict[str, str] = {}
    for field in ("external_message_id", "sender", "recipient", "body_text"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        values[field] = value.strip()
    if len(values["body_text"]) > MAX_BODY_LENGTH:
        raise ValueError(f"body_text exceeds {MAX_BODY_LENGTH} characters")
    subject = payload.get("subject", "")
    if not isinstance(subject, str) or len(subject) > 500:
        raise ValueError("subject must be a string of at most 500 characters")
    # A channel-scoped conversation key serializes related work.
    work_key = f"local:{values['sender'].casefold()}:{values['recipient'].casefold()}"
    return NormalizedEvent(
        channel="local", external_message_id=values["external_message_id"],
        sender=values["sender"], recipient=values["recipient"], subject=subject.strip(),
        body_text=values["body_text"], work_key=work_key,
    )
