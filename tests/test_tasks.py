import json
from pathlib import Path

import pytest

from nepali_eval.tasks import TaskError, load_tasks

SEED = Path(__file__).parent.parent / "tasks" / "seed_v0.jsonl"
BASE = {"id": "x", "task_type": "t", "prompt": "p", "references": ["r"],
        "review_status": "unreviewed", "license": "CC0-1.0", "source": "s"}


def write(tmp_path, *objs):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in objs), encoding="utf-8")
    return p


def test_seed_file_valid_and_all_unreviewed():
    tasks = load_tasks(SEED)
    assert len(tasks) == 24
    assert {t.review_status for t in tasks} == {"unreviewed"}
    assert len({t.id for t in tasks}) == len(tasks)


def test_seed_numbers_survive_digit_conversion():
    from nepali_eval.normalize import extract_numbers
    t = {t.id: t for t in load_tasks(SEED)}["ne-en-010"]
    assert extract_numbers(t.prompt) == ["9012345678"] == extract_numbers(t.references[0])


@pytest.mark.parametrize("patch,msg", [
    ({"references": []}, "non-empty"),
    ({"references": ["ok", ""]}, "non-empty string"),
    ({"review_status": "maybe"}, "review_status"),
    ({"metrics": ["bleu9"]}, "unknown metric"),
    ({"checks": {"nope": 1}}, "unknown check"),
])
def test_invalid_tasks_rejected(tmp_path, patch, msg):
    with pytest.raises(TaskError, match=msg):
        load_tasks(write(tmp_path, {**BASE, **patch}))


def test_missing_field_and_duplicate_and_bad_json(tmp_path):
    bad = {k: v for k, v in BASE.items() if k != "prompt"}
    with pytest.raises(TaskError, match="missing"):
        load_tasks(write(tmp_path, bad))
    with pytest.raises(TaskError, match="duplicate"):
        load_tasks(write(tmp_path, BASE, BASE))
    p = tmp_path / "b.jsonl"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(TaskError, match="invalid JSON"):
        load_tasks(p)
