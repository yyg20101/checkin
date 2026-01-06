# 自动签到脚本集合

这个项目包含了多个网站的自动签到脚本，通过 GitHub Actions 实现每日自动执行。

## 支持的网站

1. **DoingFB** - 使用 `checkin_doingfb.py`
2. **恩山无线论坛** - 使用 `checkin_enshan.py`
3. **Hostloc** - 使用 `checkin_hostloc.py`

## 新版统一工作流

### 优化特性

- **并行执行**: 使用 GitHub Actions 矩阵策略，多个签到任务并行执行
- **性能优化**: 
  - 启用 pip 缓存，减少依赖安装时间
  - 限制最大并发数为 2，避免对目标网站造成压力
  - 按需安装依赖，每个任务只安装必要的包
- **容错机制**: 
  - 单个任务失败不影响其他任务执行
  - 失败时自动上传日志文件便于调试
- **状态汇总**: 提供整体执行状态概览

### 配置说明

需要在 GitHub Secrets 中配置以下变量：

- `COOKIE_DOINGFB` - DoingFB 网站的 Cookie
- `COOKIE_ENSHAN` - 恩山论坛的 Cookie  
- `COOKIE_HOSTLOC` - Hostloc 论坛的 Cookie

### 执行时间

- **自动执行**: 每天 UTC 22:00 (北京时间上午 6:00)
- **手动触发**: 支持在 GitHub Actions 页面手动运行

### 工作流文件

- **新版统一工作流**: `.github/workflows/unified_daily_checkin.yml`

## 依赖说明

- `requests` - HTTP 请求库
- `curl_cffi[requests]` - 模拟浏览器请求，防止被反爬虫检测

## 使用方法

1. Fork 这个仓库
2. 在仓库设置中添加必要的 Secrets
3. 启用 GitHub Actions
4. 工作流将自动每日执行，或可手动触发