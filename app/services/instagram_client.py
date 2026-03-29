import httpx
from app.core.config import settings


class InstagramGraphClient:
    """Async HTTP client for Meta Instagram Graph API."""

    BASE_URL = "https://graph.instagram.com"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.api_version = settings.instagram_api_version

    async def get_user_info(self, user_id: str = "me") -> dict:
        """Get Instagram user info."""
        url = f"{self.BASE_URL}/{self.api_version}/{user_id}"
        params = {
            "fields": "ig_username,username,name,biography,website,profile_picture_url,followers_count,follows_count,media_count",
            "access_token": self.access_token,
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def get_media_list(self, user_id: str = "me", limit: int = 25) -> dict:
        """Get user's media list."""
        url = f"{self.BASE_URL}/{self.api_version}/{user_id}/media"
        params = {
            "fields": "id,caption,media_type,media_url,timestamp,like_count,comments_count",
            "access_token": self.access_token,
            "limit": limit,
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def create_media_container(
        self,
        user_id: str,
        media_type: str,
        media_url: str | None = None,
        caption: str = "",
        is_carousel_item: bool = False,
        children: list[str] | None = None,
    ) -> dict:
        """Create media container for publishing (carousel, image, video, reels)."""
        url = f"{self.BASE_URL}/{self.api_version}/{user_id}/media"
        data = {
            "media_type": media_type,
            "access_token": self.access_token,
        }
        if media_type == "IMAGE" or media_type == "VIDEO":
            if not media_url:
                raise ValueError("media_url is required for IMAGE/VIDEO container")
            data["image_url" if media_type == "IMAGE" else "video_url"] = media_url
        if is_carousel_item:
            data["is_carousel_item"] = "true"
        if children:
            data["children"] = ",".join(children)
        if caption:
            data["caption"] = caption

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return response.json()

    async def publish_media(self, user_id: str, media_id: str) -> dict:
        """Publish a created media container."""
        url = f"{self.BASE_URL}/{self.api_version}/{user_id}/media_publish"
        data = {
            "creation_id": media_id,
            "access_token": self.access_token,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return response.json()
