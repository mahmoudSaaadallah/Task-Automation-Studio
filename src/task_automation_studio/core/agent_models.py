from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentGoalType(StrEnum):
    REPETITIVE_TASK = "repetitive_task"
    WEB_TASK = "web_task"
    DATA_ENTRY = "data_entry"
    CUSTOM = "custom"


class AgentConstraint(BaseModel):
    max_step_attempts: int = Field(default=3, ge=1, le=10)
    max_total_steps: int = Field(default=20, ge=1, le=200)
    require_verification: bool = True


class AgentGoal(BaseModel):
    goal_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    goal_type: AgentGoalType = AgentGoalType.REPETITIVE_TASK
    description: str = ""
    success_criteria: list[str] = Field(default_factory=list)
    requested_intents: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    constraints: AgentConstraint = Field(default_factory=AgentConstraint)

    @field_validator("requested_intents")
    @classmethod
    def validate_intents(cls, value: list[str]) -> list[str]:
        return [intent.strip() for intent in value if intent and intent.strip()]


class AgentState(BaseModel):
    active_window_title: str | None = None
    current_url: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    observations: dict[str, Any] = Field(default_factory=dict)


class SkillDescriptor(BaseModel):
    skill_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    supported_intents: list[str] = Field(min_length=1)
    required_inputs: list[str] = Field(default_factory=list)
    default_success_signals: list[str] = Field(default_factory=list)
    reliability_score: float = Field(default=0.8, ge=0.0, le=1.0)


class AgentPlanStep(BaseModel):
    step_id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_bindings: dict[str, Any] = Field(default_factory=dict)
    expected_signals: list[str] = Field(default_factory=list)
    fallback_skill_ids: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=2, ge=1, le=10)


class AgentPlan(BaseModel):
    plan_id: str = Field(min_length=1)
    goal_id: str = Field(min_length=1)
    steps: list[AgentPlanStep] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
