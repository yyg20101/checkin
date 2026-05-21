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
