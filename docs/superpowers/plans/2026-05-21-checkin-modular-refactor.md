# Checkin Modular Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the automatic check-in project into a lightweight task-based runner and add SMZDM check-in support.

**Architecture:** Add a small `checkin` package with core result/config/runner modules and site-specific task modules. `run_checkin.py` becomes the single entrypoint for all tasks or one selected task, while GitHub Actions delegates execution and summary generation to the runner.

**Tech Stack:** Python 3.13, `requests`, `curl_cffi[requests]`, `beautifulsoup4`, `pytest`, GitHub Actions.

---

## File Structure

- Create `checkin/__init__.py`: package marker.
- Create `checkin/core/__init__.py`: core package marker.
- Create `checkin/core/result.py`: `CheckinResult` dataclass and summary serialization.
- Create `checkin/core/config.py`: load and validate `checkin_config.json`.
- Create `checkin/core/runner.py`: task import, cookie lookup, exception isolation, CLI orchestration helpers.
- Create `checkin/tasks/__init__.py`: task package marker.
- Create `checkin/tasks/doingfb.py`: DoingFB task logic migrated from `checkin_doingfb.py`.
- Create `checkin/tasks/enshan.py`: Enshan task logic migrated from `checkin_enshan.py`, retained for manual or future enablement.
- Create `checkin/tasks/hostloc.py`: Hostloc task logic migrated from `checkin_hostloc.py`.
- Create `checkin/tasks/smzdm.py`: SMZDM task adapted from upstream `dailycheckin/smzdm/main.py`.
- Create `run_checkin.py`: command-line entrypoint.
- Create `tests/test_result.py`: unit tests for summary serialization.
- Create `tests/test_config.py`: unit tests for config loading and validation.
- Create `tests/test_runner.py`: unit tests for task filtering, missing cookie handling, and exception isolation.
- Modify `checkin_config.json`: change entries to task id/display/module/secret format and add SMZDM; keep Enshan out of the unified daily task list until explicitly enabled.
- Modify `.github/workflows/daily_checkin.yml`: export enabled-task Cookie secrets, run `python run_checkin.py`, keep log archive and release summary with per-task details.
- Modify `requirements.txt`: add `pytest`, remove unused browser automation dependencies unless kept for unrelated user workflows.
- Modify `README.md`: document unified runner, local single-task execution, and `COOKIE_SMZDM`.
- Modify existing `checkin_*.py` scripts: keep as thin compatibility wrappers or remove references from docs/workflow. Use thin wrappers to reduce breakage.

## Task 1: Core Result Model

**Files:**
- Create: `checkin/__init__.py`
- Create: `checkin/core/__init__.py`
- Create: `checkin/core/result.py`
- Test: `tests/test_result.py`

- [ ] **Step 1: Write failing result serialization tests**

Create `tests/test_result.py`:

```python
import json

from checkin.core.result import CheckinResult


def test_summary_line_serializes_success_result():
    result = CheckinResult.success(
        "签到成功",
        details={"coins": 18, "site": "demo"},
    )

    line = result.to_summary_line()

    assert line.startswith("[CHECKIN_SUMMARY] ")
    payload = json.loads(line.replace("[CHECKIN_SUMMARY] ", "", 1))
    assert payload == {
        "status": "success",
        "message": "签到成功",
        "details": {"coins": 18, "site": "demo"},
    }


def test_failed_result_defaults_to_empty_details():
    result = CheckinResult.failed("Cookie 缺失")

    assert result.status == "failed"
    assert result.details == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_result.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'checkin'`.

- [ ] **Step 3: Implement `CheckinResult`**

Create `checkin/__init__.py` as an empty package marker.

Create `checkin/core/__init__.py` as an empty package marker.

Create `checkin/core/result.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal


ResultStatus = Literal["success", "failed", "skipped"]


@dataclass(frozen=True)
class CheckinResult:
    status: ResultStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str, details: dict[str, Any] | None = None) -> "CheckinResult":
        return cls(status="success", message=message, details=details or {})

    @classmethod
    def failed(cls, message: str, details: dict[str, Any] | None = None) -> "CheckinResult":
        return cls(status="failed", message=message, details=details or {})

    @classmethod
    def skipped(cls, message: str, details: dict[str, Any] | None = None) -> "CheckinResult":
        return cls(status="skipped", message=message, details=details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }

    def to_summary_line(self) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"[CHECKIN_SUMMARY] {payload}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_result.py -v`

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add checkin/__init__.py checkin/core/__init__.py checkin/core/result.py tests/test_result.py
git commit -m "feat: add checkin result model"
```

## Task 2: Config Loader

**Files:**
- Create: `checkin/core/config.py`
- Modify: `checkin_config.json`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py`:

