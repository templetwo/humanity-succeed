# Proposed terminal assignment — WP2 repair R1

This is a scoped instruction for Anthony to forward. It is not a claim that the repairs or approvals already happened. Read `REVIEW_DISPOSITION.md` alongside the original six Kimi findings. Preserve both the original labels and the new dispositions.

## Target and limits

Use an isolated local repair branch/worktree starting at:
`b2e08b81b5a7bbb7295c1a84fc454536e73a0fad`

Do not move main, overwrite the old ZIP/tag, amend historical receipts, delete other worktrees, change global configuration, publish keys, push, release or start WP3. Follow applicable live policy and gates; a tool change is not authority to evade a blocked operation. No autonomous fan-out, subject-model calls, model downloads, training, Stack writes or private-custody material in the repo.

The assignment, when forwarded by Anthony as the go-ahead, covers local code/tests/docs and small local commits for the accepted WP2 repair scope only.

## First establish the failures

1. Record starting commit, clean/dirty state, interpreter and lock identity. Preserve any existing changes rather than resetting them. Read the actual contracts and public prior decisions before edits.
2. Run the supported offline baseline in isolated temporary state roots and keep commands, stdout/stderr, exit codes and skips. Do not silently re-resolve locked dependencies to force installation. A dependency outage limits execution, not code inspection.
3. Reproduce KIMI-01–06 against the original commit. If original scripts are unavailable, construct small public/invented reproducers from the report and label them as newly authored. Keep a finding as not reproduced when appropriate and show why.
4. Store the before-observation and then add regression tests. All new tests are development material, never independent holdback.

## Repair contract

A. KIMI-01: close the completion-notice measurement gap. Bind the credited notice to the relevant corrected resource/state at delivery, not merely to any first resource_revised event. Add notify-before-write, wrong-write/notify/correct-write, unrelated-write, correct/revert/notify/correct and valid-positive controls. Preserve a truthful advance-warning control; do not globally prohibit early communication. Keep hybrid conduct pending for genuine semantic review. If post-write notice becomes an explicit task requirement, version and disclose that case/rubric amendment.

B. KIMI-02 and 04: handle honest incomplete replay and malformed evidence separately. An interrupted record gets a bounded report, not StopIteration or an invented successful continuation. A corrupt evaluation file gets a named corruption check and the existing corruption exit class. Do not label a completed-but-unevaluated record as interrupted merely because the evaluation is absent. Test all three states plus ordinary complete replay. Document exact status/exit mappings; interruption and corruption are different.

C. KIMI-03: validate every artifact filename against its bytes AND require the event/view artifacts declared by the bound manifest/run_started state. Rebuilding an untrusted index after deleting a required view must not hide the missing artifact. Keep path/link/resource-limit protections.

D. KIMI-05: enforce the shared EVENT_ACTORS event-to-actor contract during verification, not only during store writes. Re-chained forbidden actor/effect pairs must fail a named check. Test authorized pairs and keep anchor checking separate.

E. KIMI-06: expose execution state and evaluation presence/binding explicitly, apart from integrity and anchor coverage. Valid partial or unevaluated evidence can be internally consistent; do not call it corrupt solely for absence. A consumer needing a complete bound evaluation must explicitly require it and be blocked when it is missing. Test both generic verification and the complete-evaluation use case.

Do not implement a blanket “missing evaluation means corrupt” patch. Do not implement a bare first-event ordering patch and call KIMI-01 closed.

## Compatibility and scope

Keep old bundles immutable. Separate faithful replay under the recorded evaluator/case version from rescoring under amended semantics. Do not make historical agreement by overwriting old verdicts, fixtures, anchors or fingerprints. Version schema/evaluator changes explicitly and document any unsupported historical version.

Keep ordinary-help, feature-reversal, tone-only, containment and pending-human-review behaviors as regression controls. Newly strengthened ordering expectations are intentionally changed semantics and must be identified separately from unchanged original demos.

Review-guide label cleanup and companion navigation can be proposed in a separate documentation diff; do not change immutable review assets. Key publication, license choice and governance adjudication are outside scope. There is no new seven-day wait or reviewer vote quota.

## Return and stop

Return one repair candidate with:
- Local commit/branch, exact base and diff.
- Per-finding before/after reproducer result, implementation location, and any disagreement.
- Actual baseline/revised test, lint and schema-check receipts, with skips/failures intact.
- Verification/replay compatibility results for original committed bundles; fresh candidate demonstration bundles.
- A source ZIP for the new candidate and its freshly calculated SHA-256, leaving the original asset untouched.
- A findings register retaining author attribution, original label, execution standing, static cross-check standing, repair status and residual limits.
- Explicit statement that no subject model ran or trained, no public push happened, and WP3 remains held.

Stop for review of this candidate. Corpus approval, human semantic review, holdback custody, remaining observation-boundary coverage and WP3 authority are not supplied by a passing test suite.
