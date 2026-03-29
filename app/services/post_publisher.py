from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.vault import vault
from app.db.session import AsyncSessionLocal
from app.models.instagram_account import InstagramAccount
from app.models.scheduled_post import PostStatus, ScheduledPost
from app.models.webhook_event import WebhookEvent
from app.services.instagram_client import InstagramGraphClient


def _now_utc_naive() -> datetime:
    # DB models currently store timestamps as naive UTC values.
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _parse_media_urls(media_urls: str) -> list[str]:
    return [url.strip() for url in media_urls.split(",") if url.strip()]


def _next_retry_time(attempt_count: int) -> datetime:
    # Exponential backoff: base * 2^(attempt-1)
    delay_seconds = settings.publisher_retry_base_delay_seconds * (2 ** max(attempt_count - 1, 0))
    jitter = int(delay_seconds * settings.publisher_retry_jitter_ratio)
    if jitter > 0:
        delay_seconds += random.randint(-jitter, jitter)
    delay_seconds = max(delay_seconds, settings.publisher_retry_base_delay_seconds)
    return _now_utc_naive() + timedelta(seconds=delay_seconds)


def _is_permanent_error(exc: Exception) -> bool:
    # Validation/data errors are permanent; upstream/network errors are often transient.
    return isinstance(exc, ValueError)


async def process_due_posts() -> int:
    """Process due scheduled posts and attempt Instagram publishing."""
    processed = 0
    now_utc = _now_utc_naive()

    async with AsyncSessionLocal() as db:
        stmt = (
            select(ScheduledPost)
            .where(ScheduledPost.status == PostStatus.SCHEDULED)
            .where(ScheduledPost.publish_at <= now_utc)
            .order_by(ScheduledPost.publish_at.asc())
            .limit(settings.scheduler_batch_size)
        )
        result = await db.execute(stmt)
        posts: Iterable[ScheduledPost] = result.scalars().all()

        for post in posts:
            await _publish_single_post(db, post)
            processed += 1

    return processed


async def recover_stuck_posts(db: AsyncSession | None = None) -> int:
    """Recover posts stuck in publishing state for too long."""
    recovered = 0
    threshold = _now_utc_naive() - timedelta(minutes=settings.publisher_stuck_timeout_minutes)

    if db is None:
        async with AsyncSessionLocal() as new_db:
            return await recover_stuck_posts(new_db)

    else:
        stmt = select(ScheduledPost).where(
            ScheduledPost.status == PostStatus.PUBLISHING,
            ScheduledPost.last_attempt_at.is_not(None),
            ScheduledPost.last_attempt_at <= threshold,
        )
        result = await db.execute(stmt)
        posts: Iterable[ScheduledPost] = result.scalars().all()

        for post in posts:
            if post.attempt_count >= settings.publisher_max_attempts:
                post.status = PostStatus.FAILED
                post.error_message = "Publishing timeout exceeded max retry attempts"
            else:
                post.status = PostStatus.SCHEDULED
                post.publish_at = _next_retry_time(max(post.attempt_count, 1))
                post.error_message = "Recovered from stuck publishing state"
            recovered += 1

        if recovered:
            await db.commit()

    return recovered


async def cleanup_old_webhook_events(db: AsyncSession | None = None) -> int:
    """Delete old webhook idempotency entries to keep table bounded."""
    deleted = 0
    cutoff = _now_utc_naive() - timedelta(days=settings.webhook_event_retention_days)

    if db is None:
        async with AsyncSessionLocal() as new_db:
            return await cleanup_old_webhook_events(new_db)

    else:
        stmt = select(WebhookEvent).where(WebhookEvent.created_at <= cutoff)
        result = await db.execute(stmt)
        old_events = result.scalars().all()

        for event in old_events:
            await db.delete(event)
            deleted += 1

        if deleted:
            await db.commit()

    return deleted


async def _publish_single_post(db, post: ScheduledPost) -> None:
    account = await db.get(InstagramAccount, post.instagram_account_id)
    if not account or not account.is_active:
        post.attempt_count += 1
        post.last_attempt_at = _now_utc_naive()
        post.status = PostStatus.FAILED
        post.error_message = "Instagram account is missing or inactive"
        await db.commit()
        return

    post.attempt_count += 1
    post.last_attempt_at = _now_utc_naive()
    post.status = PostStatus.PUBLISHING
    post.error_message = None
    await db.commit()

    try:
        token = vault.decrypt(account.access_token_encrypted)
        client = InstagramGraphClient(access_token=token)

        media_urls = _parse_media_urls(post.media_urls)
        if not media_urls:
            raise ValueError("No media URLs provided")

        if len(media_urls) == 1:
            container = await client.create_media_container(
                user_id=account.ig_user_id,
                media_type="IMAGE",
                media_url=media_urls[0],
                caption=post.caption,
            )
        else:
            child_ids: list[str] = []
            for media_url in media_urls:
                child = await client.create_media_container(
                    user_id=account.ig_user_id,
                    media_type="IMAGE",
                    media_url=media_url,
                    is_carousel_item=True,
                )
                child_id = child.get("id")
                if not child_id:
                    raise ValueError("Instagram did not return carousel child id")
                child_ids.append(child_id)

            container = await client.create_media_container(
                user_id=account.ig_user_id,
                media_type="CAROUSEL",
                caption=post.caption,
                children=child_ids,
            )

        creation_id = container.get("id")
        if not creation_id:
            raise ValueError("Instagram did not return media container id")

        publish_result = await client.publish_media(
            user_id=account.ig_user_id,
            media_id=creation_id,
        )

        post.instagram_post_id = publish_result.get("id")
        post.status = PostStatus.PUBLISHED
        post.error_message = None
    except Exception as exc:  # noqa: BLE001
        post.error_message = str(exc)[:2000]
        if _is_permanent_error(exc) or post.attempt_count >= settings.publisher_max_attempts:
            post.status = PostStatus.FAILED
        else:
            post.status = PostStatus.SCHEDULED
            post.publish_at = _next_retry_time(post.attempt_count)

    await db.commit()
