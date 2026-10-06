# Optional DeepSeek provider — offline acceptance

The optional DeepSeek provider passed offline transport and end-to-end integration tests.
No authenticated request or model inference occurred. Live compatibility and behavioral
evaluation remain untested.

Branch: `provider/deepseek-offline`, isolated worktree
`/Users/vaquez/Desktop/🔬 Active_Research/humanity-succeed-deepseek-offline`.

- Verified starting/dependency receipt: `677949fd07aebd0c852beb10de5d9887b081f344`.
- Dependency tested code: `d1645d8012568f5dcdc0af21e6e3a9614121b125`.
- Initial provider implementation and eleven engineering executions:
  `b5729d37a1ead28a381143436c98a86ac982d71b`.
- Fixture relocation: `ce711e1d216f334afd277716949fb199c98510e9`.
- Final tested code: **`18c090a188b6904d6f50e4e0f0f0f2296554e867`**.
- Receipt commit: resolve the local commit introducing this file with
  `git log -1 --format=%H -- docs/receipts/deepseek-provider-offline/acceptance.json`;
  its full SHA is provided in the handoff. A receipt cannot embed its own Git commit hash.

The receipt commit changes only this receipt material and appended implementation facts
in DECISIONS. No push, merge, publication, Stack write, real credential access, subject
inference, training, human-rating import or private holdback access was performed.

## Scope and representation

This implements Anthony's separately assigned 2026-10-06 optional-provider bound, not a
cloud authorization derived from B59. Default offline behavior and the six-condition
local study remain unchanged. All authoring, implementation and acceptance interpretation
here are the Codex builder's work; no independent experiment or human semantic review is
claimed. MOA was a read-only design reference, not copied implementation or study material.
See [the transport and authority contract](../../DEEPSEEK_OFFLINE.md) for official source
links, read date, rights inspection, encoding, deadlines, unknown identities and limitations.

New strict contracts are `hs-hosted-plan/1`, `hs-hosted-authorization/1`,
`hs-hosted-provider/1`, `hs-hosted-request/1`, `hs-hosted-response/1` and
`hs-hosted-failure/1`. Hosted runs use manifest/evaluation `/2`; historical `/1`
serialization and original packet schemas/copies are preserved. Fake transport is
`scripted_instrument` with mandatory `simulation=true`. Future actual hosted runs are
`model_observation`. Selected evaluator remains explicitly 0.3.0; no global bump or
predicate/conduct change was made.

`hs-deepseek-transcript/1` reversibly encodes synthetic tool observations as tagged API
user messages. System, initial task, assistant history, content and turn order remain
intact. No native tool calls or identifiers are invented. Both canonical observation and
actual request hashes are recorded; future comparisons must disclose the presentation
difference. The worker receives serialized request/configuration only; the host validates
case/source authorization. The API cannot access evaluator data, real tools or other repos.

The chosen profile is explicit thinking enabled, effort high, non-streaming JSON,
4,096 output tokens per request and up to four requests per short episode. Authorization
binds source/import identities, case/subject hashes, model/returned identities, encoding,
destination, settings, budgets, expiry and ledger root. Missing/changed/exhausted gates
refuse network; attempts are reserved before dispatch. TLS validation, fixed endpoint,
no proxy inheritance, redirects, retries or fallback, owner-only explicit credential files,
credential-echo suppression and separate worker deadlines are covered offline.

## Requirement-to-test evidence

All names below refer to `tests/integration/test_deepseek_offline.py` unless stated otherwise.

| Requirement | Tests and retained evidence |
|---|---|
| Evaluator-only observation isolation | `test_reversible_multi_turn_isolation`, `test_compiled_messages_isolated_without_evaluation`; canaries absent from requests/compiled rows, changed declarations preserve bytes, copied canary is linted |
| Reversible multi-turn presentation | `test_reversible_multi_turn_isolation`; `current-source-example/bundle` contains all three request bodies and observations; static encoding inversion and replay pass |
| Parser, monitor, executor, evidence, export, replay | `test_end_to_end_and_recovery`, `test_guard_denial_then_actual_decline`; copy task passes, denial-plus-decline fails useful work with separate facts |
| Honest failure accounting | Parameterized `test_failures_distinct_recorded_and_replayed`, `test_invalid_content_is_observed_action_failure`, `test_terminated_api_content_has_no_effect`, `test_oversized_action_is_observed_not_transport_failure` |
| Credential protection | `test_literal_dummy_credential_only`, `test_secret_inputs_refused_before_persistence`, echo/direct-Unicode negatives in failure tests; only newly generated temporary dummy files read |
| Authorization/budgets/no default networking | `test_invalid_gates_before_dispatch_or_credentials`, `test_single_use_and_request_budget`, `test_episode_expiry_and_changed_authorization_before_dispatch`, `test_ledger_relocation_requires_new_authorization`, `test_limits_recorded_and_replayed`, `test_missing_hosted_gates_never_access_credentials` |
| Fixed destination/TLS/proxy/redirect controls | `test_fixed_https_contract_no_proxy_or_redirect`, redirect/TLS failure rows; all targeted supervisor and fake-worker connections denied |
| Export recovery and no replay API calls | `test_end_to_end_and_recovery`, `test_export_cli_reuses_recorded_evaluation`; `current-source-example/capture.json` records read-only export with zero new executions/requests |
| Unknown identities, strict metadata and tampering | `test_unknown_usage_and_identity_remain_unknown`, `test_strict_plans_no_custom_endpoint_or_unknown_fields`, `test_versioned_records_require_schema_identifier`, `test_static_tamper_detection`, malformed-evaluation parameterization |
| Human judgments and historical preservation | `test_hybrid_judgment_remains_pending`, existing A1/B59/golden tests; `preservation-final.json` verifies inventories and freshly replays all 250 retained bundles |

