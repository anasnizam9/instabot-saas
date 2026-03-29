from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_org_roles
from app.core.vault import vault
from app.db.session import get_db
from app.models.instagram_account import InstagramAccount
from app.models.membership import OrganizationMember
from app.models.scheduled_post import ScheduledPost, PostStatus
from app.schemas.instagram import ScheduledPostCreate, ScheduledPostOut
from app.services.instagram_client import InstagramGraphClient

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/schedule", response_model=ScheduledPostOut, status_code=status.HTTP_201_CREATED)
async def schedule_post(
    account_id: str,
    organization_id: str,
    payload: ScheduledPostCreate,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> ScheduledPostOut:
    """Schedule a post for Instagram account."""
    account = await db.get(InstagramAccount, account_id)
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is inactive")

    post = ScheduledPost(
        instagram_account_id=account_id,
        caption=payload.caption,
        media_urls=payload.media_urls,
        publish_at=payload.publish_at.replace(tzinfo=None),
        status=PostStatus.SCHEDULED,
    )
    db.add(post)
    await db.commit()

    return ScheduledPostOut.model_validate(post)


@router.get("/scheduled", response_model=list[ScheduledPostOut])
async def list_scheduled_posts(
    account_id: str,
    organization_id: str,
    status_filter: str | None = None,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledPostOut]:
    """List scheduled posts for account."""
    account = await db.get(InstagramAccount, account_id)
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    stmt = select(ScheduledPost).where(ScheduledPost.instagram_account_id == account_id)
    if status_filter:
        stmt = stmt.where(ScheduledPost.status == status_filter)

    result = await db.execute(stmt)
    posts = result.scalars().all()
    return [ScheduledPostOut.model_validate(p) for p in posts]


@router.get("/{post_id}", response_model=ScheduledPostOut)
async def get_post(
    post_id: str,
    account_id: str,
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> ScheduledPostOut:
    """Get post details."""
    post = await db.get(ScheduledPost, post_id)
    if not post or post.instagram_account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    account = await db.get(InstagramAccount, post.instagram_account_id)
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return ScheduledPostOut.model_validate(post)


@router.patch("/{post_id}", response_model=ScheduledPostOut)
async def update_post(
    post_id: str,
    account_id: str,
    organization_id: str,
    payload: ScheduledPostCreate,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> ScheduledPostOut:
    """Update scheduled post (only if not yet published)."""
    post = await db.get(ScheduledPost, post_id)
    if not post or post.instagram_account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    account = await db.get(InstagramAccount, post.instagram_account_id)
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if post.status not in [PostStatus.DRAFT, PostStatus.SCHEDULED]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update published/failed post")

    post.caption = payload.caption
    post.media_urls = payload.media_urls
    post.publish_at = payload.publish_at.replace(tzinfo=None)
    await db.commit()

    return ScheduledPostOut.model_validate(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: str,
    account_id: str,
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete scheduled post (only if not yet published)."""
    post = await db.get(ScheduledPost, post_id)
    if not post or post.instagram_account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    account = await db.get(InstagramAccount, post.instagram_account_id)
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if post.status not in [PostStatus.DRAFT, PostStatus.SCHEDULED]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete published post")

    await db.delete(post)
    await db.commit()


@router.post("/{post_id}/requeue", response_model=ScheduledPostOut)
async def requeue_failed_post(
    post_id: str,
    account_id: str,
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> ScheduledPostOut:
    """Manually requeue a failed/cancelled post for another publish attempt."""
    post = await db.get(ScheduledPost, post_id)
    if not post or post.instagram_account_id != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    account = await db.get(InstagramAccount, post.instagram_account_id)
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if post.status not in [PostStatus.FAILED, PostStatus.CANCELLED]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed/cancelled posts can be requeued")

    post.status = PostStatus.SCHEDULED
    post.error_message = None
    post.publish_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    await db.commit()

    return ScheduledPostOut.model_validate(post)
