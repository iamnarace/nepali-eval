"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .adapters import AdapterError, build_adapter
from .normalize import classify_script, normalize_text, script_stats
from .report import human_summary, write_outputs
from .runner import run, run_metadata
from .tasks import TaskError, load_tasks


def _cmd_validate(a) -> int:
    tasks = load_tasks(a.tasks)
    unrev = sum(1 for t in tasks if t.review_status == "unreviewed")
    print(f"OK: {len(tasks)} tasks ({unrev} unreviewed)")
    return 0


def _cmd_run(a) -> int:
    tasks = load_tasks(a.tasks)
    adapter = build_adapter(a.adapter, model=a.model, base_url=a.base_url,
                            api_key_env=a.api_key_env)
    results = run(tasks, adapter)
    agg = write_outputs(a.out, run_metadata(a.tasks, adapter, tasks), tasks, results)
    o = agg["overall"]
    print(f"{adapter.name}: {o['n']} tasks, {o['errors']} errors -> {a.out}/report.md")
    for m, v in o["metrics"].items():
        print(f"  {m}: {v:.3f}")
    return 1 if o["errors"] and a.fail_on_error else 0


def _cmd_normalize(a) -> int:
    print(json.dumps({"normalized": normalize_text(a.text), "script": classify_script(a.text),
                      "stats": script_stats(a.text)}, ensure_ascii=False, indent=2))
    return 0


def _cmd_human(a) -> int:
    print(json.dumps(human_summary(a.review_csv), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nepali-eval", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a task file")
    v.add_argument("tasks")
    v.set_defaults(fn=_cmd_validate)
    r = sub.add_parser("run", help="run an adapter over a task file and write a report")
    r.add_argument("--tasks", required=True)
    r.add_argument("--adapter", required=True,
                   help="oracle | echo | file:PATH | command:CMD | openai")
    r.add_argument("--out", required=True)
    r.add_argument("--model")
    r.add_argument("--base-url")
    r.add_argument("--api-key-env", help="NAME of the env var holding the API key")
    r.add_argument("--fail-on-error", action="store_true")
    r.set_defaults(fn=_cmd_run)
    n = sub.add_parser("normalize", help="show how a string is normalised and its script mix")
    n.add_argument("text")
    n.set_defaults(fn=_cmd_normalize)
    h = sub.add_parser("human", help="summarise filled-in human scores from review.csv")
    h.add_argument("review_csv")
    h.set_defaults(fn=_cmd_human)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except (TaskError, AdapterError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
