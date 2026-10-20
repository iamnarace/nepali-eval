"""Run an adapter over tasks and score the predictions."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__, metrics
from .adapters import Adapter, AdapterError
from .normalize import classify_script, normalize_text
from .tasks import Task


@dataclass
class TaskResult:
    id: str
    task_type: str
    tags: list[str]
    review_status: str
    prediction: str | None
    error: str | None
    scores: dict[str, float] = field(default_factory=dict)
    checks_passed: bool | None = None
    failed_checks: list[str] = field(default_factory=list)
    prediction_script: str | None = None


def score_prediction(task: Task, prediction: str) -> TaskResult:
    scores: dict[str, float] = {}
    for m in task.metrics:
        if m == "exact":
            scores[m] = metrics.exact_match(prediction, task.references)
        elif m == "numbers":
            scores[m] = metrics.numbers_preserved(prediction, task.references)
        elif m == "devanagari":
            scores[m] = metrics.devanagari_ratio(prediction)
        elif m == "chrf":
            scores[m] = metrics.sentence_chrf(prediction, task.references, word_order=0)
        elif m == "chrfpp":
            scores[m] = metrics.sentence_chrf(prediction, task.references, word_order=2)
    failed: list[str] = []
    norm = normalize_text(prediction)
    c = task.checks
    min_ratio = c.get("min_devanagari_ratio")
    if min_ratio is not None and metrics.devanagari_ratio(prediction) < min_ratio:
        failed.append("min_devanagari_ratio")
    for s in c.get("must_include", []):
        if normalize_text(s) not in norm:
            failed.append(f"must_include:{s}")
    for s in c.get("must_not_include", []):
        if normalize_text(s) in norm:
            failed.append(f"must_not_include:{s}")
    return TaskResult(
        id=task.id, task_type=task.task_type, tags=task.tags,
        review_status=task.review_status, prediction=prediction, error=None, scores=scores,
        checks_passed=(not failed) if c else None, failed_checks=failed,
        prediction_script=classify_script(prediction),
    )


def run(tasks: list[Task], adapter: Adapter) -> list[TaskResult]:
    results: list[TaskResult] = []
    for t in tasks:
        try:
            pred = adapter.predict(t)
        except AdapterError as e:
            results.append(TaskResult(
                id=t.id, task_type=t.task_type, tags=t.tags, review_status=t.review_status,
                prediction=None, error=str(e), scores=dict.fromkeys(t.metrics, 0.0),
            ))
            continue
        results.append(score_prediction(t, pred))
    return results


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def aggregate(results: list[TaskResult]) -> dict:
    """Mean per metric. Failed (errored) tasks count as 0 for every metric the task
    declares, so errors cannot inflate a score; they are also reported separately."""

    def block(rs: list[TaskResult]) -> dict:
        per: dict[str, list[float]] = defaultdict(list)
        for r in rs:
            for m, v in r.scores.items():
                per[m].append(v)
        checks = [r.checks_passed for r in rs if r.checks_passed is not None]
        return {
            "n": len(rs),
            "errors": sum(1 for r in rs if r.error),
            "metrics": {m: _mean(v) for m, v in sorted(per.items())},
            "checks_pass_rate": _mean([float(c) for c in checks]),
        }

    groups: dict[str, dict[str, list[TaskResult]]] = {"task_type": defaultdict(list),
                                                      "tag": defaultdict(list)}
    for r in results:
        groups["task_type"][r.task_type].append(r)
        for tg in r.tags:
            groups["tag"][tg].append(r)
    return {
        "overall": block(results),
        "by_task_type": {k: block(v) for k, v in sorted(groups["task_type"].items())},
        "by_tag": {k: block(v) for k, v in sorted(groups["tag"].items())},
    }


def run_metadata(tasks_path: str, adapter: Adapter, tasks: list[Task]) -> dict:
    digest = hashlib.sha256(Path(tasks_path).read_bytes()).hexdigest()
    states: dict[str, int] = defaultdict(int)
    for t in tasks:
        states[t.review_status] += 1
    return {
        "nepali_eval_version": __version__,
        "tasks_file": Path(tasks_path).name,
        "tasks_sha256": digest,
        "adapter": adapter.name,
        "task_count": len(tasks),
        "task_review_status": dict(states),
    }


def as_dicts(results: list[TaskResult]) -> list[dict]:
    return [asdict(r) for r in results]