```python
import json

import pytest

from checkin.core.config import TaskConfig, load_task_configs


def test_load_task_configs_reads_new_schema(tmp_path):
    config_path = tmp_path / "checkin_config.json"
    config_path.write_text(
        json.dumps(
            {
                "checkin_tasks": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "module": "checkin.tasks.demo",
                        "cookie_secret": "COOKIE_DEMO",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    configs = load_task_configs(config_path)

    assert configs == [
        TaskConfig(
            id="demo",
            name="Demo",
            module="checkin.tasks.demo",
            cookie_secret="COOKIE_DEMO",
        )
    ]


def test_load_task_configs_rejects_duplicate_ids(tmp_path):
    config_path = tmp_path / "checkin_config.json"
    config_path.write_text(
        json.dumps(
            {
                "checkin_tasks": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "module": "checkin.tasks.demo",
                        "cookie_secret": "COOKIE_DEMO",
                    },
                    {
                        "id": "demo",
                        "name": "Demo 2",
                        "module": "checkin.tasks.demo2",
                        "cookie_secret": "COOKIE_DEMO2",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate task id"):
        load_task_configs(config_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.core.config'`.

- [ ] **Step 3: Implement config loader**

Create `checkin/core/config.py`:

```python
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
```

- [ ] **Step 4: Update `checkin_config.json`**

Replace `checkin_config.json` with the currently enabled daily tasks:

```json
{
  "checkin_tasks": [
    {
      "id": "doingfb",
      "name": "DoingFB",
      "module": "checkin.tasks.doingfb",
      "cookie_secret": "COOKIE_DOINGFB"
    },
    {
      "id": "hostloc",
      "name": "Hostloc",
      "module": "checkin.tasks.hostloc",
      "cookie_secret": "COOKIE_HOSTLOC"
    },
    {
      "id": "smzdm",
      "name": "什么值得买",
      "module": "checkin.tasks.smzdm",
      "cookie_secret": "COOKIE_SMZDM"
    }
  ]
}
```

- [ ] **Step 5: Run config tests**

Run: `pytest tests/test_config.py -v`

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
git add checkin/core/config.py checkin_config.json tests/test_config.py
git commit -m "feat: add checkin task config loader"
```

## Task 3: Runner And CLI

**Files:**
- Create: `checkin/core/runner.py`
- Create: `run_checkin.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write failing runner tests**

Create `tests/test_runner.py`:

```python
import types

from checkin.core.config import TaskConfig
from checkin.core.result import CheckinResult
from checkin.core.runner import run_tasks


def test_run_tasks_filters_by_task_id(monkeypatch):
    configs = [
        TaskConfig("one", "One", "checkin.tasks.one", "COOKIE_ONE"),
        TaskConfig("two", "Two", "checkin.tasks.two", "COOKIE_TWO"),
    ]
    monkeypatch.setenv("COOKIE_TWO", "cookie-two")

    def fake_import(module_name):
        assert module_name == "checkin.tasks.two"
        return types.SimpleNamespace(run=lambda cookie: CheckinResult.success(f"ran {cookie}"))

    results = run_tasks(configs, selected_task="two", import_module=fake_import)

    assert [(item.config.id, item.result.status, item.result.message) for item in results] == [
        ("two", "success", "ran cookie-two")
    ]


def test_run_tasks_reports_missing_cookie(monkeypatch):
    configs = [TaskConfig("one", "One", "checkin.tasks.one", "COOKIE_ONE")]
    monkeypatch.delenv("COOKIE_ONE", raising=False)

    results = run_tasks(configs, import_module=lambda name: None)

    assert results[0].result.status == "failed"
    assert "COOKIE_ONE" in results[0].result.message


def test_run_tasks_isolates_task_exception(monkeypatch):
    configs = [TaskConfig("one", "One", "checkin.tasks.one", "COOKIE_ONE")]
    monkeypatch.setenv("COOKIE_ONE", "cookie-one")

    def fake_import(module_name):
        def run(cookie):
            raise RuntimeError("site changed")

        return types.SimpleNamespace(run=run)

    results = run_tasks(configs, import_module=fake_import)

    assert results[0].result.status == "failed"
    assert "site changed" in results[0].result.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.core.runner'`.

