import os
import asyncio
import logging
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BASE_URL = "https://graph.facebook.com/v19.0"


def get_access_token(db=None) -> Optional[str]:
    """Get access token from DB config, falling back to env var."""
    if db is not None:
        try:
            from models import Config
            config = db.query(Config).first()
            if config and config.instagram_access_token:
                return config.instagram_access_token
        except Exception as e:
            logger.warning(f"Could not fetch token from DB: {e}")
    return os.getenv("INSTAGRAM_ACCESS_TOKEN")


class InstagramClient:
    def __init__(self, access_token: str):
        self.access_token = access_token

    async def _request_with_retry(
        self, method: str, url: str, max_retries: int = 3, **kwargs
    ) -> httpx.Response:
        """Make HTTP request with exponential backoff on 429."""
        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await getattr(client, method)(url, **kwargs)
                logger.info(f"[Instagram API] {method.upper()} {url} -> {response.status_code}")
                if response.status_code != 429:
                    return response
                wait = 2 ** attempt
                logger.warning(f"Rate limited. Retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
        return response

    async def reply_to_comment(self, comment_id: str, message: str) -> dict:
        url = f"{BASE_URL}/{comment_id}/replies"
        params = {"access_token": self.access_token}
        data = {"message": message}
        response = await self._request_with_retry("post", url, params=params, data=data)
        result = response.json()
        logger.info(f"Reply to comment {comment_id}: {result}")
        return result

    async def send_dm(self, instagram_user_id: str, message: str) -> dict:
        url = f"{BASE_URL}/me/messages"
        params = {"access_token": self.access_token}
        json_data = {
            "recipient": {"id": instagram_user_id},
            "message": {"text": message},
        }
        response = await self._request_with_retry("post", url, params=params, json=json_data)
        result = response.json()
        logger.info(f"DM to user {instagram_user_id}: {result}")
        return result

    async def get_post_details(self, post_id: str) -> dict:
        url = f"{BASE_URL}/{post_id}"
        params = {
            "fields": "id,caption,media_url,thumbnail_url,permalink",
            "access_token": self.access_token,
        }
        response = await self._request_with_retry("get", url, params=params)
        result = response.json()
        logger.info(f"Post details for {post_id}: {result}")
        return result


def get_instagram_client(db=None) -> Optional[InstagramClient]:
    token = get_access_token(db)
    if not token:
        return None
    return InstagramClient(access_token=token)
