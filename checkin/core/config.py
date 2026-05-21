from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskConfig:
    id: str
    name: str
    module: str
    cookie_secret: str


def load_task_configs(path: str | Path = "checkin_config.json") -> list[TaskConfig]:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    raw_tasks = data.get("checkin_tasks", [])
    if not isinstance(raw_tasks, list):
        raise ValueError("checkin_tasks must be a list")

    configs: list[TaskConfig] = []
    seen_ids: set[str] = set()
    for index, raw_task in enumerate(raw_tasks):
        task = _parse_task(raw_task, index)
        if task.id in seen_ids:
            raise ValueError(f"Duplicate task id: {task.id}")
        seen_ids.add(task.id)
        configs.append(task)
    return configs


def _parse_task(raw_task: Any, index: int) -> TaskConfig:
    if not isinstance(raw_task, dict):
        raise ValueError(f"Task at index {index} must be an object")

    missing = [
        key
        for key in ("id", "name", "module", "cookie_secret")
        if not isinstance(raw_task.get(key), str) or not raw_task[key].strip()
    ]
    if missing:
        raise ValueError(f"Task at index {index} is missing fields: {', '.join(missing)}")

    return TaskConfig(
        id=raw_task["id"].strip(),
        name=raw_task["name"].strip(),
        module=raw_task["module"].strip(),
        cookie_secret=raw_task["cookie_secret"].strip(),
    )
