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
