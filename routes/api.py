from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import Config, Campaign
from instagram import get_instagram_client

router = APIRouter(prefix="/api")


class ConfigIn(BaseModel):
    instagram_access_token: Optional[str] = None
    page_id: Optional[str] = None
    instagram_business_account_id: Optional[str] = None


class CampaignIn(BaseModel):
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool = True


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        return {"instagram_access_token": None, "page_id": None, "instagram_business_account_id": None}
    token = config.instagram_access_token
    masked = ("*" * (len(token) - 8) + token[-8:]) if token and len(token) > 8 else token
    return {
        "instagram_access_token": masked,
        "page_id": config.page_id,
        "instagram_business_account_id": config.instagram_business_account_id,
        "updated_at": config.updated_at,
    }


@router.post("/config")
def save_config(payload: ConfigIn, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        config = Config()
        db.add(config)
    if payload.instagram_access_token is not None:
        if not all(c == "*" for c in payload.instagram_access_token.replace(payload.instagram_access_token[-8:], "")):
            config.instagram_access_token = payload.instagram_access_token
    if payload.page_id is not None:
        config.page_id = payload.page_id
    if payload.instagram_business_account_id is not None:
        config.instagram_business_account_id = payload.instagram_business_account_id
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    return {"status": "saved"}


def campaign_to_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "post_id": c.post_id,
        "keywords": c.keywords,
        "comment_reply": c.comment_reply,
        "dm_message": c.dm_message,
        "is_active": c.is_active,
        "created_at": c.created_at,
    }


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [campaign_to_dict(c) for c in campaigns]


@router.post("/campaigns", status_code=201)
def create_campaign(payload: CampaignIn, db: Session = Depends(get_db)):
    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign_to_dict(campaign)


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, payload: CampaignIn, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for field, value in payload.model_dump().items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}


@router.patch("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.is_active = not campaign.is_active
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.get("/campaigns/{campaign_id}/post-preview")
async def get_post_preview(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    client = get_instagram_client(db)
    if not client:
        raise HTTPException(status_code=400, detail="Instagram access token not configured")
    result = await client.get_post_details(campaign.post_id)
    return result


@router.get("/post-preview/{post_id}")
async def preview_post(post_id: str, db: Session = Depends(get_db)):
    client = get_instagram_client(db)
    if not client:
        raise HTTPException(status_code=400, detail="Instagram access token not configured")
    result = await client.get_post_details(post_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"].get("message", "API error"))
    return result
