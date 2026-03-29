import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.vault import vault
from app.models import InstagramAccount, Organization, ScheduledPost, User
from app.models.scheduled_post import PostStatus


@pytest.mark.asyncio
async def test_webhook_verify_success(client: AsyncClient):
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": settings.instagram_webhook_verify_token,
        "hub.challenge": "challenge-123",
    }
    response = await client.get("/api/v1/instagram/webhook", params=params)

    assert response.status_code == 200
    assert response.text == "challenge-123"


@pytest.mark.asyncio
async def test_webhook_verify_invalid_token(client: AsyncClient):
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong-token",
        "hub.challenge": "challenge-123",
    }
    response = await client.get("/api/v1/instagram/webhook", params=params)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "instagram_app_secret", "test-secret")

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "media_id": "media_1",
                            "status": "published",
                        }
                    }
                ]
            }
        ]
    }

    response = await client.post(
        "/api/v1/instagram/webhook",
        json=payload,
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_stale_timestamp(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "instagram_app_secret", "test-secret")
    monkeypatch.setattr(settings, "webhook_max_age_seconds", 60)

    payload = {"entry": []}
    import json

    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

    old_ts = int((datetime.now(UTC) - timedelta(minutes=10)).timestamp())
    response = await client.post(
        "/api/v1/instagram/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
            "X-Webhook-Timestamp": str(old_ts),
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_updates_post_status_to_published(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "instagram_app_secret", "test-secret")

    async with db_session as session:
        org = Organization(id="org_webhook", name="Webhook Org", created_at=datetime.now(UTC))
        user = User(
            id="user_webhook",
            email="webhook@example.com",
            full_name="Webhook User",
            hashed_password="hashed",
            created_at=datetime.now(UTC),
        )
        account = InstagramAccount(
            id="ig_webhook",
            organization_id=org.id,
            ig_user_id="ig_webhook_user",
            username="ig_webhook_user",
            access_token_encrypted=vault.encrypt("token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post = ScheduledPost(
            id="post_webhook",
            instagram_account_id=account.id,
            caption="webhook post",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=1),
            status=PostStatus.PUBLISHING,
            instagram_post_id="media_123",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(org)
        session.add(user)
        session.add(account)
        session.add(post)
        await session.commit()

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "media_id": "media_123",
                            "status": "published",
                        }
                    }
                ]
            }
        ]
    }

    import json

    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

    response = await client.post(
        "/api/v1/instagram/webhook",
        content=body,
        headers={
            "content-type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )

    assert response.status_code == 200
    assert response.json()["updated"] == 1
    assert response.json()["duplicate"] is False

    async with db_session as session:
        updated_post = await session.get(ScheduledPost, "post_webhook")
        assert updated_post is not None
        assert updated_post.status == PostStatus.PUBLISHED
        assert updated_post.error_message is None


@pytest.mark.asyncio
async def test_webhook_duplicate_delivery_is_ignored(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "instagram_app_secret", "test-secret")

    async with db_session as session:
        org = Organization(id="org_webhook_dup", name="Webhook Dup Org", created_at=datetime.now(UTC))
        user = User(
            id="user_webhook_dup",
            email="webhook.dup@example.com",
            full_name="Webhook Dup User",
            hashed_password="hashed",
            created_at=datetime.now(UTC),
        )
        account = InstagramAccount(
            id="ig_webhook_dup",
            organization_id=org.id,
            ig_user_id="ig_webhook_dup_user",
            username="ig_webhook_dup_user",
            access_token_encrypted=vault.encrypt("token"),
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        post = ScheduledPost(
            id="post_webhook_dup",
            instagram_account_id=account.id,
            caption="webhook dup post",
            media_urls="https://example.com/image.jpg",
            publish_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=1),
            status=PostStatus.PUBLISHING,
            instagram_post_id="media_dup_123",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(org)
        session.add(user)
        session.add(account)
        session.add(post)
        await session.commit()

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "media_id": "media_dup_123",
                            "status": "published",
                        }
                    }
                ]
            }
        ]
    }

    import json

    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    headers = {
        "content-type": "application/json",
        "X-Hub-Signature-256": f"sha256={signature}",
    }

    first = await client.post("/api/v1/instagram/webhook", content=body, headers=headers)
    second = await client.post("/api/v1/instagram/webhook", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["updated"] == 1
    assert first.json()["duplicate"] is False

    assert second.status_code == 200
    assert second.json()["updated"] == 0
    assert second.json()["duplicate"] is True
