import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_org_roles
from app.db.session import get_db
from app.models.automation_rule import AutomationRule
from app.models.automation_rule_run import AutomationRuleRun
from app.models.membership import OrganizationMember
from app.services.automation_engine import RuleValidationError, run_rules_for_organization, simulate_rule, validate_rule_config
from app.schemas.phase4 import (
    AutomationRuleCreate,
    AutomationRuleOut,
    AutomationRuleRunListOut,
    AutomationRuleRunOut,
    AutomationRuleUpdate,
)

router = APIRouter(prefix="/automation-rules", tags=["automation-rules"])


@router.post("", response_model=AutomationRuleOut, status_code=status.HTTP_201_CREATED)
async def create_automation_rule(
    organization_id: str,
    payload: AutomationRuleCreate,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleOut:
    try:
        validate_rule_config(payload.rule_type, payload.rule_config)
    except RuleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    rule = AutomationRule(
        organization_id=organization_id,
        name=payload.name,
        rule_type=payload.rule_type,
        rule_config=json.dumps(payload.rule_config),
        is_enabled=payload.is_enabled,
        cooldown_seconds=payload.cooldown_seconds,
        max_runs_per_hour=payload.max_runs_per_hour,
    )
    db.add(rule)
    await db.commit()
    return AutomationRuleOut.model_validate(rule)


@router.get("", response_model=list[AutomationRuleOut])
async def list_automation_rules(
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> list[AutomationRuleOut]:
    result = await db.execute(select(AutomationRule).where(AutomationRule.organization_id == organization_id))
    rules = result.scalars().all()
    return [AutomationRuleOut.model_validate(rule) for rule in rules]


@router.patch("/{rule_id}", response_model=AutomationRuleOut)
async def update_automation_rule(
    rule_id: str,
    organization_id: str,
    payload: AutomationRuleUpdate,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleOut:
    rule = await db.get(AutomationRule, rule_id)
    if not rule or rule.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    if payload.name is not None:
        rule.name = payload.name
    if payload.is_enabled is not None:
        rule.is_enabled = payload.is_enabled
    if payload.cooldown_seconds is not None:
        rule.cooldown_seconds = payload.cooldown_seconds
    if payload.max_runs_per_hour is not None:
        rule.max_runs_per_hour = payload.max_runs_per_hour
    if payload.rule_config is not None:
        parsed = payload.rule_config
        try:
            validate_rule_config(rule.rule_type, parsed)
        except RuleValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        rule.rule_config = json.dumps(parsed)

    await db.commit()
    return AutomationRuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation_rule(
    rule_id: str,
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner"})),
    db: AsyncSession = Depends(get_db),
) -> None:
    rule = await db.get(AutomationRule, rule_id)
    if not rule or rule.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    await db.delete(rule)
    await db.commit()


@router.post("/{rule_id}/simulate")
async def simulate_automation_rule(
    rule_id: str,
    organization_id: str,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rule = await db.get(AutomationRule, rule_id)
    if not rule or rule.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    try:
        return simulate_rule(rule)
    except RuleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/run")
async def run_automation_rules(
    organization_id: str,
    dry_run: bool = False,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager"})),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await run_rules_for_organization(db, organization_id, dry_run=dry_run)
    except RuleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/runs", response_model=AutomationRuleRunListOut)
async def list_automation_rule_runs(
    organization_id: str,
    rule_id: str | None = None,
    status_filter: str | None = None,
    run_source: str | None = None,
    limit: int = 50,
    offset: int = 0,
    membership: OrganizationMember = Depends(require_org_roles({"owner", "manager", "viewer"})),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleRunListOut:
    stmt = select(AutomationRuleRun).where(AutomationRuleRun.organization_id == organization_id)
    count_stmt = select(func.count(AutomationRuleRun.id)).where(AutomationRuleRun.organization_id == organization_id)
    if rule_id:
        stmt = stmt.where(AutomationRuleRun.automation_rule_id == rule_id)
        count_stmt = count_stmt.where(AutomationRuleRun.automation_rule_id == rule_id)
    if status_filter:
        stmt = stmt.where(AutomationRuleRun.status == status_filter)
        count_stmt = count_stmt.where(AutomationRuleRun.status == status_filter)
    if run_source:
        stmt = stmt.where(AutomationRuleRun.run_source == run_source)
        count_stmt = count_stmt.where(AutomationRuleRun.run_source == run_source)

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar_one() or 0)

    result = await db.execute(stmt.order_by(AutomationRuleRun.executed_at.desc()).offset(offset).limit(limit))
    runs = result.scalars().all()
    return AutomationRuleRunListOut(
        items=[AutomationRuleRunOut.model_validate(run) for run in runs],
        total=total,
        limit=limit,
        offset=offset,
    )
