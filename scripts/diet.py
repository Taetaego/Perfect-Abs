#!/usr/bin/env python3
"""식단 기록 도구: log.json 추가/삭제 -> docs/diet_log.md 자동 생성 -> 대시보드 출력 -> (선택) 커밋·푸시.

사용법
  diet.py add [--date YYYY-MM-DD] [--push] "끼니|음식|kcal|탄|단|지" ...   (운동은 kcal을 음수로, 끼니는 '운동')
  diet.py rm  [--date YYYY-MM-DD] [--push] 번호 ...                         (list의 번호)
  diet.py list [--date YYYY-MM-DD]
  diet.py status [--date YYYY-MM-DD]       (기록 없이 현재 상태만)
  diet.py docs                             (docs/diet_log.md만 다시 만든다)
날짜를 안 주면 오늘(KST). docs/diet_log.md는 AUTO_FROM 이후 날짜 섹션과 주간 요약만 자동으로 만든다.
"""
import argparse
import math
import re
import subprocess
import sys
from datetime import date as Date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diet_core as core  # noqa: E402

DOC = core.ROOT / "docs" / "diet_log.md"
AUTO_FROM = "2026-10-14"   # 이 날짜 이후 일별 섹션은 log.json에서 자동 생성 (이전 날짜 섹션은 손으로 쓴 그대로 둔다)
WEEK = "월화수목금토일"
SEC3 = "## 3. 식단 기록"
SEC4 = "## 4. 주간 요약 (누적용)"
SEC5 = "## 5. 메모"
TRAILER = (
    "\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\n"
    "Claude-Session: https://claude.ai/code/session_01HjTMLUsNV4U4CjakWz4E4R"
)


def half_up(x):
    return int(math.floor(x + 0.5))


def n(x):
    """숫자 표기: 정수면 정수, 아니면 소수 1~2자리."""
    x = round(x, 2)
    return str(int(x)) if x == int(x) else str(x)


def c(x):
    return f"{int(x):,}"


# ---------- 대시보드 ----------
def bar(ratio):
    if ratio < 1:
        k = max(0, half_up(ratio * 12))
        return "█" * k + "░" * (12 - k)
    return "█" * min(24, max(12, half_up(ratio * 12)))


def block(title, cur, goal, unit):
    ratio = cur / goal
    pct = half_up(ratio * 100)
    diff = goal - cur
    tail = f"남음 {c(diff)}{unit}" if diff >= 0 else f"초과 {c(-diff)}{unit}"
    return f"{title}  {c(cur)} / {c(goal)} {unit}\n{bar(ratio)}\n{pct}% · {tail}"


def dashboard(d):
    over = d["over"]
    stack = d["stack"]
    parts = [
        block("🔥 칼로리", d["net"], d["goal"], "kcal"),
        block("🍗 단백질", d["protein"], core.PROTEIN_GOAL, "g"),
        block("🍚 탄수화물", d["carb"], d["carbGoal"], "g"),
        block("🥑 지방", d["fat"], core.FAT_GOAL, "g"),
    ]
    out = "\n\n".join(parts)
    out += f"\n\n⚠️ 초과  {c(over)}kcal\n📦 누적  {c(over + stack)}kcal  (초과 {c(over)} + 쌓인 것 {c(stack)})"
    return "```\n" + out + "\n```"


def day_of(log, date):
    work = dict(log)
    work.setdefault(date, [])
    for d in core.compute(work, today=date):
        if d["d"] == date:
            return d


# ---------- docs/diet_log.md ----------
def fmt_rem(label, cur, goal):
    diff = goal - cur
    return f"{label} 남은 약 {c(diff)}g" if diff >= 0 else f"{label} 약 {c(-diff)}g 초과"


