from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.automation_rule import AutomationRule
from app.models.automation_rule_run import AutomationRuleRun

ALLOWED_RULE_TYPES = {"auto_comment_reply", "keyword_alert", "engagement_digest"}


class RuleValidationError(ValueError):
    pass


def parse_rule_config(rule: AutomationRule | str, rule_config: str | dict | None = None) -> dict:
    if isinstance(rule, AutomationRule):
        raw = rule.rule_config
    else:
        raw = rule_config

    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return {}


def validate_rule_config(rule_type: str, rule_config: dict) -> None:
    if rule_type not in ALLOWED_RULE_TYPES:
        raise RuleValidationError("Unsupported rule type")

    if rule_type == "auto_comment_reply":
        template = rule_config.get("reply_template")
        if not isinstance(template, str) or not template.strip():
            raise RuleValidationError("reply_template is required")
    elif rule_type == "keyword_alert":
        keywords = rule_config.get("keywords")
        if not isinstance(keywords, list) or not keywords:
            raise RuleValidationError("keywords list is required")


def simulate_rule(rule: AutomationRule) -> dict:
    cfg = parse_rule_config(rule)
    validate_rule_config(rule.rule_type, cfg)

    if rule.rule_type == "auto_comment_reply":
        return {
            "rule_id": rule.id,
            "rule_type": rule.rule_type,
            "status": "simulated",
            "actions": [
                {
                    "type": "reply_preview",
                    "message": cfg.get("reply_template", ""),
                }
            ],
        }

    if rule.rule_type == "keyword_alert":
        return {
            "rule_id": rule.id,
            "rule_type": rule.rule_type,
            "status": "simulated",
            "actions": [
                {
                    "type": "keyword_watchlist",
                    "keywords": cfg.get("keywords", []),
                }
            ],
        }

    return {
        "rule_id": rule.id,
        "rule_type": rule.rule_type,
        "status": "simulated",
        "actions": [{"type": "digest_preview", "window": "24h"}],
    }


async def execute_rule(db: AsyncSession, rule: AutomationRule, run_source: str = "manual") -> dict:
    run_status = "executed"
    actions_count = 0
    output_summary: str | None = None
    error_message: str | None = None

    try:
        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        if rule.cooldown_seconds > 0 and rule.last_run_at:
            next_allowed = rule.last_run_at + timedelta(seconds=rule.cooldown_seconds)
            if now < next_allowed:
                run_status = "skipped"
                output_summary = json.dumps({"reason": "cooldown_active", "next_allowed_at": next_allowed.isoformat()})
                raise RuntimeError("cooldown_active")

        if rule.max_runs_per_hour > 0:
            one_hour_ago = now - timedelta(hours=1)
            recent_count_result = await db.execute(
                select(func.count(AutomationRuleRun.id)).where(
                    AutomationRuleRun.automation_rule_id == rule.id,
                    AutomationRuleRun.status == "executed",
                    AutomationRuleRun.executed_at >= one_hour_ago,
                )
            )
            recent_count = int(recent_count_result.scalar_one() or 0)
            if recent_count >= rule.max_runs_per_hour:
                run_status = "skipped"
                output_summary = json.dumps({"reason": "hourly_limit_reached", "max_runs_per_hour": rule.max_runs_per_hour})
                raise RuntimeError("hourly_limit_reached")

        simulation = simulate_rule(rule)
        actions_count = len(simulation["actions"])
        output_summary = json.dumps(simulation["actions"])[:2000]

        snapshot = AnalyticsSnapshot(
            organization_id=rule.organization_id,
            metric_name=f"automation_rule_runs.{rule.rule_type}",
            metric_value=1.0,
            snapshot_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
        )
        db.add(snapshot)
        rule.last_run_at = now
    except Exception as exc:  # noqa: BLE001
        if run_status != "skipped":
            run_status = "failed"
            error_message = str(exc)[:2000]

    db.add(
        AutomationRuleRun(
            automation_rule_id=rule.id,
            organization_id=rule.organization_id,
            status=run_status,
            actions_count=actions_count,
            run_source=run_source,
            output_summary=output_summary,
            error_message=error_message if run_status != "skipped" else None,
        )
    )

    return {
        "rule_id": rule.id,
        "rule_type": rule.rule_type,
        "status": run_status,
        "actions_count": actions_count,
        "error_message": error_message,
    }


async def run_rules_for_organization(db: AsyncSession, organization_id: str, dry_run: bool = False) -> dict:
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.organization_id == organization_id,
            AutomationRule.is_enabled.is_(True),
        )
    )
    rules = result.scalars().all()

    outputs: list[dict] = []
    for rule in rules:
        if dry_run:
            outputs.append(simulate_rule(rule))
        else:
            outputs.append(await execute_rule(db, rule, run_source="manual"))

    if not dry_run and rules:
        await db.commit()

    return {
        "organization_id": organization_id,
        "dry_run": dry_run,
        "processed": len(outputs),
        "results": outputs,
    }


async def run_enabled_rules_global() -> int:
    processed = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AutomationRule).where(AutomationRule.is_enabled.is_(True)))
        rules = result.scalars().all()

        for rule in rules:
            await execute_rule(db, rule, run_source="scheduler")
            processed += 1

        if processed:
            await db.commit()

    return processed
