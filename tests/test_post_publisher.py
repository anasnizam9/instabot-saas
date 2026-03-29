from datetime import datetime, timedelta, UTC

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.vault import vault
from app.models import InstagramAccount, Organization, ScheduledPost, User
from app.models.scheduled_post import PostStatus
from app.services import post_publisher


@pytest.mark.asyncio
async def test_publish_single_post_retries_with_backoff(db_session: AsyncSession):
    async with db_session as session:
        org = Organization(id="org_retry_1", name="Retry Org", created_at=datetime.now(UTC))
        user = User(
            id="user_retry_1",
            email="retry1@example.com",
            full_name="Retry User",
            hashed_password="hashed",
            created_at=datetime.now(UTC),
        )
        account = InstagramAccount(
            id="ig_retry_1",
            organization_id=org.id,
            ig_user_id="ig_retry_user_1",
            username="retry_user_1",
            access_token_encrypted=vault.encrypt("token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post = ScheduledPost(
            id="post_retry_1",
            instagram_account_id=account.id,
            caption="retry test",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
            status=PostStatus.SCHEDULED,
            attempt_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(org)
        session.add(user)
        session.add(account)
        session.add(post)
        await session.commit()

        original_publish_at = post.publish_at

        class FailingClient:
            def __init__(self, access_token: str):
                self.access_token = access_token

            async def create_media_container(self, user_id: str, media_type: str, media_url: str, caption: str = "") -> dict:
                raise RuntimeError("temporary api failure")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(post_publisher, "InstagramGraphClient", FailingClient)
        monkeypatch.setattr(post_publisher.vault, "decrypt", lambda _: "token")
        monkeypatch.setattr(post_publisher.settings, "publisher_max_attempts", 3)
        monkeypatch.setattr(post_publisher.settings, "publisher_retry_base_delay_seconds", 60)

        try:
            await post_publisher._publish_single_post(session, post)
            await session.refresh(post)
        finally:
            monkeypatch.undo()

    assert post.attempt_count == 1
    assert post.status == PostStatus.SCHEDULED
    assert post.error_message is not None
    assert post.publish_at > original_publish_at


@pytest.mark.asyncio
async def test_publish_single_post_marks_failed_after_max_attempts(db_session: AsyncSession):
    async with db_session as session:
        org = Organization(id="org_retry_2", name="Retry Org 2", created_at=datetime.now(UTC))
        user = User(
            id="user_retry_2",
            email="retry2@example.com",
            full_name="Retry User 2",
            hashed_password="hashed",
            created_at=datetime.now(UTC),
        )
        account = InstagramAccount(
            id="ig_retry_2",
            organization_id=org.id,
            ig_user_id="ig_retry_user_2",
            username="retry_user_2",
            access_token_encrypted=vault.encrypt("token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post = ScheduledPost(
            id="post_retry_2",
            instagram_account_id=account.id,
            caption="retry fail test",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
            status=PostStatus.SCHEDULED,
            attempt_count=2,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(org)
        session.add(user)
        session.add(account)
        session.add(post)
        await session.commit()

        class FailingClient:
            def __init__(self, access_token: str):
                self.access_token = access_token

            async def create_media_container(self, user_id: str, media_type: str, media_url: str, caption: str = "") -> dict:
                raise RuntimeError("permanent api failure")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(post_publisher, "InstagramGraphClient", FailingClient)
        monkeypatch.setattr(post_publisher.vault, "decrypt", lambda _: "token")
        monkeypatch.setattr(post_publisher.settings, "publisher_max_attempts", 3)

        try:
            await post_publisher._publish_single_post(session, post)
            await session.refresh(post)
        finally:
            monkeypatch.undo()

    assert post.attempt_count == 3
    assert post.status == PostStatus.FAILED
    assert post.error_message is not None


@pytest.mark.asyncio
async def test_publish_single_post_supports_carousel_media(db_session: AsyncSession):
    async with db_session as session:
        org = Organization(id="org_retry_3", name="Retry Org 3", created_at=datetime.now(UTC))
        user = User(
            id="user_retry_3",
            email="retry3@example.com",
            full_name="Retry User 3",
            hashed_password="hashed",
            created_at=datetime.now(UTC),
        )
        account = InstagramAccount(
            id="ig_retry_3",
            organization_id=org.id,
            ig_user_id="ig_retry_user_3",
            username="retry_user_3",
            access_token_encrypted=vault.encrypt("token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post = ScheduledPost(
            id="post_retry_3",
            instagram_account_id=account.id,
            caption="carousel test",
            media_urls="https://example.com/image1.jpg,https://example.com/image2.jpg",
            publish_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
            status=PostStatus.SCHEDULED,
            attempt_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(org)
        session.add(user)
        session.add(account)
        session.add(post)
        await session.commit()

        calls: list[tuple[str, dict]] = []

        class CarouselClient:
            def __init__(self, access_token: str):
                self.access_token = access_token

            async def create_media_container(self, user_id: str, media_type: str, **kwargs) -> dict:
                calls.append((media_type, kwargs))
                if media_type == "CAROUSEL":
                    return {"id": "carousel_1"}
                return {"id": f"child_{len(calls)}"}

            async def publish_media(self, user_id: str, media_id: str) -> dict:
                return {"id": "ig_post_1"}

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(post_publisher, "InstagramGraphClient", CarouselClient)
        monkeypatch.setattr(post_publisher.vault, "decrypt", lambda _: "token")

        try:
            await post_publisher._publish_single_post(session, post)
            await session.refresh(post)
        finally:
            monkeypatch.undo()

    assert post.status == PostStatus.PUBLISHED
    assert post.instagram_post_id == "ig_post_1"
    assert any(call[0] == "CAROUSEL" for call in calls)