def day_section(log, d):
    date = d["d"]
    wd = WEEK[Date.fromisoformat(date).weekday()]
    entries = log[date]
    burn = d["burn"]
    lines = [f"### {date} ({wd})"]
    ex = [e for e in entries if e["kcal"] < 0]
    if ex:
        names = " + ".join(f"{e['food']} 약 {c(-e['kcal'])} kcal" for e in ex)
        lines.append(f"운동: {names} = 소모 약 {c(burn)} kcal (추정)")
    lines += ["", "| 끼니 | 음식 | kcal | 탄(g) | 단(g) | 지(g) |", "|---|---|---|---|---|---|"]
    for e in entries:
        k = e["kcal"]
        ks = f"−{c(-k)}" if k < 0 else c(k)
        lines.append(f"| {e['meal']} | {e['food']} | {ks} | {n(e['carb'])} | {n(e['protein'])} | {n(e['fat'])} |")
    nets = f"−{c(-d['net'])}" if d["net"] < 0 else c(d["net"])
    lines.append(f"| **합계 (순섭취)** | | **{nets}** | **{d['carb']}** | **{d['protein']}** | **{d['fat']}** |")
    lines += ["", f"**목표 대비 (순섭취 기준{'' if burn else ', 운동 없음'})**"]
    left = d["goal"] - d["net"]
    head = f"순섭취 {c(d['net'])}" if d["net"] >= 0 else f"순섭취 −{c(-d['net'])}"
    if burn:
        head += f" (먹은 {c(d['eaten'])} − 운동 {c(burn)})"
    if left >= 0:
        lines.append(f"- {head} / 오늘 목표 {c(d['goal'])} → 남은 약 {c(left)} kcal")
    else:
        lines.append(f"- {head} / 오늘 목표 {c(d['goal'])} → 약 {c(-left)} kcal 초과 (이월 누적 {c(d['carry'])})")
    cg = f"목표 {d['carbGoal']}g = 130 + {burn}/8" if burn else f"목표 {d['carbGoal']}g"
    lines.append(
        f"- {fmt_rem('단백질', d['protein'], core.PROTEIN_GOAL)} / "
        f"{fmt_rem('탄수화물', d['carb'], d['carbGoal'])} ({cg}) / {fmt_rem('지방', d['fat'], core.FAT_GOAL)}"
    )
    return "\n".join(lines) + "\n\n"


def week_row(d, today):
    mmdd = d["d"][5:]
    label = f"{mmdd} (진행 중)" if d["d"] == today else mmdd
    nets = f"−{c(-d['net'])}" if d["net"] < 0 else c(d["net"])
    kc = f"순 {nets} (먹은 {c(d['eaten'])}, 운동 −{c(d['burn'])})" if d["burn"] else nets
    left = d["goal"] - d["net"]
    goal_txt = f"순섭취 {c(left)} 남음" if left >= 0 else f"순섭취 {c(-left)} 초과"
    if d["d"] >= core.CARRY_START:
        goal_txt += f" (목표 {c(d['goal'])}), 이월 누적 {c(d['carry'])}"
        if d["d"] == today:
            goal_txt += " (진행 중이라 절약분 미반영)"
    return f"| {label} | {kc} | {d['carb']} | {d['protein']} | {d['fat']} | {goal_txt} |"


def build_docs(log):
    today = core.today_kst()
    days = core.compute(log, today=today)
    text = DOC.read_text(encoding="utf-8")
    i3, i4, i5 = text.index(SEC3), text.index(SEC4), text.index(SEC5)
    body3 = text[i3 + len(SEC3):i4]
    chunks = re.split(r"(?m)^(?=### \d{4}-\d{2}-\d{2})", body3)
    kept = [ch for ch in chunks[1:] if re.match(r"### (\d{4}-\d{2}-\d{2})", ch).group(1) < AUTO_FROM]
    new3 = SEC3 + "\n\n" + "".join(kept)
    new3 += "".join(day_section(log, d) for d in days if d["d"] >= AUTO_FROM)
    new4 = SEC4 + "\n| 날짜 | 총 kcal | 탄(g) | 단(g) | 지(g) | 목표 대비 |\n|---|---|---|---|---|---|\n"
    new4 += "\n".join(week_row(d, today) for d in days) + "\n\n"
    DOC.write_text(text[:i3] + new3 + new4 + text[i5:], encoding="utf-8")


# ---------- git ----------
def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=core.ROOT, check=check, capture_output=True, text=True)


