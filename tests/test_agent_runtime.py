from task_automation_studio.core.agent_models import AgentGoal, AgentGoalType, AgentPlan, AgentPlanStep, AgentState, SkillDescriptor
from task_automation_studio.services.agent_runtime import AgentRuntime
from task_automation_studio.services.agent_skills import AgentSkillRegistry


def _descriptor(skill_id: str, intent: str) -> SkillDescriptor:
    return SkillDescriptor(
        skill_id=skill_id,
        name=skill_id,
        supported_intents=[intent],
        required_inputs=[],
        default_success_signals=[],
        reliability_score=0.8,
    )


def test_agent_runtime_runs_success_path() -> None:
    registry = AgentSkillRegistry()
    registry.register(_descriptor("locate_skill", "locate_target"))
    registry.register(_descriptor("apply_skill", "apply_action"))

    registry.register_handler(
        skill_id="locate_skill",
        handler=lambda **kwargs: {  # type: ignore[no-any-return]
            "success": True,
            "verified": True,
            "message": "located",
            "state_updates": {"target_found": True},
            "signals": ["ok"],
        },
    )
    registry.register_handler(
        skill_id="apply_skill",
        handler=lambda **kwargs: {  # type: ignore[no-any-return]
            "success": True,
            "verified": True,
            "message": "applied",
            "state_updates": {"submitted": True},
            "signals": ["done"],
        },
    )

    goal = AgentGoal(goal_id="g1", name="Goal", goal_type=AgentGoalType.REPETITIVE_TASK)
    plan = AgentPlan(
        plan_id="p1",
        goal_id=goal.goal_id,
        steps=[
            AgentPlanStep(step_id="s1", intent="locate_target", skill_id="locate_skill", description="locate"),
            AgentPlanStep(step_id="s2", intent="apply_action", skill_id="apply_skill", description="apply"),
        ],
    )

    runtime = AgentRuntime(skills=registry)
    summary = runtime.run(goal=goal, plan=plan, state=AgentState())

    assert summary.completed is True
    assert summary.completed_steps == 2
    assert summary.failed_step_id is None
    assert summary.state.variables["target_found"] is True
    assert summary.state.variables["submitted"] is True


def test_agent_runtime_uses_fallback_skill() -> None:
    registry = AgentSkillRegistry()
    registry.register(_descriptor("primary", "apply_action"))
    registry.register(_descriptor("fallback", "apply_action"))

    attempts = {"primary": 0, "fallback": 0}

    def _primary_handler(**kwargs):  # type: ignore[no-untyped-def]
        attempts["primary"] += 1
        return {
            "success": False,
            "verified": False,
            "message": "primary failed",
            "signals": [],
        }

    def _fallback_handler(**kwargs):  # type: ignore[no-untyped-def]
        attempts["fallback"] += 1
        return {
            "success": True,
            "verified": True,
            "message": "fallback ok",
            "signals": [],
        }

    registry.register_handler(skill_id="primary", handler=_primary_handler)
    registry.register_handler(skill_id="fallback", handler=_fallback_handler)

    goal = AgentGoal(goal_id="g2", name="Goal")
    plan = AgentPlan(
        plan_id="p2",
        goal_id=goal.goal_id,
        steps=[
            AgentPlanStep(
                step_id="s1",
                intent="apply_action",
                skill_id="primary",
                fallback_skill_ids=["fallback"],
                description="act",
                max_attempts=2,
            )
        ],
    )

    runtime = AgentRuntime(skills=registry)
    summary = runtime.run(goal=goal, plan=plan)

    assert summary.completed is True
    assert attempts["primary"] == 2
    assert attempts["fallback"] == 1
    assert summary.traces[-1].selected_skill_id == "fallback"


def test_agent_runtime_fails_when_all_paths_fail() -> None:
    registry = AgentSkillRegistry()
    registry.register(_descriptor("broken", "verify_outcome"))
    registry.register_handler(
        skill_id="broken",
        handler=lambda **kwargs: {  # type: ignore[no-any-return]
            "success": False,
            "verified": False,
            "message": "failed",
            "signals": [],
        },
    )
    goal = AgentGoal(goal_id="g3", name="Goal")
    plan = AgentPlan(
        plan_id="p3",
        goal_id=goal.goal_id,
        steps=[AgentPlanStep(step_id="s1", intent="verify_outcome", skill_id="broken", description="verify", max_attempts=2)],
    )

    runtime = AgentRuntime(skills=registry)
    summary = runtime.run(goal=goal, plan=plan)

    assert summary.completed is False
    assert summary.failed_step_id == "s1"
    assert summary.completed_steps == 0
    assert len(summary.traces) == 2
