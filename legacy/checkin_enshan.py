import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    cookie = os.environ.get("COOKIE_ENSHAN")
    if not cookie:
        print("错误：未找到 COOKIE_ENSHAN，请在 GitHub Secrets 中配置。")
        sys.exit(1)
    from checkin.tasks.enshan import run

    result = run(cookie)
    print(result.message)
    print(result.to_summary_line())
    sys.exit(0 if result.status == "success" else 1)