def push(msg):
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    git("fetch", "-q", "origin", branch)
    git("merge", "--ff-only", f"origin/{branch}", check=False)
    git("add", "data/log.json", "docs/diet_log.md")
    git("commit", "-q", "-m", msg + TRAILER)
    r = git("push", "-u", "origin", branch, check=False)
    print("push:", "ok" if r.returncode == 0 else "실패\n" + r.stderr)


# ---------- 명령 ----------
def num(x):
    return float(x) if "." in x else int(x)


def load_presets():
    import json
    raw = json.loads((Path(__file__).resolve().parent / "presets.json").read_text(encoding="utf-8"))
    table = {}
    for key, p in raw.items():
        for name in [key, *p.get("alias", [])]:
            table[name] = p
    return table


def preset_item(s):
    """'현미 80ml', '뉴팩 2', '닭가슴살 1.5덩이', '알밤 3개' 같은 줄임 입력을 항목으로 바꾼다."""
    m = re.match(r"^(\S+?)\s*([\d.]+)?\s*([^\d\s]*)$", s.strip())
    table = load_presets()
    if not m or m.group(1) not in table:
        raise SystemExit(f"프리셋을 못 찾음: {s} (전체 형식은 '끼니|음식|kcal|탄|단|지')")
    p = table[m.group(1)]
    qty = float(m.group(2)) if m.group(2) else 1.0
    unit = m.group(3) or next(iter(p["units"]))
    if unit not in p["units"]:
        raise SystemExit(f"단위 {unit}를 모름: {s} (가능: {', '.join(p['units'])})")
    ratio = qty / p["units"][unit]
    k, cb, pr, f = (v * ratio for v in p["base"])
    qtxt = f"{qty:g}{unit}"
    food = f"{p['name']} {qtxt}" + (f" ({p['note']})" if p["note"] else "")
    return {"meal": p["meal"], "food": food, "kcal": round(k), "carb": round(cb, 1),
            "protein": round(pr, 1), "fat": round(f, 1)}


def parse_item(s):
    if "|" not in s:
        e = preset_item(s)
        return {k: (int(v) if isinstance(v, float) and v == int(v) else v) for k, v in e.items()}
    meal, food, k, cb, p, f = [x.strip() for x in s.split("|")]
    return {"meal": meal, "food": food, "kcal": num(k), "carb": num(cb), "protein": num(p), "fat": num(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["add", "rm", "list", "status", "docs"])
    ap.add_argument("items", nargs="*")
    ap.add_argument("--date")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_intermixed_args()
    date = a.date or core.today_kst()
    log = core.load_log()

    if a.cmd == "docs":
        build_docs(log)
        return
    if a.cmd == "list":
        for i, e in enumerate(log.get(date, [])):
            print(i, e["meal"], e["food"], e["kcal"], e["carb"], e["protein"], e["fat"], sep=" | ")
        return
    added = []
    if a.cmd == "add":
        added = [parse_item(s) for s in a.items]
        log.setdefault(date, []).extend(added)
    elif a.cmd == "rm":
        idx = sorted({int(x) for x in a.items}, reverse=True)
        removed = [log[date].pop(i) for i in idx]
        print("삭제:", ", ".join(e["food"] for e in removed))
    if a.cmd in ("add", "rm"):
        core.save_log(log)
        build_docs(log)
    d = day_of(log, date)
    print(dashboard(d))
    if added:
        print("\n재료·요리별 칼로리 (탄 / 단 / 지)")
        for e in added:
            print(f"- {e['food']}: {c(e['kcal'])}kcal ({n(e['carb'])} / {n(e['protein'])} / {n(e['fat'])})")
        if len(added) > 1:
            t = [sum(e[k] for e in added) for k in ("kcal", "carb", "protein", "fat")]
            print(f"- 합계: {c(t[0])}kcal (탄 {n(t[1])} / 단 {n(t[2])} / 지 {n(t[3])})")
    if a.push and a.cmd in ("add", "rm"):
        names = ", ".join(e["food"].split(" (")[0] for e in (added or [])) or "기록 수정"
        push(f"{date[5:].replace('-', '/')} 기록: {names}")


if __name__ == "__main__":
    main()
