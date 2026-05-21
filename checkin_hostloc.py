import os
import sys


if __name__ == "__main__":
    cookie = os.environ.get("COOKIE_HOSTLOC")
    if not cookie:
        print("错误：未找到 COOKIE_HOSTLOC，请在 GitHub Secrets 中配置。")
        sys.exit(1)
    from checkin.tasks.hostloc import run

    result = run(cookie)
    print(result.message)
    print(result.to_summary_line())
    sys.exit(0 if result.status == "success" else 1)
