from task_automation_studio.core.models import StepDefinition, WorkflowDefinition


def build_zoom_signup_workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="zoom_signup_v1",
        name="Zoom Account Signup",
        steps=[
            StepDefinition(
                step_id="open_signup",
                name="Open Signup Page",
                action="browser.open_signup",
                params={"url": "https://zoom.us/signup"},
                success_signals=["page_loaded"],
            ),
            StepDefinition(
                step_id="fill_signup_form",
                name="Fill Signup Form",
                action="browser.fill_signup_form",
                params={
                    "first_name_selector": "input[name='firstName']",
                    "last_name_selector": "input[name='lastName']",
                    "email_selector": "input[name='email']",
                },
                required_inputs=["first_name", "last_name", "email"],
                success_signals=["form_filled"],
            ),
            StepDefinition(
                step_id="submit_form",
                name="Submit Form",
                action="browser.submit_signup",
                params={"submit_selector": "button[type='submit']"},
                success_signals=["submission_sent"],
            ),
            StepDefinition(
                step_id="fetch_otp",
                name="Fetch OTP",
                action="email.fetch_otp",
                params={
                    "sender_contains": "zoom",
                    "otp_pattern": r"\b(\d{6})\b",
                    "lookback_minutes": 20,
                },
                required_inputs=["email"],
                success_signals=["otp_found"],
            ),
            StepDefinition(
                step_id="confirm_otp",
                name="Confirm OTP",
                action="browser.confirm_otp",
                params={
                    "otp_selector": "input[name='code']",
                    "confirm_selector": "button[type='submit']",
                },
                success_signals=["account_created"],
            ),
        ],
    )
