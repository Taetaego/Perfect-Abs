#!/usr/bin/env python3
"""data/log.json -> 배포용 data.json (일별 합계만, 음식 이름은 넣지 않는다)."""
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diet_core import (KCAL_GOAL, PROTEIN_GOAL, FAT_GOAL, CARB_BASE, compute, load_log)  # noqa: E402

days = [{k: v for k, v in d.items() if k != "stack"} for d in compute(load_log())]

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
