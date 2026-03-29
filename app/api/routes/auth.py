from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.db.session import get_db
from app.models.membership import OrganizationMember
from app.models.organization import Organization
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPairResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_token_pair(db: AsyncSession, user_id: str) -> TokenPairResponse:
    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)
    refresh_hash = hash_token(refresh_token)
    expires_at = (datetime.now(tz=timezone.utc) + timedelta(days=settings.refresh_token_expire_days)).replace(tzinfo=None)
    db.add(RefreshToken(user_id=user_id, token_hash=refresh_hash, expires_at=expires_at))
    await db.flush()
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=TokenPairResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenPairResponse:
    exists_stmt = select(User).where(User.email == payload.email)
    exists_result = await db.execute(exists_stmt)
    existing_user = exists_result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
    )
    org = Organization(name=payload.organization_name)
    db.add_all([user, org])
    await db.flush()

    member = OrganizationMember(user_id=user.id, organization_id=org.id, role="owner")
    db.add(member)
    token_pair = await _issue_token_pair(db=db, user_id=user.id)
    await db.commit()
    return token_pair


@router.post("/login", response_model=TokenPairResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPairResponse:
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token_pair = await _issue_token_pair(db=db, user_id=user.id)
    await db.commit()
    return token_pair


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_tokens(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPairResponse:
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh" or "sub" not in decoded:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    refresh_hash = hash_token(payload.refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == refresh_hash)
    result = await db.execute(stmt)
    refresh_record = result.scalar_one_or_none()
    if not refresh_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found")

    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    if refresh_record.revoked_at is not None or refresh_record.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")

    refresh_record.revoked_at = now
    token_pair = await _issue_token_pair(db=db, user_id=decoded["sub"])
    await db.commit()
    return token_pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> Response:
    refresh_hash = hash_token(payload.refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == refresh_hash)
    result = await db.execute(stmt)
    refresh_record = result.scalar_one_or_none()
    if refresh_record and refresh_record.revoked_at is None:
        refresh_record.revoked_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