- [ ] **Step 3: Implement runner**

Create `checkin/core/runner.py`:

```python
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
```

- [ ] **Step 4: Implement CLI entrypoint**

Create `run_checkin.py`:

```python
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
```

- [ ] **Step 5: Run runner tests**

Run: `pytest tests/test_runner.py -v`

Expected: PASS, 3 tests.

- [ ] **Step 6: Run all current unit tests**

Run: `pytest tests -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add checkin/core/runner.py run_checkin.py tests/test_runner.py
git commit -m "feat: add unified checkin runner"
```

## Task 4: Migrate Existing Site Tasks

**Files:**
- Create: `checkin/tasks/__init__.py`
- Create: `checkin/tasks/doingfb.py`
- Create: `checkin/tasks/enshan.py`
- Create: `checkin/tasks/hostloc.py`
- Modify: `checkin_doingfb.py`
- Modify: `checkin_enshan.py`
- Modify: `checkin_hostloc.py`

- [ ] **Step 1: Create task package marker**

Create `checkin/tasks/__init__.py` as an empty package marker.

- [ ] **Step 2: Migrate DoingFB**

Create `checkin/tasks/doingfb.py` by moving the existing request functions from `checkin_doingfb.py`, with this public interface:

```python
from __future__ import annotations

import json

import requests
from bs4 import BeautifulSoup

from checkin.core.result import CheckinResult


def run(cookie: str) -> CheckinResult:
    with requests.Session() as session:
        cookie_dict = _parse_cookie(cookie)
        session.cookies.update(cookie_dict)
        session.headers.update(
            {
                "user-agent": "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36 Edg/143.0.0.0",
            }
        )
        user_id, token, allow_checkin, days_count = get_initial_data(session)
        if not allow_checkin:
            return CheckinResult.success(
                f"📅 已签到过，连续 {days_count} 天",
                {"consecutive_days": days_count},
            )

        user_info = perform_checkin(session, user_id, token, allow_checkin, days_count)
        display_name = user_info.get("displayName")
        money = user_info.get("money")
        if not display_name:
            return CheckinResult.failed("⚠️ 未能解析用户信息")
        return CheckinResult.success(
            f"💰 签到成功，硬币: {money}",
            {"coins": money, "display_name": display_name},
        )
```

Retain `get_initial_data()` and `perform_checkin()` from the current script, but remove full header/cookie debug printing.

- [ ] **Step 3: Migrate Enshan**

Create `checkin/tasks/enshan.py` by moving `get_home_vars()`, `do_sign()`, and `get_profile_info()` from `checkin_enshan.py`, with this public interface:

```python
from __future__ import annotations

from curl_cffi import requests

from checkin.core.result import CheckinResult


def run(cookie: str) -> CheckinResult:
    base_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
        "Cookie": cookie,
    }
    with requests.Session() as session:
        session.headers.update(base_headers)
        formhash, uid = get_home_vars(session, base_headers)
        if not formhash or not uid:
            return CheckinResult.failed("❌ 未能提取 formhash 或 uid")

        if not do_sign(session, base_headers, formhash):
            return CheckinResult.failed("❌ 签到请求失败")

        esb, user, gid = get_profile_info(session, base_headers, uid)
        if esb is None:
            return CheckinResult.failed("❌ 未能获取恩山币信息")
        return CheckinResult.success(
            f"🪙 签到成功，恩山币: {esb}",
            {"coins": esb, "username": user, "user_group": gid, "uid": uid},
        )
```

- [ ] **Step 4: Migrate Hostloc**

Create `checkin/tasks/hostloc.py` by moving `visit_random_profiles()` and `get_user_credits()` from `checkin_hostloc.py`, with this public interface:

