from urllib.parse import urlencode
import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_org_roles
from app.core.config import settings
from app.core.vault import vault
from app.db.session import get_db
from app.models.instagram_account import InstagramAccount
from app.models.membership import OrganizationMember
from app.models.scheduled_post import PostStatus, ScheduledPost
from app.models.user import User
from app.models.webhook_event import WebhookEvent
from app.schemas.instagram import InstagramAccountOut, InstagramOAuthRedirectRequest
from app.services.instagram_client import InstagramGraphClient

router = APIRouter(prefix="/instagram", tags=["instagram"])
logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature_header: str | None) -> bool:
    if not settings.instagram_app_secret:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        settings.instagram_app_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


def _map_event_status(raw_status: str) -> PostStatus | None:
    status_value = raw_status.strip().lower()
    if status_value in {"published", "success", "succeeded", "finished", "complete", "completed"}:
        return PostStatus.PUBLISHED
    if status_value in {"failed", "error"}:
        return PostStatus.FAILED
    return None


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Meta webhook verification challenge endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == settings.instagram_webhook_verify_token and hub_challenge:
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed")


@router.post("/webhook")
async def process_webhook_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle incoming Instagram webhook events and reconcile post status."""
    body = await request.body()
    timestamp_header = request.headers.get("X-Webhook-Timestamp")
    signature = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(body, signature):
        logger.warning("Rejected webhook due to invalid signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    if timestamp_header:
        try:
            event_ts = int(timestamp_header)
            now_ts = int(datetime.now(tz=timezone.utc).timestamp())
            if abs(now_ts - event_ts) > settings.webhook_max_age_seconds:
                logger.warning("Rejected webhook due to stale timestamp window")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook timestamp expired")
        except ValueError as exc:
            logger.warning("Rejected webhook due to malformed timestamp header")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook timestamp header") from exc

    event_hash = hashlib.sha256(body).hexdigest()
    existing_event = await db.execute(
        select(WebhookEvent).where(WebhookEvent.event_hash == event_hash)
    )
    if existing_event.scalar_one_or_none():
        logger.info("Duplicate webhook ignored")
        return {"received": True, "updated": 0, "duplicate": True}

    db.add(WebhookEvent(source="instagram", event_hash=event_hash))

    payload = await request.json()
    updated = 0

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            media_id = value.get("media_id") or value.get("id")
            raw_status = value.get("status") or value.get("event")

            if not media_id or not raw_status:
                continue

            mapped_status = _map_event_status(str(raw_status))
            if not mapped_status:
                continue

            result = await db.execute(
                select(ScheduledPost).where(ScheduledPost.instagram_post_id == str(media_id))
            )
            post = result.scalar_one_or_none()
            if not post:
                continue

            post.status = mapped_status
            if mapped_status == PostStatus.FAILED:
                post.error_message = value.get("error") or value.get("message") or "Webhook reported publish failure"
            else:
                post.error_message = None
            updated += 1

    await db.commit()

    return {"received": True, "updated": updated, "duplicate": False}


@router.post("/oauth/redirect-url")
async def get_oauth_redirect_url(
    payload: InstagramOAuthRedirectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get Instagram OAuth authorization URL."""
    # Verify user has owner role in the organization
    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == payload.organization_id,
        OrganizationMember.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if membership is None or membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access denied or insufficient role")
    
    params = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": settings.instagram_redirect_uri,
        "scope": "instagram_basic,instagram_graph_user_media",
        "response_type": "code",
        "state": membership.organization_id,
    }
    auth_url = f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.post("/oauth/callback")
async def handle_oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> InstagramAccountOut:
    """Handle Instagram OAuth callback and save account with encrypted token."""
    import httpx

    organization_id = state

    token_url = "https://graph.instagram.com/v23.0/access_token"
    token_payload = {
        "client_id": settings.instagram_app_id,
        "client_secret": settings.instagram_app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": settings.instagram_redirect_uri,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=token_payload)
        token_response.raise_for_status()
        token_data = token_response.json()

    access_token = token_data["access_token"]
    user_id = token_data.get("user_id")

    if not access_token or not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to obtain access token")

    ig_client = InstagramGraphClient(access_token)
    user_info = await ig_client.get_user_info(str(user_id))

    encrypted_token = vault.encrypt(access_token)

    existing = await db.execute(
        select(InstagramAccount).where(InstagramAccount.ig_user_id == str(user_id))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Instagram account already connected")

    account = InstagramAccount(
        organization_id=organization_id,
        ig_user_id=str(user_id),
        username=user_info.get("username", ""),
        access_token_encrypted=encrypted_token,
    )
    db.add(account)
    await db.commit()

    return InstagramAccountOut.model_validate(account)


@router.get("/accounts", response_model=list[InstagramAccountOut])
async def list_accounts(
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> list[InstagramAccountOut]:
    """List Instagram accounts for organization."""
    stmt = select(InstagramAccount).where(InstagramAccount.organization_id == organization_id)
    result = await db.execute(stmt)
    accounts = result.scalars().all()
    return [InstagramAccountOut.model_validate(acc) for acc in accounts]


@router.get("/accounts/{account_id}", response_model=InstagramAccountOut)
async def get_account(
    account_id: str,
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> InstagramAccountOut:
    """Get Instagram account details."""
    account = await db.get(
        InstagramAccount,
        account_id,
    )
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    return InstagramAccountOut.model_validate(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    account_id: str,
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner"})),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect Instagram account from organization."""
    account = await db.get(InstagramAccount, account_id)
    if not account or account.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    await db.delete(account)
    await db.commit()
