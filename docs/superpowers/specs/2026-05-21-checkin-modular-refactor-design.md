# 自动签到模块化重构与 SMZDM 集成 PRD

## 1. Executive Summary

- **Problem Statement**: 当前项目由多个独立签到脚本组成，每个脚本重复处理 Cookie 读取、异常捕获、日志输出和结果摘要，新增站点会继续复制这些样板逻辑。GitHub Actions 依赖脚本各自约定输出，失败原因和本地单任务调试也不够集中。
- **Proposed Solution**: 引入轻量模块化 Task 架构：站点逻辑只负责请求和解析，统一 runner 负责配置加载、环境变量读取、异常隔离、任务筛选和 `[CHECKIN_SUMMARY]` 输出。同时新增什么值得买（SMZDM）签到 task，并接入现有每日执行流程。
- **Success Criteria**:
  - 新增站点只需新增 1 个 task 模块和 1 条 `checkin_config.json` 配置，不需要复制 runner/CI 汇总代码。
  - `python run_checkin.py --task smzdm` 可只执行 SMZDM，退出码和摘要可用于本地调试。
  - 任意单站点执行失败时，runner 继续执行后续任务，并在最终汇总中标记失败站点和失败原因。
  - 所有任务保持统一 `[CHECKIN_SUMMARY]` JSON 输出，现有 GitHub Actions 日志汇总语义不退化。
  - Cookie、请求头等敏感值不在正常日志中完整打印。

## 2. User Experience & Functionality

- **User Personas**:
  - 仓库维护者：维护多个站点签到脚本，并希望后续接入新站点时变更范围小。
  - 自动化使用者：依赖 GitHub Actions 每日执行签到，希望失败时能快速定位是哪一个站点出问题。
  - 本地调试者：需要在本地只运行某一个站点，验证 Cookie 或接口变更。

- **User Stories**:
  - As a maintainer, I want each site check-in to implement the same task interface so that adding a new site does not require copying runner logic.
  - As an automation user, I want one site failure to be isolated so that other check-ins still run.
  - As a local debugger, I want to run a single named task so that I can validate one site's Cookie or request flow quickly.
  - As an SMZDM user, I want SMZDM included in the daily check-in list so that it is executed with the same schedule and summary reporting.

- **Acceptance Criteria**:
  - Task modules expose a uniform callable such as `run(cookie: str) -> CheckinResult`.
  - `CheckinResult` contains `status`, `message`, and `details`, and can serialize to the existing `[CHECKIN_SUMMARY]` JSON format.
  - `run_checkin.py` supports running all configured tasks and running one task by id.
  - `checkin_config.json` includes `doingfb`, `enshan`, `hostloc`, and `smzdm` task declarations with display name, module path, and Secret name.
  - SMZDM uses `COOKIE_SMZDM` and returns a success summary for already-signed or newly-signed states when the upstream API reports a non-fatal result.
  - Missing Cookie or unexpected task exceptions are reported as task-level failures without preventing later tasks from running.
  - GitHub Actions invokes the unified runner and passes `COOKIE_SMZDM` along with existing Cookie Secrets.

- **Non-Goals**:
  - Do not build a database, web UI, notification bot, or account management system.
  - Do not rewrite the project into a published Python package.
  - Do not introduce browser automation for SMZDM unless the HTTP API flow stops working.
  - Do not make live network tests mandatory in CI because they require private Cookies and depend on third-party sites.

## 3. AI System Requirements (If Applicable)

- **Tool Requirements**: Not applicable. This project does not add an AI feature.
- **Evaluation Strategy**: Not applicable for AI quality. Validation is covered by unit tests and manual/local task execution.

## 4. Technical Specifications

- **Architecture Overview**:
  - `run_checkin.py` is the single command entrypoint.
  - `checkin/core/result.py` defines `CheckinResult` and summary serialization.
  - `checkin/core/config.py` loads and validates `checkin_config.json`.
  - `checkin/core/runner.py` resolves task modules, reads the configured Cookie environment variable, runs each task, catches exceptions, and prints summaries.
  - `checkin/tasks/*.py` contains site-specific logic for DoingFB, Enshan, Hostloc, and SMZDM.
  - Existing one-off scripts can either become thin wrappers around the task modules or be replaced by the unified runner after the workflow is updated.

- **Integration Points**:
  - GitHub Secrets: existing `COOKIE_DOINGFB`, `COOKIE_ENSHAN`, `COOKIE_HOSTLOC`; new `COOKIE_SMZDM`.
  - GitHub Actions: `.github/workflows/daily_checkin.yml` installs dependencies, exports Cookie Secrets, calls `python run_checkin.py`, archives generated logs, and creates the release summary.
  - SMZDM APIs adapted from upstream:
    - `https://user-api.smzdm.com/robot/token`
    - `https://user-api.smzdm.com/checkin`
    - `https://user-api.smzdm.com/checkin/all_reward`
    - Optional account/activity endpoints under `https://zhiyou.smzdm.com/user/`

- **Security & Privacy**:
  - Do not print full Cookie values or full request headers containing Cookie.
  - Keep Cookie access in the runner via environment variables.
  - Task logs may include status code, response shape, and parsed account metadata, but should avoid sensitive raw payloads by default.
  - SMZDM upstream constants used for signing are treated as public client parameters copied from the upstream implementation, not user secrets.

## 5. Risks & Roadmap

- **Phased Rollout**:
  - **MVP**: Introduce core result/config/runner modules, migrate existing three tasks, add SMZDM task, update config and workflow.
  - **v1.1**: Add focused unit tests for config loading, task selection, exception handling, and summary serialization.
  - **v2.0**: Consider matrix-based GitHub Actions parallelization if runtime or failure isolation becomes a stronger requirement.

- **Technical Risks**:
  - Third-party site HTML/API responses may change without notice, especially SMZDM reward/account parsing.
  - SMZDM activity draw may fail independently from normal check-in; it should not block the main sign-in result.
  - Existing scripts print verbose debug output, including request headers in some paths; migration must reduce sensitive log exposure.
  - GitHub Actions release-summary behavior depends on consistent summary output; runner changes must preserve parseable JSON summaries.