```python
from __future__ import annotations

from curl_cffi import requests

from checkin.core.result import CheckinResult


def run(cookie: str) -> CheckinResult:
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    }
    with requests.Session() as session:
        visit_random_profiles(session, headers)
        credits = get_user_credits(session, headers)
        if not credits:
            return CheckinResult.failed("❌ 未能获取积分信息")
        return CheckinResult.success(
            f"💎 金钱: {credits['money']} | 🏆 积分: {credits['points']}",
            credits,
        )
```

- [ ] **Step 5: Convert legacy scripts to wrappers**

Replace each legacy script with the same wrapper pattern, changing the module and secret names:

```python
import os
import sys

from checkin.tasks.doingfb import run


if __name__ == "__main__":
    cookie = os.environ.get("COOKIE_DOINGFB")
    if not cookie:
        print("错误：未找到 COOKIE_DOINGFB，请在 GitHub Secrets 中配置。")
        sys.exit(1)
    result = run(cookie)
    print(result.message)
    print(result.to_summary_line())
    sys.exit(0 if result.status == "success" else 1)
```

Use `checkin.tasks.enshan` with `COOKIE_ENSHAN` in `checkin_enshan.py`, and `checkin.tasks.hostloc` with `COOKIE_HOSTLOC` in `checkin_hostloc.py`.

- [ ] **Step 6: Run unit tests and import checks**

Run: `pytest tests -v`

Expected: PASS.

Run: `python run_checkin.py --task doingfb`

Expected without secrets: exits with code 1 and prints a failed summary mentioning `COOKIE_DOINGFB`.

- [ ] **Step 7: Commit**

```bash
git add checkin/tasks/__init__.py checkin/tasks/doingfb.py checkin/tasks/enshan.py checkin/tasks/hostloc.py checkin_doingfb.py checkin_enshan.py checkin_hostloc.py
git commit -m "refactor: migrate existing checkins to task modules"
```

## Task 5: Add SMZDM Task

**Files:**
- Create: `checkin/tasks/smzdm.py`
- Modify: `checkin_config.json`

- [ ] **Step 1: Implement SMZDM task module**

Create `checkin/tasks/smzdm.py`:

