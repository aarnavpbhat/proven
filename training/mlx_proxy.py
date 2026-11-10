"""A loopback shim between `proven`'s openweight extractor and `mlx_lm.server`.

    python training/mlx_proxy.py --port 8090 --upstream http://127.0.0.1:8190 \
        --log /path/to/requests.jsonl

Why it exists: `mlx_lm.server` treats the request's `model` field as a path or Hugging Face
repo to load. Proven needs a distinct model name per proposer (it keys the proposal cache),
so this shim rewrites `model` to `default_model` (the model and adapter the server was
started with) and forwards everything else unchanged: the same messages, `temperature: 0`,
and `response_format`, which `mlx_lm.server` ignores (it has no constrained decoding, so the
reply is validated only by openweight's own parser, as for any server).

It also appends one line per request to `--log` (wall time, prompt and completion tokens),
which is where the latency and tokens/sec figures in docs/finetune.md come from.

Standard library only. Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_handler(upstream: str, log_path: str | None, lock: threading.Lock):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    class Handler(BaseHTTPRequestHandler):
        def _forward(self, method: str, body: bytes | None) -> tuple[int, bytes]:
            request = urllib.request.Request(upstream + self.path, data=body, method=method,
                                             headers={"Content-Type": "application/json"})
            try:
                with opener.open(request, timeout=900) as response:
                    status, data = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, data = exc.code, exc.read()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return status, data

        def do_GET(self) -> None:  # noqa: N802
            self._forward("GET", None)

        def do_POST(self) -> None:  # noqa: N802
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = None
            requested = None
            if isinstance(body, dict):
                requested = body.get("model")
                body["model"] = "default_model"
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            started = time.monotonic()
            status, data = self._forward("POST", raw)
            elapsed = time.monotonic() - started
            if log_path:
                usage = {}
                try:
                    usage = json.loads(data).get("usage") or {}
                except (json.JSONDecodeError, AttributeError):
                    pass
                entry = {"at": time.time(), "model": requested, "status": status,
                         "seconds": round(elapsed, 3),
                         "prompt_tokens": usage.get("prompt_tokens"),
                         "completion_tokens": usage.get("completion_tokens")}
                with lock, open(log_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry) + "\n")

        def log_message(self, *args) -> None:
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--upstream", default="http://127.0.0.1:8190")
    parser.add_argument("--log", default=None)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 make_handler(args.upstream.rstrip("/"), args.log, threading.Lock()))
    print(f"proxy on http://127.0.0.1:{args.port}/v1 -> {args.upstream}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
