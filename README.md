# 自动签到脚本集合

这个项目通过统一 runner 执行多个网站的自动签到任务，并由 GitHub Actions 每日自动运行、归档日志和生成执行摘要。

## 每日统一任务

每日任务由 `checkin_config.json` 控制，当前纳入统一执行的网站：

1. **DoingFB**
2. **Hostloc**
3. **什么值得买**

已实现但暂不纳入统一每日任务：

- **恩山无线论坛**：保留 `checkin/tasks/enshan.py` 和 `checkin_enshan.py` 兼容入口，后续需要时再加入 `checkin_config.json`。

## 项目结构

```text
checkin/
  core/
    config.py      # 读取并校验任务配置
    result.py      # 统一签到结果与摘要格式
    runner.py      # 任务筛选、执行、异常隔离和汇总输出
  tasks/
    doingfb.py
    enshan.py      # 已实现，暂未纳入每日统一任务
    hostloc.py
    smzdm.py
run_checkin.py     # 统一命令行入口
checkin_config.json
```

每个站点 task 暴露 `run(cookie: str) -> CheckinResult`。新增站点时，通常只需要新增一个 `checkin/tasks/*.py` 文件，并在 `checkin_config.json` 中添加一条配置。

新增站点接入规范见 `docs/new-site-task-template.md`。

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
- `COOKIE_HOSTLOC`
- `COOKIE_SMZDM`

可选变量：

- `COOKIE_ENSHAN`：仅在手动运行 `checkin_enshan.py` 或未来把恩山加入 `checkin_config.json` 时需要。

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
- Release 摘要会展示每个任务的状态、主消息和 `details` 明细，便于每天查看积分、连续签到、奖励和失败原因

## 依赖

- `requests`
- `curl_cffi`
- `beautifulsoup4`
- `pytest`
