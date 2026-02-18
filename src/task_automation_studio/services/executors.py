from __future__ import annotations

import logging
from dataclasses import dataclass

from task_automation_studio.connectors.browser_connector import PlaywrightBrowserConnector
from task_automation_studio.connectors.email_connector import EmailOTPConnector
from task_automation_studio.core.enums import ExecutionStatus
from task_automation_studio.core.interfaces import StepExecutor
from task_automation_studio.core.models import RecordContext, StepDefinition, StepExecutionResult


@dataclass(slots=True)
class EmailRuntimeConfig:
    enabled: bool = False
    host: str = ""
    username: str = ""
    password: str = ""
    folder: str = "INBOX"


class BrowserStepExecutor:
    def __init__(self, connector: PlaywrightBrowserConnector, logger: logging.Logger | None = None) -> None:
        self._connector = connector
        self._logger = logger or logging.getLogger(__name__)

    def execute(
        self,
        *,
        step: StepDefinition,
        context: RecordContext,
        dry_run: bool = False,
    ) -> StepExecutionResult:
        payload = {
            "record": context.record.model_dump(),
            "params": step.params,
            "metadata": context.metadata,
        }

        if dry_run:
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.SUCCESS,
                message=f"Dry-run browser action: {step.action}",
                evidence={"dry_run": True, "action": step.action},
            )

        try:
            response = self._connector.run_action(step.action, payload)
        except Exception as exc:
            self._logger.exception("Browser action '%s' failed.", step.action)
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                message=f"Browser action failed: {exc}",
                evidence={"action": step.action},
            )

        state_updates = response.get("state_updates")
        if isinstance(state_updates, dict):
            context.metadata.update(state_updates)

        verified = bool(response.get("verified", False))
        status = ExecutionStatus.SUCCESS if verified else ExecutionStatus.FAILED
        message = response.get("message") or ("Browser step verified." if verified else "Browser step not verified.")
        return StepExecutionResult(
            step_id=step.step_id,
            status=status,
            message=message,
            evidence=response,
        )


class EmailOtpStepExecutor:
    def __init__(self, config: EmailRuntimeConfig, logger: logging.Logger | None = None) -> None:
        self._config = config
        self._logger = logger or logging.getLogger(__name__)

    def execute(
        self,
        *,
        step: StepDefinition,
        context: RecordContext,
        dry_run: bool = False,
    ) -> StepExecutionResult:
        if dry_run:
            otp = "000000"
            context.metadata["otp"] = otp
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.SUCCESS,
                message="Dry-run OTP generated.",
                evidence={"dry_run": True, "otp": otp},
            )

        if not self._config.enabled:
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                message="Email connector is not configured for live execution.",
                evidence={"configured": False},
            )

        sender_filter = str(step.params.get("sender_contains", "")).strip()
        if not sender_filter:
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                message="Missing 'sender_contains' in step params for OTP lookup.",
                evidence={"configured": True},
            )

        try:
            connector = EmailOTPConnector(
                host=self._config.host,
                username=self._config.username,
                password=self._config.password,
                folder=self._config.folder,
            )
            otp = connector.fetch_latest_otp(
                sender_contains=sender_filter,
                otp_pattern=str(step.params.get("otp_pattern", r"\b(\d{6})\b")),
                lookback_minutes=int(step.params.get("lookback_minutes", 15)),
            )
        except Exception as exc:
            self._logger.exception("OTP retrieval failed.")
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                message=f"OTP retrieval failed: {exc}",
                evidence={"sender_contains": sender_filter},
            )

        if not otp:
            return StepExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                message="OTP not found within configured time window.",
                evidence={"sender_contains": sender_filter},
            )

        context.metadata["otp"] = otp
        return StepExecutionResult(
            step_id=step.step_id,
            status=ExecutionStatus.SUCCESS,
            message="OTP retrieved successfully.",
            evidence={"sender_contains": sender_filter, "otp_found": True},
        )


class UnsupportedActionExecutor:
    def execute(
        self,
        *,
        step: StepDefinition,
        context: RecordContext,
        dry_run: bool = False,
    ) -> StepExecutionResult:
        del context, dry_run
        return StepExecutionResult(
            step_id=step.step_id,
            status=ExecutionStatus.FAILED,
            message=f"Unsupported action: {step.action}",
            evidence={"action": step.action},
        )


def build_executors_for_workflow(
    actions: list[str],
    *,
    email_config: EmailRuntimeConfig,
    browser_connector: PlaywrightBrowserConnector | None = None,
) -> dict[str, StepExecutor]:
    connector = browser_connector or PlaywrightBrowserConnector(headless=True)
    browser_executor = BrowserStepExecutor(connector=connector)
    email_executor = EmailOtpStepExecutor(config=email_config)
    unsupported = UnsupportedActionExecutor()

    executors: dict[str, StepExecutor] = {}
    for action in actions:
        if action.startswith("browser."):
            executors[action] = browser_executor
        elif action.startswith("email."):
            executors[action] = email_executor
        else:
            executors[action] = unsupported
    return executors
