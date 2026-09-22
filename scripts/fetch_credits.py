#!/usr/bin/env python3
"""拉取 WorkBuddy 账号积分：基础 / 平台奖励，以及本月过期 / 之后过期。"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "credits.json"
TZ = timezone(timedelta(hours=8))
BASE = "https://copilot.tencent.com"

# 包码 → 中文名
COMMODITY = {
    "TCACA_code_001_PqouKr6QWV": ("free", "每日免费额度"),
    "TCACA_code_002_AkiJS3ZHF5": ("proMon", "Pro 月卡"),
    "TCACA_code_003_FAnt7lcmRT": ("proYear", "Pro 年卡"),
    "TCACA_code_005_maRGyrHhw1": ("proMonPlus", "Pro 月卡增强"),
    "TCACA_code_006_DbXS0lrypC": ("gift", "赠送包"),
    "TCACA_code_007_nzdH5h4Nl0": ("activity", "运营/活动奖励"),
    "TCACA_code_008_cfWoLwvjU4": ("freeMon", "体验版月包"),
    "TCACA_code_009_0XmEQc2xOf": ("extra", "加量包"),
    "TCACA_code_023_4xbGhMrE6q": ("youth", "青年版"),
    "TCACA_code_026_BaESVICNoi": ("advanced", "高级版"),
    "TCACA_code_027_0FCGVA6vSa": ("flagship", "旗舰版"),
    "TCACA_code_028_NtpWi0jzXs": ("bonus28", "平台奖励 28"),
    "TCACA_code_029_6wCGEWquYy": ("bonus29", "平台奖励 29"),
    "TCACA_code_030_BjSt89qTvr": ("bonus30", "平台奖励 30"),
    "TCACA_code_035_ArVxJcGDsm": ("freeMonIntl", "体验版月包(国际)"),
    "TCACA_code_036_lupO5WgNdG": ("extraIntl", "加量包(国际)"),
    "TCACA_code_037_WxOD3MpI2o": ("bonusIntl", "平台奖励(国际)"),
    "TCACA_code_038_OhvqZtiPKr": ("extra38", "加量包 38"),
    "TCACA_code_039_KRcQj7wUat": ("proTrialMon", "Pro 试用月"),
    "TCACA_code_040_mi9rCYg46x": ("proTrialYear", "Pro 试用年"),
}

# 视为「基础积分」的包码 key
BASE_KEYS = {
    "free", "proMon", "proMonPlus", "proYear", "youth", "advanced", "flagship",
    "freeMon", "freeMonIntl", "proTrialMon", "proTrialYear",
}
# 视为「平台奖励 / 加赠」
BONUS_KEYS = {
    "gift", "activity", "extra", "extra38", "extraIntl",
    "bonus28", "bonus29", "bonus30", "bonusIntl",
}

PAID_CODES = [
    "TCACA_code_002_AkiJS3ZHF5", "TCACA_code_005_maRGyrHhw1", "TCACA_code_003_FAnt7lcmRT",
    "TCACA_code_023_4xbGhMrE6q", "TCACA_code_026_BaESVICNoi", "TCACA_code_027_0FCGVA6vSa",
    "TCACA_code_009_0XmEQc2xOf", "TCACA_code_038_OhvqZtiPKr", "TCACA_code_036_lupO5WgNdG",
]
FREE_CODES = [
    "TCACA_code_001_PqouKr6QWV", "TCACA_code_008_cfWoLwvjU4", "TCACA_code_035_ArVxJcGDsm",
    "TCACA_code_006_DbXS0lrypC", "TCACA_code_039_KRcQj7wUat", "TCACA_code_040_mi9rCYg46x",
    "TCACA_code_007_nzdH5h4Nl0", "TCACA_code_028_NtpWi0jzXs", "TCACA_code_029_6wCGEWquYy",
    "TCACA_code_030_BjSt89qTvr", "TCACA_code_037_WxOD3MpI2o",
]

AUTH_CANDIDATES = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info",
    Path(os.environ.get("APPDATA", "")) / "CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info",
    Path.home() / "Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info",
)


def log(msg: str) -> None:
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def load_credentials() -> dict | None:
    token = os.environ.get("WORKBUDDY_ACCESS_TOKEN", "").strip()
    if token:
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
        except Exception:
            continue
        auth = data.get("auth") or {}
        account = data.get("account") or {}
        tok = (auth.get("accessToken") or "").strip()
        if not tok:
            continue
        return {
            "accessToken": tok,
            "uid": (account.get("uid") or "").strip() or None,
            "domain": (auth.get("domain") or "copilot.tencent.com").strip(),
        }
    return None


def post(path: str, creds: dict, payload: dict | None = None) -> dict | None:
    url = f"{BASE}{path}"
    headers = {
        "Authorization": f"Bearer {creds['accessToken']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "workbuddy-qiandao/2.1",
        "Accept-Language": "zh-CN,zh",
    }
    if creds.get("uid"):
        headers["X-User-Id"] = creds["uid"]
    if creds.get("domain"):
        headers["X-Domain"] = creds["domain"]
    body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:300]
        log(f"HTTP {e.code} {path}: {err}")
        return None
    except Exception as e:
        log(f"request failed {path}: {e}")
        return None


def to_float(v) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def parse_end_ms(item: dict) -> datetime | None:
    # 积分到期看周期结束 CycleEndTime；DeductionEndTime 是扣费窗口，可能很长
    for key in ("CycleEndTime", "ExpiredTime"):
        val = item.get(key) or ""
        if isinstance(val, str) and len(val) >= 19:
            try:
                return datetime.strptime(val[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
            except Exception:
                pass
    de = item.get("DeductionEndTime")
    if isinstance(de, (int, float)) and de > 0:
        return datetime.fromtimestamp(de / 1000, tz=TZ)
    return None


def classify(code: str) -> str:
    key, _ = COMMODITY.get(code, (code, code))
    if key in BASE_KEYS:
        return "base"
    if key in BONUS_KEYS:
        return "bonus"
    # 未知包：赠送类默认 bonus，其余默认 base
    return "bonus" if "bonus" in key or "gift" in key or "extra" in key or "activity" in key else "base"


def main() -> int:
    creds = load_credentials()
    if not creds:
        log("未找到 token")
        return 1

    now = datetime.now(TZ)
    y, m = now.year, now.month
    month_start = datetime(y, m, 1, tzinfo=TZ)
    month_end = datetime(y, m, monthrange(y, m)[1], 23, 59, 59, tzinfo=TZ)

    summary_raw = post("/billing/meter/get-user-resource-summary", creds)
    if not summary_raw or not summary_raw.get("data"):
        log("summary 失败")
        return 1
    packages = (summary_raw.get("data") or {}).get("Packages") or []
    is_paid = bool((summary_raw.get("data") or {}).get("IsPaidUser"))

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    paid_raw = post(
        "/billing/meter/get-user-resource-paid-packages",
        creds,
        {
            "PageNumber": 1,
            "PageSize": 100,
            "PackageCodes": PAID_CODES,
            "Status": [0, 3],
            "NeedRenewInfo": True,
        },
    )
    free_raw = post(
        "/billing/meter/get-user-resource-free-packages",
        creds,
        {
            "PageNumber": 1,
            "PageSize": 100,
            "PackageCodes": FREE_CODES,
            "Status": [0, 3],
            "SlicePeriodStartTime": day_start.strftime("%Y-%m-%d %H:%M:%S"),
            "SlicePeriodEndTime": day_end.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )

    accounts: list[dict] = []
    for raw in (paid_raw, free_raw):
        if raw and isinstance(raw.get("data"), dict):
            accounts.extend(raw["data"].get("Accounts") or [])

    # 汇总包级别余额
    by_pkg = {}
    for p in packages:
        code = p.get("PackageCode") or ""
        key, name = COMMODITY.get(code, (code, code))
        kind = classify(code)
        remain = to_float(p.get("CycleRemainCapacity") or p.get("CycleRemainCapacityPrecise"))
        # 优先 precise
        remain = to_float(p.get("CycleRemainCapacityPrecise") or p.get("CycleRemainCapacity"))
        total = to_float(p.get("CycleTotalCapacityPrecise") or p.get("CycleTotalCapacity"))
        used = to_float(p.get("CycleUsedCapacityPrecise") or p.get("CycleUsedCapacity"))
        by_pkg[code] = {
            "code": code,
            "key": key,
            "name": name,
            "kind": kind,
            "remain": remain,
            "total": total,
            "used": used,
            "count": p.get("TotalCount"),
        }

    # 切片级：按到期时间分桶
    exp_this_month = 0.0
    exp_after_month = 0.0
    base_remain = 0.0
    bonus_remain = 0.0
    slices = []
    for a in accounts:
        code = a.get("PackageCode") or ""
        key, name = COMMODITY.get(code, (code, code))
        kind = classify(code)
        remain = to_float(a.get("CycleCapacityRemainPrecise") or a.get("CycleCapacityRemain"))
        end = parse_end_ms(a)
        end_iso = end.isoformat() if end else None
        in_month = bool(end and month_start <= end <= month_end)
        after_month = bool(end and end > month_end)
        if kind == "base":
            base_remain += remain
        else:
            bonus_remain += remain
        if in_month:
            exp_this_month += remain
        elif after_month:
            exp_after_month += remain
        # 已过期（end < now）仍计在 remain 里的少见，忽略
        if remain > 0.001:
            slices.append(
                {
                    "packageCode": code,
                    "name": name,
                    "kind": kind,
                    "remain": remain,
                    "expireAt": end_iso,
                    "expireLabel": end.strftime("%Y-%m-%d %H:%M") if end else None,
                }
            )

    # 若切片不全，用包级余额兜底
    sum_pkg_remain = sum(v["remain"] for v in by_pkg.values())
    if base_remain + bonus_remain <= 0 and sum_pkg_remain > 0:
        for v in by_pkg.values():
            if v["kind"] == "base":
                base_remain += v["remain"]
            else:
                bonus_remain += v["remain"]

    # 包级也可按 CycleEnd 粗分（当切片缺失时）
    if exp_this_month + exp_after_month <= 0 and sum_pkg_remain > 0:
        # 用免费包 list 为空时的保守估计：体验包按月末
        pass

    # 本月过期 / 之后过期；若切片合计对不上包级，把差额按包 kind 记入「之后」
    slice_sum = exp_this_month + exp_after_month
    gap = sum_pkg_remain - slice_sum
    if abs(gap) > 0.05:
        exp_after_month += max(gap, 0)
        log(f"切片与汇总差额 {gap:.2f}，并入之后过期")

    slices.sort(key=lambda x: (x.get("expireAt") or "", x["remain"]))

    result = {
        "updatedAt": now.isoformat(timespec="seconds"),
        "source": "workbuddy-user-resource",
        "isPaidUser": is_paid,
        # 账号总余额
        "total_remain": round(sum_pkg_remain, 2),
        "base_remain": round(base_remain, 2),
        "bonus_remain": round(bonus_remain, 2),
        "base_total": round(sum(v["total"] for v in by_pkg.values() if v["kind"] == "base"), 2),
        "bonus_total": round(sum(v["total"] for v in by_pkg.values() if v["kind"] == "bonus"), 2),
        # 到期
        "expire_this_month": round(exp_this_month, 2),
        "expire_after_month": round(exp_after_month, 2),
        "never_expire": 0.0,  # 免费/赠送包均会到期；付费包若有续费则按周期刷新
        "month": f"{y}-{m:02d}",
        "packages": list(by_pkg.values()),
        "expiring_slices": slices[:40],
        "note": "基础=体验/套餐额度；平台奖励=活动/赠送/加量。免费与赠送积分均有到期日。",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 合并旧的签到活动字段，保留页面兼容
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    keep_keys = [
        "today_credit", "daily_credit", "activity_total_credits", "streak_bonus_credit",
        "streak_bonus_days", "streak", "checkin_days", "checkin_dates", "week_checkin_days",
        "season", "activity_name", "theme_name", "start_time", "end_time",
        "base_credit", "bonus_credit", "platform_reward",
    ]
    for k in keep_keys:
        if k in old and k not in result:
            result[k] = old[k]
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log(f"总余额={result['total_remain']} 基础={result['base_remain']} 奖励={result['bonus_remain']}")
    log(f"本月过期={result['expire_this_month']} 之后过期={result['expire_after_month']}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
