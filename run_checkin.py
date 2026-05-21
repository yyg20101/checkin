from __future__ import annotations

import argparse
import sys

from checkin.core.config import load_task_configs
from checkin.core.runner import has_failures, print_task_runs, run_tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automatic check-in tasks")
    parser.add_argument("--task", help="Run one task by id, for example: smzdm")
    parser.add_argument("--config", default="checkin_config.json", help="Path to checkin config JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configs = load_task_configs(args.config)
    try:
        runs = run_tasks(configs, selected_task=args.task)
    except ValueError as exc:
        print(f"错误: {exc}")
        return 2
    print_task_runs(runs)
    return 1 if has_failures(runs) else 0


if __name__ == "__main__":
    sys.exit(main())
