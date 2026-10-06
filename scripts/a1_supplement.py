"""Separate B59 commands. No model, training, review import, retry or global default change."""

import argparse
from pathlib import Path

from humanity_succeed.a1_supplement.contract import validate_supplement
from humanity_succeed.a1_supplement.study import enactment_check, freeze, generate, preflight, run
from humanity_succeed.canonical import canonical_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate")
    gen.add_argument("--out", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--corpus", type=Path, required=True)
    validate.add_argument("--enactment", action="store_true")
    freeze_cmd = commands.add_parser("freeze")
    freeze_cmd.add_argument("--out", type=Path, required=True)
    freeze_cmd.add_argument("--state-root", type=Path, required=True)
    for name in ("preflight", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        report = generate(args.out)
    elif args.command == "validate":
        report = enactment_check(args.corpus) if args.enactment else validate_supplement(args.corpus)
    elif args.command == "freeze":
        report = freeze(args.out, args.state_root)
    elif args.command == "preflight":
        plan = preflight(args.plan)
        report = {"status": "valid", "evaluator": plan.evaluator, "source_commit": plan.source_commit}
    else:
        report = run(args.plan)
        print(canonical_bytes({k: v for k, v in report.items() if k != "rows"}).decode())
        return int(bool(report["discrepancies"]) or not report["all_evidence_checks_passed"])
    print(canonical_bytes(report).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
