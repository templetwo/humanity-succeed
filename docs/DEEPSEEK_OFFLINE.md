# Optional hosted engineering provider

This extension implements Anthony's 2026-10-06 assignment: optional DeepSeek plumbing,
fake-only offline integration evidence and an unexecuted connectivity proposal. B59 did
not authorize cloud execution. The six-condition local study, human judgments and
commissioning requirements are unchanged. No real credential was accessed, authenticated
request sent, model invoked or training performed during this build.

## Public interface reference

Read date: 2026-10-06. DeepSeek's [Chat Completions contract](https://api-docs.deepseek.com/api/create-chat-completion/)
requires `tool_call_id` for native tool messages. It documents thinking enabled by default,
explicit `thinking` and `reasoning_effort`, non-streaming responses, JSON output, usage and
termination reasons. This profile explicitly uses thinking **enabled**, effort **high**,
`max_tokens=4096`, `stream=false` and `response_format={"type":"json_object"}`. Temperature
has no effect in thinking mode and is omitted. The existing system instructions already
request JSON and provide an example; they are not rewritten. JSON formatting does not
replace the local strict action contract.

The [thinking-mode guide](https://api-docs.deepseek.com/guides/thinking_mode/) says prior
reasoning need not be supplied in subsequent requests without native tools. Accordingly,
returned reasoning is retained in a bounded, credential-screened API artifact and never
forwarded as an action or inserted into the common workroom conversation. The
[JSON guide](https://api-docs.deepseek.com/guides/json_mode/) documents possible empty
content and truncation. Neither triggers repair or another request here. The
[error-code reference](https://api-docs.deepseek.com/quick_start/error_codes/) informs
HTTP error classification. Documentation suggestions to retry are not adopted.
Model aliases are mutable; weights and tokenizer identity remain unknown. No model is
selected by default. Current public model names may be inspected by a human using public
documentation; this implementation has no model-list route.

MOA at `3a6f81b78277b085fdc5130bf66ad8f79b276378` was inspected as a design reference
(`moa/deepseek.py`, `docs/deepseek.md`, AGENTS and package rights metadata only). No
license grant was identified in that inspection. This is original implementation code;
no MOA code, scenarios, policies, settings or credentials were copied, and MOA was not
changed. Its authenticated model-list/warmup workflow was not adopted.

## Transport encoding: hs-deepseek-transcript/1

The canonical input remains `hs-workroom-interface/1`: system instructions, initial user
observation, then alternating assistant action text and synthetic tool result text.
`encode()` preserves the system, original user and assistant messages byte-for-byte in
content and order. Each internal tool message becomes an API **user** message containing
canonical JSON with exactly `encoding`, `original_role: "tool"` and the original `content`.
The odd positions after the initial pair identify these envelopes; `decode()` reconstructs
the canonical input exactly, including nested JSON strings. Role order is checked. There
are no API tools, native tool calls, invented identifiers, history truncation or summaries.

This changes presentation. A future comparison must report this encoding difference;
identical task semantics do not establish identical local and hosted presentation.
Every request records SHA-256 of the canonical subject observation and the actual
outgoing canonical JSON body. Authentication headers are never an artifact. The provider
worker gets only request bytes, selected transport limits and its host credential; it
gets no case, evaluator, answer key, rubric, future schedule, store or engine handle.
The API receives only the serialized conversation and generation settings. Effects stay
with the synthetic reference monitor and executor; no filesystem, shell, messaging or
cross-repository tools are offered to the model.

## Authorization and budgets

`hs hosted plan` requires an explicit model and allowed returned model identities. It
writes `hs-hosted-plan/1` without reading credentials or making requests. The plan binds
the imported path, resolved source commit and implementation fingerprint, case and subject
hashes, evaluator 0.3.0, encoding, fixed destination, settings and limits.

`hs hosted execute` additionally requires `--enable-cloud`, an explicitly selected
`--credential-file`, a strict `hs-hosted-authorization/1`, and explicit store, output and
ledger locations. Authorization binds the entire plan hash, simulation class, issuance,
expiry, approver and absolute ledger root. This is a trusted operator receipt, not a
cryptographic signature or a defense against a malicious administrator. The original
approval schema's `allow_network=false` is untouched and cannot authorize this path.
Simulation authorization cannot enter the live CLI transport.

The credential file accepts exactly one literal `DEEPSEEK_API_KEY=...` assignment with
an ASCII token, bounded at 64 KiB, in an owner-only file (0600 or stricter). No search, shell sourcing, expansion, environment lookup
or default location exists. All files used in this bound contain newly generated dummy
values in temporary state directories. Missing/expired/mismatched gates, changed source,
case or observation, and changed authorization refuse dispatch. Source and authorization
are rechecked immediately before each request. Credential content in source/configuration
is rejected before run persistence; credential-bearing observations are rejected before
observation persistence. Direct and JSON Unicode-escaped response echoes are discarded
before artifacts. Remote error bodies and exception text are never stored or printed.
This screening is not a claim to recognize every conceivable secret transformation.

Ceilings are four requests, 4,096 completion tokens per request (16,384 reserved total),
65,536 request bytes, 1,000,000 API response bytes, 64,000 action bytes, 45 seconds per
request and 180 seconds per episode. Lower explicit limits are allowed. Exact hosted
tokenization is unavailable: the byte guard is not a tokenizer/context audit or a dollar
budget. Available usage is recorded; missing usage remains null. No billing estimate is
invented. The single-use claim is exclusive in the authorization's pinned ledger. Each
attempt is durably reserved and fsynced before dispatch. A timeout consumes that attempt,
may leave server completion and billing unknown, and never permits retry. A fresh episode
requires fresh authorization. The ledger is not automatically reset or resumed.

The stdlib HTTPS client has one host `api.deepseek.com` and one POST path
`/chat/completions`, validated certificates and hostname, no custom base URL, proxy
inheritance, redirect following, retries or fallback. The spawned worker is terminated
at the request/remaining-episode deadline; this cancels local waiting, not necessarily the
server's generation. Fake workers deny socket connections as well as using fake replies.

## Evidence and failure contract

Hosted runs use prospective `hs-run-manifest/2` and `hs-evaluation/2` envelopes plus strict
versioned request/response/failure payload extensions to existing event types. Original
packet schemas and packaged copies remain unchanged. Legacy runs omit all new fields,
retain `/1` envelopes and serialize identically. The evaluator default remains 0.2.0;
hosted plans select 0.3.0 explicitly. Its predicates, guard facts, abstention facts and
pending human judgments are unchanged. `/2` changes provenance, not grading.

Future authenticated runs classify as `model_observation`; fake runs remain
`scripted_instrument` with mandatory `simulation=true`. Manifest, starting event,
evaluation and bundle classification agree. No fake result is a model observation.
Provider identity, approved settings, response model/id/fingerprint, nullable usage,
elapsed time, finish reason, request hashes and authorization/reservation metadata are
bound by the event chain. A model alias is not a weight hash. Unknown weight and tokenizer
identity stay null. API response artifacts preserve reasoning/termination metadata;
these are host evidence, not subject observations or reviewer judgments.

HTTP authentication, balance, rejected request, rate limit, server, TLS, redirect, timeout,
size and malformed API-envelope failures have separate codes and terminate as
`provider_failure`. Empty, prose-only, unknown-action, malformed or oversized **action
content** is a recorded `provider_response` followed by `action_parse_failed` and
`invalid_action`, not a network error. Every such response consumes its allowance.
Non-stop API termination (including length/content filter/abort/resource exhaustion)
preserves content and metadata but executes no partial action and ends `api_terminated`.
Mechanical predicates still report the actual local trace; no decline is inferred from
missing/invalid output. Guard denials and executed declines remain separate.

Export retains referenced request and API response artifacts. Static verification checks
strict identities, encoding inversion, request settings, source/class/evaluator bindings,
response contents and counters in addition to the existing chain and retained anchors.
Faithful replay uses `RecordedProvider`, recorded failures and timing metadata, the local
engine and the recorded evaluator. It does not remeasure provider latency, reauthorize a
live request or call the API. `hs hosted export` recovers from an already bound evaluation
in the existing store without executing, evaluating or contacting a provider. Failed
exports do not replenish authorization. Errors after execution identify the retained run.

## Offline acceptance and remaining boundary

`examples/deepseek_offline/case.json` is newly authored generic calibration-tag material,
not B59 or training data. `scripts/deepseek_offline_acceptance.py` is fake-only and denies
network in the supervisor and workers. Tests exercise isolation, reversible multi-turn
encoding, engine execution, failures, secret screening, gates, budgets, recovery and replay.
The receipt maps these to concrete commands and hashes.

The B59 regression harness explicitly validates frozen source against recorded repair
commit `d1645d8…`. Its real report preflight continues rejecting changed source. B59
freezes, fixtures, receipts, pending grids, suite-v1 and old golden files are not changed.
No independent technical/semantic reviewer or experimental authorship is claimed.

Live TLS/service compatibility, model behavior, actual usage/billing and any comparison
remain untested. The first connectivity proposal is non-executable until the human selects
model/returned identities, credential location and a fresh plan-bound authorization. It
permits one disposable episode, not a study or training arm. No human review, private
custody or holdback work, Stack write, push, merge, publication or release is in this bound.
