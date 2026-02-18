from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from task_automation_studio.core.agent_models import AgentGoal, AgentPlan, AgentPlanStep, AgentState
from task_automation_studio.services.agent_skills import AgentSkillRegistry


class AgentObserver(Protocol):
    def observe(self, *, goal: AgentGoal, step: AgentPlanStep, state: AgentState, attempt: int) -> dict[str, Any]:
        ...


class AgentVerifier(Protocol):
    def verify(
        self,
        *,
        step: AgentPlanStep,
        state: AgentState,
        observation: dict[str, Any],
        action_result: dict[str, Any],
    ) -> bool:
        ...


class DefaultAgentObserver:
    def observe(self, *, goal: AgentGoal, step: AgentPlanStep, state: AgentState, attempt: int) -> dict[str, Any]:
        del goal
        return {
            "attempt": attempt,
            "intent": step.intent,
            "active_window_title": state.active_window_title,
            "current_url": state.current_url,
            "state_variables": dict(state.variables),
        }


class DefaultAgentVerifier:
    def verify(
        self,
        *,
        step: AgentPlanStep,
        state: AgentState,
        observation: dict[str, Any],
        action_result: dict[str, Any],
    ) -> bool:
        del state, observation
        if not bool(action_result.get("success", False)):
            return False
        verified_flag = action_result.get("verified")
        if isinstance(verified_flag, bool):
            if not verified_flag:
                return False
        if not step.expected_signals:
            return True
        signals = action_result.get("signals", [])
        if not isinstance(signals, list):
            return False
        signals_set = {str(item) for item in signals}
        return all(signal in signals_set for signal in step.expected_signals)


@dataclass(slots=True)
class AgentStepRunTrace:
    step_id: str
    intent: str
    selected_skill_id: str
    attempt: int
    verified: bool
    message: str
    observation: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentRunSummary:
    plan_id: str
    goal_id: str
    completed: bool
    completed_steps: int
    failed_step_id: str | None
    traces: list[AgentStepRunTrace]
    state: AgentState

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "completed": self.completed,
            "completed_steps": self.completed_steps,
            "failed_step_id": self.failed_step_id,
            "traces": [
                {
                    "step_id": item.step_id,
                    "intent": item.intent,
                    "selected_skill_id": item.selected_skill_id,
                    "attempt": item.attempt,
                    "verified": item.verified,
                    "message": item.message,
                    "observation": item.observation,
                    "evidence": item.evidence,
                }
                for item in self.traces
            ],
            "state": state_to_dict(self.state),
        }


def state_to_dict(state: AgentState) -> dict[str, object]:
    return {
        "active_window_title": state.active_window_title,
        "current_url": state.current_url,
        "variables": state.variables,
        "observations": state.observations,
    }


class AgentRuntime:
    """Executes agent plans with observe -> decide -> act -> verify cycle."""

    def __init__(
        self,
        *,
        skills: AgentSkillRegistry,
        observer: AgentObserver | None = None,
        verifier: AgentVerifier | None = None,
    ) -> None:
        self._skills = skills
        self._observer = observer or DefaultAgentObserver()
        self._verifier = verifier or DefaultAgentVerifier()

    def run(self, *, goal: AgentGoal, plan: AgentPlan, state: AgentState | None = None) -> AgentRunSummary:
        runtime_state = state or AgentState()
        traces: list[AgentStepRunTrace] = []
        completed_steps = 0

        for step in plan.steps:
            success, step_traces = self._run_step(goal=goal, step=step, state=runtime_state)
            traces.extend(step_traces)
            if not success:
                return AgentRunSummary(
                    plan_id=plan.plan_id,
                    goal_id=goal.goal_id,
                    completed=False,
                    completed_steps=completed_steps,
                    failed_step_id=step.step_id,
                    traces=traces,
                    state=runtime_state,
                )
            completed_steps += 1

        return AgentRunSummary(
            plan_id=plan.plan_id,
            goal_id=goal.goal_id,
            completed=True,
            completed_steps=completed_steps,
            failed_step_id=None,
            traces=traces,
            state=runtime_state,
        )

    def _run_step(self, *, goal: AgentGoal, step: AgentPlanStep, state: AgentState) -> tuple[bool, list[AgentStepRunTrace]]:
        traces: list[AgentStepRunTrace] = []
        skill_sequence = [step.skill_id, *step.fallback_skill_ids]
        for skill_id in skill_sequence:
            handler = self._skills.handler_for(skill_id)
            if handler is None:
                traces.append(
                    AgentStepRunTrace(
                        step_id=step.step_id,
                        intent=step.intent,
                        selected_skill_id=skill_id,
                        attempt=0,
                        verified=False,
                        message=f"No handler for skill '{skill_id}'.",
                    )
                )
                continue

            for attempt in range(1, step.max_attempts + 1):
                observation = self._observer.observe(
                    goal=goal,
                    step=step,
                    state=state,
                    attempt=attempt,
                )
                state.observations[step.step_id] = observation

                action_result = handler(
                    step=step,
                    goal=goal,
                    state=state,
                    observation=observation,
                    attempt=attempt,
                )
                if not isinstance(action_result, dict):
                    action_result = {"success": False, "message": "Skill returned invalid action result.", "evidence": {}}

                state_updates = action_result.get("state_updates")
                if isinstance(state_updates, dict):
                    state.variables.update(state_updates)

                verified = self._verifier.verify(
                    step=step,
                    state=state,
                    observation=observation,
                    action_result=action_result,
                )

                trace = AgentStepRunTrace(
                    step_id=step.step_id,
                    intent=step.intent,
                    selected_skill_id=skill_id,
                    attempt=attempt,
                    verified=verified,
                    message=str(action_result.get("message", "")),
                    observation=observation,
                    evidence=action_result.get("evidence", {}) if isinstance(action_result.get("evidence"), dict) else {},
                )
                traces.append(trace)

                if verified:
                    return True, traces

        return False, traces
