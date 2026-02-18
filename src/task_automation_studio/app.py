from __future__ import annotations

import argparse
import logging

from task_automation_studio.config.settings import Settings
from task_automation_studio.utils.logging_config import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Task Automation Studio")
    parser.add_argument("--ui", action="store_true", help="Launch desktop UI.")
    return parser


def main() -> int:
    settings = Settings.from_env()
    configure_logging(settings.log_dir)
    logger = logging.getLogger("task_automation_studio")

    parser = build_parser()
    args = parser.parse_args()

    if args.ui:
        from task_automation_studio.ui.main_window import launch_ui

        return launch_ui()

    logger.info("Scaffold initialized. Use --ui to launch desktop app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
