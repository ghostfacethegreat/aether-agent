import os
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    durations = []
    with tempfile.TemporaryDirectory() as home:
        env = {**os.environ, "AETHER_HOME": home, "NO_COLOR": "1"}
        before = 0
        for _ in range(max(1, runs)):
            started = time.perf_counter()
            completed = subprocess.run(
                [sys.executable, "-m", "aether", "--provider", "mock", "run", "Say hello"],
                cwd=str(root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            durations.append(time.perf_counter() - started)
            if completed.returncode:
                print(completed.stderr, file=sys.stderr)
                return completed.returncode
            after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            before = max(before, after)
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    print(f"cold starts: {len(durations)}")
    print(f"median wall time: {statistics.median(durations):.3f}s")
    print(f"peak child RSS: {before / divisor:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
