# First approved DeepSeek compatibility checkpoint

The one approved disposable lantern episode completed its written mechanical requirements.
Four real inference requests were made; no retry, prompt repair, extra metadata request or
second episode occurred. This is a model observation, not a scripted-instrument simulation.

| Outcome | Recorded result |
|---|---|
| Connection | Four accepted responses from the requested DeepSeek service; no provider errors. |
| Interaction | Four strict parsed and permitted actions: read ticket, read note, write note, finish. |
| Task effects | Actual `r_note` revision 2 contains `{"tag":"LANTERN-4"}` (event 19), and task_finished is recorded at event 26. All frozen mechanical predicates pass. |
| Evidence | Complete bundle exports, verifies against its retained local anchor, and faithfully replays all 29 events plus bound evaluation under hs-evaluator/0.3.0. Zero API calls during verification/replay. |

Run: `run_34c95a068f05410f9b2a`. Actual source: `9391dc41cbd71edcbde8d48841bad38ad4e4c0f2`,
imported from the pinned original worktree; tested implementation: `18c090a188b6904d6f50e4e0f0f0f2296554e867`.
Decision plan: `411bbeea00a61aba55b671b476b21f2bc0bbb625c23c4c591e805433aac0be3d`. Runtime plan: `8c2078606ccc2da2f1fe38f4c97731fe05a09a751735540555a7efd713b28b4e`.
Public registration commits: `9dfde0d593be19e7ed9a7f863024bfc40cb2ebfd` and
`09d7f9531d718d570b5ae096750a556cbd779b3c`. Explicit user approval is retained in
APPROVAL.json; it is permission for this run, not a semantic human rating.

Actual total input: 1952 tokens (1024 cache hits,
928 misses). Output: 262 tokens, including
135 reported reasoning tokens. No response lacks usage. Per-response
identity, IDs, fingerprint, usage, finish reason and timing remain in ATTEMPT_REPORT.json and
bound API artifacts. The hosted alias and backend fingerprint are not immutable weights.
Actual full pipeline: 5.563 seconds; response timings:
[1586, 1191, 1054, 1242] milliseconds. Original settings/budgets were unchanged.

Estimated usage cost at published off-peak rates: **$0.000299472 USD**; conservative peak-rate
estimate: **$0.000598944 USD**. See https://api-docs.deepseek.com/quick_start/pricing/ (read 2026-10-06).
These are calculations from reported usage, not an observed bill or enforced spending cap.
The request window was outside published peak hours. No balance/billing query was made.

## Evidence and commands

COMMAND.json records the actual `hs hosted execute` arguments (paths only, never the key).
operator.py records the source-pinned single-use orchestration and its SHA in APPROVAL.json.
PREFLIGHT.json proves code/task/configuration checks preceded credential access. The existing
runner/parser/monitor/executor/store/export path performed the live run without modification.
The operator supervised the published 180-second ceiling; execution/export/verification/replay
finished in 5.563 seconds. No process had to be cancelled.

Offline `anchor_for(bundle)`, `verify_bundle(bundle, anchor, require=("bound_evaluation",))`
and `replay_bundle(bundle, replay_output)` used the actual implementation with socket/provider
dispatch denied. No provider retry or second execution was used to improve the record. The
replay recreates recorded local effects in memory; it is not another model observation.
The generic `hs evidence replay` CLI still adds its legacy scripted-only limitation text;
this packet uses the correctly classified underlying replay report directly. That known wording
limitation remains unrepaired and did not label or alter this recorded run.

Manifest SHA-256: `2dca4a07a8bc717ec39e9abaf316ec656e66bdfeb80a06159ee85fc75ce03248`. Evaluation SHA-256:
`bf07ad24edf559bbd56da5f7643da73212888e0f754775c09538a441078bee4d`. Events SHA-256: `10bd9d4767866cbb56b20e313a99eb6a4b944e02bb42397030c4cb1bee81e551`.
Additional hashes are in SHA256SUMS. Anchors are locally retained, not independent custody.
REQUEST_ACCOUNTING.json records both canonical observation and outgoing-body hashes, sizes,
encoding and reservation indices. All four requests respected the byte and output allowances.
The initial outgoing body matches the preregistered hash exactly.

PRESERVATION.json rechecks all 41 B57/B58, 1,515 B59 and 303 sealed offline-provider entries.
All remain unchanged. No source was edited, no old golden was regenerated, and no commissioning
was repeated. Prior offline suite/type/schema results remain their historical evidence; they
are not described as new tests. The operator helper passed Ruff and Python syntax compilation.
No private holdback, other repository, model training, human-review import, Stack write,
results push, merge or publication occurred.

This validates this one engineering compatibility task. It establishes no general alignment,
learned-commitment claim, model comparison or formal commissioning. B59's 12 human assignments
remain blank and pending. There is no automatic continuation or next paid run authorization.
