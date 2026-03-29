from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_org_roles
from app.db.session import get_db
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.membership import OrganizationMember
from app.schemas.phase4 import AnalyticsSnapshotCreate, AnalyticsSnapshotOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/snapshots", response_model=AnalyticsSnapshotOut, status_code=status.HTTP_201_CREATED)
async def create_analytics_snapshot(
    organization_id: str,
    payload: AnalyticsSnapshotCreate,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSnapshotOut:
    snapshot = AnalyticsSnapshot(
        organization_id=organization_id,
        metric_name=payload.metric_name,
        metric_value=payload.metric_value,
        snapshot_at=payload.snapshot_at,
    )
    db.add(snapshot)
    await db.commit()
    return AnalyticsSnapshotOut.model_validate(snapshot)


@router.get("/snapshots", response_model=list[AnalyticsSnapshotOut])
async def list_analytics_snapshots(
    organization_id: str,
    metric_name: str | None = None,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> list[AnalyticsSnapshotOut]:
    stmt = select(AnalyticsSnapshot).where(AnalyticsSnapshot.organization_id == organization_id)
    if metric_name:
        stmt = stmt.where(AnalyticsSnapshot.metric_name == metric_name)

    result = await db.execute(stmt.order_by(AnalyticsSnapshot.snapshot_at.desc()))
    snapshots = result.scalars().all()
    return [AnalyticsSnapshotOut.model_validate(s) for s in snapshots]


@router.get("/snapshots/summary")
async def analytics_summary(
    organization_id: str,
    metric_prefix: str | None = None,
    last_hours: int = 24,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> dict:
    since = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(hours=last_hours)
    stmt = select(AnalyticsSnapshot).where(
        AnalyticsSnapshot.organization_id == organization_id,
        AnalyticsSnapshot.snapshot_at >= since,
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()

    summary: dict[str, dict] = {}
    for row in rows:
        if metric_prefix and not row.metric_name.startswith(metric_prefix):
            continue

        bucket = summary.setdefault(
            row.metric_name,
            {
                "count": 0,
                "sum": 0.0,
                "min": row.metric_value,
                "max": row.metric_value,
                "latest_value": row.metric_value,
                "latest_at": row.snapshot_at.isoformat(),
            },
        )
        bucket["count"] += 1
        bucket["sum"] += row.metric_value
        bucket["min"] = min(bucket["min"], row.metric_value)
        bucket["max"] = max(bucket["max"], row.metric_value)
        if row.snapshot_at.isoformat() >= bucket["latest_at"]:
            bucket["latest_value"] = row.metric_value
            bucket["latest_at"] = row.snapshot_at.isoformat()

    for metric_name, bucket in summary.items():
        count = bucket["count"]
        bucket["avg"] = bucket["sum"] / count if count else 0.0
        del bucket["sum"]

    return {
        "organization_id": organization_id,
        "last_hours": last_hours,
        "metrics": summary,
    }
