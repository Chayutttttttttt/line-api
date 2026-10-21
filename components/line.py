"""Persist signed LINE events and jobs atomically before acknowledging delivery."""
import base64
import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from config import CHANNEL_SECRET, LINE_CHANNEL_ID, LINE_PROVIDER_ID
from db.database import get_session
from db.models import Job, LineIdentity, UserProfile, WebhookEvent, utc_now

router = APIRouter(tags=["line"])


def verify_signature(body: bytes, signature: str):
    if not CHANNEL_SECRET or not LINE_CHANNEL_ID or not LINE_PROVIDER_ID:
        raise HTTPException(503, "LINE_WEBHOOK_NOT_CONFIGURED")
    expected = base64.b64encode(hmac.new(CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(400, "INVALID_SIGNATURE")


@router.post("/webhook")
@router.post("/webhooks/line")
async def webhook(request: Request, x_line_signature: str = Header(""), db: Session = Depends(get_session)):
    body = await request.body()
    verify_signature(body, x_line_signature)
    return await run_in_threadpool(persist_events, body, db)


def persist_events(body: bytes, db: Session):
    try:
        payload = json.loads(body)
        events = payload["events"]
        if not isinstance(events, list) or len(events) > 100:
            raise ValueError()
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("webhookEventId"), str) or len(event["webhookEventId"]) > 255:
                raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "INVALID_WEBHOOK_BODY") from None
    accepted = 0
    for event in events:
        statement = insert(WebhookEvent).values(channel_id=LINE_CHANNEL_ID,
            event_id=event["webhookEventId"], state="received", attempts=0, created_at=utc_now())
        event_id = db.execute(statement.on_conflict_do_nothing(constraint="uq_channel_event").returning(WebhookEvent.id)).scalar_one_or_none()
        if event_id is None:
            continue
        accepted += 1
        source = event.get("source", {})
        if source.get("type") != "user":
            continue  # No group content or cross-user conversation context in the pilot.
        identity = db.exec(select(LineIdentity).where(LineIdentity.provider_id == LINE_PROVIDER_ID,
            LineIdentity.line_sub == source.get("userId"))).first()
        if not identity:
            continue  # Users register with verified LIFF login and course membership first.
        if event.get("type") in {"unfollow", "follow"}:
            profile = db.exec(select(UserProfile).where(UserProfile.user_id == identity.user_id).with_for_update()).first()
            if profile:
                profile.preferences = {**profile.preferences, "oa_blocked": event["type"] == "unfollow"}
                db.add(profile)
        message = event.get("message", {})
        if event.get("type") == "message" and message.get("type") == "text":
            text = message.get("text", "")
            if isinstance(text, str) and 0 < len(text) <= 4000:
                profile = db.exec(select(UserProfile).where(UserProfile.user_id == identity.user_id)).first()
                selected = profile.preferences.get("active_course_id") if profile else None
                db.add(Job(webhook_event_id=event_id, user_id=identity.user_id,
                    payload={"text": text, "course_id": selected, "line_message_id": message.get("id"),
                        "timestamp": event.get("timestamp"), "request_id": str(event_id)}))
    db.commit()
    return {"accepted": accepted}
