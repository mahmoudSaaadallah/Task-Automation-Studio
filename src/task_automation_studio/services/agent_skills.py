from __future__ import annotations

from task_automation_studio.core.agent_models import SkillDescriptor


class AgentSkillRegistry:
    """In-memory skill registry used by the planner."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDescriptor] = {}

    def register(self, descriptor: SkillDescriptor) -> None:
        self._skills[descriptor.skill_id] = descriptor

    def get(self, skill_id: str) -> SkillDescriptor | None:
        return self._skills.get(skill_id)

    def list(self) -> list[SkillDescriptor]:
        return list(self._skills.values())

    def skills_for_intent(self, intent: str) -> list[SkillDescriptor]:
        intent_norm = intent.strip().lower()
        matches: list[SkillDescriptor] = []
        for descriptor in self._skills.values():
            if any(item.lower() == intent_norm for item in descriptor.supported_intents):
                matches.append(descriptor)
        return matches
