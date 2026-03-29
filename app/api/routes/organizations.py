from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, require_org_roles
from app.db.session import get_db
from app.models.membership import OrganizationMember
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import (
    MembershipOut,
    MembershipUpdate,
    OrganizationCreate,
    OrganizationDetail,
    OrganizationOut,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationOut:
    org = Organization(name=payload.name)
    db.add(org)
    await db.flush()

    member = OrganizationMember(user_id=current_user.id, organization_id=org.id, role="owner")
    db.add(member)
    await db.commit()
    return OrganizationOut.model_validate(org)


@router.get("", response_model=list[OrganizationOut])
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationOut]:
    stmt = (
        select(Organization)
        .join(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    orgs = result.scalars().all()
    return [OrganizationOut.model_validate(org) for org in orgs]


@router.get("/{organization_id}", response_model=OrganizationDetail)
async def get_organization(
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDetail:
    org = await db.get(Organization, organization_id, options=[joinedload(Organization.members)])
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationDetail.model_validate(org)


@router.get("/{organization_id}/my-role", response_model=MembershipOut)
async def get_my_role(
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
) -> MembershipOut:
    return MembershipOut.model_validate(membership)


@router.patch("/{organization_id}/members/{user_id}", response_model=MembershipOut)
async def update_member_role(
    organization_id: str,
    user_id: str,
    payload: MembershipUpdate,
    membership: OrganizationMember = Depends(require_org_roles({"owner"})),
    db: AsyncSession = Depends(get_db),
) -> MembershipOut:
    target_stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == user_id,
    )
    result = await db.execute(target_stmt)
    target_member = result.scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    target_member.role = payload.role
    await db.commit()
    return MembershipOut.model_validate(target_member)


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    organization_id: str,
    user_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner"})),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user_id == membership.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    target_stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == user_id,
    )
    result = await db.execute(target_stmt)
    target_member = result.scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    await db.delete(target_member)
    await db.commit()


@router.get("/{organization_id}/owner-area", response_model=MembershipOut)
async def owner_area(
    membership: OrganizationMember = Depends(require_org_roles({"owner"})),
) -> MembershipOut:
    return MembershipOut.model_validate(membership)
