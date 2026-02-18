from __future__ import annotations

from uuid import uuid4

from task_automation_studio.core.agent_models import (
    AgentGoal,
    AgentGoalType,
    AgentPlan,
    AgentPlanStep,
    AgentState,
    SkillDescriptor,
)
from task_automation_studio.services.agent_skills import AgentSkillRegistry


DEFAULT_INTENTS_BY_GOAL_TYPE: dict[AgentGoalType, list[str]] = {
    AgentGoalType.REPETITIVE_TASK: [
        "prepare_context",
        "locate_target",
        "apply_action",
        "verify_outcome",
        "persist_result",
    ],
    AgentGoalType.WEB_TASK: [
        "open_page",
        "locate_target",
        "apply_action",
        "verify_outcome",
    ],
    AgentGoalType.DATA_ENTRY: [
        "locate_target",
        "fill_value",
        "verify_outcome",
        "persist_result",
    ],
    AgentGoalType.CUSTOM: [
        "locate_target",
        "apply_action",
        "verify_outcome",
    ],
}


class GoalPlanner:
    """Builds a deterministic action plan from goal + available skills."""

    def __init__(self, skill_registry: AgentSkillRegistry) -> None:
        self._skills = skill_registry

    def build_plan(self, *, goal: AgentGoal, state: AgentState | None = None) -> AgentPlan:
        state = state or AgentState()
        intents = goal.requested_intents or DEFAULT_INTENTS_BY_GOAL_TYPE[goal.goal_type]
        if not intents:
            raise ValueError("Goal has no requested intents and no defaults.")

        steps: list[AgentPlanStep] = []
        for index, intent in enumerate(intents, start=1):
            selected, fallbacks = self._select_skills_for_intent(intent=intent, goal=goal, state=state)
            input_bindings = self._build_input_bindings(goal=goal, skill=selected)
            step = AgentPlanStep(
                step_id=f"s{index:02d}",
                intent=intent,
                skill_id=selected.skill_id,
                description=f"{selected.name} ({intent})",
                input_bindings=input_bindings,
                expected_signals=selected.default_success_signals or list(goal.success_criteria),
                fallback_skill_ids=[item.skill_id for item in fallbacks],
                max_attempts=goal.constraints.max_step_attempts,
            )
            steps.append(step)

        if len(steps) > goal.constraints.max_total_steps:
            raise ValueError("Generated plan exceeded max_total_steps constraint.")

        return AgentPlan(
            plan_id=uuid4().hex,
            goal_id=goal.goal_id,
            steps=steps,
            metadata={
                "goal_type": goal.goal_type.value,
                "active_window_title": state.active_window_title,
                "current_url": state.current_url,
            },
        )

    def _select_skills_for_intent(
        self,
        *,
        intent: str,
        goal: AgentGoal,
        state: AgentState,
    ) -> tuple[SkillDescriptor, list[SkillDescriptor]]:
        candidates = self._skills.skills_for_intent(intent)
        if not candidates:
            raise ValueError(f"No registered skill can handle intent '{intent}'.")

        ranked = sorted(
            candidates,
            key=lambda item: self._skill_score(item=item, goal=goal, state=state),
            reverse=True,
        )
        return ranked[0], ranked[1:]

    def _skill_score(self, *, item: SkillDescriptor, goal: AgentGoal, state: AgentState) -> float:
        score = item.reliability_score
        goal_input_keys = set(goal.inputs.keys())
        required_keys = set(item.required_inputs)
        if required_keys and required_keys.issubset(goal_input_keys):
            score += 0.12
        if goal.goal_type == AgentGoalType.WEB_TASK and state.current_url:
            score += 0.03
        if goal.goal_type == AgentGoalType.DATA_ENTRY and "row_id" in goal_input_keys:
            score += 0.04
        return score

    def _build_input_bindings(self, *, goal: AgentGoal, skill: SkillDescriptor) -> dict[str, object]:
        bindings: dict[str, object] = {}
        for key in skill.required_inputs:
            if key in goal.inputs:
                bindings[key] = goal.inputs[key]
            else:
                bindings[key] = f"{{{{input.{key}}}}}"
        return bindings
