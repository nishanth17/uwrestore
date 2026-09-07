"""Serialise heavy MPS/CPU inference across concurrently working processes.

Round 2 acquires six model stacks in parallel — mostly network and pip work —
but this machine has ONE 24 GB unified memory pool. Two 9 GB models resident at
once is how a smoke test becomes an OOM that looks like a model failure. So any
command that actually runs a network takes this lock first.

    python round2/gpu_lock.py -- <command> [args...]

Blocking flock, released on process exit (including a crash), so a stuck holder
cannot deadlock the others past its own lifetime.
"""
import fcntl
import os
import subprocess
import sys

LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", ".gpu.lock")


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print(__doc__)
        return 2
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(f"{os.getpid()} {' '.join(argv)}\n")
        fh.flush()
        return subprocess.run(argv).returncode


if __name__ == "__main__":
    raise SystemExit(main())
