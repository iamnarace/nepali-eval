"""Human-review workflow: export a spreadsheet for native speakers, apply their verdicts.

Nothing here verifies a reviewer's language competence. ``reviewed`` means "a named person who attested
fluency approved this task"; it is a recorded claim, not a certification.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .lint import lint_task
from .tasks import load_tasks

COLUMNS = [
    "id", "task_type", "review_status", "prompt", "references", "automated_findings",
    "reviewer", "reviewer_attests_fluent_nepali", "prompt_natural_and_correct", "references_correct",
    "register", "extra_valid_references", "region_or_dialect_notes", "verdict", "comments",
]
VERDICTS = {"approve", "revise", "reject"}
YES = {"y", "yes", "true", "1"}


class ReviewError(ValueError):
    pass


def export_review(tasks_path, out_path) -> int:
    tasks = load_tasks(tasks_path)
    with Path(out_path).open("w", encoding="utf-8-sig", newline="") as f:  # BOM: opens correctly in Excel
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for t in tasks:
            findings = "; ".join(f"{x.code}" for x in lint_task(t) if x.code != "unreviewed")
            w.writerow([t.id, t.task_type, t.review_status, t.prompt,
                        " | ".join(t.references), findings] + [""] * (len(COLUMNS) - 6))
    return len(tasks)


def apply_review(tasks_path, review_csv, out_path) -> dict:
    """Merge verdicts into a new task file (the input is never modified).

    - approve (needs a reviewer name and fluency attestation): status -> reviewed, reviewer recorded
    - revise: extra_valid_references (separated by ' | ') appended; status stays unreviewed; comment kept in notes
    - reject: status -> disputed
    Rows with an empty verdict are ignored. Unknown ids are an error.
    """
    raw = [json.loads(line) for line in Path(tasks_path).read_text(encoding="utf-8").splitlines()
           if line.strip().startswith("{")]
    header = [line for line in Path(tasks_path).read_text(encoding="utf-8").splitlines()
              if line.startswith("#")]
    by = {r["id"]: r for r in raw}
    counts = {"approved": 0, "revised": 0, "rejected": 0, "skipped": 0}
    with Path(review_csv).open(encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            verdict = (row.get("verdict") or "").strip().lower()
            if not verdict:
                counts["skipped"] += 1
                continue
            if verdict not in VERDICTS:
                raise ReviewError(f"row {n}: verdict must be one of {sorted(VERDICTS)}")
            rid = row.get("id", "")
            if rid not in by:
                raise ReviewError(f"row {n}: unknown task id {rid!r}")
            task = by[rid]
            reviewer = (row.get("reviewer") or "").strip()
            if not reviewer:
                raise ReviewError(f"row {n}: a reviewer name/handle is required")
            comment = (row.get("comments") or "").strip()
            if verdict == "approve":
                if (row.get("reviewer_attests_fluent_nepali") or "").strip().lower() not in YES:
                    raise ReviewError(f"row {n}: approval requires reviewer_attests_fluent_nepali=yes")
                if (row.get("references_correct") or "").strip().lower() not in YES:
                    raise ReviewError(f"row {n}: approval requires references_correct=yes")
                task["review_status"] = "reviewed"
                task.setdefault("reviewers", []).append(reviewer)
                counts["approved"] += 1
            elif verdict == "revise":
                extra = [x.strip() for x in (row.get("extra_valid_references") or "").split("|") if x.strip()]
                for x in extra:
                    if x not in task["references"]:
                        task["references"].append(x)
                if comment:
                    task["notes"] = (task.get("notes", "") + f" [revise by {reviewer}: {comment}]").strip()
                counts["revised"] += 1
            else:
                task["review_status"] = "disputed"
                if comment:
                    task["notes"] = (task.get("notes", "") + f" [rejected by {reviewer}: {comment}]").strip()
                counts["rejected"] += 1
            reg = (row.get("register") or "").strip()
            if reg and f"register-{reg}" not in task.setdefault("tags", []):
                task["tags"].append(f"register-{reg}")
    Path(out_path).write_text(
        "\n".join(header) + ("\n" if header else "")
        + "\n".join(json.dumps(r, ensure_ascii=False) for r in raw) + "\n", encoding="utf-8")
    return counts
