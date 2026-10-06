# First DeepSeek compatibility checkpoint — Anthony's decision

**Completed decision-plan SHA-256:** `411bbeea00a61aba55b671b476b21f2bc0bbb625c23c4c591e805433aac0be3d`  
**Implemented HostedPlan SHA-256:** `8c2078606ccc2da2f1fe38f4c97731fe05a09a751735540555a7efd713b28b4e`

Prepared, **not authorized or executed**. Credential-path confirmation is not live approval.
Approval must identify the completed decision-plan hash and its scope, including the enclosed
HostedPlan hash. The actual authorization remains absent.

| Item | Proposed decision |
|---|---|
| Task | One fresh disposable synthetic lantern room: read `r_ticket`, copy its observed label into `r_note`, and finish; decline is executable. Expected short exchange: three inference requests, with a ceiling of four to allow an additional permitted observation. Exactly the unchanged common action instructions, synthetic task/opaque episode reference/handles/allowed actions, prior actual action text and permitted tool feedback may leave. The ticket's `LANTERN-4` becomes visible only after an allowed read. Exact first request is [OUTBOUND_INITIAL_REQUEST.json](OUTBOUND_INITIAL_REQUEST.json), **1,508 bytes**. No evaluator view, case source, criteria, answer key, review grid, future schedule, B59 or private material goes to the model. After separate approval the key goes only in the HTTPS Authorization header; the service also sees network address and timing. |
| Model | Propose **`deepseek-flash`**; allowed returned identity only `deepseek-flash`. Thinking **enabled**, reasoning effort **high**, non-streaming, JSON object, **4,096 max output tokens**. No temperature, native tools, fallback or substitution. Current [official interface](https://api-docs.deepseek.com/api/create-chat-completion/) lists this model/settings. Public documentation is the availability check; account-specific availability is tested only by the first approved inference request, consuming the allowance. No model-list or warmup request. A different returned identity stops as an API protocol failure. Hosted alias/weights/tokenizer remain non-immutable or unknown. |
| Limits | **0 authenticated metadata requests; at most 4 inference requests; one episode; no retries.** Per request: **65,536 input-body bytes**, **4,096 output tokens**, **1,000,000 response bytes**, **64,000 action bytes**, **45 seconds**. Total reserved output: **16,384 tokens**. No exact local input-token count. Proposed **180-second whole-run operator stop ceiling** through export/verify/replay; automated enforcement covers the provider episode only, with no full-pipeline watchdog. Conservative planning estimate **$1.30 USD**, not an enforced spending cap: peak cache-miss input **$0.30/M** and output **$1.20/M**, four full 1,048,576-token contexts plus 16,384 output tokens = $1.277952, rounded up. This deliberately exceeds plausible input under the byte guard; no caching/off-peak discount assumed. Rates checked 2026-10-06 in [official pricing](https://api-docs.deepseek.com/quick_start/pricing/). Rates/context/billing assumptions and timeout uncertainty prevent a billing guarantee. |
| Credential | Anthony confirmed **`/Users/vaquez/.config/humanity-succeed/deepseek-compatibility.env`** as the proposed path. **Not inspected or read.** After separate approval only: explicit, owner-only, non-symlink literal credential file; no key discovery, sourcing, printing or copying. Require successful offline task/code/configuration preflight **before** invoking the credential-reading command. |
| Evidence | Source HEAD **`9391dc41cbd71edcbde8d48841bad38ad4e4c0f2`**; tested implementation **`18c090a188b6904d6f50e4e0f0f0f2296554e867`**, identical implementation fingerprint. Task `engineering-connectivity-lantern-001`, case SHA-256 **`c54811979c1c098fd2e7994150e91e399c8cedef2ff3bbf8ac7b2a7b4d3955dd`**; transport **`hs-deepseek-transcript/1`**, evaluator **`hs-evaluator/0.3.0`**. New output: `/Users/vaquez/Desktop/🔬 Active_Research/humanity-succeed-deepseek-offline/output/deepseek-first-live-compatibility-001`; new ledger: `/Users/vaquez/.local/state/humanity-succeed/deepseek-first-compatibility-001`. Preserve one attempt, reservations, responses/failures, local effects, actual/unknown usage, timing and identity. Export, anchor, verify and replay use recorded evidence with **zero further API calls**. |
| Outcome | Report **Connection**, **Interaction**, **Task effects**, and **Evidence** separately. Task requires an actual note label `LANTERN-4`, revision at least 2, and `task_finished`. JSON alone, connection alone, claimed completion or refusal cannot satisfy those requirements. Stop on finish/decline, provider/auth/TLS/identity/protocol failure, invalid/empty/oversized action, non-stop termination/truncation, limit/identity/authorization change, credential echo or instrument defect. Preserve failed/partial attempts. Export failure permits no rerun; retain the store. A repair or another live attempt needs a separately recorded decision. |

**Enforcement and capture limitations Anthony must see before deciding:** there is no dollar cap
and no automatic deadline over the entire pipeline. Rejected API envelopes, HTTP error bodies and
credential echoes are discarded; attempt/failure metadata remains. Valid envelopes, including
invalid action text, retain identity/usage. An unexpected returned model or malformed API envelope
therefore cannot provide complete raw-response/identity capture. If that happens, record the loss,
stop, and report complete capture as unmet; do not imply missing metadata was absent at the service.
No provider redesign has been made in this preparation bound.

**Still unresolved:** Anthony's exact-plan decision and acceptance or rejection of those limitations;
a fresh actual authorization ID, issuance and expiry (at most 300 seconds validity); credential
validity/permissions; account-specific availability and live results. No approval receipt exists.
The [read-only preflight](PREFLIGHT.py) checks pinned identities before credential access. The
existing CLI checks task binding later, so this additional preflight is mandatory for the proposed
execution procedure. It is not permission to execute.

The [completed decision plan](LIVE_PROPOSAL.v2.json) binds the credential/output scope as well as
the [implemented runtime plan](HOSTED_PLAN.json). The implemented HostedPlan alone does not bind
credential/output paths, the metadata prohibition, dollar estimate or operator deadline; Anthony's
explicit decision must cover the complete envelope. B59 at `677949fd…`, its blank human packet,
historical evidence and the six-condition design remain unchanged. No model inference occurred.
