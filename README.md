# 自动签到脚本集合

这个项目通过统一 runner 执行多个网站的自动签到任务，并由 GitHub Actions 每日自动运行、归档日志和生成执行摘要。

## 每日统一任务

每日任务由 `checkin_config.json` 控制，当前纳入统一执行的网站：

1. **DoingFB**
2. **Hostloc**
3. **Hifiti**
4. **MT管理器论坛**
5. **V2EX**
6. **什么值得买**

已实现但暂不纳入统一每日任务：

- **恩山无线论坛**：已按 qd-today HAR 流程更新 `checkin/tasks/enshan.py`，保留 `legacy/checkin_enshan.py` 兼容入口，后续需要时再加入 `checkin_config.json`。

## 项目结构

```text
checkin/
  core/
    config.py      # 读取并校验任务配置
    result.py      # 统一签到结果与摘要格式
    runner.py      # 任务筛选、执行、异常隔离和汇总输出
  tasks/
    binmt.py
    doingfb.py
    enshan.py      # 已实现，暂未纳入每日统一任务
    hifiti.py
    hostloc.py
    smzdm.py
    v2ex.py
legacy/
  checkin_doingfb.py   # 旧单站点兼容入口
  checkin_enshan.py
  checkin_hostloc.py
tools/
  cocos_file_copy.py   # 非签到主链路工具脚本
  driver_options.py
  lsb.py
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

需要在 GitHub Secrets 中配置的变量与网站对应关系如下：

| Secret 变量 | 网站 | task id | 当前状态 |
| --- | --- | --- | --- |
| `COOKIE_DOINGFB` | DoingFB | `doingfb` | 每日任务 |
| `COOKIE_HOSTLOC` | Hostloc | `hostloc` | 每日任务 |
| `COOKIE_HIFITI` | Hifiti | `hifiti` | 每日任务 |
| `COOKIE_BINMT` | MT管理器论坛 | `binmt` | 每日任务 |
| `COOKIE_V2EX` | V2EX | `v2ex` | 每日任务 |
| `COOKIE_SMZDM` | 什么值得买 | `smzdm` | 每日任务 |
| `COOKIE_ENSHAN` | 恩山无线论坛 | `enshan` | 可选，暂不进入每日任务 |

本地调试时，可以通过同名环境变量传入 Cookie。

## 多账号配置

`checkin_config.json` 同时支持旧的单账号格式和新的多账号格式。旧格式会自动当作一个默认账号执行：

```json
{
  "id": "v2ex",
  "name": "V2EX",
  "module": "checkin.tasks.v2ex",
  "cookie_secret": "COOKIE_V2EX"
}
```

推荐在 GitHub Actions 中继续只配置一个 Secret，例如 `COOKIE_V2EX`，再通过 Secret 值里的特殊分隔符区分单账号和多账号。

单账号时，Secret 值直接填 Cookie：

```text
foo=bar; session=xxx
```

多账号时，账号之间用 `---CHECKIN_ACCOUNT---` 分隔：

```text
foo=bar; session=xxx---CHECKIN_ACCOUNT---foo=bar; session=yyy
```

如果希望 Release 摘要显示账号名，可以在每个账号前加上账号名，并用 `---CHECKIN_COOKIE---` 分隔账号名和 Cookie：

```text
主账号---CHECKIN_COOKIE---foo=bar; session=xxx---CHECKIN_ACCOUNT---备用账号---CHECKIN_COOKIE---foo=bar; session=yyy
```

runner 只有在 Secret 值包含 `---CHECKIN_ACCOUNT---` 或 `---CHECKIN_COOKIE---` 时才按多账号解析；普通 Cookie 会保持单账号流程。

也可以使用 `accounts` 配置多个不同的 Secret 变量：

```json
{
  "id": "v2ex",
  "name": "V2EX",
  "module": "checkin.tasks.v2ex",
  "accounts": [
    {
      "id": "main",
      "name": "主账号",
      "cookie_secret": "COOKIE_V2EX"
    },
    {
      "id": "alt",
      "name": "备用账号",
      "cookie_secret": "COOKIE_V2EX_ALT"
    }
  ]
}
```

这种方式需要同时在 `.github/workflows/daily_checkin.yml` 的 `env` 中显式暴露每个 Secret。GitHub Actions 不会自动把所有仓库 Secrets 作为环境变量传给脚本。

runner 会把每个账号作为独立执行单元输出摘要，例如 `V2EX / 主账号`、`V2EX / 备用账号`。单个账号失败不会阻止同站点其他账号或其他站点继续执行。Release 摘要会展示账号名称和 Secret 变量名，但不会打印 Cookie 内容。

## 根目录整理

主流程只需要根目录的 `run_checkin.py`、`checkin_config.json`、`requirements.txt` 和项目文档。

- `checkin_*.py` 旧入口不参与 GitHub Actions，也不被统一 runner 引用；它们已移到 `legacy/`，只用于兼容手动单站点运行。
- `lsb.py`、`cocos_file_copy.py`、`driver_options.py` 不属于签到主链路；它们已移到 `tools/`。
- 新增站点请优先放在 `checkin/tasks/`，并通过 `checkin_config.json` 接入。

## GitHub Actions

工作流文件：

- `.github/workflows/daily_checkin.yml`

执行时间：

- 自动执行：每天北京时间上午 8:17（避开 GitHub Actions 整点调度高峰，实际启动仍可能受平台排队影响）
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
