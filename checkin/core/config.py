from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AccountConfig:
    id: str
    name: str
    cookie_secret: str


@dataclass(frozen=True)
class TaskConfig:
    id: str
    name: str
    module: str
    accounts: tuple[AccountConfig, ...] | str

    def __post_init__(self) -> None:
        if isinstance(self.accounts, str):
            object.__setattr__(
                self,
                "accounts",
                (
                    AccountConfig(
                        id="default",
                        name="默认账号",
                        cookie_secret=self.accounts,
                    ),
                ),
            )

    @property
    def cookie_secret(self) -> str:
        return self.accounts[0].cookie_secret


def load_task_configs(path: str | Path = "checkin_config.json") -> list[TaskConfig]:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config root must be an object")
    if "checkin_tasks" not in data:
        raise ValueError("checkin_tasks is required")

    raw_tasks = data["checkin_tasks"]
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
        for key in ("id", "name", "module")
        if not isinstance(raw_task.get(key), str) or not raw_task[key].strip()
    ]
    if missing:
        raise ValueError(f"Task at index {index} is missing fields: {', '.join(missing)}")

    accounts = _parse_accounts(raw_task, index)
    return TaskConfig(
        id=raw_task["id"].strip(),
        name=raw_task["name"].strip(),
        module=raw_task["module"].strip(),
        accounts=accounts,
    )


def _parse_accounts(raw_task: dict[str, Any], task_index: int) -> tuple[AccountConfig, ...]:
    if "accounts" in raw_task:
        raw_accounts = raw_task["accounts"]
        if not isinstance(raw_accounts, list):
            raise ValueError(f"Task at index {task_index} accounts must be a list")
        if not raw_accounts:
            raise ValueError(f"Task at index {task_index} accounts must not be empty")

        accounts: list[AccountConfig] = []
        seen_ids: set[str] = set()
        for account_index, raw_account in enumerate(raw_accounts):
            account = _parse_account(raw_account, task_index, account_index)
            if account.id in seen_ids:
                raise ValueError(f"Duplicate account id in task at index {task_index}: {account.id}")
            seen_ids.add(account.id)
            accounts.append(account)
        return tuple(accounts)

    cookie_secret = raw_task.get("cookie_secret")
    if not isinstance(cookie_secret, str) or not cookie_secret.strip():
        raise ValueError(f"Task at index {task_index} is missing fields: cookie_secret")

    return (
        AccountConfig(
            id="default",
            name="默认账号",
            cookie_secret=cookie_secret.strip(),
        ),
    )


def _parse_account(raw_account: Any, task_index: int, account_index: int) -> AccountConfig:
    if not isinstance(raw_account, dict):
        raise ValueError(f"Account at task index {task_index}, account index {account_index} must be an object")

    missing = [
        key
        for key in ("id", "name", "cookie_secret")
        if not isinstance(raw_account.get(key), str) or not raw_account[key].strip()
    ]
    if missing:
        raise ValueError(
            f"Account at task index {task_index}, account index {account_index} is missing fields: {', '.join(missing)}"
        )

    return AccountConfig(
        id=raw_account["id"].strip(),
        name=raw_account["name"].strip(),
        cookie_secret=raw_account["cookie_secret"].strip(),
    )
