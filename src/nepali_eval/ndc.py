"""Convert records from a nepali-data-commons dataset (or its export) into nepali-eval tasks.

This is a *format* bridge only: the two projects share no code or dependency. Because a data-commons
``accepted`` status means "a second person reviewed the record", not "a verified native speaker validated the
translation", converted tasks default to ``review_status: unreviewed``.
"""

from __future__ import annotations

import json
from pathlib import Path

DIRECTIONS = {
    "ne-en": ("translation_ne_en", "Translate into English. Reply with the translation only:\n", "text_ne", "text_en"),
    "en-ne": ("translation_en_ne",
              "Translate into Nepali (Devanagari script). Reply with the translation only:\n", "text_en", "text_ne"),
}


class ImportError_(ValueError):
    pass


def convert(records_path, out_path, direction: str = "ne-en", *, trust_ndc_review: bool = False) -> int:
    if direction not in DIRECTIONS:
        raise ImportError_(f"direction must be one of {sorted(DIRECTIONS)}")
    task_type, instruction, src_key, ref_key = DIRECTIONS[direction]
    tasks = []
    for n, line in enumerate(Path(records_path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            raise ImportError_(f"{records_path}:{n}: invalid JSON ({e.msg})") from e
        if "status" in r and r["status"] != "accepted":
            continue  # working files contain unreviewed rows; only accepted ones may become tasks
        if r.get("consent") is False or not r.get(src_key) or not r.get(ref_key):
            continue
        task = {
            "id": f"ndc-{r['id']}", "task_type": task_type, "prompt": instruction + r[src_key],
            "references": [r[ref_key]], "metrics": ["chrfpp", "exact"], "tags": ["from-data-commons"],
            "source": f"nepali-data-commons record {r['id']} (source_type: {r.get('source_type', 'unknown')})",
            "license": r.get("license", "unknown"),
            "review_status": "reviewed" if (trust_ndc_review and r.get("reviewer")) else "unreviewed",
        }
        if direction == "en-ne":
            task["checks"] = {"min_devanagari_ratio": 0.9}
            task["metrics"].append("devanagari")
        tasks.append(task)
    if not tasks:
        raise ImportError_("no accepted records with both text_ne and text_en were found")
    Path(out_path).write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in tasks) + "\n",
                              encoding="utf-8")
    return len(tasks)