```python
from __future__ import annotations

import hashlib
import re
import time
from typing import Any

import requests

from checkin.core.result import CheckinResult


APP_KEY = "apr1$AwP!wRRT$gJ/q.X24poeBInlUJC"
APP_VERSION = "10.4.1"
APP_SK = "ierkM0OZZbsuBKLoAgQ6OJneLMXBQXmzX+LXkNTuKch8Ui2jGlahuFyWIzBiDq/L"


def run(cookie: str) -> CheckinResult:
    headers = {
        "Host": "user-api.smzdm.com",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie,
        "User-Agent": "smzdm_android_V10.4.1 rv:841 (22021211RC;Android12;zh)smzdmapp",
    }
    active_messages = _safe_active(cookie)
    token = robot_token(headers)
    error_msg, data = sign(headers, token)
    reward_messages = all_reward(headers, data)

    details = {
        "sign_result": error_msg,
        "activity": active_messages,
        "rewards": reward_messages,
    }
    reward_text = "，".join(item["value"] for item in reward_messages if item.get("value"))
    message = f"什么值得买: {error_msg}"
    if reward_text:
        message = f"{message}，{reward_text}"
    return CheckinResult.success(message, details)


def robot_token(headers: dict[str, str]) -> str:
    ts = round(time.time() * 1000)
    data = {
        "f": "android",
        "v": APP_VERSION,
        "weixin": 1,
        "time": ts,
        "sign": _md5_upper(f"f=android&time={ts}&v={APP_VERSION}&weixin=1&key={APP_KEY}"),
    }
    resp = requests.post(
        url="https://user-api.smzdm.com/robot/token",
        headers=headers,
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload["data"]["token"]


def sign(headers: dict[str, str], token: str) -> tuple[str, dict[str, Any]]:
    time_stamp = round(time.time() * 1000)
    data = {
        "f": "android",
        "v": APP_VERSION,
        "sk": APP_SK,
        "weixin": 1,
        "time": time_stamp,
        "token": token,
        "sign": _md5_upper(
            f"f=android&sk={APP_SK}&time={time_stamp}&token={token}&v={APP_VERSION}&weixin=1&key={APP_KEY}"
        ),
    }
    resp = requests.post(
        url="https://user-api.smzdm.com/checkin",
        headers=headers,
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    return str(payload.get("error_msg", "签到接口无返回消息")), data


def all_reward(headers: dict[str, str], data: dict[str, Any]) -> list[dict[str, str]]:
    resp = requests.post(
        url="https://user-api.smzdm.com/checkin/all_reward",
        headers=headers,
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    normal_reward = payload.get("data", {}).get("normal_reward")
    if not normal_reward:
        return []

    reward_add = normal_reward.get("reward_add", {})
    messages: list[dict[str, str]] = []
    if reward_add.get("content"):
        messages.append({"name": "签到奖励", "value": str(reward_add["content"])})
    if normal_reward.get("sub_title"):
        messages.append({"name": "连续签到", "value": str(normal_reward["sub_title"])})
    return messages


def active(cookie: str) -> list[dict[str, str]]:
    active_id = "ljX8qVlEA7"
    headers = {
        "Host": "zhiyou.smzdm.com",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/smzdm 10.4.6 rv:130.1 (iPhone 13; iOS 15.6; zh_CN)/iphone_smzdmapp/10.4.6/wkwebview/jsbv_1.0.0",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Referer": "https://m.smzdm.com/",
        "Accept-Encoding": "gzip, deflate, br",
    }
    draw_url = f"https://zhiyou.smzdm.com/user/lottery/jsonp_draw?active_id={active_id}"
    info_url = "https://zhiyou.smzdm.com/user/"
    draw_payload = requests.post(draw_url, headers=headers, timeout=30).json()
    account_html = requests.get(info_url, headers=headers, timeout=30).text
    return [
        {"name": "活动结果", "value": str(draw_payload.get("error_msg", "活动接口无返回消息"))},
        {"name": "等级", "value": _extract_first(r'level/(.*?).png\?v=1', account_html)},
        {"name": "昵称", "value": _extract_first(r'<a href="https://zhiyou.smzdm.com/user"> (.*?) </a>', account_html)},
        {
            "name": "金币",
            "value": _clean_asset(
                _extract_first(
                    r'<div class="assets-part assets-gold">\n\s*(.*?)</span>',
                    account_html,
                )
            ),
        },
        {
            "name": "碎银",
            "value": _clean_asset(
                _extract_first(
                    r'<div class="assets-part assets-prestige">\n\s*(.*?)</span>',
                    account_html,
                )
            ),
        },
    ]


def _safe_active(cookie: str) -> list[dict[str, str]]:
    try:
        return active(cookie)
    except Exception:
        return [{"name": "活动结果", "value": "活动接口失败，不影响主签到"}]


def _md5_upper(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest().upper()


def _extract_first(pattern: str, text: str) -> str:
    matches = re.findall(pattern, text, re.S)
    return str(matches[0]).strip() if matches else ""


def _clean_asset(value: str) -> str:
    return (
        value.replace('<span class="assets-part-element assets-num">', "")
        .replace("'’", "")
        .strip()
    )
```

- [ ] **Step 2: Use explicit SMZDM success handling**

Confirm that `sign(headers, token)` parses the JSON response and returns both `error_msg` and the exact request `data` used by `all_reward()`:

```python
def sign(headers: dict[str, str], token: str) -> tuple[str, dict[str, Any]]:
    time_stamp = round(time.time() * 1000)
    data = {
        "f": "android",
        "v": APP_VERSION,
        "sk": APP_SK,
        "weixin": 1,
        "time": time_stamp,
        "token": token,
        "sign": _md5_upper(
            f"f=android&sk={APP_SK}&time={time_stamp}&token={token}&v={APP_VERSION}&weixin=1&key={APP_KEY}"
        ),
    }
    resp = requests.post(url="https://user-api.smzdm.com/checkin", headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    return str(payload.get("error_msg", "签到接口无返回消息")), data
```

- [ ] **Step 3: Run SMZDM without secret to validate config path**

Run: `python run_checkin.py --task smzdm`

Expected without secrets: exits with code 1 and prints a failed summary mentioning `COOKIE_SMZDM`.

- [ ] **Step 4: Commit**

```bash
git add checkin/tasks/smzdm.py checkin_config.json
git commit -m "feat: add smzdm checkin task"
```

