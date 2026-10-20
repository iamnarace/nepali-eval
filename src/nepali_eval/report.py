"""Write JSON / Markdown / CSV outputs and merge human review scores."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .runner import TaskResult, aggregate, as_dicts
from .tasks import Task

CAVEAT = (
    "> **Read before citing these numbers.** Scores come from the task file named above. "
    "Tasks marked `unreviewed` have not been checked by a native speaker; small task counts "
    "give wide uncertainty; automatic metrics (chrF/chrF++, exact match) do not measure "
    "fluency or correctness reliably and must not be presented as a general Nepali ability score.\n"
)


def _fmt(v, metric: str = "") -> str:
    if v is None:
        return "n/a"
    return f"{v:.1f}" if metric.startswith("chrf") else f"{v:.3f}"


def _table(title: str, groups: dict) -> list[str]:
    if not groups:
        return []
    metric_names = sorted({m for g in groups.values() for m in g["metrics"]})
    header = "| group | n | errors | checks pass | " + " | ".join(metric_names) + " |"
    lines = [f"### {title}", "", header, "|---|---|---|---|" + "---|" * len(metric_names)]
    for k, g in groups.items():
        cells = [_fmt(g["metrics"].get(m), m) for m in metric_names]
        lines.append(f"| {k} | {g['n']} | {g['errors']} | {_fmt(g['checks_pass_rate'])} | "
                     + " | ".join(cells) + " |")
    return lines + [""]


def write_outputs(out_dir: str | Path, meta: dict, tasks: list[Task],
                  results: list[TaskResult]) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    agg = aggregate(results)
    (out / "results.json").write_text(
        json.dumps({"meta": meta, "aggregate": agg}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with (out / "results.jsonl").open("w", encoding="utf-8") as f:
        for d in as_dicts(results):
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    md = ["# nepali-eval report", "", CAVEAT,
          f"- adapter: `{meta['adapter']}`", f"- tasks: `{meta['tasks_file']}` "
          f"(sha256 `{meta['tasks_sha256'][:12]}…`, {meta['task_count']} tasks, "
          f"review status {meta['task_review_status']})",
          f"- nepali-eval {meta['nepali_eval_version']}", "",
          f"Errors (counted as missing, scored 0): {agg['overall']['errors']}", ""]
    md += _table("Overall", {"all": agg["overall"]})
    md += _table("By task type", agg["by_task_type"])
    md += _table("By tag", agg["by_tag"])
    fails = [r for r in results if r.error or r.failed_checks]
    if fails:
        md += ["### Failures", ""]
        for r in fails:
            md.append(f"- `{r.id}`: " + (r.error or ", ".join(r.failed_checks)))
        md.append("")
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")
    by_id = {t.id: t for t in tasks}
    with (out / "review.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "prompt", "prediction", "references", "human_score_0_to_5",
                    "reviewer", "notes"])
        for r in results:
            t = by_id[r.id]
            w.writerow([r.id, t.prompt, r.prediction or "", " | ".join(t.references), "", "", ""])
    return agg


def human_summary(review_csv: str | Path) -> dict:
    """Mean of filled-in ``human_score_0_to_5`` values, overall and per reviewer."""
    scores: list[float] = []
    per: dict[str, list[float]] = {}
    with Path(review_csv).open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("human_score_0_to_5") or "").strip()
            if not raw:
                continue
            v = float(raw)
            if not 0 <= v <= 5:
                raise ValueError(f"score out of range 0-5 for {row.get('id')}: {raw}")
            scores.append(v)
            per.setdefault((row.get("reviewer") or "unknown").strip(), []).append(v)
    return {
        "n_scored": len(scores),
        "mean": sum(scores) / len(scores) if scores else None,
        "by_reviewer": {k: {"n": len(v), "mean": sum(v) / len(v)} for k, v in sorted(per.items())},
    }
