from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from types import ModuleType
from typing import Callable

from checkin.core.config import AccountConfig, TaskConfig
from checkin.core.result import CheckinResult


ImportModule = Callable[[str], ModuleType]
VALID_STATUSES = {"success", "failed", "skipped"}


@dataclass(frozen=True)
class TaskRun:
    config: TaskConfig
    account: AccountConfig
    result: CheckinResult


@dataclass(frozen=True)
class AccountSecret:
    account: AccountConfig
    cookie: str


SECRET_ACCOUNT_SEPARATOR = "---CHECKIN_ACCOUNT---"
SECRET_ACCOUNT_NAME_SEPARATOR = "---CHECKIN_COOKIE---"


def run_tasks(
    configs: list[TaskConfig],
    selected_task: str | None = None,
    import_module: ImportModule = importlib.import_module,
) -> list[TaskRun]:
    selected_configs = _select_configs(configs, selected_task)
    runs: list[TaskRun] = []
    for config in selected_configs:
        try:
            module = import_module(config.module)
        except Exception as exc:
            for account in config.accounts:
                runs.append(
                    TaskRun(
                        config=config,
                        account=account,
                        result=CheckinResult.failed(f"{config.name} 加载失败: {exc}"),
                    )
                )
            continue

        for account in config.accounts:
            secret_value = os.environ.get(account.cookie_secret)
            if not secret_value or not secret_value.strip():
                runs.append(
                    TaskRun(
                        config=config,
                        account=account,
                        result=CheckinResult.skipped(f"未配置环境变量 {account.cookie_secret}，跳过该账号"),
                    )
                )
                continue

            account_secrets, parse_error = _parse_account_secret_value(account, secret_value)
            if parse_error:
                runs.append(
                    TaskRun(
                        config=config,
                        account=account,
                        result=CheckinResult.failed(parse_error),
                    )
                )
                continue

            for account_secret in account_secrets:
                runs.append(_run_account(config, module, account_secret))
    return runs


def _run_account(config: TaskConfig, module: ModuleType, account_secret: AccountSecret) -> TaskRun:
    account = account_secret.account
    try:
        result = module.run(account_secret.cookie)
        if not isinstance(result, CheckinResult):
            result = CheckinResult.failed(f"{config.name} / {account.name} 返回了无效结果类型")
        elif result.status not in VALID_STATUSES:
            result = CheckinResult.failed(f"{config.name} / {account.name} 返回了无效状态: {result.status}")
    except Exception as exc:
        result = CheckinResult.failed(f"{config.name} / {account.name} 执行失败: {exc}")
    return TaskRun(config=config, account=account, result=result)


def _parse_account_secret_value(account: AccountConfig, secret_value: str) -> tuple[list[AccountSecret], str | None]:
    value = secret_value.strip()
    uses_multi_format = SECRET_ACCOUNT_SEPARATOR in value or SECRET_ACCOUNT_NAME_SEPARATOR in value
    if not uses_multi_format:
        return [AccountSecret(account=account, cookie=value)], None

    raw_entries = value.split(SECRET_ACCOUNT_SEPARATOR)
    account_secrets: list[AccountSecret] = []
    for index, raw_entry in enumerate(raw_entries, start=1):
        entry = raw_entry.strip()
        if not entry:
            return [], f"{account.cookie_secret} 多账号格式错误: 第 {index} 个账号为空"

        account_name = _default_multi_account_name(account, index)
        cookie = entry
        if SECRET_ACCOUNT_NAME_SEPARATOR in entry:
            raw_name, raw_cookie = entry.split(SECRET_ACCOUNT_NAME_SEPARATOR, 1)
            account_name = raw_name.strip()
            cookie = raw_cookie.strip()
            if not account_name:
                return [], f"{account.cookie_secret} 多账号格式错误: 第 {index} 个账号名称为空"
            if not cookie:
                return [], f"{account.cookie_secret} 多账号格式错误: 第 {index} 个 Cookie 为空"

        account_secrets.append(
            AccountSecret(
                account=AccountConfig(
                    id=f"{account.id}-{index}",
                    name=account_name,
                    cookie_secret=account.cookie_secret,
                ),
                cookie=cookie,
            )
        )
    return account_secrets, None


def _default_multi_account_name(account: AccountConfig, index: int) -> str:
    if account.name == "默认账号":
        return f"账号 {index}"
    return f"{account.name} #{index}"


def print_task_runs(runs: list[TaskRun]) -> None:
    for run in runs:
        print(f"\n========== {run.config.name} / {run.account.name} ==========")
        print(run.result.message)
        details = dict(run.result.details)
        details.setdefault("task_id", run.config.id)
        details.setdefault("task_name", run.config.name)
        details.setdefault("account_id", run.account.id)
        details.setdefault("account_name", run.account.name)
        details.setdefault("cookie_secret", run.account.cookie_secret)
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
