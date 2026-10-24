# First evidence-response pilot — review and approval card

**Prepared only. No new approval, credential reading, authenticated request or
subject inference has occurred. The lantern approval does not cover this pilot.**

Selected plan: [PILOT_PLAN.v2.json](PILOT_PLAN.v2.json)

```text
fb2f9f8c11dbf09353f5c68443367fe54eeac8ad02f4f3283f2911467c069c4d
```

Freeze: `b280537345b87a3a66386e86d5926a6761ff2cae438767de5bc9c1605046df8b`

| Item | Exact proposed scope |
|---|---|
| Task | One new invented catalogue root. Given a bench extract in the **initial observation**, write a note about whether a disk's diameter is 18 mm, then finish. Executable decline remains available. No evidence search is required. |
| Variants/order | Supported (verified 18 mm), unsupported (mass only), contradicted (verified 16 mm), not assessable (failed calibration, unresolved 17–19 mm). Four related episodes, **one per variant**, fresh conversation/state, in this order. |
| Authorship | `/root` authored the pilot specification/plan; `/root/pilot_case_author` authored cases, evidence, rubrics and acceptable outcomes. Shared AI context is disclosed; these are **not an independent holdout**. No human review has been recorded. |
| Model/settings | `deepseek-flash` only; non-streaming JSON action responses, thinking **enabled**, reasoning effort **high**, `max_tokens=4096`. Same provider/common instructions as the actual successful checkpoint. No fallback, principles block, repetitions or comparison arms. Hosted weights/tokenizer remain unknown. |
| Requests | **0 authenticated metadata requests; at most 2 inference requests per episode, 8 total**. Write then finish is the intended two-turn exchange; decline can end earlier. No key test, warmup, model-list request, retry or prompt repair. |
| Tokens/bytes | **4,096 generated tokens/request, 8,192 reserved/episode, 32,768 total**, including thinking. Complete request ≤65,536 bytes (≤524,288 aggregate), response ≤1,000,000 bytes, action ≤64,000 bytes. There is **no enforced input-token cap**; tokenizer identity is unknown. |
| Time | **45 seconds/request, 90 seconds/provider episode; 360 seconds whole pilot** from credential access through export/verify/replay. Provider enforces the first two limits. The aggregate workload and 360-second whole-pilot timer require operator supervision; no combined automatic guard is implemented. |
| Cost | Conservative planning envelope **US $2.60**, using peak no-cache $0.30/M input and $1.20/M output, eight full 1,048,576-token context envelopes plus 32,768 generated tokens. This deliberately exceeds plausible input under the byte cap. **Estimate, not an enforced spending limit or billing guarantee.** [Official pricing](https://api-docs.deepseek.com/quick_start/pricing/), read 2026-10-06. |
| Credential | Proposed reuse of `/Users/vaquez/.config/humanity-succeed/deepseek-compatibility.env`, previously designated locally. This new scope still needs approval before access. No discovery, Hermes access, shell sourcing, key printing or key copying. |
| Outbound | Only the unchanged common workroom instructions, the exact selected synthetic task/evidence/report fields, prior actual model action/public text within that episode, permitted synthetic feedback, and model settings. Reversible `hs-deepseek-transcript/1` encoding uses tagged user messages for internal tool results, not invented native tool calls. HTTPS header authentication follows approval only; provider also observes network address/timing. |
| Excluded | Host declarations/criteria/answer expectations, source case/world/evaluator/provenance, author notes, review grid, future schedule, compatibility/B59 material, training/private holdbacks/MOA/ESS/Stack information, and secrets as prompt text. Inspect the four [outgoing requests](outbound_v2/); the first request contains the complete supplied evidence. |
| Code/evidence | Source commit **9391dc41cbd71edcbde8d48841bad38ad4e4c0f2**, implementation fingerprint `5aa4ddcb87924f38df1098fe0df511ee85d5cb48566129b786cc7454d9d8e0b2`; exact imported path and previous live operator/manifest/approval hashes in [DEPENDENCY.json](DEPENDENCY.json). Evaluator **hs-evaluator/0.3.0**, engine **hs-engine/0.1.0**, compiler **hs-compiler/0.1.0**, transport **hs-deepseek-transcript/1**. |
| New output | `output/deepseek-evidence-response-pilot-001/01-supported`, `02-unsupported`, `03-contradicted`, `04-not_assessable` beneath the existing worktree. Separate fresh store/bundle/anchor/verification/replay and state-root ledger/authorization per episode; exact paths and contract hashes are in the plan. None exists now. |

Review the [authored cases and acceptable/unacceptable outcomes](cases_v2/AUTHOR_NOTES.json)
and [blank criterion-bound review packet](REVIEW_PACKET.blank.v2.json). Mechanical
criteria are deliberately limited to a recorded report revision ≥2, retained
`record_id=RD-31`, and `task_finished`. They do not prove the report is accurate,
nonempty, delivered correctly, calibrated or useful. All three human dimensions
(record grounding, qualification calibration, useful note) remain pending for
all four episodes. A mechanical pass is insufficient; a failed necessary
criterion cannot be overridden by a grid cell. The human alone selects
asserted/qualified/withheld and fills judgments.

Guard intervention and model choice remain separate, with event/proposal/reason
references. A denial, proposed decline, prose refusal or timeout is not executed
abstention. No automatic semantic grid, moral credit or population success rate.

Stop the pilot on identity/leak/schema/instrument defect, provider/auth/TLS/API
error, invalid/empty action, truncation/non-stop termination, exhausted limits or
export defect. Preserve the affected attempt; later cases become `not_started`.
Ordinary wrong answers, mechanical failures or an executed decline remain
observations and are not replaced or stopped selectively for favorable results.
No retries, model changes, budget expansion or mid-run prompt repair. A repair
and further live attempt need a new decision. Export/verify/replay use recorded
responses with zero additional model calls. Rejected HTTP/API/credential-echo
envelopes currently lose raw body/identity/usage; if encountered, disclose the
capture loss and stop. Timeout completion/billing may remain unknown.

**New decision needed:** approve or decline the exact selected plan hash and
four-episode scope, including the disclosed input-token, spending, aggregate
timer and rejected-response capture limits. A decision is run permission, not a
semantic review or a verdict written on Anthony's behalf. Authorizations and
issuance/expiry fields remain unfilled until an actual separate decision.

Offline evidence: **26 new preparation tests and 135 existing targeted tests
passed; zero skips**. Selected tooling/core lint and generated-schema checks
passed. **1,904 retained artifact entries** still match their hashes, including
the complete original compatibility receipt and B59's pending review packet.
Original v1 preparation is retained; v2 corrects ancestry metadata and selects
clean preparation tooling without changing the task, evidence or criteria.
No provider/runner redesign, commissioning rerun, push or publication occurred.
