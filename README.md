# WorkBuddy 签到

自动领取腾讯 **WorkBuddy**「Buddy 加油站」每日积分（约 100 分，连签有额外奖励）。

由 **GitHub Actions** 每天 **09:05（北京时间）** 在云端执行，**电脑不用开机**。

## 原理

```text
GitHub Secrets 存 WorkBuddy accessToken
        ↓
每天 09:05 Actions 运行 scripts/checkin.py
        ↓
调用官方签到接口（与桌面客户端相同）
        ↓
结果写入 data/ 并由 Pages 统计页展示
```

接口：
- 状态：`POST /v2/billing/meter/checkin-activity-status`
- 领取：`POST /v2/billing/meter/daily-checkin`

## 一次性配置（必须）

1. 打开本机登录态文件（登录过 WorkBuddy 桌面端后会存在）：
   - Windows：`%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info`
   - macOS：`~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info`
2. 复制 `auth.accessToken`、`account.uid`、`auth.domain`（不要发给别人、不要提交到仓库）
3. 打开仓库 **Settings → Secrets and variables → Actions**，新建：

| Name | Value |
|------|--------|
| `WORKBUDDY_ACCESS_TOKEN` | `auth.accessToken` 整段 |
| `WORKBUDDY_UID` | `account.uid` |
| `WORKBUDDY_DOMAIN` | 一般是 `copilot.tencent.com` |

4. **Actions** → **WorkBuddy Daily Check-in** → **Run workflow** 试跑一次

> `accessToken` 等同账号登录态。仓库建议设为 **Private**；token 过期后重新登录 WorkBuddy，再更新 Secret 即可，不用改代码。

## 本地调试

```powershell
python scripts/checkin.py
```

本机会自动读桌面端登录态，不需要配 Secret。

## 查看统计

- 工作流日志 / Summary 看当天结果
- Pages：`https://newtypepan12-svg.github.io/workbuddy-qiandao/`（连续天数、日历）

## 说明

- 幂等：今日已签到会直接返回成功，不会重复领
- 仅操作你自己的账号，等价于每天点一次「领取」
- 非官方脚本，接口可能变动；与腾讯无隶属关系，使用风险自负
