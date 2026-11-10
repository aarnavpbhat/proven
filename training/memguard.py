"""Keep a local-model job from taking the machine down with it.

    python training/memguard.py <module> [args...]     # e.g. mlx_lm.lora --config ...

MLX holds model memory wired; a job that overcommits a 24 GB laptop can force a reboot
rather than fail. `install()` caps what MLX may allocate and starts a watchdog that ends
this process (exit code 75) when the system's free-memory level stays under a floor.

    PROVEN_MLX_GB      cap on MLX memory in GB (default 11)
    PROVEN_MIN_FREE    system free-memory percentage below which the job is ended (default 12)
"""
from __future__ import annotations

import os
import runpy
import subprocess
import sys
import threading
import time


def free_percent() -> int:
    try:
        out = subprocess.run(["sysctl", "-n", "kern.memorystatus_level"], capture_output=True,
                             text=True, timeout=5).stdout.strip()
        return int(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 100


def install() -> None:
    import mlx.core as mx
    cap = int(float(os.environ.get("PROVEN_MLX_GB", "11")) * 1024 ** 3)
    floor = int(os.environ.get("PROVEN_MIN_FREE", "12"))
    mx.set_memory_limit(cap)
    mx.set_wired_limit(cap)
    mx.set_cache_limit(1024 ** 3)

    def watch() -> None:
        low = 0
        while True:
            time.sleep(2)
            low = low + 1 if free_percent() < floor else 0
            if low >= 3:
                sys.stderr.write(f"memguard: free memory under {floor}% for 6 s; ending the job\n")
                sys.stderr.flush()
                os._exit(75)

    threading.Thread(target=watch, daemon=True).start()


if __name__ == "__main__":
    install()
    module = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
