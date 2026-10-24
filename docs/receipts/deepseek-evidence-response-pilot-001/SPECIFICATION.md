# First evidence-response pilot — preparation contract v1

Anthony's assignment in this conversation authorizes local preparation only. It
does not authorize credentials, authenticated metadata, inference, review import,
training, publication or changes to the six-condition study. This is a small
exploratory, after-supplied-evidence observation, separate from commissioning.

Specification/plan author: root Codex agent `/root`. Case author:
`/root/pilot_case_author`, delegated specifically by the user's instruction.
Both are collaborating AI agents with shared conversation/model context; exact
model revision is unavailable. This is procedural author separation, not
independent experimental authorship, a holdout, replication or human review.
Anthony may review these AI-authored cases; no agent reviews on his behalf.

## Frozen design

- One newly authored synthetic task root, four related case documents, all in
  `pilot`, measurement mode `after_supplied_evidence`.
- Order: supported, unsupported, contradicted, not_assessable. One episode per
  variant, sequentially, fresh synthetic state and conversation each time.
- The source extract needed to respond is in the initial permitted observation.
  Reading/searching for evidence is not an experimental requirement.
- Same common workroom instructions, task structure, action interface and
  permitted response paths. Only the evidence extract varies.
- Case declarations, criteria, provenance, root/status identifiers and review
  grid remain host-only. No demonstrations or training targets.
- All four cases are hybrid. Frozen predicates test recorded procedural effects;
  a mechanical pass cannot establish factual grounding, calibration or usefulness.
  Human rubric dimensions remain pending. Preserve mechanical failures.
- The human grid has blank asserted/qualified/withheld cells for each authored
  evidence status. Every cell references exactly one frozen human criterion. No
  model/evaluator assigns a category, verdict, reviewer, rationale or adjudication.
- Guard denials and executed declines are separate, nonexclusive trace facts.
  A denied decline, prose refusal, timeout or silence is not executed abstention.
  The guard enforces permissions, not truth or the authored correct response.
- Related episodes are reported individually; no population success rate,
  statistical gate, alignment conclusion, training comparison or formal
  commissioning claim follows from four dependent observations.

## Prospective workload and ceilings

Reuse the provider and runner pinned by the completed compatibility manifest:
`9391dc41cbd71edcbde8d48841bad38ad4e4c0f2`, evaluator `hs-evaluator/0.3.0`,
transport `hs-deepseek-transcript/1`, model `deepseek-flash` only. No substitution.
Keep non-stream JSON output, thinking enabled, reasoning effort high, 4,096
generated tokens per request. No principles block, training or extra arms.

Exactly four planned episodes; at most two inference requests per episode, eight
total. Intended exchange: write report then finish; executable decline may end
earlier. Zero metadata/key-check/warmup requests, retries or repeat samples.
Per request: 65,536 request bytes, 1,000,000 response bytes, 64,000 action bytes,
45 seconds. Per provider episode: 90 seconds. Reserved output ceiling: 8,192
tokens per episode and 32,768 total, including thinking. Aggregate transmitted
request-body ceiling: 524,288 bytes, including repeated history.

The provider enforces per-plan request/size/output reservations and request and
episode deadlines. It has no exact input-token enforcement or dollar spending
cap. Input tokenizer and immutable weights are unknown. The proposed 360-second
whole-pilot ceiling and four-episode aggregate are operator supervision duties,
not newly implemented automatic guards. These limitations must be accepted in
the new approval; this packet cannot silently strengthen provider guarantees.

## Execution and stopping contract (not enacted)

First obtain a new explicit human decision naming the complete PILOT_PLAN.json
hash and these limits, outbound contents and limitations. The completed lantern
approval is inapplicable. Do not create an approval receipt during preparation.
Before any credential access, run read-only PREFLIGHT.py with the approved hash;
check all source, case, declaration, review-grid, plan and fresh-path identities.
Recheck between episodes. Each episode gets a fresh short-lived real
`hs-hosted-authorization/1` bound to its exact existing HostedPlan and unique
ledger, derived only from that new human decision. No authorizations exist now.

Use only the designated credential file after that gate. Execute each existing
`hs hosted execute` path once in order, with the exact frozen case and plan. Start
the whole-pilot operator timer before credential access. Every planned episode
has a retained status, including not_started when a stop prevents later episodes.

An ordinary permitted response, wrong factual answer, mechanical failure or
executed decline does not justify replacement or early stopping for a favorable
result. A guard denial remains visible and may consume the next already-budgeted
turn. Stop the entire pilot on identity/leak/schema/instrument defect,
authentication/provider/TLS/protocol error, empty or malformed action, non-stop
API termination/truncation, export defect, or request/size/time exhaustion.
Retain that attempt and label later episodes not_started; no retries, model
changes, prompt repair, budget increase or continuing after a defect. A repair
and further live attempt need a separately frozen decision.

Export, retain anchors, verify bound evaluations and replay from recorded
responses/effects with networking denied. Export recovery must never re-execute
an episode. Use the actual replay API and honest manifest evidence class; the
generic CLI's inherited scripted-only limitation wording is unsuitable for
hosted evidence. Record usage or missing usage, requested/returned alias,
response IDs, termination, timing, request and canonical-observation hashes.
Rejected HTTP/API/credential-echo envelopes currently retain failure metadata
but discard raw body/returned identity/usage; disclose loss and stop if encountered.
Timeouts may leave remote completion and billing unknown; never retry them.

Preparation checks may use explicitly labelled scripted/fake transport fixtures,
dummy credentials and denied networking. They are not any of the four planned
subject episodes and do not fill the human grid or constitute model evidence.
Existing compatibility evidence, B57/B58, B59 and pending reviews stay unchanged.
