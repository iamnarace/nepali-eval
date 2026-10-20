"""Tests for the lint, human-review and data-commons import workflows."""

import csv
import json
from pathlib import Path

import pytest

from nepali_eval.adapters import AdapterError, OpenAICompatAdapter
from nepali_eval.cli import main
from nepali_eval.lint import lint_task, lint_tasks
from nepali_eval.ndc import ImportError_, convert
from nepali_eval.review import ReviewError, apply_review, export_review
from nepali_eval.tasks import load_tasks, parse_task

SEED = Path(__file__).parent.parent / "tasks" / "seed_v0.jsonl"
BASE = {"id": "t", "task_type": "translation_en_ne", "prompt": "Translate: Hello",
        "references": ["नमस्ते।"], "review_status": "unreviewed", "license": "CC0-1.0", "source": "s"}


def codes(obj):
    return {f.code for f in lint_task(parse_task({**BASE, **obj}))}


def test_seed_has_no_errors_or_warnings():
    bad = [f for f in lint_tasks(load_tasks(SEED)) if f.severity in ("error", "warning")]
    assert bad == []


def test_seed_contains_no_phone_like_numbers():
    text = SEED.read_text(encoding="utf-8")
    from nepali_eval.normalize import extract_numbers
    assert not [n for n in extract_numbers(text) if len(n) == 10 and n[:2] in ("97", "98")]


@pytest.mark.parametrize("obj,code", [
    ({"references": ["call 9841234567"]}, "phone-like"),
    ({"prompt": "मेरो नम्बर ९८४१२३४५६७"}, "phone-like"),
    ({"references": ["नम‍स्ते।"]}, "zero-width"),
    ({"references": ["१० 10 बजे।"]}, "mixed-digits"),
    ({"references": ["Hello there"]}, "reference-script"),
    ({"references": ["नमस्ते."]}, "ascii-full-stop"),
    ({"references": ["म घर जान्छु"]}, "no-sentence-end"),
    ({"references": ["कहाँ छ ?"]}, "space-before-mark"),
    ({"references": ["नमस्ते।", "नमस्ते"]}, "duplicate-reference"),
    ({"task_type": "translation_ne_en", "references": ["Hello."]}, "single-reference"),
    ({"prompt": "तिम्रो नाम के हो?"}, "register"),
])
def test_lint_detects(obj, code):
    assert code in codes(obj)


def test_lint_is_quiet_on_clean_task_and_tagged_register():
    assert codes({"references": ["नमस्ते।", "नमस्कार।"]}) == {"unreviewed"}
    assert "register" not in codes({"prompt": "तिम्रो नाम?", "tags": ["register-informal"],
                                    "references": ["नमस्ते।", "नमस्कार।"]})


def test_lint_cli_exit_codes(tmp_path, capsys):
    good = tmp_path / "g.jsonl"
    good.write_text(json.dumps(BASE, ensure_ascii=False), encoding="utf-8")
    assert main(["lint", str(good)]) == 0
    bad = tmp_path / "b.jsonl"
    bad.write_text(json.dumps({**BASE, "references": ["9841234567"]}), encoding="utf-8")
    assert main(["lint", str(bad)]) == 1
    warn = tmp_path / "w.jsonl"
    warn.write_text(json.dumps({**BASE, "references": ["Hello"]}), encoding="utf-8")
    assert main(["lint", str(warn)]) == 0 and main(["lint", str(warn), "--strict"]) == 1
    assert "not a linguistic review" in capsys.readouterr().out


def test_review_export_and_apply_roundtrip(tmp_path):
    tasks = tmp_path / "t.jsonl"
    tasks.write_text("# header comment\n" + "\n".join(json.dumps(
        {**BASE, "id": i, "references": ["नमस्ते।", "नमस्कार।"]}, ensure_ascii=False) for i in "abc") + "\n",
        encoding="utf-8")
    sheet = tmp_path / "review.csv"
    assert export_review(tasks, sheet) == 3
    with sheet.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["review_status"] == "unreviewed" and "नमस्ते।" in rows[0]["references"]
    rows[0].update(verdict="approve", reviewer="asha", reviewer_attests_fluent_nepali="yes",
                   references_correct="yes", register="formal")
    rows[1].update(verdict="revise", reviewer="ram", extra_valid_references="अभिवादन। | नमस्ते।",
                   comments="add greeting variant")
    rows[2].update(verdict="reject", reviewer="sita", comments="unnatural")
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    out = tmp_path / "out.jsonl"
    before = tasks.read_text(encoding="utf-8")
    counts = apply_review(tasks, sheet, out)
    assert counts == {"approved": 1, "revised": 1, "rejected": 1, "skipped": 0}
    assert tasks.read_text(encoding="utf-8") == before          # input never modified
    got = {t.id: t for t in load_tasks(out)}
    assert got["a"].review_status == "reviewed" and "register-formal" in got["a"].tags
    assert got["b"].review_status == "unreviewed" and got["b"].references[-1] == "अभिवादन।"
    assert got["b"].references.count("नमस्ते।") == 1            # no duplicate added
    assert got["c"].review_status == "disputed" and "unnatural" in got["c"].notes
    assert out.read_text(encoding="utf-8").startswith("# header comment")
    assert json.loads(out.read_text(encoding="utf-8").splitlines()[1])["reviewers"] == ["asha"]


