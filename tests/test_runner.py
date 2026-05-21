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


def test_run_tasks_rejects_invalid_result_status(monkeypatch):
    configs = [TaskConfig("one", "One", "checkin.tasks.one", "COOKIE_ONE")]
    monkeypatch.setenv("COOKIE_ONE", "cookie-one")

    def fake_import(module_name):
        return types.SimpleNamespace(run=lambda cookie: CheckinResult(status="error", message="bad"))

    results = run_tasks(configs, import_module=fake_import)

    assert results[0].result.status == "failed"
    assert "无效状态" in results[0].result.message
    assert "error" in results[0].result.message
