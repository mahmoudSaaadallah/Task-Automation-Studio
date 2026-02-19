from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from task_automation_studio.core.agent_models import AgentGoal, AgentGoalType, AgentState, SkillDescriptor
from task_automation_studio.core.teach_models import TeachEventData, TeachEventType
from task_automation_studio.services.agent_planner import GoalPlanner
from task_automation_studio.services.agent_runtime import AgentRunSummary, AgentRuntime
from task_automation_studio.services.agent_skills import AgentSkillRegistry
from task_automation_studio.services.smart_locator import resolve_smart_click_position
from task_automation_studio.services.teach_sessions import TeachSessionService

LOGGER = logging.getLogger("task_automation_studio")


def _normalize_speed_factor(value: float) -> float:
    if value <= 0:
        return 1.0
    return min(value, 10.0)


def _is_escape_key(key: Any) -> bool:
    char = getattr(key, "char", None)
    if isinstance(char, str) and char.lower() == "\x1b":
        return True
    key_name = str(key).lower()
    return key_name in {"key.esc", "esc"}


def _sleep_with_stop(total_seconds: float, stop_event: threading.Event) -> bool:
    remaining = max(0.0, total_seconds)
    while remaining > 0:
        if stop_event.is_set():
            return False
        chunk = min(0.05, remaining)
        time.sleep(chunk)
        remaining -= chunk
    return not stop_event.is_set()


def _event_time_ms(event: TeachEventData) -> int:
    payload_time = event.payload.get("t_ms")
    if isinstance(payload_time, int):
        return max(payload_time, 0)
    return int(event.timestamp.timestamp() * 1000)


def _button_name_to_key(name: str, mouse_module: Any) -> Any:
    normalized = name.lower()
    if normalized == "left":
        return mouse_module.Button.left
    if normalized == "right":
        return mouse_module.Button.right
    if normalized == "middle":
        return mouse_module.Button.middle
    return mouse_module.Button.left


def _key_name_to_key(name: str, keyboard_module: Any) -> Any:
    normalized = name.lower()
    special = getattr(keyboard_module.Key, normalized, None)
    if special is not None:
        return special
    return normalized


def _modifier_name_to_key(name: str, keyboard_module: Any) -> Any:
    normalized = name.lower()
    if normalized == "ctrl":
        key = getattr(keyboard_module.Key, "ctrl", None) or getattr(keyboard_module.Key, "ctrl_l", None)
        return key
    if normalized == "alt":
        key = getattr(keyboard_module.Key, "alt", None) or getattr(keyboard_module.Key, "alt_l", None)
        return key
    if normalized == "shift":
        key = getattr(keyboard_module.Key, "shift", None) or getattr(keyboard_module.Key, "shift_l", None)
        return key
    if normalized == "cmd":
        key = getattr(keyboard_module.Key, "cmd", None)
        if key is None:
            key = getattr(keyboard_module.Key, "cmd_l", None)
        return key
    return None


def _resolve_click_target(payload: dict[str, Any]) -> tuple[int, int] | None:
    smart_click = resolve_smart_click_position(payload)
    if smart_click is not None:
        return smart_click
    x = payload.get("x")
    y = payload.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return x, y
    return None


@dataclass(slots=True)
class ReplaySummary:
    session_id: str
    replayed_events: int
    skipped_events: int
    speed_factor: float
    stopped_by_user: bool
    diagnostics: list[dict[str, object]]
    diagnostics_file: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "replayed_events": self.replayed_events,
            "skipped_events": self.skipped_events,
            "speed_factor": self.speed_factor,
            "stopped_by_user": self.stopped_by_user,
            "diagnostics": self.diagnostics,
            "diagnostics_file": self.diagnostics_file,
        }


@dataclass(slots=True)
class EventApplyResult:
    applied: bool
    reason: str
    details: dict[str, object]


