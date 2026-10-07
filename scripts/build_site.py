#!/usr/bin/env python3
"""data/log.json -> 배포용 data.json (일별 합계만, 음식 이름은 넣지 않는다)."""
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"

KCAL_GOAL = 1750      # 순섭취 목표
PROTEIN_GOAL = 170
FAT_GOAL = 65
CARB_BASE = 130
CARB_CAP = 250
CARRY_START = "2026-10-02"   # 초과분 이월 시작일
CARRY_MAX_PER_DAY = 300

log = json.loads((ROOT / "data" / "log.json").read_text(encoding="utf-8"))

days = []
carry = 0
for date in sorted(log):
    entries = log[date]
    eaten = sum(e["kcal"] for e in entries if e["kcal"] > 0)
    burn = -sum(e["kcal"] for e in entries if e["kcal"] < 0)
    net = eaten - burn
    carb = sum(e["carb"] for e in entries)
    protein = sum(e["protein"] for e in entries)
    fat = sum(e["fat"] for e in entries)

    goal = KCAL_GOAL
    if date >= CARRY_START:
        goal = KCAL_GOAL - min(CARRY_MAX_PER_DAY, carry)
        carry = max(0, carry + net - KCAL_GOAL)
    over = max(0, net - goal)

    days.append({
        "d": date,
        "eaten": round(eaten),
        "burn": round(burn),
        "net": round(net),
        "goal": round(goal),
        "carb": round(carb),
        "protein": round(protein),
        "fat": round(fat),
        "carbGoal": round(min(CARB_CAP, CARB_BASE + burn / 8)),
        "over": round(over),
        "carry": round(carry),
    })

OUT.mkdir(parents=True, exist_ok=True)
shutil.copytree(ROOT / "site", OUT, dirs_exist_ok=True)
data = {
    "updated": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="minutes"),
    "goal": {"kcal": KCAL_GOAL, "protein": PROTEIN_GOAL, "fat": FAT_GOAL, "carb": CARB_BASE},
    "targetDate": "2027-01-01",
    "days": days,
}
(OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(days)} days -> {OUT / 'data.json'}")
