import types

from checkin.core.config import AccountConfig, TaskConfig
from checkin.core.result import CheckinResult
from checkin.core.runner import print_task_runs, run_tasks


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
    assert results[0].account.id == "default"


def test_run_tasks_reports_missing_cookie(monkeypatch):
    configs = [TaskConfig("one", "One", "checkin.tasks.one", "COOKIE_ONE")]
    monkeypatch.delenv("COOKIE_ONE", raising=False)

    results = run_tasks(configs, import_module=lambda name: None)

    assert results[0].result.status == "failed"
    assert "COOKIE_ONE" in results[0].result.message
    assert results[0].account.cookie_secret == "COOKIE_ONE"


def test_run_tasks_expands_multiple_accounts(monkeypatch):
    configs = [
        TaskConfig(
            "one",
            "One",
            "checkin.tasks.one",
            (
                AccountConfig("main", "主账号", "COOKIE_ONE_MAIN"),
                AccountConfig("alt", "备用账号", "COOKIE_ONE_ALT"),
            ),
        )
    ]
    monkeypatch.setenv("COOKIE_ONE_MAIN", "cookie-main")
    monkeypatch.setenv("COOKIE_ONE_ALT", "cookie-alt")

    def fake_import(module_name):
        return types.SimpleNamespace(run=lambda cookie: CheckinResult.success(f"ran {cookie}"))

    results = run_tasks(configs, import_module=fake_import)

    assert [(item.account.id, item.result.message) for item in results] == [
        ("main", "ran cookie-main"),
        ("alt", "ran cookie-alt"),
    ]


def test_run_tasks_isolates_missing_cookie_by_account(monkeypatch):
    configs = [
        TaskConfig(
            "one",
            "One",
            "checkin.tasks.one",
            (
                AccountConfig("main", "主账号", "COOKIE_ONE_MAIN"),
                AccountConfig("alt", "备用账号", "COOKIE_ONE_ALT"),
            ),
        )
    ]
    monkeypatch.setenv("COOKIE_ONE_MAIN", "cookie-main")
    monkeypatch.delenv("COOKIE_ONE_ALT", raising=False)

    def fake_import(module_name):
        return types.SimpleNamespace(run=lambda cookie: CheckinResult.success(f"ran {cookie}"))

    results = run_tasks(configs, import_module=fake_import)

    assert [(item.account.id, item.result.status, item.result.message) for item in results] == [
        ("main", "success", "ran cookie-main"),
        ("alt", "failed", "缺少环境变量 COOKIE_ONE_ALT"),
    ]


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


def test_run_tasks_rejects_invalid_result_status(monkeypatch):
    configs = [TaskConfig("one", "One", "checkin.tasks.one", "COOKIE_ONE")]
    monkeypatch.setenv("COOKIE_ONE", "cookie-one")

    def fake_import(module_name):
        return types.SimpleNamespace(run=lambda cookie: CheckinResult(status="error", message="bad"))

    results = run_tasks(configs, import_module=fake_import)

    assert results[0].result.status == "failed"
    assert "无效状态" in results[0].result.message
    assert "error" in results[0].result.message


def test_print_task_runs_includes_account_details(capsys):
    config = TaskConfig(
        "one",
        "One",
        "checkin.tasks.one",
        (AccountConfig("main", "主账号", "COOKIE_ONE_MAIN"),),
    )
    runs = [
        types.SimpleNamespace(
            config=config,
            account=config.accounts[0],
            result=CheckinResult.success("ok"),
        )
    ]

    print_task_runs(runs)

    output = capsys.readouterr().out
    assert "One / 主账号" in output
    assert '"account_id": "main"' in output
    assert '"account_name": "主账号"' in output
    assert '"cookie_secret": "COOKIE_ONE_MAIN"' in output
