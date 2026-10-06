# Fresh B57/B58 technical dependency review

Reviewer: `/root/review_dependency`, a fresh technical-review agent. Case author:
`/root/case_author`; supplement machinery builder and prior evaluator builder: `/root`.
Specification author and approval: Anthony's bound and recorded B59 decision.
This is collaborating-agent technical review, not human semantic review or an
independent experiment. No B59 fixture was evaluated during this review.

Reference `3f304a14da78ef29165254a574d2f015aecd7d20` is an ancestor of tested
implementation `fede45e3a9a749318e9415c1f071c3d996c22882`, which is an ancestor of
receipt `555b1b299bc9f78c90227f348c9fc1d91acc3a45`. The receipt changes only
`docs/receipts/a1-measurement-v030/` and appended implementation facts in
`docs/DECISIONS.md`; it contains no code change. The dependency worktree stayed clean.
All 41 receipt checksum entries match. Its checksum inventory itself has SHA-256
`a3630ae2e4be55915967c28507593905ad3dae911a849f584d3d16c9099d5447`.

No blocking defect was found for bounded scripted B59. Inspection confirmed:

- Prospective explicit 0.3.0 selection with the 0.2.0 legacy default retained.
- Metadata refusal by older evaluators before execution/compilation.
- Manifest/evaluation chain binding, required new-field validation and recorded-version replay.
- Strict four-status declarations, no implicit empty extension on legacy cases.
- Allowlisted subject views and actual provider/SFT-prefix canary isolation tests.
- Guard denials traced separately from executed declines, including denied-decline,
  prose-only, silence and interruption negatives; no conduct credit from denial.
- Pending human review remains pending; no grid or qualification judgment is populated.
- Historical serialized results, hashes and frozen artifacts remain preserved.

Fresh rerun: `.venv/bin/python -m pytest -q -p no:cacheprovider tests/integration/test_a1_measurement.py`
returned **45 passed in 2.27 seconds**, no skips or failures. Fresh anchored verification
of the retained example returned internal consistent, verified against anchor, bound
evaluation, evaluator 0.3.0, and all 24 verification checks passed.

Reused historical evidence was checked directly: all 380 actual event/evaluation hashes
match the retained 190-bundle receipt (30 at 0.1.0, 160 at 0.2.0). Retained verification,
replay and recorded versions agree; both golden hashes match. The reference-to-dependency
diff over all 11 retained historical paths is empty. The hashed offline regression log
records 684 passes in 198.31 seconds. The reviewer did not repeat all 190 replays or the
full offline suite because the retained evidence was sufficient for this dependency review.

Mypy logs were compared as multisets of path, severity, complete diagnostic/error code,
and source-line text at each recorded commit, preserving duplicate occurrences. All
44 diagnostic lines match (40 errors, four notes), with zero new/resolved diagnostics.
Source line shifts alone account for location differences. The baseline checked 54
source files and the dependency 55; no new dependency type error needs repair.

Commands included read-only git status/rev-parse/log/show/diff/merge-base, SHA-256
calculations and diagnostic/source comparisons. No private packets, holdbacks,
external services, Stack writes or source mutations were used. Limitations: local
anchors are not independent custody; declarations are authored rather than certified;
leakage checks are mechanical; 40 unrelated baseline Mypy errors remain.
