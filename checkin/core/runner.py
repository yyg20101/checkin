from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from types import ModuleType
from typing import Callable

from checkin.core.config import TaskConfig
from checkin.core.result import CheckinResult


ImportModule = Callable[[str], ModuleType]


@dataclass(frozen=True)
class TaskRun:
    config: TaskConfig
    result: CheckinResult


def run_tasks(
    configs: list[TaskConfig],
    selected_task: str | None = None,
    import_module: ImportModule = importlib.import_module,
) -> list[TaskRun]:
    selected_configs = _select_configs(configs, selected_task)
    runs: list[TaskRun] = []
    for config in selected_configs:
        cookie = os.environ.get(config.cookie_secret)
        if not cookie:
            runs.append(
                TaskRun(
                    config=config,
                    result=CheckinResult.failed(f"缺少环境变量 {config.cookie_secret}"),
                )
            )
            continue

        try:
            module = import_module(config.module)
            result = module.run(cookie)
            if not isinstance(result, CheckinResult):
                result = CheckinResult.failed(f"{config.name} 返回了无效结果类型")
        except Exception as exc:
            result = CheckinResult.failed(f"{config.name} 执行失败: {exc}")
        runs.append(TaskRun(config=config, result=result))
    return runs


def print_task_runs(runs: list[TaskRun]) -> None:
    for run in runs:
        print(f"\n========== {run.config.name} ==========")
        print(run.result.message)
        details = dict(run.result.details)
        details.setdefault("task_id", run.config.id)
        details.setdefault("task_name", run.config.name)
        summary_result = CheckinResult(
            status=run.result.status,
            message=run.result.message,
            details=details,
        )
        print(summary_result.to_summary_line())

    total = len(runs)
    success = sum(1 for run in runs if run.result.status == "success")
    failed = sum(1 for run in runs if run.result.status == "failed")
    skipped = sum(1 for run in runs if run.result.status == "skipped")
    print("\n========== 任务汇总 ==========")
    print(f"总任务: {total}, 成功: {success}, 失败: {failed}, 跳过: {skipped}")


def has_failures(runs: list[TaskRun]) -> bool:
    return any(run.result.status == "failed" for run in runs)


def _select_configs(configs: list[TaskConfig], selected_task: str | None) -> list[TaskConfig]:
    if selected_task is None:
        return configs

    matches = [config for config in configs if config.id == selected_task]
    if not matches:
        available = ", ".join(config.id for config in configs)
        raise ValueError(f"Unknown task '{selected_task}'. Available tasks: {available}")
    return matches
