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
                success_signals=["page_loaded"],
            ),
            StepDefinition(
                step_id="fill_signup_form",
                name="Fill Signup Form",
                action="browser.fill_signup_form",
                required_inputs=["first_name", "last_name", "email"],
                success_signals=["form_filled"],
            ),
            StepDefinition(
                step_id="submit_form",
                name="Submit Form",
                action="browser.submit_signup",
                success_signals=["submission_sent"],
            ),
            StepDefinition(
                step_id="fetch_otp",
                name="Fetch OTP",
                action="email.fetch_otp",
                required_inputs=["email"],
                success_signals=["otp_found"],
            ),
            StepDefinition(
                step_id="confirm_otp",
                name="Confirm OTP",
                action="browser.confirm_otp",
                success_signals=["account_created"],
            ),
        ],
    )
