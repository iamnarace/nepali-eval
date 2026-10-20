"""Model adapters. An adapter turns a prompt into a prediction string.

No adapter ever receives or stores credentials on the command line: the OpenAI-compatible
adapter reads its key from an environment variable *name* you pass in.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


class AdapterError(RuntimeError):
    pass


class Adapter:
    name = "adapter"

    def predict(self, task) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class OracleAdapter(Adapter):
    """Returns the first reference. Only for sanity checks: scores must be perfect."""

    name = "oracle"

    def predict(self, task) -> str:
        return task.references[0]


class EchoAdapter(Adapter):
    """Returns the prompt unchanged. A trivial baseline that should score poorly."""

    name = "echo"

    def predict(self, task) -> str:
        return task.prompt


class FileAdapter(Adapter):
    """Reads predictions from a JSONL file of ``{"id": ..., "prediction": ...}``."""

    def __init__(self, path: str):
        self.name = f"file:{Path(path).name}"
        self._preds: dict[str, str] = {}
        for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                self._preds[str(obj["id"])] = str(obj["prediction"])
            except (json.JSONDecodeError, KeyError) as e:
                raise AdapterError(f"{path}:{n}: expected {{'id','prediction'}} JSON") from e

    def predict(self, task) -> str:
        if task.id not in self._preds:
            raise AdapterError(f"no prediction for task {task.id!r}")
        return self._preds[task.id]


class CommandAdapter(Adapter):
    """Runs a local command (no shell), writes the prompt to stdin, reads stdout."""

    def __init__(self, command: str, timeout: float = 120):
        self.argv = shlex.split(command)
        if not self.argv:
            raise AdapterError("empty command")
        self.timeout = timeout
        self.name = f"command:{self.argv[0]}"

    def predict(self, task) -> str:
        try:
            r = subprocess.run(
                self.argv, input=task.prompt, capture_output=True, text=True,
                timeout=self.timeout, encoding="utf-8", check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AdapterError(f"command failed: {e}") from e
        if r.returncode != 0:
            raise AdapterError(f"command exited {r.returncode}: {r.stderr.strip()[:200]}")
        return r.stdout.strip()


class OpenAICompatAdapter(Adapter):
    """Calls an OpenAI-compatible ``/chat/completions`` endpoint (cloud or local server).

    Using a hosted API may cost money and sends task prompts to that provider.
    """

    def __init__(self, base_url: str, model: str, api_key_env: str | None = None,
                 timeout: float = 120):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.key = os.environ.get(api_key_env, "") if api_key_env else ""
        if api_key_env and not self.key:
            raise AdapterError(f"environment variable {api_key_env} is not set")
        self.timeout = timeout
        self.name = f"openai-compat:{model}"

    def predict(self, task) -> str:
        body = json.dumps({
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": task.prompt}],
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                data = json.load(resp)
            return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, OSError) as e:
            raise AdapterError(f"request failed: {e}") from e


def build_adapter(spec: str, *, model: str | None = None, base_url: str | None = None,
                  api_key_env: str | None = None) -> Adapter:
    kind, _, arg = spec.partition(":")
    if kind == "oracle":
        return OracleAdapter()
    if kind == "echo":
        return EchoAdapter()
    if kind == "file":
        return FileAdapter(arg)
    if kind == "command":
        return CommandAdapter(arg)
    if kind == "openai":
        if not (model and base_url):
            raise AdapterError("openai adapter needs --model and --base-url")
        return OpenAICompatAdapter(base_url, model, api_key_env)
    raise AdapterError(f"unknown adapter {spec!r} (oracle|echo|file:PATH|command:CMD|openai)")
