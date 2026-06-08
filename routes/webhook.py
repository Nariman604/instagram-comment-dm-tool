import os
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Campaign, ProcessedComment
from instagram import get_instagram_client

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_signature(body: bytes, signature_header: str) -> bool:
    app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not app_secret:
        logger.warning("FACEBOOK_APP_SECRET not set; skipping signature verification")
        return True
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.get("/webhook/instagram")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
    if mode == "subscribe" and token == verify_token:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/instagram")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if sig_header and not verify_signature(body, sig_header):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    logger.info(f"Received webhook: {data}")
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            await process_comment_event(value, db)
    return {"status": "ok"}


async def process_comment_event(value: dict, db: Session):
    comment_id = value.get("id")
    post_id = value.get("media", {}).get("id") or value.get("post_id", "")
    comment_text = value.get("text", "")
    commenter_id = value.get("from", {}).get("id")
    if not comment_id:
        return
    existing = db.query(ProcessedComment).filter_by(comment_id=comment_id).first()
    if existing:
        logger.info(f"Comment {comment_id} already processed, skipping")
        return
    campaigns = db.query(Campaign).filter_by(post_id=post_id, is_active=True).all()
    if not campaigns:
        logger.info(f"No active campaigns for post {post_id}")
        return
    client = get_instagram_client(db)
    if not client:
        logger.error("No Instagram client available (access token not configured)")
        return
    for campaign in campaigns:
        keywords = [kw.strip().lower() for kw in campaign.keywords.split(",") if kw.strip()]
        if keywords and not any(kw in comment_text.lower() for kw in keywords):
            continue
        logger.info(f"Matched campaign {campaign.id} for comment {comment_id}")
        if campaign.comment_reply:
            try:
                await client.reply_to_comment(comment_id, campaign.comment_reply)
            except Exception as e:
                logger.error(f"Failed to reply to comment {comment_id}: {e}")
        if campaign.dm_message and commenter_id:
            try:
                await client.send_dm(commenter_id, campaign.dm_message)
            except Exception as e:
                logger.error(f"Failed to send DM to {commenter_id}: {e}")
        processed = ProcessedComment(comment_id=comment_id, campaign_id=campaign.id)
        db.add(processed)
        db.commit()
        break
