# WorkBuddy 签到

云端每日自动打卡：由 **GitHub Actions** 每天早上 **08:00（北京时间）** 自动执行，**不需要开着你的电脑**。

## 原理

```text
GitHub Actions (cron 08:00 CST)
        → scripts/checkin.py
        → data/checkins.json  (提交回仓库)
        → GitHub Pages 展示连续天数 / 日历
```

## 功能

- 每日自动打卡（Actions 定时）
- 连续天数、累计次数
- 日历与最近记录
- 支持在 GitHub 上手动运行（workflow_dispatch）

## 手动跑一次

仓库页 → **Actions** → **Daily Check-in** → **Run workflow**

## 查看统计

1. 仓库 **Settings → Pages**
2. Source 选 `Deploy from a branch`，分支 `main`，目录 `/ (root)`
3. 保存后访问：`https://newtypepan12-svg.github.io/workbuddy-qiandao/`

## 本地调试

```powershell
python scripts/checkin.py
```

## 数据

- 打卡记录：`data/checkins.json`
- 最近一次运行：`data/last-run.json`
