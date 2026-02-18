import pytest

from task_automation_studio.core.models import RecordInput


def test_record_input_valid_email_normalized() -> None:
    record = RecordInput(first_name="A", last_name="B", email="USER@EXAMPLE.COM")
    assert record.email == "user@example.com"


def test_record_input_invalid_email_rejected() -> None:
    with pytest.raises(ValueError):
        RecordInput(first_name="A", last_name="B", email="bad-email")
