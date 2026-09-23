#!/usr/bin/env python3
"""腾讯 WorkBuddy「Buddy 加油站」每日签到。

凭证来源（优先级）：
1. 环境变量 WORKBUDDY_ACCESS_TOKEN（GitHub Actions / 云端）
2. 本机 WorkBuddy 桌面端登录态文件

成功后写入 data/checkins.json 供统计页展示。绝不打印 token。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "checkins.json"
LAST_RUN = ROOT / "data" / "last-run.json"
TZ = timezone(timedelta(hours=8))  # Asia/Shanghai

# 官方客户端同一组接口；不同版本域名可能切换，按候选依次尝试
API_HOSTS = (
    os.environ.get("WORKBUDDY_DOMAIN", "").strip() or "copilot.tencent.com",
    "www.codebuddy.cn",
    "copilot.tencent.com",
)

AUTH_CANDIDATES = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info",
    Path(os.environ.get("APPDATA", "")) / "CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info",
    Path.home() / "Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info",
    Path(os.environ.get("LOCALAPPDATA", "")) / "WorkBuddy/Data/Public/auth/workbuddy-desktop.info",
)


def log(msg: str) -> None:
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def load_credentials() -> dict | None:
    token = os.environ.get("WORKBUDDY_ACCESS_TOKEN", "").strip()
    if token:
        log("使用环境变量 WORKBUDDY_ACCESS_TOKEN")
        return {
            "accessToken": token,
            "uid": os.environ.get("WORKBUDDY_UID", "").strip() or None,
            "domain": os.environ.get("WORKBUDDY_DOMAIN", "").strip() or "copilot.tencent.com",
        }

    for path in AUTH_CANDIDATES:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"读取登录态失败 ({path}): {e}")
            continue
        auth = data.get("auth") or {}
        account = data.get("account") or {}
        raw_tok = auth.get("accessToken")
        # 新版 WorkBuddy 会把 token 加密成 {"$wbEncrypted":1,"envelope":"..."}
        if isinstance(raw_tok, dict):
            log(f"本机 token 已加密（{path.name}），本地无法直接使用；请走 GitHub Actions Secret")
            continue
        tok = (raw_tok or "").strip()
        if not tok:
            continue
        log(f"使用本机登录态: {path.name}")
        return {
            "accessToken": tok,
            "uid": (account.get("uid") or "").strip() or None,
            "domain": (auth.get("domain") or "copilot.tencent.com").strip(),
        }

    log("未找到 token：请登录 WorkBuddy 桌面端，或设置 WORKBUDDY_ACCESS_TOKEN")
    return None


def _headers(creds: dict) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {creds['accessToken']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "workbuddy-qiandao/2.0",
    }
    if creds.get("uid"):
        headers["X-User-Id"] = creds["uid"]
    if creds.get("domain"):
        headers["X-Domain"] = creds["domain"]
    return headers


def _post(url: str, creds: dict) -> tuple[int, dict | None, str]:
    req = urllib.request.Request(url, data=b"{}", method="POST", headers=_headers(creds))
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, (json.loads(body) if body else {}), body[:400]
            except Exception:
                return resp.status, None, body[:400]
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        try:
            parsed = json.loads(body) if body else None
        except Exception:
            parsed = None
        return e.code, parsed, body[:400]
    except Exception as e:
        return 0, None, str(e)


def _msg(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("message") or payload.get("msg") or payload.get("Message") or "")


def is_already(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    code = payload.get("code")
    msg = _msg(payload)
    if code in (10001, 10002) or any(k in msg for k in ("已签到", "已经签到", "already", "Already")):
        return True
    data = payload.get("data")
    if isinstance(data, dict) and (data.get("today_checked_in") or data.get("checked_in") or data.get("todayCheckedIn")):
        return True
    return bool(payload.get("today_checked_in") or payload.get("checked_in"))


def is_auth_error(status: int, payload: dict | None) -> bool:
    if status in (401, 403):
        return True
    if isinstance(payload, dict):
        code = payload.get("code")
        if code in (401, 403, 10000):
            msg = _msg(payload)
            if any(k in msg.lower() for k in ("token", "auth", "login", "unauthorized", "登录")):
                return True
    return False


def extract_result(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    credit = (
        data.get("credit")
        or data.get("today_credit")
        or data.get("points")
        or data.get("reward")
        or data.get("credits")
    )
    streak = data.get("streak_days") or data.get("streakDays") or data.get("streak")
    return {
        "credit": credit,
        "streak": streak,
        "today_credit": data.get("today_credit"),
        "daily_credit": data.get("daily_credit"),
        "total_credits": data.get("total_credits"),
        "streak_bonus_credit": data.get("streak_bonus_credit"),
        "streak_bonus_days": data.get("streak_bonus_days"),
        "week_checkin_days": data.get("week_checkin_days"),
        "checkin_dates": data.get("checkin_dates"),
        "season": data.get("season"),
        "activity_name": data.get("activity_name"),
        "theme_name": data.get("theme_name"),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
        "base_credit": data.get("base_credit") or data.get("baseCredit") or data.get("basic_credit"),
        "bonus_credit": data.get("bonus_credit") or data.get("bonusCredit") or data.get("gift_credit") or data.get("extra_credit"),
        "platform_reward": data.get("platform_reward") or data.get("platformReward") or data.get("reward_credit"),
        "raw_keys": list(data.keys())[:16],
    }


def try_hosts(creds: dict, path: str) -> tuple[int, dict | None, str, str]:
    hosts = []
    seen = set()
    for h in (creds.get("domain"), *API_HOSTS):
        h = (h or "").strip().lstrip("https://").rstrip("/")
        if h and h not in seen:
            seen.add(h)
            hosts.append(h)
    last = (0, None, "")
    for host in hosts:
        url = f"https://{host}{path}"
        status, payload, raw = _post(url, creds)
        log(f"  POST {url} -> {status}")
        if status != 0 and not is_auth_error(status, payload):
            return status, payload, raw, url
        last = (status, payload, raw)
        if is_auth_error(status, payload):
            return status, payload, raw, url
    return last[0], last[1], last[2], ""


def save_history(success: bool, detail: dict) -> None:
    today = datetime.now(TZ).date().isoformat()
    data = {
        "timezone": "Asia/Shanghai",
        "createdAt": today,
        "checkins": [],
    }
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    checkins = sorted(set(data.get("checkins") or []))
    if success and today not in checkins:
        checkins.append(today)
        checkins.sort()
    data["checkins"] = checkins
    if success:
        data["lastCheckin"] = today
    data["updatedAt"] = datetime.now(TZ).isoformat(timespec="seconds")
    if detail.get("credit") is not None:
        data["lastCredit"] = detail.get("credit")
    if detail.get("streak") is not None:
        data["lastStreak"] = detail.get("streak")
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    days = sorted(datetime.fromisoformat(d).date() for d in checkins)
    streak_n = 0
    if days:
        cursor = datetime.now(TZ).date()
        if cursor not in days and (cursor - timedelta(days=1)) in days:
            cursor = cursor - timedelta(days=1)
        day_set = set(days)
        while cursor in day_set:
            streak_n += 1
            cursor -= timedelta(days=1)
    LAST_RUN.write_text(
        json.dumps(
            {
                "date": today,
                "status": "ok" if success else "fail",
                "streak": detail.get("streak", streak_n),
                "total": len(checkins),
                "credit": detail.get("credit"),
                "report": detail.get("report", ""),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    credits = {
        "updatedAt": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": "workbuddy-checkin-activity",
        "today_credit": detail.get("today_credit") or detail.get("credit"),
        "daily_credit": detail.get("daily_credit"),
        "activity_total_credits": detail.get("total_credits"),
        "streak_bonus_credit": detail.get("streak_bonus_credit") or 0,
        "streak_bonus_days": detail.get("streak_bonus_days") or 0,
        "streak": detail.get("streak") or streak_n,
        "checkin_days": len(checkins),
        "checkin_dates": detail.get("checkin_dates") or checkins[-14:],
        "week_checkin_days": detail.get("week_checkin_days"),
        "season": detail.get("season"),
        "activity_name": detail.get("activity_name"),
        "theme_name": detail.get("theme_name"),
        "start_time": detail.get("start_time"),
        "end_time": detail.get("end_time"),
        # 账号总览（若接口返回则填入）
        "base_credit": detail.get("base_credit"),
        "bonus_credit": detail.get("bonus_credit"),
        "platform_reward": detail.get("platform_reward"),
    }
    Path(ROOT / "data" / "credits.json").write_text(
        json.dumps(credits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    log("=" * 48)
    log("WorkBuddy Buddy 加油站每日签到")
    log("=" * 48)

    creds = load_credentials()
    if not creds:
        save_history(False, {"report": "未找到登录凭据"})
        return 1

    # 1) 查询今日是否已签
    log("查询签到状态…")
    status, payload, raw, url = try_hosts(creds, "/v2/billing/meter/checkin-activity-status")
    if is_auth_error(status, payload):
        log("登录态失效：请重新登录 WorkBuddy 桌面端后更新 Secret")
        save_history(False, {"report": "登录态失效"})
        return 1
    if is_already(payload):
        info = extract_result(payload)
        report = f"今日已签到（连续 {info.get('streak') or '?'} 天）"
        log(report)
        save_history(True, {**info, "report": report})
        return 0

    # 2) 状态接口若路径不对，再试旧路径
    if status in (404, 0) and not payload:
        status, payload, raw, url = try_hosts(creds, "/v2/billing/meter/checkin-status")
        if is_already(payload):
            info = extract_result(payload)
            report = f"今日已签到（连续 {info.get('streak') or '?'} 天）"
            log(report)
            save_history(True, {**info, "report": report})
            return 0

    # 3) 领取
    log("领取今日积分…")
    result_status, result, result_raw, result_url = try_hosts(creds, "/v2/billing/meter/daily-checkin")
    if is_already(result):
        info = extract_result(result)
        report = f"今日已签到（连续 {info.get('streak') or '?'} 天）"
        log(report)
        save_history(True, {**info, "report": report})
        return 0

    if is_auth_error(result_status, result):
        log("登录态失效：请重新登录 WorkBuddy 桌面端后更新 Secret")
        save_history(False, {"report": "登录态失效"})
        return 1

    if result_status == 200 or (isinstance(result, dict) and result.get("code") in (0, 200, None)):
        info = extract_result(result)
        if isinstance(result, dict) and result.get("success") is False:
            report = f"领取未成功: {_msg(result) or result}"
            log(report)
            save_history(False, {**info, "report": report})
            return 1
        credit = info.get("credit")
        streak = info.get("streak")
        report = f"签到成功 credit={credit} streak={streak}"
        log(report)
        log(f"响应字段: {info.get('raw_keys')}")
        save_history(True, {**info, "report": report})
        return 0

    report = f"签到失败 HTTP={result_status} body={result_raw or raw}"
    log(report)
    save_history(False, {"report": report})
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
