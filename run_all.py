"""Regenerate every output from the raw CSVs in data/, then run the tests.

    python run_all.py              # full rebuild + tests (a few minutes: the bootstraps dominate)
    python run_all.py --no-tests   # rebuild only
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("Data audit", "src/audit.py", "outputs/audit.txt"),
    ("Phase 1: ad ingredients", "src/phase1_ads.py", None),
    ("Phase 1: label spot-check", "src/spotcheck.py", None),
    ("Phase 1: ingredient summary", "src/phase1_summary.py", None),
    ("Phase 2: creator scoring", "src/phase2_creators.py", None),
    ("Phase 3: briefs", "src/phase3_briefs.py", None),
    ("Phase 4: report", "src/report.py", None),
]


def main():
    (ROOT / "outputs").mkdir(exist_ok=True)
    env = {"PYTHONIOENCODING": "utf-8", **__import__("os").environ}
    for name, script, capture in STEPS:
        t = time.time()
        print(f"-> {name} ...", end=" ", flush=True)
        out = open(ROOT / capture, "w", encoding="utf-8") if capture else subprocess.DEVNULL
        res = subprocess.run([sys.executable, script], cwd=ROOT, env=env, stdout=out, stderr=subprocess.PIPE, text=True)
        if capture:
            out.close()
        if res.returncode != 0:
            print("FAILED")
            print(res.stderr)
            sys.exit(res.returncode)
        print(f"done ({time.time() - t:.0f}s)")
    if "--no-tests" not in sys.argv:
        print("-> Tests")
        sys.exit(subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=ROOT, env=env).returncode)


if __name__ == "__main__":
    main()
