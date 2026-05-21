import json

import pytest

from checkin.core.config import AccountConfig, TaskConfig, load_task_configs


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
            accounts=(
                AccountConfig(
                    id="default",
                    name="默认账号",
                    cookie_secret="COOKIE_DEMO",
                ),
            ),
        )
    ]
    assert configs[0].cookie_secret == "COOKIE_DEMO"


def test_load_task_configs_reads_accounts_schema(tmp_path):
    config_path = tmp_path / "checkin_config.json"
    config_path.write_text(
        json.dumps(
            {
                "checkin_tasks": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "module": "checkin.tasks.demo",
                        "accounts": [
                            {
                                "id": "main",
                                "name": "主账号",
                                "cookie_secret": "COOKIE_DEMO",
                            },
                            {
                                "id": "alt",
                                "name": "备用账号",
                                "cookie_secret": "COOKIE_DEMO_ALT",
                            },
                        ],
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
            accounts=(
                AccountConfig(id="main", name="主账号", cookie_secret="COOKIE_DEMO"),
                AccountConfig(id="alt", name="备用账号", cookie_secret="COOKIE_DEMO_ALT"),
            ),
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


def test_load_task_configs_rejects_non_object_root(tmp_path):
    config_path = tmp_path / "checkin_config.json"
    config_path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="config root must be an object"):
        load_task_configs(config_path)


def test_load_task_configs_requires_checkin_tasks_key(tmp_path):
    config_path = tmp_path / "checkin_config.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(ValueError, match="checkin_tasks"):
        load_task_configs(config_path)


def test_load_task_configs_rejects_empty_accounts(tmp_path):
    config_path = tmp_path / "checkin_config.json"
    config_path.write_text(
        json.dumps(
            {
                "checkin_tasks": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "module": "checkin.tasks.demo",
                        "accounts": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="accounts must not be empty"):
        load_task_configs(config_path)


def test_load_task_configs_rejects_duplicate_account_ids(tmp_path):
    config_path = tmp_path / "checkin_config.json"
    config_path.write_text(
        json.dumps(
            {
                "checkin_tasks": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "module": "checkin.tasks.demo",
                        "accounts": [
                            {"id": "main", "name": "主账号", "cookie_secret": "COOKIE_DEMO"},
                            {"id": "main", "name": "重复账号", "cookie_secret": "COOKIE_DEMO_2"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate account id"):
        load_task_configs(config_path)
