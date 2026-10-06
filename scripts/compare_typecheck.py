"""Compare Mypy diagnostic multisets including source-line content, not error totals."""

import argparse
import re
import subprocess
from collections import Counter
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, write_new_file

REPO = Path(__file__).resolve().parents[1]
DIAGNOSTIC = re.compile(r"^(.+?):(\d+): (error|note): (.+)$")


def diagnostics(log: Path, commit: str | None) -> list[tuple[str, str, str, str]]:
    source = {}
    result = []
    for line in log.read_text().splitlines():
        matched = DIAGNOSTIC.fullmatch(line)
        if not matched:
            continue
        path, number, severity, content = matched.groups()
        if path not in source:
            source[path] = (subprocess.run(["git", "show", commit + ":" + path], cwd=REPO,
                            check=True, capture_output=True, text=True).stdout if commit
                            else (REPO / path).read_text()).splitlines()
        result.append((path, severity, content, source[path][int(number) - 1].strip()))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-log", type=Path, required=True)
    parser.add_argument("--current-log", type=Path, required=True)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    before = Counter(diagnostics(args.baseline_log, args.baseline_commit))
    after = Counter(diagnostics(args.current_log, None))
    extra, resolved = after - before, before - after
    report = {"schema_id": "hs-typecheck-comparison/1", "baseline_commit": args.baseline_commit,
              "identity": ["path", "severity", "full message including error code", "source-line content"],
              "baseline_diagnostics": sum(before.values()), "current_diagnostics": sum(after.values()),
              "new": [{"identity": list(k), "occurrences": v} for k, v in extra.items()],
              "resolved": [{"identity": list(k), "occurrences": v} for k, v in resolved.items()],
              "baseline_errors": sum(v for k, v in before.items() if k[1] == "error"),
              "current_errors": sum(v for k, v in after.items() if k[1] == "error"),
              "all_diagnostics_preexisting": not extra}
    write_new_file(args.out, canonical_bytes(report))
    print(canonical_bytes(report).decode())
    raise SystemExit(int(bool(extra)))
