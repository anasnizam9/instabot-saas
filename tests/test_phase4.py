from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Organization


@pytest.mark.asyncio
async def test_create_and_list_automation_rules(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
    db_session: AsyncSession,
):
    user, org = user_with_org

    create_response = await client.post(
        f"/api/v1/automation-rules?organization_id={org.id}",
        json={
            "name": "Auto Reply Rule",
            "rule_type": "auto_comment_reply",
            "rule_config": {"reply_template": "Thanks for your comment!"},
            "is_enabled": True,
            "cooldown_seconds": 0,
            "max_runs_per_hour": 0,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Auto Reply Rule"
    assert created["rule_config"]["reply_template"] == "Thanks for your comment!"

    list_response = await client.get(
        f"/api/v1/automation-rules?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1


@pytest.mark.asyncio
async def test_create_automation_rule_invalid_config_fails(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org

    response = await client.post(
        f"/api/v1/automation-rules?organization_id={org.id}",
        json={
            "name": "Keyword Rule",
            "rule_type": "keyword_alert",
            "rule_config": {"keywords": []},
            "is_enabled": True,
            "cooldown_seconds": 0,
            "max_runs_per_hour": 0,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_automation_rule(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org

    create_response = await client.post(
        f"/api/v1/automation-rules?organization_id={org.id}",
        json={
            "name": "Digest Rule",
            "rule_type": "engagement_digest",
            "rule_config": {},
            "is_enabled": True,
            "cooldown_seconds": 0,
            "max_runs_per_hour": 0,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert create_response.status_code == 201
    rule_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/automation-rules/{rule_id}?organization_id={org.id}",
        json={"is_enabled": False},
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["is_enabled"] is False

    delete_response = await client.delete(
        f"/api/v1/automation-rules/{rule_id}?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_create_and_filter_analytics_snapshots(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org

    now = datetime.now(UTC)
    first = await client.post(
        f"/api/v1/analytics/snapshots?organization_id={org.id}",
        json={
            "metric_name": "followers_count",
            "metric_value": 1200,
            "snapshot_at": (now - timedelta(hours=1)).isoformat(),
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/analytics/snapshots?organization_id={org.id}",
        json={
            "metric_name": "engagement_rate",
            "metric_value": 4.5,
            "snapshot_at": now.isoformat(),
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert second.status_code == 201

    list_all = await client.get(
        f"/api/v1/analytics/snapshots?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert list_all.status_code == 200
    assert len(list_all.json()) >= 2

    list_filtered = await client.get(
        f"/api/v1/analytics/snapshots?organization_id={org.id}&metric_name=followers_count",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert list_filtered.status_code == 200
    rows = list_filtered.json()
    assert len(rows) >= 1
    assert all(row["metric_name"] == "followers_count" for row in rows)


@pytest.mark.asyncio
async def test_simulate_automation_rule(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org

    create_response = await client.post(
        f"/api/v1/automation-rules?organization_id={org.id}",
        json={
            "name": "Simulation Rule",
            "rule_type": "auto_comment_reply",
            "rule_config": {"reply_template": "Thanks!"},
            "is_enabled": True,
            "cooldown_seconds": 0,
            "max_runs_per_hour": 0,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert create_response.status_code == 201
    rule_id = create_response.json()["id"]

    simulate_response = await client.post(
        f"/api/v1/automation-rules/{rule_id}/simulate?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert simulate_response.status_code == 200
    payload = simulate_response.json()
    assert payload["rule_id"] == rule_id
    assert payload["status"] == "simulated"
    assert len(payload["actions"]) >= 1


@pytest.mark.asyncio
async def test_run_automation_rules_creates_execution_metrics(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org

    create_response = await client.post(
        f"/api/v1/automation-rules?organization_id={org.id}",
        json={
            "name": "Keyword Execution Rule",
            "rule_type": "keyword_alert",
            "rule_config": {"keywords": ["sale", "offer"]},
            "is_enabled": True,
            "cooldown_seconds": 0,
            "max_runs_per_hour": 0,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert create_response.status_code == 201

    run_response = await client.post(
        f"/api/v1/automation-rules/run?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["dry_run"] is False
    assert run_payload["processed"] >= 1

    snapshots_response = await client.get(
        f"/api/v1/analytics/snapshots?organization_id={org.id}&metric_name=automation_rule_runs.keyword_alert",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert snapshots_response.status_code == 200
    assert len(snapshots_response.json()) >= 1

    runs_response = await client.get(
        f"/api/v1/automation-rules/runs?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    runs = runs_payload["items"]
    assert runs_payload["total"] >= 1
    assert len(runs) >= 1
    assert any(r["status"] in ["executed", "failed"] for r in runs)


@pytest.mark.asyncio
async def test_automation_runs_pagination_and_filters(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org

    create_response = await client.post(
        f"/api/v1/automation-rules?organization_id={org.id}",
        json={
            "name": "Filter Rule",
            "rule_type": "engagement_digest",
            "rule_config": {},
            "is_enabled": True,
            "cooldown_seconds": 0,
            "max_runs_per_hour": 0,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert create_response.status_code == 201
    rule_id = create_response.json()["id"]

    run_response = await client.post(
        f"/api/v1/automation-rules/run?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert run_response.status_code == 200

    filtered = await client.get(
        f"/api/v1/automation-rules/runs?organization_id={org.id}&rule_id={rule_id}&status_filter=executed&run_source=manual&limit=10&offset=0",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert payload["total"] >= 1
    assert all(row["run_source"] == "manual" for row in payload["items"])


@pytest.mark.asyncio
async def test_automation_rule_guardrails_cooldown_and_hourly_limit(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org

    create_response = await client.post(
        f"/api/v1/automation-rules?organization_id={org.id}",
        json={
            "name": "Guardrail Rule",
            "rule_type": "engagement_digest",
            "rule_config": {},
            "is_enabled": True,
            "cooldown_seconds": 3600,
            "max_runs_per_hour": 1,
        },
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert create_response.status_code == 201

    first_run = await client.post(
        f"/api/v1/automation-rules/run?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert first_run.status_code == 200

    second_run = await client.post(
        f"/api/v1/automation-rules/run?organization_id={org.id}",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert second_run.status_code == 200

    runs_response = await client.get(
        f"/api/v1/automation-rules/runs?organization_id={org.id}&status_filter=skipped",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert runs_response.status_code == 200
    assert runs_response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_analytics_summary_endpoint(
    client: AsyncClient,
    user_with_org: tuple[User, Organization],
):
    user, org = user_with_org
    now = datetime.now(UTC)

    for value in [1000, 1020, 1015]:
        response = await client.post(
            f"/api/v1/analytics/snapshots?organization_id={org.id}",
            json={
                "metric_name": "followers_count",
                "metric_value": value,
                "snapshot_at": now.isoformat(),
            },
            headers={"Authorization": f"Bearer {user.access_token}"},
        )
        assert response.status_code == 201

    summary = await client.get(
        f"/api/v1/analytics/snapshots/summary?organization_id={org.id}&last_hours=24",
        headers={"Authorization": f"Bearer {user.access_token}"},
    )
    assert summary.status_code == 200
    body = summary.json()
    assert "followers_count" in body["metrics"]
    metric = body["metrics"]["followers_count"]
    assert metric["count"] >= 3
    assert metric["max"] >= metric["min"]
