from __future__ import annotations

from task_automation_studio.config.settings import Settings
from task_automation_studio.ui.main_window import launch_ui


def main() -> int:
    return launch_ui(settings=Settings.from_env())


if __name__ == "__main__":
    raise SystemExit(main())