class TeachSessionReplayer:
    """Replay teach session events using global mouse/keyboard controllers."""

    def __init__(self, session_service: TeachSessionService) -> None:
        self._service = session_service

    def replay(
        self,
        *,
        session_id: str,
        speed_factor: float = 1.0,
        diagnostics_output_file: str | Path | None = None,
        save_diagnostics: bool = False,
    ) -> ReplaySummary:
        try:
            from pynput import keyboard, mouse  # pylint: disable=import-outside-toplevel
        except Exception as exc:  # pragma: no cover - platform/import dependent
            raise RuntimeError("Replay requires 'pynput'. Install dependencies with: pip install -e .[dev]") from exc

        session = self._service.get_session(session_id=session_id)
        events = sorted(session.events, key=lambda item: item.timestamp)
        if not events:
            summary = ReplaySummary(
                session_id=session_id,
                replayed_events=0,
                skipped_events=0,
                speed_factor=1.0,
                stopped_by_user=False,
                diagnostics=[],
            )
            if save_diagnostics or diagnostics_output_file is not None:
                diagnostics_path = self.save_diagnostics(summary=summary, output_file=diagnostics_output_file)
                summary.diagnostics_file = str(diagnostics_path)
            return summary

        safe_speed = _normalize_speed_factor(speed_factor)
        mouse_controller = mouse.Controller()
        keyboard_controller = keyboard.Controller()
        stop_event = threading.Event()

        def _on_stop_key(key: Any) -> bool | None:
            if _is_escape_key(key):
                stop_event.set()
                return False
            return None

        stop_listener = keyboard.Listener(on_press=_on_stop_key)
        stop_listener.start()

        replayed_count = 0
        skipped_count = 0
        diagnostics: list[dict[str, object]] = []
        previous_time = _event_time_ms(events[0])

        for event in events:
            if stop_event.is_set():
                break
            current_time = _event_time_ms(event)
            delay_seconds = max(0, current_time - previous_time) / 1000 / safe_speed
            if delay_seconds > 0:
                if not _sleep_with_stop(delay_seconds, stop_event):
                    break
            previous_time = current_time

            result = self._apply_event(
                event=event,
                mouse_module=mouse,
                keyboard_module=keyboard,
                mouse_controller=mouse_controller,
                keyboard_controller=keyboard_controller,
            )
            diagnostics.append(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "applied": result.applied,
                    "reason": result.reason,
                    "details": result.details,
                }
            )
            if result.applied:
                replayed_count += 1
            else:
                skipped_count += 1

        stop_listener.stop()
        summary = ReplaySummary(
            session_id=session_id,
            replayed_events=replayed_count,
            skipped_events=skipped_count,
            speed_factor=safe_speed,
            stopped_by_user=stop_event.is_set(),
            diagnostics=diagnostics,
        )
        if save_diagnostics or diagnostics_output_file is not None:
            diagnostics_path = self.save_diagnostics(summary=summary, output_file=diagnostics_output_file)
            summary.diagnostics_file = str(diagnostics_path)
        return summary

    def save_diagnostics(self, *, summary: ReplaySummary, output_file: str | Path | None = None) -> Path:
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self._service.artifacts_dir() / f"replay_diagnostics_{summary.session_id}_{timestamp}.json"
        else:
            output_path = Path(output_file)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
        return output_path

    def _apply_event(
        self,
        *,
        event: TeachEventData,
        mouse_module: Any,
        keyboard_module: Any,
        mouse_controller: Any,
        keyboard_controller: Any,
    ) -> EventApplyResult:
        if event.event_type == TeachEventType.MOUSE_CLICK:
            return self._run_mouse_click_agent(
                event=event,
                mouse_module=mouse_module,
                mouse_controller=mouse_controller,
            )

        if event.event_type == TeachEventType.MOUSE_SCROLL:
            x = event.payload.get("x")
            y = event.payload.get("y")
            if isinstance(x, int) and isinstance(y, int):
                mouse_controller.position = (x, y)
            dx = int(event.payload.get("dx", 0))
            dy = int(event.payload.get("dy", 0))
            mouse_controller.scroll(dx, dy)
            return EventApplyResult(applied=True, reason="scroll_applied", details={"dx": dx, "dy": dy})

        if event.event_type == TeachEventType.KEY_PRESS:
            return self._run_key_press_agent(
                event=event,
                keyboard_module=keyboard_module,
                keyboard_controller=keyboard_controller,
            )

        if event.event_type == TeachEventType.HOTKEY:
            return self._run_hotkey_agent(
                event=event,
                keyboard_module=keyboard_module,
                keyboard_controller=keyboard_controller,
            )

        return EventApplyResult(
            applied=False,
            reason="unsupported_event_type",
            details={"event_type": event.event_type.value},
        )

    def _run_mouse_click_agent(
        self, *, event: TeachEventData, mouse_module: Any, mouse_controller: Any
    ) -> EventApplyResult:
        button_name = str(event.payload.get("button", "left")).lower()
        registry = AgentSkillRegistry()
        registry.register(
            SkillDescriptor(
                skill_id="ui_locate_click",
                name="Locate click target",
                supported_intents=["locate_target"],
                required_inputs=["event_payload", "button_name"],
                default_success_signals=["target_located"],
                reliability_score=0.9,
            )
        )
        registry.register(
            SkillDescriptor(
                skill_id="ui_apply_click",
                name="Apply mouse click",
                supported_intents=["apply_action"],
                required_inputs=["button_name"],
                default_success_signals=["click_applied"],
                reliability_score=0.92,
            )
        )
        registry.register(
            SkillDescriptor(
                skill_id="ui_verify_click",
                name="Verify mouse click",
                supported_intents=["verify_outcome"],
                required_inputs=[],
                default_success_signals=["click_verified"],
                reliability_score=0.88,
            )
        )

        def _locate_handler(**kwargs):  # type: ignore[no-untyped-def]
            step = kwargs["step"]
            state = kwargs["state"]
            payload = step.input_bindings.get("event_payload")
            if not isinstance(payload, dict):
                return {"success": False, "verified": False, "message": "Missing event payload.", "signals": []}
            target = _resolve_click_target(payload)
            if target is None:
                return {"success": False, "verified": False, "message": "No click target resolved.", "signals": []}
            state.variables["target_x"] = target[0]
            state.variables["target_y"] = target[1]
            state.variables["button_name"] = str(step.input_bindings.get("button_name", "left")).lower()
            return {
                "success": True,
                "verified": True,
                "message": "Target located.",
                "signals": ["target_located"],
                "state_updates": {"target_x": target[0], "target_y": target[1]},
                "evidence": {"target": target},
            }

        def _apply_handler(**kwargs):  # type: ignore[no-untyped-def]
            state = kwargs["state"]
            target_x = state.variables.get("target_x")
            target_y = state.variables.get("target_y")
            if not isinstance(target_x, int) or not isinstance(target_y, int):
                return {"success": False, "verified": False, "message": "Target coordinates are missing.", "signals": []}
            click_button_name = str(state.variables.get("button_name", button_name))
            mouse_controller.position = (target_x, target_y)
            mouse_controller.click(_button_name_to_key(click_button_name, mouse_module), 1)
            return {
                "success": True,
                "verified": True,
                "message": "Click applied.",
                "signals": ["click_applied"],
                "state_updates": {"click_applied": True},
                "evidence": {"clicked_point": [target_x, target_y], "button": click_button_name},
            }

        def _verify_handler(**kwargs):  # type: ignore[no-untyped-def]
            state = kwargs["state"]
            clicked = bool(state.variables.get("click_applied", False))
            target_x = state.variables.get("target_x")
            target_y = state.variables.get("target_y")
            if not clicked or not isinstance(target_x, int) or not isinstance(target_y, int):
                return {"success": False, "verified": False, "message": "Click not applied.", "signals": []}
            return {
                "success": True,
                "verified": True,
                "message": "Click verified.",
                "signals": ["click_verified"],
                "evidence": {"target": [target_x, target_y]},
            }

        registry.register_handler(skill_id="ui_locate_click", handler=_locate_handler)
        registry.register_handler(skill_id="ui_apply_click", handler=_apply_handler)
        registry.register_handler(skill_id="ui_verify_click", handler=_verify_handler)

        goal = AgentGoal(
            goal_id=event.event_id,
            name="Replay mouse click",
            goal_type=AgentGoalType.REPETITIVE_TASK,
            requested_intents=["locate_target", "apply_action", "verify_outcome"],
            inputs={"event_payload": event.payload, "button_name": button_name},
            success_criteria=["click_verified"],
        )

        return self._execute_agent_goal(event=event, goal=goal, registry=registry)

    def _run_key_press_agent(
        self, *, event: TeachEventData, keyboard_module: Any, keyboard_controller: Any
    ) -> EventApplyResult:
        registry = AgentSkillRegistry()
        registry.register(
            SkillDescriptor(
                skill_id="ui_locate_key_press",
                name="Locate key press input",
                supported_intents=["locate_target"],
                required_inputs=["key_name"],
                default_success_signals=["key_resolved"],
                reliability_score=0.9,
            )
        )
        registry.register(
            SkillDescriptor(
                skill_id="ui_apply_key_press",
                name="Apply key press",
                supported_intents=["apply_action"],
                required_inputs=["key_name"],
                default_success_signals=["key_applied"],
                reliability_score=0.92,
            )
        )
        registry.register(
            SkillDescriptor(
                skill_id="ui_verify_key_press",
                name="Verify key press",
                supported_intents=["verify_outcome"],
                required_inputs=[],
                default_success_signals=["key_verified"],
                reliability_score=0.85,
            )
        )

        def _locate_handler(**kwargs):  # type: ignore[no-untyped-def]
            step = kwargs["step"]
            state = kwargs["state"]
            key_name = str(step.input_bindings.get("key_name", "")).lower().strip()
            if not key_name or key_name == "esc":
                return {"success": False, "verified": False, "message": "Invalid key_name for replay.", "signals": []}
            state.variables["key_name"] = key_name
            return {
                "success": True,
                "verified": True,
                "message": "Key resolved.",
                "signals": ["key_resolved"],
                "state_updates": {"key_name": key_name},
                "evidence": {"key_name": key_name},
            }

        def _apply_handler(**kwargs):  # type: ignore[no-untyped-def]
            state = kwargs["state"]
            key_name = str(state.variables.get("key_name", "")).lower().strip()
            if not key_name:
                return {"success": False, "verified": False, "message": "Missing key_name in state.", "signals": []}
            key = _key_name_to_key(key_name, keyboard_module)
            keyboard_controller.press(key)
            keyboard_controller.release(key)
            return {
                "success": True,
                "verified": True,
                "message": "Key press applied.",
                "signals": ["key_applied"],
                "state_updates": {"key_applied": True},
                "evidence": {"key_name": key_name},
            }

        def _verify_handler(**kwargs):  # type: ignore[no-untyped-def]
            state = kwargs["state"]
            applied = bool(state.variables.get("key_applied", False))
            if not applied:
                return {"success": False, "verified": False, "message": "Key was not applied.", "signals": []}
            return {
                "success": True,
                "verified": True,
                "message": "Key press verified.",
                "signals": ["key_verified"],
                "evidence": {"key_name": state.variables.get("key_name")},
            }

        registry.register_handler(skill_id="ui_locate_key_press", handler=_locate_handler)
        registry.register_handler(skill_id="ui_apply_key_press", handler=_apply_handler)
        registry.register_handler(skill_id="ui_verify_key_press", handler=_verify_handler)

        key_name = str(event.payload.get("key", "")).lower().strip()
        goal = AgentGoal(
            goal_id=event.event_id,
            name="Replay key press",
            goal_type=AgentGoalType.REPETITIVE_TASK,
            requested_intents=["locate_target", "apply_action", "verify_outcome"],
            inputs={"key_name": key_name},
            success_criteria=["key_verified"],
        )
        return self._execute_agent_goal(event=event, goal=goal, registry=registry)

    def _run_hotkey_agent(
        self, *, event: TeachEventData, keyboard_module: Any, keyboard_controller: Any
    ) -> EventApplyResult:
        registry = AgentSkillRegistry()
        registry.register(
            SkillDescriptor(
                skill_id="ui_locate_hotkey",
                name="Locate hotkey input",
                supported_intents=["locate_target"],
                required_inputs=["key_name", "modifiers"],
                default_success_signals=["hotkey_resolved"],
                reliability_score=0.9,
            )
        )
        registry.register(
            SkillDescriptor(
                skill_id="ui_apply_hotkey",
                name="Apply hotkey",
                supported_intents=["apply_action"],
                required_inputs=["key_name", "modifiers"],
                default_success_signals=["hotkey_applied"],
                reliability_score=0.92,
            )
        )
        registry.register(
            SkillDescriptor(
                skill_id="ui_verify_hotkey",
                name="Verify hotkey",
                supported_intents=["verify_outcome"],
                required_inputs=[],
                default_success_signals=["hotkey_verified"],
                reliability_score=0.85,
            )
        )

        def _locate_handler(**kwargs):  # type: ignore[no-untyped-def]
            step = kwargs["step"]
            state = kwargs["state"]
            key_name = str(step.input_bindings.get("key_name", "")).lower().strip()
            modifiers_value = step.input_bindings.get("modifiers", [])
            if not key_name or key_name == "esc" or not isinstance(modifiers_value, list):
                return {"success": False, "verified": False, "message": "Invalid hotkey payload.", "signals": []}
            modifiers = [str(item).lower().strip() for item in modifiers_value if str(item).strip()]
            state.variables["hotkey_key_name"] = key_name
            state.variables["hotkey_modifiers"] = modifiers
            return {
                "success": True,
                "verified": True,
                "message": "Hotkey resolved.",
                "signals": ["hotkey_resolved"],
                "state_updates": {"hotkey_key_name": key_name, "hotkey_modifiers": modifiers},
                "evidence": {"key_name": key_name, "modifiers": modifiers},
            }

        def _apply_handler(**kwargs):  # type: ignore[no-untyped-def]
            state = kwargs["state"]
            key_name = str(state.variables.get("hotkey_key_name", "")).lower().strip()
            modifiers = state.variables.get("hotkey_modifiers", [])
            if not key_name or not isinstance(modifiers, list):
                return {"success": False, "verified": False, "message": "Missing hotkey state.", "signals": []}

            pressed_modifiers: list[Any] = []
            for modifier_name in [str(item).lower() for item in modifiers]:
                modifier_key = _modifier_name_to_key(modifier_name, keyboard_module)
                if modifier_key is None:
                    continue
                keyboard_controller.press(modifier_key)
                pressed_modifiers.append(modifier_key)

            target_key = _key_name_to_key(key_name, keyboard_module)
            keyboard_controller.press(target_key)
            keyboard_controller.release(target_key)
            for modifier_key in reversed(pressed_modifiers):
                keyboard_controller.release(modifier_key)

            return {
                "success": True,
                "verified": True,
                "message": "Hotkey applied.",
                "signals": ["hotkey_applied"],
                "state_updates": {"hotkey_applied": True},
                "evidence": {"key_name": key_name, "modifiers_used": [str(item) for item in pressed_modifiers]},
            }

        def _verify_handler(**kwargs):  # type: ignore[no-untyped-def]
            state = kwargs["state"]
            if not bool(state.variables.get("hotkey_applied", False)):
                return {"success": False, "verified": False, "message": "Hotkey was not applied.", "signals": []}
            return {
                "success": True,
                "verified": True,
                "message": "Hotkey verified.",
                "signals": ["hotkey_verified"],
                "evidence": {
                    "key_name": state.variables.get("hotkey_key_name"),
                    "modifiers": state.variables.get("hotkey_modifiers", []),
                },
            }

        registry.register_handler(skill_id="ui_locate_hotkey", handler=_locate_handler)
        registry.register_handler(skill_id="ui_apply_hotkey", handler=_apply_handler)
        registry.register_handler(skill_id="ui_verify_hotkey", handler=_verify_handler)

        key_name = str(event.payload.get("key", "")).lower().strip()
        modifiers_payload = event.payload.get("modifiers", [])
        goal = AgentGoal(
            goal_id=event.event_id,
            name="Replay hotkey",
            goal_type=AgentGoalType.REPETITIVE_TASK,
            requested_intents=["locate_target", "apply_action", "verify_outcome"],
            inputs={"key_name": key_name, "modifiers": modifiers_payload},
            success_criteria=["hotkey_verified"],
        )
        return self._execute_agent_goal(event=event, goal=goal, registry=registry)

    def _execute_agent_goal(
        self, *, event: TeachEventData, goal: AgentGoal, registry: AgentSkillRegistry
    ) -> EventApplyResult:
        planner = GoalPlanner(skill_registry=registry)
        plan = planner.build_plan(goal=goal, state=AgentState())
        runtime = AgentRuntime(skills=registry)
        summary = runtime.run(goal=goal, plan=plan, state=AgentState())
        self._log_agent_summary(event=event, summary=summary)
        if summary.completed:
            return EventApplyResult(
                applied=True,
                reason="agent_completed",
                details={"traces": len(summary.traces)},
            )

        last_trace_message = ""
        if summary.traces:
            last_trace_message = summary.traces[-1].message
        return EventApplyResult(
            applied=False,
            reason="agent_failed",
            details={
                "failed_step_id": summary.failed_step_id,
                "completed_steps": summary.completed_steps,
                "trace_count": len(summary.traces),
                "last_trace_message": last_trace_message,
            },
        )

    def _log_agent_summary(self, *, event: TeachEventData, summary: AgentRunSummary) -> None:
        level = logging.INFO if summary.completed else logging.WARNING
        LOGGER.log(
            level,
            "Replay agent result event_id=%s event_type=%s completed=%s failed_step=%s traces=%s",
            event.event_id,
            event.event_type.value,
            summary.completed,
            summary.failed_step_id,
            len(summary.traces),
        )
        for trace in summary.traces:
            trace_level = logging.DEBUG if trace.verified else logging.WARNING
            LOGGER.log(
                trace_level,
                "Replay agent trace event_id=%s step=%s intent=%s skill=%s attempt=%s verified=%s message=%s evidence=%s",
                event.event_id,
                trace.step_id,
                trace.intent,
                trace.selected_skill_id,
                trace.attempt,
                trace.verified,
                trace.message,
                trace.evidence,
            )
