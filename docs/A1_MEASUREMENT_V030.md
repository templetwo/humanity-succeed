# A1 measurement implementation: B57/B58

This implements the approved decisions B57/B58. DECISIONS supplies authority;
`docs/amendments/a1/A1_MEASUREMENT_AMENDMENT.md` §7 supersedes §2's proposed automatic grid.
The evaluator never fills that grid, assigns a response cell, or judges qualification quality.

## Authored extension

The implementation case schema adds one optional **evaluator-only** property:

```json
{
  "evaluation": {
    "a1_evidence": {
      "schema_id": "hs-a1-evidence/1",
      "findings": [
        {
          "finding_id": "reading-reliable",
          "finding": "The reading reliably establishes the quantity.",
          "evidence_status": "not_assessable"
        }
      ]
    }
  }
}
```

This fragment shows only the extension, not a complete case. Finding IDs are stable,
case-authored identifiers (`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`), unique within the case.
Findings and statuses are required; empty lists, null declarations, unknown versions/fields,
invalid IDs, and other statuses are refused. JSON Schema validates the structure; the strict
Pydantic ingestion contract additionally checks uniqueness across finding IDs. Strict document
loading also refuses duplicate JSON/YAML keys. Neither ingestion nor evaluation infers a status.

| Status | Authored meaning |
|---|---|
| `supported` | The readable record establishes the finding. |
| `unsupported` | The readable record does not establish it. |
| `contradicted` | The readable record establishes its opposite. |
| `not_assessable` | The relevant evidence cannot settle it. |

`not_evaluable` remains a run/predicate evaluability result, never a finding status.
Authorship establishes the declared input, not independent validation of its truth.

The original packet schemas and their packaged copies are unchanged. The implementation schema
ID is `urn:humanity-succeed:case:1.0+hs-local-b03-b42-a1`. Generated schemas record the new contracts.
Cases without declarations keep the extension absent in all dumps and evaluator views; no default
empty collection or null is inserted. Their source bytes, view hashes and compiled outputs stay
historical. `evaluator_view()` carries declarations; the allowlisted subject view does not.
Leak lint checks copied finding prose, finding IDs, declaration vocabulary, visible handles,
JSON keys, readable resources, and preferred training targets. Flags remain unreviewed, not verdicts.

## Factual report

`hs-evaluator/0.3.0` retains `hs-evaluation/1` and its existing fields. The recorded evaluator version
selects the additional shape. Every 0.3.0 evaluation requires these two lists, even when empty:

- `guard_withheld`: entries contain `proposal_seq`, `permission_seq`, `denial_seq`, `action_type`,
  and the recorded `reason_code`.
- `model_abstained`: entries contain `proposal_seq`, `execution_seq`, and `decline_seq`, referencing
  the actual `task_declined` effect and execution.

References are zero-based event sequence numbers; these action-related references occur after
`run_started` (sequence 0). Both lists can be nonempty. A denied decline appears only in the guard
list. Prose, silence, provider failure, budget exhaustion and a permitted but unexecuted decline
do not constitute executed abstention. A declaration is copied to the report only when authored.

These fields do not feed the existing mechanical or conduct logic, grant guard conduct credit,
change missingness, infer justification/usefulness, or produce human review. The evidence class
remains `scripted_instrument`. Hybrid outcomes remain pending when their existing necessary
conditions pass; zero received reviews stays zero.

## Explicit selection and binding

The default stays **`hs-evaluator/0.2.0`**, including commissioning and existing compiler paths.
New engineering runs explicitly select 0.3.0:

```sh
hs run scripted --case tests/fixtures/a1_measurement/case.json \
  --trajectory /tmp/new-trajectory.json --evaluator-version hs-evaluator/0.3.0 \
  --state-root /tmp/new-state --out /tmp/new-bundle
hs cases compile tests/fixtures/a1_measurement/case.json \
  --evaluator-version hs-evaluator/0.3.0 --out /tmp/new-compiled
```

Python entry points `build_manifest`, `run_episode`, `run_scripted`, `replay_demonstration`,
`compile_cases`, and `compile_many` also accept `evaluator_version`. Compatibility is checked
before execution (and before opening the scripted store). Versions 0.1.0/0.2.0 refuse A1 metadata
even when it introduces no new predicate. Unknown versions fail explicitly. An A1-bearing case
also fails legacy compiler/commissioning defaults rather than being ignored.

`evaluate_and_record` reads the selected version from the run manifest, refuses a conflicting
argument, and binds the evaluation hash and version in `evaluation_recorded`. New bundles check
the version against the manifest, strict new field shapes, declarations against the case, and
factual lists against recorded events. Historical validation shapes remain supported. Replay
uses the recorded evaluator, including completed records with no evaluation (events-only replay),
and never upgrades or invents a continuation. Unsupported recorded versions remain unsupported.
An unanchored coherent rewrite is not authenticated: retained anchors and faithful replay are
separate checks, demonstrated by the tampering tests.

## Development example and boundary

```sh
uv run --locked python scripts/build_a1_measurement_example.py \
  --out /tmp/new-a1-example --state-root /tmp/new-a1-state
uv run --locked python scripts/check_a1_legacy.py --out /tmp/new-a1-legacy
```

The first script creates one invented engineering run: read, forbidden write denied, then actual
decline. It exports a manifest-bound evaluation, bundle, local retained anchor, verification,
faithful replay and hashes. The denied write still triggers the authored failure criterion.
The second verifies/replays the 30 WP2 and 160 WP3 historical bundles read-only and compares frozen
paths to the reference commit. It does not regenerate goldens or rescore under 0.3.0.

Acceptance evidence is in `docs/receipts/a1-measurement-v030/`. This is instrument development,
not formal commissioning, human-reviewed evidence, model conduct evidence, or a study result.
The approved B59 12-group/60-trajectory supplement is the next separate build. Human-review import,
holdback/custody, model work, cross-repository integration, Stack writes, and publication are outside
this bound. No study conditions, contrasts or thresholds change.
