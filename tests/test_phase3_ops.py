from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.vault import vault
from app.models import InstagramAccount, Organization, ScheduledPost, User, WebhookEvent
from app.models.scheduled_post import PostStatus
from app.services import post_publisher


@pytest.mark.asyncio
async def test_manual_requeue_failed_post(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
    db_session: AsyncSession,
):
    user, org = user_with_org

    async with db_session as session:
        ig_account = InstagramAccount(
            id="ig_requeue_1",
            organization_id=org.id,
            ig_user_id="ig_requeue_user_1",
            username="requeue_user_1",
            access_token_encrypted=vault.encrypt("token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post = ScheduledPost(
            id="post_requeue_1",
            instagram_account_id=ig_account.id,
            caption="failed post",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
            status=PostStatus.FAILED,
            error_message="publish failed",
            attempt_count=3,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(ig_account)
        session.add(post)
        await session.commit()

    response = await client.post(
        f"/api/v1/posts/post_requeue_1/requeue?account_id=ig_requeue_1&organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == PostStatus.SCHEDULED.value
    assert data["error_message"] is None


@pytest.mark.asyncio
async def test_recover_stuck_posts(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with db_session as session:
        org = Organization(id="org_stuck_1", name="Stuck Org", created_at=datetime.now(UTC))
        user = User(
            id="user_stuck_1",
            email="stuck1@example.com",
            full_name="Stuck User",
            hashed_password="hashed",
            created_at=datetime.now(UTC),
        )
        account = InstagramAccount(
            id="ig_stuck_1",
            organization_id=org.id,
            ig_user_id="ig_stuck_user_1",
            username="stuck_user_1",
            access_token_encrypted=vault.encrypt("token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post = ScheduledPost(
            id="post_stuck_1",
            instagram_account_id=account.id,
            caption="stuck post",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
            status=PostStatus.PUBLISHING,
            attempt_count=1,
            last_attempt_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=45),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(org)
        session.add(user)
        session.add(account)
        session.add(post)
        await session.commit()

    monkeypatch.setattr(post_publisher.settings, "publisher_stuck_timeout_minutes", 15)
    monkeypatch.setattr(post_publisher.settings, "publisher_max_attempts", 3)

    async with db_session as session:
        recovered = await post_publisher.recover_stuck_posts(session)
    assert recovered >= 1

    async with db_session as session:
        updated = await session.get(ScheduledPost, "post_stuck_1")
        assert updated is not None
        assert updated.status == PostStatus.SCHEDULED


@pytest.mark.asyncio
async def test_cleanup_old_webhook_events(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with db_session as session:
        old_event = WebhookEvent(
            id="evt_old_1",
            source="instagram",
            event_hash="a" * 64,
            created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30),
        )
        new_event = WebhookEvent(
            id="evt_new_1",
            source="instagram",
            event_hash="b" * 64,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(old_event)
        session.add(new_event)
        await session.commit()

    monkeypatch.setattr(post_publisher.settings, "webhook_event_retention_days", 14)
    async with db_session as session:
        deleted = await post_publisher.cleanup_old_webhook_events(session)
    assert deleted >= 1

    async with db_session as session:
        old_loaded = await session.get(WebhookEvent, "evt_old_1")
        new_loaded = await session.get(WebhookEvent, "evt_new_1")
        assert old_loaded is None
        assert new_loaded is not None
