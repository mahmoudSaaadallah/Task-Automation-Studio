from task_automation_studio.core.agent_models import AgentGoal, AgentGoalType, AgentState, SkillDescriptor
from task_automation_studio.services.agent_planner import GoalPlanner
from task_automation_studio.services.agent_skills import AgentSkillRegistry


def _skill(
    *,
    skill_id: str,
    name: str,
    intents: list[str],
    required_inputs: list[str] | None = None,
    reliability: float = 0.8,
) -> SkillDescriptor:
    return SkillDescriptor(
        skill_id=skill_id,
        name=name,
        supported_intents=intents,
        required_inputs=required_inputs or [],
        default_success_signals=["ok"],
        reliability_score=reliability,
    )


def test_skill_registry_filter_by_intent() -> None:
    registry = AgentSkillRegistry()
    registry.register(_skill(skill_id="s1", name="Locate A", intents=["locate_target"]))
    registry.register(_skill(skill_id="s2", name="Verify A", intents=["verify_outcome"]))
    matches = registry.skills_for_intent("locate_target")
    assert len(matches) == 1
    assert matches[0].skill_id == "s1"


def test_goal_planner_build_plan_with_requested_intents() -> None:
    registry = AgentSkillRegistry()
    registry.register(_skill(skill_id="locate", name="Locate UI", intents=["locate_target"], reliability=0.7))
    registry.register(
        _skill(
            skill_id="locate_alt",
            name="Locate Fallback",
            intents=["locate_target"],
            reliability=0.6,
        )
    )
    registry.register(
        _skill(
            skill_id="apply",
            name="Apply Action",
            intents=["apply_action"],
            required_inputs=["email"],
            reliability=0.82,
        )
    )

    goal = AgentGoal(
        goal_id="g1",
        name="Create account",
        goal_type=AgentGoalType.WEB_TASK,
        requested_intents=["locate_target", "apply_action"],
        inputs={"email": "x@example.com"},
        success_criteria=["account_created"],
    )
    planner = GoalPlanner(skill_registry=registry)
    plan = planner.build_plan(goal=goal, state=AgentState(current_url="https://zoom.us"))

    assert plan.goal_id == "g1"
    assert len(plan.steps) == 2
    assert plan.steps[0].skill_id == "locate"
    assert plan.steps[0].fallback_skill_ids == ["locate_alt"]
    assert plan.steps[1].skill_id == "apply"
    assert plan.steps[1].input_bindings["email"] == "x@example.com"


def test_goal_planner_raises_when_intent_has_no_skill() -> None:
    registry = AgentSkillRegistry()
    registry.register(_skill(skill_id="only_locate", name="Locate", intents=["locate_target"]))
    goal = AgentGoal(
        goal_id="g2",
        name="Broken goal",
        requested_intents=["locate_target", "verify_outcome"],
    )
    planner = GoalPlanner(skill_registry=registry)

    try:
        planner.build_plan(goal=goal)
    except ValueError as exc:
        assert "verify_outcome" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError when intent has no skill.")