@pytest.mark.parametrize("patch,msg", [
    ({"reviewer": ""}, "reviewer name"),
    ({"reviewer_attests_fluent_nepali": "no"}, "fluent"),
    ({"references_correct": ""}, "references_correct"),
    ({"verdict": "maybe"}, "verdict"),
    ({"id": "zzz"}, "unknown task id"),
])
def test_review_rejects_incomplete_approvals(tmp_path, patch, msg):
    tasks = tmp_path / "t.jsonl"
    tasks.write_text(json.dumps(BASE, ensure_ascii=False) + "\n", encoding="utf-8")
    row = {"id": "t", "verdict": "approve", "reviewer": "asha", "reviewer_attests_fluent_nepali": "yes",
           "references_correct": "yes", **patch}
    sheet = tmp_path / "r.csv"
    with sheet.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        w.writeheader()
        w.writerow(row)
    with pytest.raises(ReviewError, match=msg):
        apply_review(tasks, sheet, tmp_path / "o.jsonl")


def test_empty_verdicts_are_skipped(tmp_path):
    tasks = tmp_path / "t.jsonl"
    tasks.write_text(json.dumps(BASE, ensure_ascii=False) + "\n", encoding="utf-8")
    sheet = tmp_path / "r.csv"
    export_review(tasks, sheet)
    assert apply_review(tasks, sheet, tmp_path / "o.jsonl")["skipped"] == 1


NDC = [
    {"id": "a", "text_ne": "मलाई चिया मन पर्छ।", "text_en": "I like tea.", "license": "CC0-1.0",
     "consent": True, "source_type": "original", "status": "accepted", "reviewer": "bob"},
    {"id": "b", "text_ne": "म घर जान्छु।", "text_en": "I go home.", "license": "CC0-1.0",
     "consent": True, "source_type": "original", "status": "submitted"},
    {"id": "c", "text_ne": "आज मौसम राम्रो छ।", "license": "CC0-1.0", "consent": True, "status": "accepted"},
]


def test_import_ndc_only_accepted_with_translation(tmp_path):
    src = tmp_path / "ndc.jsonl"
    src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in NDC) + "\n", encoding="utf-8")
    out = tmp_path / "tasks.jsonl"
    assert convert(src, out) == 1
    t = load_tasks(out)[0]
    assert t.id == "ndc-a" and t.references == ["I like tea."] and t.license == "CC0-1.0"
    assert t.review_status == "unreviewed"                        # ndc acceptance != linguistic validation
    assert convert(src, out, trust_ndc_review=True) == 1 and load_tasks(out)[0].review_status == "reviewed"
    assert convert(src, out, "en-ne") == 1
    assert load_tasks(out)[0].checks == {"min_devanagari_ratio": 0.9}
    assert main(["import-ndc", str(src), "--out", str(out)]) == 0


def test_import_ndc_errors(tmp_path):
    src = tmp_path / "ndc.jsonl"
    src.write_text(json.dumps(NDC[1]) + "\n", encoding="utf-8")
    with pytest.raises(ImportError_, match="no accepted"):
        convert(src, tmp_path / "o.jsonl")
    src.write_text("{oops\n", encoding="utf-8")
    with pytest.raises(ImportError_, match="invalid JSON"):
        convert(src, tmp_path / "o.jsonl")
    assert main(["import-ndc", str(src), "--out", str(tmp_path / "o.jsonl")]) == 2


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org/x", "//no-scheme", "not a url"])
def test_openai_adapter_refuses_non_http_schemes(url):
    with pytest.raises(AdapterError, match="http"):
        OpenAICompatAdapter(url, "m")


def test_openai_adapter_refuses_key_over_plain_http_to_remote_host(monkeypatch):
    monkeypatch.setenv("K", "secret")
    with pytest.raises(AdapterError, match="plain http"):
        OpenAICompatAdapter("http://api.example.org/v1", "m", "K")
    OpenAICompatAdapter("http://localhost:8080/v1", "m", "K")      # local servers are fine
    OpenAICompatAdapter("https://api.example.org/v1", "m", "K")
