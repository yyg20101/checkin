import json

from checkin.core import report


def test_build_task_results_renders_status_and_details():
    summaries = [
        {
            "status": "success",
            "message": "签到成功\n第二行",
            "details": {
                "task_id": "demo",
                "task_name": "Demo",
                "account_id": "main",
                "account_name": "主账号",
                "coins": 10,
                "rewards": [
                    {"name": "签到奖励", "value": "+10 金币"},
                    {"name": "连续签到", "value": "3 天"},
                ],
            },
        },
        {
            "status": "failed",
            "message": "Cookie 缺失",
            "details": {"task_name": "Other"},
        },
    ]

    total_tasks, success_tasks, task_results = report.build_task_results(summaries)

    assert total_tasks == 2
    assert success_tasks == 1
    assert "**Demo / 主账号:** ✅ 成功" in task_results
    assert "  - 签到成功 第二行" in task_results
    assert "  - **硬币/金币:** 10" in task_results
    assert "  - **奖励详情:**" in task_results
    assert "    - 签到奖励: +10 金币" in task_results
    assert "    - 连续签到: 3 天" in task_results
    assert "**Other:** ❌ 失败" in task_results
    assert "账号 ID" not in task_results


def test_write_github_env_reads_summary_lines(tmp_path):
    log_path = tmp_path / "checkin.log"
    env_path = tmp_path / "github.env"
    payload = {
        "status": "skipped",
        "message": "跳过",
        "details": {"task_name": "Demo"},
    }
    log_path.write_text(
        "normal line\n" f"{report.SUMMARY_MARKER} {json.dumps(payload, ensure_ascii=False)}\n",
        encoding="utf-8",
    )

    report.write_github_env(log_path, env_path)

    output = env_path.read_text(encoding="utf-8")
    assert "TOTAL_TASKS=1\n" in output
    assert "SUCCESS_TASKS=0\n" in output
    assert f"TASK_RESULTS<<{report.ENV_MULTILINE_DELIMITER}\n" in output
    assert "**Demo:** ⏭️ 跳过" in output
    assert output.endswith(f"\n{report.ENV_MULTILINE_DELIMITER}\n")
