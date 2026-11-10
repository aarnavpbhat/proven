"""`mlx_lm.lora` with the gradient norm clipped, under the memory guard.

    $MLX_PY training/lora_clip.py --config run-config.yaml --model <hf-model> --data <dir> --adapter-path <dir>

`mlx_lm.lora` has no clipping option. The 7B base model's loss went to NaN between
iterations 40 and 50 at two learning rates (1e-4 and 4e-5) without it. `PROVEN_CLIP` sets
the largest gradient norm (default 1.0); a gradient that is not finite becomes a zero update.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mlx.core as mx  # noqa: E402
import mlx.optimizers as optim  # noqa: E402
from mlx.utils import tree_map  # noqa: E402

import memguard  # noqa: E402

LIMIT = float(os.environ.get("PROVEN_CLIP", "1.0"))
_update = optim.Optimizer.update


def update(self, model, gradients):
    """Clip to LIMIT; a gradient that is not finite becomes a zero update (the step runs
    inside a compiled function, so this is a `where`, not a Python branch)."""
    clipped, norm = optim.clip_grad_norm(gradients, LIMIT)
    ok = mx.isfinite(norm)
    safe = tree_map(lambda g: mx.where(ok, mx.nan_to_num(g), mx.zeros_like(g)), clipped)
    return _update(self, model, safe)


if __name__ == "__main__":
    memguard.install()
    optim.Optimizer.update = update
    sys.argv = ["mlx_lm.lora", *sys.argv[1:]]
    runpy.run_module("mlx_lm.lora", run_name="__main__")
