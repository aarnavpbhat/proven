"""Vercel entry point: the console's JSON API as one Python serverless function.

Live at https://proven-lac.vercel.app; every push to `main` redeploys it.

On Vercel the console's static files (index.html, app.js, style.css) are copied
from `proven/web/` into `public/` at build time and served from the CDN; every
`/api/*` request is routed here. The request handler is the same class
`python -m proven serve` uses — nothing about the checks differs.

Two things do differ from running locally, both deliberately:

* Resolutions are appended under /tmp, the only writable path on Vercel, so on
  the hosted demo they last only as long as the function instance. Run the
  console locally to keep them.
* The runtime network guard is not installed here, so as not to interfere with
  the platform's own runtime. The hosted demo still makes no outbound calls:
  the Claude extractor refuses to run unless the process explicitly allowed the
  network, and this one does not.
"""
from pathlib import Path

from proven.server import App, make_handler

_ProvenHandler = make_handler(App(Path("/tmp/proven")))


class handler(_ProvenHandler):  # noqa: N801 — Vercel looks for a class with exactly this name
    """Declared as a class rather than assigned: Vercel recognises a Python
    function by reading its source for `class handler`, and does not deploy a
    file whose handler is only assigned (checked with `vercel build`)."""