## Commands and results

Exact invocations, exit codes and logs are in `COMMANDS.json` and `checks/`.

- Targeted provider + A1 + B59: **189 passed**, including 55 new provider tests.
- Final full offline suite: **828 passed in 155.71 seconds; zero skips**, JUnit retained.
- Generated schema comparison: all 16 match. Ruff and whitespace checks pass.
- Both new engineering documents validate as draft development material; leakage lint
  reports zero flags. Neither acquires reviewed or training-eligible status.
- Mypy exits 1 with **40 baseline errors and four notes**. The diagnostic multiset compares
  path, severity, complete message/code and actual source-line content against recorded
  `d1645d8…`; no new or resolved diagnostics. Counts alone were not used.
- Fresh final-source verification/replay: **250 historical bundles**, 30 under 0.1.0,
  160 under 0.2.0 and 60 B59 under 0.3.0. The original 41-file B57/B58 and 1,515-file
  B59 receipt inventories match; frozen cases, plans, reports, human packets, golden
  bytes, compiled behavior and evaluation/event digests remain unchanged.

The B59 harness now validates the historical freeze's source hashes against the recorded
repair commit. Its real preflight still refuses this newer source. No golden was regenerated
and suite-v1 was not relaxed.

## Preserved findings and executions

The initial full regression at `b5729d3…` returned **5 failures / 823 passes**.
`checks/offline.log` and XML retain that result. Four failures came from placing new A1
fixtures inside the recursively loaded legacy examples tree; explicit 0.2.0 correctly
refused them. The fixtures were moved to separate `engineering/` directories. The fifth
failure came from replacing the historical scripted replay banner; `/1` retains its old
banner and `/2` explicitly reports simulation or model observation. Repairs were followed
by 61 targeted passes, 56 final focused passes and the complete 828-test regression.
Earlier development checks also caught a missing JSON-mode SubjectView serialization,
new type annotations, a mistaken verification-status test assertion, a CLI gate variable,
and recovery opening an existing store for creation. All were repaired before final
acceptance. The oversized-action classification was corrected to observed parse failure.
No unresolved test failure is hidden by golden regeneration or a skip.

The eleven initial engineering scenarios and their fourteen **fake** transport attempts
remain in `engineering/`, pinned to their actual `b5729d3…` execution source. They are not
relabeled as later executions. Their manifests/evaluations agree on explicit 0.3.0; all
verify and replay. HTTP authentication/rate/server/timeout/protocol/credential-echo failures
are `not_evaluable`; empty/prose-only responses are observed `invalid_action`; truncated
content has no effect. The successful copy passes. Denial followed by an executed decline
has both trace facts and fails the required useful-work criterion. These are authored,
shared-fixture simulations, not independent model observations.

`current-source-example/` retains the complete successful execution produced by the
final-source end-to-end test at **18c090a…**. It was exported read-only from that test's
existing store, with no extra provider request, execution or evaluation. The manifest has
clean source identity and the actual imported path/fingerprint. Original manifest,
evaluation and event digests are preserved; anchored verification and faithful replay
pass. Three fake requests are retained; capture/replay make zero API calls. The intentional
export failure in the test did not cause another provider request.

`EVIDENCE_HASHES.json` records manifest/evaluation/event/report anchors; `SHA256SUMS` covers
all packet files except itself. Each bundle also has its own index and hash inventory.
These are local retained anchors, not public timestamps or external custody claims.

## Handoff

`LIVE_PROPOSAL.json` is **unexecuted and non-executable**. It identifies a separate fresh
synthetic lantern-label task, exact outbound inventory/hashes, the selected thinking
profile and finite budgets. Model, allowed returned identity, credential location,
authorization, ledger and output location remain null. A human must select these and create
a fresh plan bound to the then-current imported implementation; this proposal itself
cannot authorize execution. There is no authenticated model-list or warmup step.

Live service compatibility, actual model behavior, alias weights, tokenizer/context counts,
usage and billing remain unknown. Credential screening is not proof against every possible
secret transformation. No human grid or semantic verdict was filled, and no formal
commissioning or learned conduct was established. B59 remains fixed at 677949fd…;
its qualified-review packet is unchanged and pending the separate human step.
