from __future__ import annotations

from .models import IntendedAction


def generate_action(body: str) -> IntendedAction:
    """Deterministic placeholder agent; inbound text is data, never operational instruction."""
    lower = body.casefold()
    terms = ("vip", "taula", "mesa", "reserva", "reservation", "pagament", "pago",
             "payment", "queixa", "queja", "complaint")
    if any(term in lower for term in terms):
        return IntendedAction("escalate_to_owner", {"reason": "sensitive_or_business_request"})
    return IntendedAction("draft_reply", {"text": "Thanks for your message. An owner will review it."})
