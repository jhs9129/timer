"""Delivery adapters. Business logic never imports pywebpush or httpx directly."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import Settings
from app.models.notification import PushSubscription

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


@dataclass(frozen=True)
class SendResult:
    ok: bool
    error: str | None = None
    gone: bool = False  # the push endpoint no longer exists: revoke the subscription


class PushSender(Protocol):
    async def send(self, subscription: PushSubscription, payload: dict[str, Any]) -> SendResult: ...


class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, text: str, html: str) -> SendResult: ...


@dataclass
class Senders:
    push: PushSender
    email: EmailSender


class LoggingSender:
    """Used when no credentials are configured. Logs and reports a failure."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    async def send(self, *args: Any, **kwargs: Any) -> SendResult:
        log.info("%s sender not configured; dropping message", self.channel)
        return SendResult(ok=False, error="not configured")


class WebPushSender:
    def __init__(self, settings: Settings) -> None:
        self.private_key = settings.vapid_private_key
        self.claims = {"sub": settings.vapid_subject}

    async def send(self, subscription: PushSubscription, payload: dict[str, Any]) -> SendResult:
        from pywebpush import WebPushException, webpush

        info = {
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        }
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=info,
                data=json.dumps(payload),
                vapid_private_key=self.private_key,
                vapid_claims=dict(self.claims),
                ttl=3600,
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            return SendResult(ok=False, error=str(exc)[:250], gone=status in (404, 410))
        except Exception as exc:  # network errors etc.
            return SendResult(ok=False, error=str(exc)[:250])
        return SendResult(ok=True)


class ResendEmailSender:
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.resend_api_key
        self.sender = settings.email_from

    async def send(self, *, to: str, subject: str, text: str, html: str) -> SendResult:
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                res = await http.post(
                    RESEND_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "from": self.sender,
                        "to": [to],
                        "subject": subject,
                        "text": text,
                        "html": html,
                    },
                )
        except httpx.HTTPError as exc:
            return SendResult(ok=False, error=str(exc)[:250])
        if res.status_code >= 300:
            return SendResult(ok=False, error=f"resend {res.status_code}: {res.text[:200]}")
        return SendResult(ok=True)


@dataclass
class RecordingSender:
    """Test double: records every call and answers with a scripted result."""

    result: SendResult = SendResult(ok=True)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def send(self, *args: Any, **kwargs: Any) -> SendResult:
        record: dict[str, Any] = dict(kwargs)
        if args:
            record["subscription"] = args[0]
            record["payload"] = args[1] if len(args) > 1 else None
        self.calls.append(record)
        return self.result


def build_senders(settings: Settings) -> Senders:
    push: PushSender = (
        WebPushSender(settings) if settings.vapid_private_key else LoggingSender("push")
    )
    email: EmailSender = (
        ResendEmailSender(settings) if settings.resend_api_key else LoggingSender("email")
    )
    return Senders(push=push, email=email)
