from datetime import datetime
from pydantic import BaseModel, Field


class InstagramAccountOut(BaseModel):
    id: str
    ig_user_id: str
    username: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduledPostStatus(str):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledPostCreate(BaseModel):
    caption: str = Field(max_length=2200)
    media_urls: str = Field(min_length=1, description="Comma-separated URLs")
    publish_at: datetime


class ScheduledPostOut(BaseModel):
    id: str
    caption: str
    media_urls: str
    publish_at: datetime
    status: str
    instagram_post_id: str | None
    error_message: str | None
    attempt_count: int
    last_attempt_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InstagramOAuthRedirectRequest(BaseModel):
    organization_id: str


class InstagramOAuthCallbackRequest(BaseModel):
    code: str
    state: str