## Task 6: Workflow, Dependencies, And README

**Files:**
- Modify: `.github/workflows/daily_checkin.yml`
- Modify: `requirements.txt`
- Modify: `README.md`

- [ ] **Step 1: Update dependencies**

Replace `requirements.txt` with:

```text
requests
curl_cffi[requests]
beautifulsoup4
pytest
```

Keep Selenium, webdriver-manager, Playwright, and nodriver only if a current task still imports them after migration. The planned task modules do not require them.

- [ ] **Step 2: Update GitHub Actions environment**

In `.github/workflows/daily_checkin.yml`, add:

```yaml
      COOKIE_SMZDM: ${{ secrets.COOKIE_SMZDM }}
```

Replace the loop that manually reads `checkin_config.json` and calls each script with a simpler runner call:

```bash
python run_checkin.py 2>&1 | tee -a "checkin-logs/all-${DATE}.log"
EXIT_CODE=${PIPESTATUS[0]}
```

Build the release variables from the combined log with this shell block:

```bash
TOTAL_TASKS=$(grep -c "\[CHECKIN_SUMMARY\]" "checkin-logs/all-${DATE}.log" || true)
SUCCESS_TASKS=$(grep "\[CHECKIN_SUMMARY\]" "checkin-logs/all-${DATE}.log" | python3 -c 'import json,sys
count=0
for line in sys.stdin:
    payload=line.split("[CHECKIN_SUMMARY]", 1)[1].strip()
    if json.loads(payload).get("status") == "success":
        count += 1
print(count)' || echo "0")
TASK_RESULTS=$(grep "\[CHECKIN_SUMMARY\]" "checkin-logs/all-${DATE}.log" | python3 -c 'import json,sys
for line in sys.stdin:
    payload=line.split("[CHECKIN_SUMMARY]", 1)[1].strip()
    data=json.loads(payload)
    status="✅ 成功" if data.get("status") == "success" else "❌ 失败"
    details=data.get("details", {})
    task_name=details.get("task_name", "任务")
    message=data.get("message", "")
    print(f"- **{task_name}**: {status}")
    print(f"  - {message}")
    print()' || true)
echo "TOTAL_TASKS=$TOTAL_TASKS" >> "$GITHUB_ENV"
echo "SUCCESS_TASKS=$SUCCESS_TASKS" >> "$GITHUB_ENV"
{
  echo "TASK_RESULTS<<EOF"
  echo "$TASK_RESULTS"
  echo "EOF"
} >> "$GITHUB_ENV"
exit "$EXIT_CODE"
```

- [ ] **Step 3: Update README**

Document:

```markdown
## 支持的网站

1. DoingFB
2. 恩山无线论坛
3. Hostloc
4. 什么值得买

## 本地运行

```bash
python run_checkin.py
python run_checkin.py --task smzdm
```

## Secrets

- `COOKIE_DOINGFB`
- `COOKIE_ENSHAN`
- `COOKIE_HOSTLOC`
- `COOKIE_SMZDM`
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests -v`

Expected: PASS.

- [ ] **Step 5: Run all tasks without secrets**

Run: `python run_checkin.py`

Expected without secrets: exits with code 1, prints four failed summaries, and each failure mentions the missing Cookie Secret for that task.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/daily_checkin.yml requirements.txt README.md
git commit -m "chore: wire unified runner into workflow"
```

## Task 7: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run unit test suite**

Run: `pytest tests -v`

Expected: PASS.

- [ ] **Step 2: Run single-task missing secret check**

Run: `python run_checkin.py --task smzdm`

Expected without secrets: exits with code 1 and prints `[CHECKIN_SUMMARY] {"status": "failed", ... "COOKIE_SMZDM" ...}`.

- [ ] **Step 3: Run full missing secret check**

Run: `python run_checkin.py`

Expected without secrets: exits with code 1 and prints one `[CHECKIN_SUMMARY]` line for each configured task.

- [ ] **Step 4: Review changed files**

Run: `git status --short`

Expected: clean after all commits, or only intentional uncommitted changes if the user asked to stop before committing.

Run: `git log --oneline -6`

Expected: recent commits show the PRD commit plus implementation commits from this plan.
