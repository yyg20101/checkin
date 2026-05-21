# 自动签到脚本集合

这个项目通过统一 runner 执行多个网站的自动签到任务，并由 GitHub Actions 每日自动运行、归档日志和生成执行摘要。

## 支持的网站

1. **DoingFB**
2. **恩山无线论坛**
3. **Hostloc**
4. **什么值得买**

## 项目结构

```text
checkin/
  core/
    config.py      # 读取并校验任务配置
    result.py      # 统一签到结果与摘要格式
    runner.py      # 任务筛选、执行、异常隔离和汇总输出
  tasks/
    doingfb.py
    enshan.py
    hostloc.py
    smzdm.py
run_checkin.py     # 统一命令行入口
checkin_config.json
```

每个站点 task 暴露 `run(cookie: str) -> CheckinResult`。新增站点时，通常只需要新增一个 `checkin/tasks/*.py` 文件，并在 `checkin_config.json` 中添加一条配置。

## 本地运行

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

运行全部任务：

```bash
python3 run_checkin.py
```

只运行某一个任务：

```bash
python3 run_checkin.py --task smzdm
```

可用任务 id 由 `checkin_config.json` 中的 `id` 字段决定。

## Secrets

需要在 GitHub Secrets 中配置以下变量：

- `COOKIE_DOINGFB`
- `COOKIE_ENSHAN`
- `COOKIE_HOSTLOC`
- `COOKIE_SMZDM`

本地调试时，可以通过同名环境变量传入 Cookie。

## GitHub Actions

工作流文件：

- `.github/workflows/daily_checkin.yml`

执行时间：

- 自动执行：每天 UTC 1:00，对应北京时间上午 9:00
- 手动触发：支持在 GitHub Actions 页面手动运行

执行方式：

- GitHub Actions 调用 `python run_checkin.py`
- runner 会继续执行后续任务，即使单个站点失败
- 每个任务都会输出 `[CHECKIN_SUMMARY]` JSON 摘要
- workflow 会上传日志 artifact，并创建当天的 Release 摘要

## 依赖

- `requests`
- `curl_cffi`
- `beautifulsoup4`
- `pytest`
