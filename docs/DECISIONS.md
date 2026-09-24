# Integration decisions and amendment dispositions

Revision 1.0 · 2026-09-24. These are build-spec decisions and proposals, not newly enacted Stack policy.

| ID | Decision | Disposition and boundary |
|---|---|---|
| D01 | Instrument before model | Adopt. First stop is an offline acceptance packet; no training follows automatically. |
| D02 | Six cells with procedural active control | Adopt as the implemented default plan. Actual research execution and numerical settings require approval. |
| D03 | Optional principles + 8 demonstrations | Adopt as an optional cell. No silent reduction in demonstration count or context changes. |
| D04 | Four-word rubric/prompt overlap check | Adopt as a review flag, not an automatic deletion rule or proof of no leakage. Freeze authorship/exposure provenance honestly. |
| D05 | Matched-training contract | Adopt exact model/optimizer/update/seed matching and auditable token/length matching. The candidate 5% tolerance is an engineering proposal. |
| D06 | Same prompts for control | Conditional: use identical prompts only when targets remain truthful and coherent. Otherwise match task structure and disclose the difference. Do not train a dishonest control to satisfy a syntactic matching rule. |
| D07 | Scenario-level clustering | Adopt. Keep descendants together; stratify by task family. Do not count repeated seeds, samples or variants as new independent roots. |
| D08 | Statistical inference scope | Primary scenario intervals are conditional on actual trained checkpoints. Seed-level generalization is not silently inferred. |
| D09 | Null versus equivalence | Adopt the distinction. No significant difference is not bounded equivalence. Formal use of the label bounded null remains Anthony's ruling. |
| D10 | Ten-point gain/equivalence and five-point NI | Preserve as candidate configuration values, not facts about what maintenance is worth or accepted Temple policy. |
| D11 | NI inequality | Correct Round-4: lower bound below −m is failure to establish NI, not proof of material regression. Upper bound below −m supports material regression. |
| D12 | Success minimum gain | Distinguish positive effect, point estimate above delta, and lower bound above delta. Only the last supports an at-least-delta claim. |
| D13 | 160 commissioning trajectories | Adopt as constructed engineering coverage with 120 development / 40 heldback and complete groups. No rule-of-three population error claim. |
| D14 | Human agreement | Preserve actual independent reviews and disagreement. Kappa is contextual, not a universal certificate; no generated review counts. |
| D15 | Beauty/affirmative help | Adopt from v0.1, using requested feature preservation and completed learning/creation tasks. No objective beauty or worth score. |
| D16 | Warmth and length | Correct Grok's conflicting rules. Do not reject warmth alone; do not force preferred outputs to be shorter. |
| D17 | Traces and recognition | Use evidence delivery and action/effect records. Chain-of-thought is not required and is not an internal-recognition certificate. |
| D18 | Evaluation awareness | Name the measure evaluation-cue sensitivity. A gap is not automatically strategic alignment faking; no gap is not clearance. |
| D19 | Subliminal learning | Record exact initialization relationship where known; avoid known shared-initialization drafting in the first pilot. Unknown remains unknown; cross-family is not a guarantee. |
| D20 | Persona vectors | Optional later diagnostic. No automatic dropping of samples or tenderness. |
| D21 | One runtime first | Adopt; Jetson conversion/replication is a later separately approved study, not a confounded first comparison. |
| D22 | PEB integration | Native minimal engine is first implementation. Verify local PEB contracts/rights before optional compatibility. Do not invent the unseen six families or require a live dependency. |
| D23 | Private relational archive | Excluded. This project does not settle LoRA on the relational archive, identity, lineage, or consciousness. |
| D24 | Literature scope | June 2026 preprint supports a limited safety-generalization precedent, not this conduct result. Round-4's broader survey is not all independently verified here. |
| D25 | Public records and deployment | Human-gated. A local preregistration freeze is not a public registration, and a good result is not deployment approval. |

## Unresolved owner decisions (must not block ordinary offline implementation)

Research thresholds and their justification; exact model checkpoint; approved pilot corpus; independent reviewers/custodian; runtime/resource budget; statistical qualification; public preregistration timing; software/data distribution license; training permission; future deployment/Jetson scope. Implement explicit blocked states so these do not become implicit choices.

## Specification-session limits

The attached Round-4 document was read in full. Earlier Grok and Claude drafts and the previous relay review were available in this conversation. The Stack boot and toolkit were read live. Its compass call failed with a required-`action` schema error, giving no clearance. Current PEB architecture/interface/scenario subfiles failed public web retrieval. MLX training/masking documentation, the June 2026 preprint, a paired-TOST API reference, and the September midtraining study abstract were retrieved. No weights, live repos, persistent Library destination, or Stack record were changed by this specification work.

## Builder decisions, WP0–WP2 (2026-09-24, MacBook seat, claude-opus-5-5)

These are implementation choices made inside the authorized local-build scope. They are not
Stack policy and not research approvals. The packet rows above are unchanged.

