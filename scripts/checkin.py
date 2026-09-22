#!/usr/bin/env python3
"""WorkBuddy 每日打卡：写入今日记录并维护连续天数。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "checkins.json"
TZ = timezone(timedelta(hours=8))  # Asia/Shanghai


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {
            "timezone": "Asia/Shanghai",
            "createdAt": datetime.now(TZ).date().isoformat(),
            "checkins": [],
        }
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def streak_of(checkins: list[str]) -> int:
    if not checkins:
        return 0
    days = sorted(datetime.fromisoformat(d).date() for d in checkins)
    today = datetime.now(TZ).date()
    # 连续天数从今天或昨天往回数；今天未打卡则从昨天起算（仍算历史连续）
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    n = 0
    day_set = set(days)
    while cursor in day_set:
        n += 1
        cursor -= timedelta(days=1)
    return n


def main() -> int:
    today = datetime.now(TZ).date().isoformat()
    data = load_data()
    checkins: list[str] = list(data.get("checkins") or [])

    if today in checkins:
        print(f"already checked in: {today}")
        status = "already"
    else:
        checkins.append(today)
        checkins = sorted(set(checkins))
        data["checkins"] = checkins
        data["lastCheckin"] = today
        data["updatedAt"] = datetime.now(TZ).isoformat(timespec="seconds")
        save_data(data)
        print(f"checked in: {today}")
        status = "ok"

    streak = streak_of(checkins)
    total = len(checkins)
    print(f"streak={streak} total={total}")

    # 供 workflow 输出
    summary = ROOT / "data" / "last-run.json"
    summary.write_text(
        json.dumps(
            {
                "date": today,
                "status": status,
                "streak": streak,
                "total": total,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
