#!/usr/bin/env python3
"""Hevy 운동 텍스트 → 종목별 칼로리. 사용: python3 scripts/workout.py [파일] [--add --push --date D]
표준입력/파일에서 Hevy 텍스트를 읽어 종목별 항목을 만든다. --add면 diet.py add로 바로 기록한다.
유산소(스테어머신 등)는 기기 수치가 필요하므로 건너뛰고 알려 준다(`diet.py add "스테어머신 890"`)."""
import json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BW = 83.5
BASE, ECC, EFF = 7.0, 1.3, 0.25
TABLE = {k: v for k, v in json.loads((HERE / "exercises.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}


def key_of(name):
    s = re.sub(r"\(.*?\)", "", name).lower()
    return re.sub(r"[^a-z가-힣0-9]", "", s)


def set_kcal(ex, kg, reps):
    load = kg + BW * ex["bw"]
    work = ECC * load * 9.81 * ex["rom"] * reps / EFF / 4184
    return BASE + work


def parse(text):
    out, cur = [], None
    for ln in (l.strip() for l in text.splitlines()):
        m = re.match(r"^Set\s+\d+:\s*(.*)$", ln)
        if m and cur is not None:
            cur["sets"].append(m.group(1))
        elif ln and not m and not re.match(r"^(@|https?:|단백질|닭|[A-Z][a-z]+day,)", ln) and "," not in ln[:12]:
            cur = {"name": ln, "sets": []}
            out.append(cur)
        elif not ln:
            cur = None
    return [e for e in out if e["sets"]]


def main():
    args = [a for a in sys.argv[1:]]
    do_add = "--add" in args
    push = "--push" in args
    date = args[args.index("--date") + 1] if "--date" in args else None
    files = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--date")]
    text = Path(files[0]).read_text(encoding="utf-8") if files else sys.stdin.read()
    items, notes, total = [], [], 0
    for e in parse(text):
        k = key_of(e["name"])
        first = e["sets"][0]
        if re.search(r"steps|km|mi\b", first):
            notes.append(f"유산소 건너뜀: {e['name']} → 기기 수치로 `diet.py add \"스테어머신 <수치>\"`")
            continue
        if re.match(r"^\d+min", first) or k == "stretching":
            mins = sum(int(re.search(r"(\d+)min", s).group(1)) + (int(re.search(r"(\d+)s", s).group(1)) / 60 if re.search(r"(\d+)s", s) else 0)
                       for s in e["sets"] if re.search(r"min", s))
            kc = round(mins * 1.8)
            items.append(f"운동|스트레칭 {mins:g}분 (분당 1.8kcal)|-{kc}|0|0|0")
            total += kc
            continue
        ex = TABLE.get(k)
        if ex is None:
            ex = {"name": e["name"], "rom": 0.5, "bw": 0}
            notes.append(f"⚠️ 프리셋 없음: {e['name']} (임시값 가동범위 0.5m) → scripts/exercises.json에 추가")
        kc_sum, desc = 0.0, []
        for s in e["sets"]:
            m = re.match(r"^([\d.]+)\s*(kg|lbs?)\s*x\s*(\d+)", s)
            if m:
                kg = float(m.group(1)) * (0.4536 if m.group(2).startswith("lb") else 1)
                reps = int(m.group(3))
                desc.append(f"{float(m.group(1)):g}{m.group(2)}×{reps}")
            else:
                m = re.match(r"^(\d+)\s*reps?", s)
                if not m:
                    notes.append(f"읽지 못함: {e['name']} / {s}")
                    continue
                kg, reps = 0.0, int(m.group(1))
                desc.append(f"맨몸×{reps}")
            kc_sum += set_kcal(ex, kg, reps)
        kc = round(kc_sum)
        total += kc
        items.append(f"운동|{ex['name']} {len(e['sets'])}세트 ({', '.join(desc)})|-{kc}|0|0|0")
    for it in items:
        print(it)
    print(f"합계 -{total}kcal (유산소 제외)")
    for n in notes:
        print(n)
    if do_add and items:
        cmd = [sys.executable, str(HERE / "diet.py"), "add"] + (["--push"] if push else []) + (["--date", date] if date else []) + items
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