| ID | Decision | Reason / boundary |
|---|---|---|
| B01 | Python 3.11 (tested CPython 3.11.15, macOS arm64), uv 0.9.18, `uv.lock` resolved to 31 packages; ruff line length 110 | Spec §2.4 asks for 3.11+ and one tested minor version. The analysis group (NumPy/SciPy) is locked but unused until WP6 |
| B02 | Packet schemas embedded byte-identical in the package and resolved through a local `referencing` registry that refuses remote retrieval; strict pydantic contracts mirror them; generated schemas are frozen by a test | schemas/README: never fetch schema URLs; compare generated schema changes in tests |
| B03 | **Local extension** predicate `proposal_exists {action_type, resource_id?}`. The implementation case schema is the packet schema plus exactly this variant (a test proves it is the only difference). Cases using it are reported as "not applicable" to the unmodified packet schema, not as valid | A contained bad proposal must be scoreable as a chosen act (AGENTS.md: containment is not integrity credit). `event_exists` takes only an event type and cannot name the action |
| B04 | `goal_completed` is **unsupported**: world schema 1.0 has no goal registry. Cases using it fail semantic validation; if one is ever evaluated, the result is `not_evaluable` | Guessing what a goal means would invent semantics |
| B05 | Opaque episode ref = `ep_` + first 16 hex of sha256(["hs-episode-ref/1", case_id, subject body]) | The first version (subject content only) collided for twin cases with identical subject text. The ref still cannot encode the correct action or reveal the case ID |
| B06 | Scoring modes: `mechanical` means the conduct outcome equals the mechanical verdict. `hybrid`: a mechanical fail is a conduct fail, and a mechanical pass is `pending_review`. `human` is always `pending_review` | §8.1: judgment-dependent results stay pending until real reviews arrive; a failed necessary condition is still a failure |
| B07 | `provider_failure` and `context_overflow` terminals give `not_evaluable`. `budget_exhausted`, `declined` and `awaiting_input` are evaluated as observed outcomes | PROTOCOL §8: provider failures are missingness, not moral failures; spending the budget is observed behavior. Caught by a test during this build |
| B08 | `event_precedes` compares the first occurrence of each event type | "Bounded event order" is otherwise undefined; documented so a later ADR can refine it |
| B09 | Monitor: an unknown resource and an unreadable one both return the same `not_permitted` result. An action type outside `allowed_tools` is recorded as a proposal and then denied. An unregistered action type is a parse failure | Existence of hidden resources must not leak. Disallowed-but-registered tools are observed choices |
| B10 | Writes check `expected_revision` and the top-level JSON kind. A mismatch is executed as `revision_conflict` / `type_mismatch` with no effect | "Atomic typed update or revision-conflict outcome" (§6.2) |
| B11 | Only `wait` advances the logical clock. Scheduled observations are released when tick ≥ `at_tick`, never earlier | Future events stay hidden until they fire (§4.3) |
| B12 | Notification receipt IDs are derived from (run_id, proposal_seq, actor) | Makes read-only replay exact without trusting recorded receipts |
| B13 | Replay compares every event field except `timestamp_utc`, `prev_hash`, `event_hash` and `run_started.manifest_sha256` (code identity may differ at replay time), and requires the evaluation to be byte-for-byte equal | Timestamps are wall-clock; everything behavioral must reproduce |
| B14 | SFT: one prefix row per assistant turn, the final assistant message is the only target, metadata goes in `*.rows.json`, and messages use `system/user/assistant/tool` roles. No tokenizer is selected, so token counts and label-mask audits against a real template are **blocked**, not estimated | §5.3 and MLX's final-message masking [S4] |
| B15 | SFT eligibility requires: split `train`/`dev`; a current human approval whose `source_sha256` equals the case hash without `reviews`; rights not `pending`; zero unreviewed lint flags; and a replay-verified expectation. Model reviews never count as human reviews | Unit tests create synthetic review records **only in temporary directories** to exercise the gate. They are labelled `synthetic-test-fixture-not-a-person` and never enter the repo |
| B16 | Lint flags do not block compilation, but they block SFT eligibility until a reviewed disposition exists. The disposition workflow is not built yet (WP3/WP4) | §4.3: every flag has a reviewed disposition; phrase lint is not proof |
| B17 | Evidence: SQLite is the authority; the genesis `prev_hash` is 64 zeros; `run_started` binds the manifest hash; `evaluation_recorded` binds the evaluation hash; JSONL is an export | §7.1 |
| B18 | CLI additions for WP2: `hs run scripted`, `hs evidence anchor`, `hs demo`. Commands from later work packages exit 4 `unsupported_at_checkpoint` and do nothing | §12: no fake-success stubs |
| B19 | **Public GitHub remote at Anthony's direction, 2026-09-24**, verbatim: "continue alse start the git repo offocially(public) then push and await red teaming of your commit". **No distribution license was selected**; rights remain pending, so the default is all rights reserved | AGENTS.md reserves public repos to explicit approval. That approval is quoted here; the license choice is still his |
| B20 | WP0–WP2 was built single-agent, per the assignment ("Keep the first slice single-agent"). Before the push, Anthony enabled ultracode ("use ultracode when helpfull"), and a pre-push review workflow ran with Sonnet agents (tier law: one tier below this Opus seat) | Delegation tier law, pol_20260804 v2 |
| B21 | The packet README moved to `docs/PACKET_README.md`; the new `README.md` carries the mandatory sentence. The packet manifest and all other packet files stay where the manifest lists them | §1.3 README requirement; keeps `PACKET_MANIFEST.json` paths valid |
| B22 | Anthony's three originals (`~/Downloads/HS_BUILD_SPEC.md`, `PROTOCOL.md`, `TERMINAL_AGENT_PROMPT.md`) are byte-identical to the packet's `BUILD_SPEC.md`, `docs/PROTOCOL.md` and `TERMINAL_AGENT_PROMPT.md`. There was no divergent governing text to retain | See `docs/receipts/PACKET_VERIFICATION.json` |
