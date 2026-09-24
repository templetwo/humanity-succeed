"""Export implementation JSON Schemas from the pydantic contracts, reproducibly.

    uv run python scripts/export_schemas.py            # writes schemas/generated/
    uv run python scripts/export_schemas.py --check    # exit 1 if committed files differ

tests/unit/test_contracts.py runs the --check comparison, so a contract change shows up as a
reviewed schema diff rather than silently.
"""

from __future__ import annotations

import sys
from pathlib import Path

from humanity_succeed.canonical import canonical_str
from humanity_succeed.contracts.actions import ActionEnvelope
from humanity_succeed.contracts.case import CaseSource
from humanity_succeed.contracts.events import EventEnvelope
from humanity_succeed.contracts.schemas import implementation_case_schema

OUT = Path(__file__).resolve().parents[1] / "schemas" / "generated"


def rendered() -> dict[str, str]:
    docs = {
        "pydantic-case.schema.json": CaseSource.model_json_schema(),
        "pydantic-action.schema.json": ActionEnvelope.model_json_schema(),
        "pydantic-event.schema.json": EventEnvelope.model_json_schema(),
        "implementation-case.schema.json": implementation_case_schema(),
    }
    return {name: canonical_str(doc) + "\n" for name, doc in docs.items()}


def main(check: bool) -> int:
    want = rendered()
    if check:
        diff = [n for n, t in want.items()
                if not (OUT / n).is_file() or (OUT / n).read_text() != t]
        extra = sorted({p.name for p in OUT.glob("*.json")} - set(want))
        if diff or extra:
            print("schema drift:", diff, "unexpected:", extra)
            return 1
        print("schemas/generated matches the contracts")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for n, t in want.items():
        (OUT / n).write_text(t)
    print(f"wrote {len(want)} schemas to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--check" in sys.argv))
