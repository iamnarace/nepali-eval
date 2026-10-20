import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from nepali_eval.adapters import (
    AdapterError,
    CommandAdapter,
    FileAdapter,
    OpenAICompatAdapter,
    build_adapter,
)
from nepali_eval.cli import main
from nepali_eval.tasks import load_tasks

SEED = str(Path(__file__).parent.parent / "tasks" / "seed_v0.jsonl")


def test_oracle_scores_perfectly_and_echo_does_not(tmp_path, capsys):
    assert main(["run", "--tasks", SEED, "--adapter", "oracle", "--out", str(tmp_path / "o")]) == 0
    res = json.loads((tmp_path / "o" / "results.json").read_text(encoding="utf-8"))
    m = res["aggregate"]["overall"]["metrics"]
    assert m["exact"] == 1.0 and m["numbers"] == 1.0 and m["chrfpp"] == pytest.approx(100.0)
    assert res["aggregate"]["overall"]["checks_pass_rate"] == 1.0
    assert main(["run", "--tasks", SEED, "--adapter", "echo", "--out", str(tmp_path / "e")]) == 0
    echo = json.loads((tmp_path / "e" / "results.json").read_text(encoding="utf-8"))
    assert echo["aggregate"]["overall"]["metrics"]["chrfpp"] < 50
    for f in ("report.md", "results.jsonl", "review.csv"):
        assert (tmp_path / "o" / f).exists()
    assert "Read before citing" in (tmp_path / "o" / "report.md").read_text(encoding="utf-8")


def test_digit_and_variant_credit_in_end_to_end(tmp_path):
    preds = tmp_path / "p.jsonl"
    preds.write_text(
        json.dumps({"id": "qa-002", "prediction": "सात"}, ensure_ascii=False) + "\n"
        + json.dumps({"id": "qa-001", "prediction": "काठमाडौँ।"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    one = tmp_path / "t.jsonl"
    tasks = [json.loads(line) for line in Path(SEED).read_text(encoding="utf-8").splitlines()
             if line.startswith("{")]
    one.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in tasks
                             if t["id"] in {"qa-001", "qa-002"}), encoding="utf-8")
    out = tmp_path / "out"
    assert main(["run", "--tasks", str(one), "--adapter", f"file:{preds}", "--out", str(out)]) == 0
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert res["aggregate"]["overall"]["metrics"]["exact"] == 1.0


def test_missing_prediction_is_error_not_silent_zero_credit(tmp_path):
    preds = tmp_path / "p.jsonl"
    preds.write_text(json.dumps({"id": "nope", "prediction": "x"}) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    rc = main(["run", "--tasks", SEED, "--adapter", f"file:{preds}", "--out", str(out),
               "--fail-on-error"])
    assert rc == 1
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert res["aggregate"]["overall"]["errors"] == 24
    # errored tasks are scored 0, never silently dropped from the averages
    assert res["aggregate"]["overall"]["metrics"]["chrfpp"] == 0.0


def test_validate_and_normalize_commands(capsys):
    assert main(["validate", SEED]) == 0
    assert "24 tasks" in capsys.readouterr().out
    assert main(["normalize", "१० बजे।"]) == 0
    assert "10 बजे." in capsys.readouterr().out
    assert main(["validate", "/nonexistent/file.jsonl"]) == 2


def test_command_adapter_uses_stdin_without_shell():
    task = load_tasks(SEED)[0]
    ad = CommandAdapter(f"{sys.executable} -c \"import sys;print(sys.stdin.read().upper())\"")
    assert "TRANSLATE INTO ENGLISH" in ad.predict(task)
    with pytest.raises(AdapterError):
        CommandAdapter(f"{sys.executable} -c \"import sys;sys.exit(3)\"").predict(task)


def test_file_adapter_rejects_malformed(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"id": "a"}\n', encoding="utf-8")
    with pytest.raises(AdapterError):
        FileAdapter(str(p))


class _Handler(BaseHTTPRequestHandler):
    seen: dict = {}

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.seen = {"path": self.path, "auth": self.headers.get("Authorization"), "body": body}
        out = json.dumps({"choices": [{"message": {"content": " I like tea. "}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def test_openai_compatible_adapter_against_local_server(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("TEST_KEY", "secret-test-key")
        ad = build_adapter("openai", model="m", base_url=f"http://127.0.0.1:{srv.server_port}/v1",
                           api_key_env="TEST_KEY")
        assert ad.predict(load_tasks(SEED)[0]) == "I like tea."
        assert _Handler.seen["path"] == "/v1/chat/completions"
        assert _Handler.seen["auth"] == "Bearer secret-test-key"
        assert _Handler.seen["body"]["temperature"] == 0
    finally:
        srv.shutdown()


def test_openai_adapter_requires_declared_key_and_reports_connection_errors(monkeypatch):
    monkeypatch.delenv("NOPE_KEY", raising=False)
    with pytest.raises(AdapterError, match="NOPE_KEY"):
        OpenAICompatAdapter("http://127.0.0.1:1", "m", "NOPE_KEY")
    with pytest.raises(AdapterError):
        OpenAICompatAdapter("http://127.0.0.1:1", "m", timeout=2).predict(load_tasks(SEED)[0])
    with pytest.raises(AdapterError, match="unknown adapter"):
        build_adapter("bogus")


def test_human_review_summary(tmp_path, capsys):
    p = tmp_path / "review.csv"
    p.write_text("id,prompt,prediction,references,human_score_0_to_5,reviewer,notes\n"
                 "a,p,x,r,4,asha,\nb,p,x,r,2,asha,\nc,p,x,r,,,\nd,p,x,r,5,ram,\n",
                 encoding="utf-8")
    assert main(["human", str(p)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["n_scored"] == 3 and out["by_reviewer"]["asha"]["mean"] == 3.0
    p.write_text("id,human_score_0_to_5\na,9\n", encoding="utf-8")
    assert main(["human", str(p)]) == 2
