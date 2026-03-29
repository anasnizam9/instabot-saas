import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALLOWED_RULE_TYPES = {"auto_comment_reply", "keyword_alert", "engagement_digest"}


class AutomationRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    rule_type: str
    rule_config: dict
    is_enabled: bool = True
    cooldown_seconds: int = 0
    max_runs_per_hour: int = 0

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, value: str) -> str:
        if value not in ALLOWED_RULE_TYPES:
            raise ValueError("Unsupported rule type")
        return value


class AutomationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    rule_config: dict | None = None
    is_enabled: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)
    max_runs_per_hour: int | None = Field(default=None, ge=0)


class AutomationRuleOut(BaseModel):
    id: str
    organization_id: str
    name: str
    rule_type: str
    rule_config: dict
    is_enabled: bool
    cooldown_seconds: int
    max_runs_per_hour: int
    last_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("rule_config", mode="before")
    @classmethod
    def decode_rule_config(cls, value):
        if isinstance(value, str):
            return json.loads(value)
        return value


class AnalyticsSnapshotCreate(BaseModel):
    metric_name: str = Field(min_length=1, max_length=80)
    metric_value: float
    snapshot_at: datetime


class AnalyticsSnapshotOut(BaseModel):
    id: str
    organization_id: str
    metric_name: str
    metric_value: float
    snapshot_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AutomationRuleRunOut(BaseModel):
    id: str
    automation_rule_id: str
    organization_id: str
    status: str
    actions_count: int
    run_source: str
    output_summary: str | None
    error_message: str | None
    executed_at: datetime

    model_config = {"from_attributes": True}


class AutomationRuleRunListOut(BaseModel):
    items: list[AutomationRuleRunOut]
    total: int
    limit: int
    offset: int
