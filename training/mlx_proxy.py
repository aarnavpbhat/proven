"""A loopback shim between `proven`'s openweight extractor and `mlx_lm.server`.

    python training/mlx_proxy.py --port 8090 --upstream http://127.0.0.1:8190 \
        --log /path/to/requests.jsonl

Why it exists: `mlx_lm.server` treats the request's `model` field as a path or Hugging Face
repo to load. Proven needs a distinct model name per proposer (it keys the proposal cache),
so this shim rewrites `model` to `default_model` (the model and adapter the server was
started with) and forwards everything else unchanged: the same messages, `temperature: 0`,
and `response_format`, which `mlx_lm.server` ignores (it has no constrained decoding, so the
reply is validated only by openweight's own parser, as for any server).

With `--name`, `GET /v1/models` answers with that one id, so the console lists the
proposer under the name its cache entries use.

It also appends one line per request to `--log` (wall time, prompt and completion tokens),
which is where the latency and tokens/sec figures in docs/finetune.md come from.

Standard library only. Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def wrap_bare_objects(content: str) -> str | None:
    """`{...}\\n\\n{...}` -> `{"claims": [{...}, {...}]}`, or None if the reply needs no repair
    (it already has a `claims` list) or holds no claim-shaped objects.

    Only for `--repair-bare-objects`: an untuned model behind a server without constrained
    decoding often emits the claim objects without the wrapper the JSON schema requires
    (Ollama's grammar would have forced it). The repair is a measurement aid for the BASE
    model only, so its vocabulary is measured rather than its formatting; openweight.py's
    validation is untouched and every repaired reply is counted in the log."""
    text = re.sub(r"```(?:json)?", "", content or "")
    decoder = json.JSONDecoder()
    objects, i = [], 0
    while True:
        start = text.find("{", i)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            i = start + 1
            continue
        if isinstance(value, dict) and isinstance(value.get("claims"), list):
            return None
        if isinstance(value, dict) and "quote" in value:
            objects.append(value)
        elif isinstance(value, list):
            objects.extend(v for v in value if isinstance(v, dict) and "quote" in v)
        i = end
    return json.dumps({"claims": objects}, ensure_ascii=False) if objects else None


def make_handler(upstream: str, log_path: str | None, lock: threading.Lock, name: str | None = None,
                 repair: bool = False):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    class Handler(BaseHTTPRequestHandler):
        def _upstream(self, method: str, body: bytes | None) -> tuple[int, bytes]:
            request = urllib.request.Request(upstream + self.path, data=body, method=method,
                                             headers={"Content-Type": "application/json"})
            try:
                with opener.open(request, timeout=900) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read()
            except (urllib.error.URLError, OSError) as exc:
                return 502, json.dumps({"error": f"upstream: {type(exc).__name__}: {exc}"}).encode()

        def _send(self, status: int, data: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if name and self.path.rstrip("/").endswith("/models"):
                self._send(200, json.dumps({"object": "list", "data": [
                    {"id": name, "object": "model", "owned_by": "local"}]}).encode())
                return
            self._send(*self._upstream("GET", None))

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
            status, data = self._upstream("POST", raw)
            elapsed = time.monotonic() - started
            usage, repaired = {}, False
            try:
                reply = json.loads(data)
                usage = reply.get("usage") or {}
                if repair and status == 200:
                    message = reply["choices"][0]["message"]
                    fixed = wrap_bare_objects(message.get("content") or "")
                    if fixed is not None:
                        message["content"], repaired = fixed, True
                        data = json.dumps(reply, ensure_ascii=False).encode("utf-8")
            except (json.JSONDecodeError, AttributeError, KeyError, IndexError, TypeError):
                pass
            self._send(status, data)
            if log_path:
                entry = {"at": time.time(), "model": requested, "status": status,
                         "seconds": round(elapsed, 3), "repaired": repaired,
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
    parser.add_argument("--name", default=None,
                        help="the one model id GET /v1/models reports (what the console lists)")
    parser.add_argument("--repair-bare-objects", action="store_true",
                        help="base-model measurement aid: wrap bare claim objects in {\"claims\": [...]}")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 make_handler(args.upstream.rstrip("/"), args.log, threading.Lock(),
                                              args.name, args.repair_bare_objects))
    print(f"proxy on http://127.0.0.1:{args.port}/v1 -> {args.upstream}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
