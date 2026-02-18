from __future__ import annotations

from typing import Any, Protocol

from task_automation_studio.core.agent_models import AgentGoal, AgentPlanStep, AgentState
from task_automation_studio.core.agent_models import SkillDescriptor


class AgentSkillHandler(Protocol):
    def __call__(
        self,
        *,
        step: AgentPlanStep,
        goal: AgentGoal,
        state: AgentState,
        observation: dict[str, Any],
        attempt: int,
    ) -> dict[str, Any]:
        ...


class AgentSkillRegistry:
    """In-memory skill registry used by the planner."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDescriptor] = {}
        self._handlers: dict[str, AgentSkillHandler] = {}

    def register(self, descriptor: SkillDescriptor) -> None:
        self._skills[descriptor.skill_id] = descriptor

    def register_handler(self, *, skill_id: str, handler: AgentSkillHandler) -> None:
        if skill_id not in self._skills:
            raise ValueError(f"Cannot register handler for unknown skill_id '{skill_id}'.")
        self._handlers[skill_id] = handler

    def get(self, skill_id: str) -> SkillDescriptor | None:
        return self._skills.get(skill_id)

    def handler_for(self, skill_id: str) -> AgentSkillHandler | None:
        return self._handlers.get(skill_id)

    def list(self) -> list[SkillDescriptor]:
        return list(self._skills.values())

    def skills_for_intent(self, intent: str) -> list[SkillDescriptor]:
        intent_norm = intent.strip().lower()
        matches: list[SkillDescriptor] = []
        for descriptor in self._skills.values():
            if any(item.lower() == intent_norm for item in descriptor.supported_intents):
                matches.append(descriptor)
        return matches
