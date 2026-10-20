"""Task file format (JSON Lines) and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("id", "task_type", "prompt", "references", "review_status", "license", "source")
REVIEW_STATES = {"unreviewed", "reviewed", "disputed"}
KNOWN_METRICS = {"exact", "chrf", "chrfpp", "numbers", "devanagari"}
KNOWN_CHECKS = {"min_devanagari_ratio", "must_include", "must_not_include"}


class TaskError(ValueError):
    pass


@dataclass
class Task:
    id: str
    task_type: str
    prompt: str
    references: list[str]
    metrics: list[str]
    review_status: str
    license: str
    source: str
    tags: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    notes: str = ""


def parse_task(obj: dict, where: str = "") -> Task:
    missing = [k for k in REQUIRED if k not in obj]
    if missing:
        raise TaskError(f"{where}: missing field(s) {missing}")
    if not isinstance(obj["references"], list) or not obj["references"]:
        raise TaskError(f"{where}: 'references' must be a non-empty list")
    if not all(isinstance(r, str) and r.strip() for r in obj["references"]):
        raise TaskError(f"{where}: every reference must be a non-empty string")
    if obj["review_status"] not in REVIEW_STATES:
        raise TaskError(f"{where}: review_status must be one of {sorted(REVIEW_STATES)}")
    metrics = obj.get("metrics") or ["chrfpp"]
    unknown = set(metrics) - KNOWN_METRICS
    if unknown:
        raise TaskError(f"{where}: unknown metric(s) {sorted(unknown)}")
    checks = obj.get("checks", {})
    bad = set(checks) - KNOWN_CHECKS
    if bad:
        raise TaskError(f"{where}: unknown check(s) {sorted(bad)}")
    return Task(
        id=str(obj["id"]),
        task_type=obj["task_type"],
        prompt=obj["prompt"],
        references=obj["references"],
        metrics=metrics,
        review_status=obj["review_status"],
        license=obj["license"],
        source=obj["source"],
        tags=list(obj.get("tags", [])),
        checks=checks,
        notes=obj.get("notes", ""),
    )


def load_tasks(path: str | Path) -> list[Task]:
    tasks: list[Task] = []
    seen: set[str] = set()
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        where = f"{path}:{n}"
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise TaskError(f"{where}: invalid JSON ({e.msg})") from e
        task = parse_task(obj, where)
        if task.id in seen:
            raise TaskError(f"{where}: duplicate task id {task.id!r}")
        seen.add(task.id)
        tasks.append(task)
    if not tasks:
        raise TaskError(f"{path}: no tasks found")
    return tasks
