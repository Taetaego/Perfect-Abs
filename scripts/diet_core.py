"""식단 집계 규칙 (목표, 이월, 탄수화물 목표). build_site.py와 diet.py가 함께 쓴다."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "data" / "log.json"

PROTEIN_GOAL = 170
CARB_CAP = 250
# 시작일별 목표 (순섭취 kcal, 지방 g, 탄수화물 기본 g). 마지막 줄이 현재 목표.
GOAL_STEPS = [
    ("2000-01-01", {"kcal": 1750, "fat": 65, "carb": 130}),
    ("2026-10-21", {"kcal": 1600, "fat": 55, "carb": 100}),   # 적자 −600 (유지 2,200 기준, 주당 약 0.55kg)
]
KCAL_GOAL = GOAL_STEPS[-1][1]["kcal"]
FAT_GOAL = GOAL_STEPS[-1][1]["fat"]
CARB_BASE = GOAL_STEPS[-1][1]["carb"]
CARRY_START = "2026-10-02"   # 초과분 이월 시작일
CARRY_MAX_PER_DAY = 300

KST = timezone(timedelta(hours=9))
DAY_START_HOUR = 4   # 새벽 4시 전 기록은 전날로 친다 (자정 넘긴 야식)


def today_kst():
    return (datetime.now(KST) - timedelta(hours=DAY_START_HOUR)).date().isoformat()


def goals_for(date):
    g = GOAL_STEPS[0][1]
    for start, step in GOAL_STEPS:
        if date >= start:
            g = step
    return g


def load_log():
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def save_log(log):
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compute(log, today=None):
    """일별 합계 리스트. 당일(진행 중)은 아직 안 먹은 절약분을 미리 빼지 않는다."""
    today = today or today_kst()
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

        base = goals_for(date)
        goal = base["kcal"]
        stack = 0
        carry_shown = carry
        if date >= CARRY_START:
            prev = carry
            goal = base["kcal"] - min(CARRY_MAX_PER_DAY, prev)
            stack = prev - min(CARRY_MAX_PER_DAY, prev)
            carry = max(0, prev + net - base["kcal"])
            carry_shown = carry
            if date == today:
                carry_shown = stack + max(0, net - goal)
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
            "carbGoal": round(min(CARB_CAP, base["carb"] + burn / 8)),
            "carbBase": base["carb"],
            "fatGoal": base["fat"],
            "over": round(over),
            "carry": round(carry_shown),
            "stack": round(stack),
        })
    return days
