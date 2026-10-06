# Live compatibility preparation — local, unexecuted

The approval card and completed decision plan are prepared for Anthony's explicit decision.
Decision-plan SHA-256: `411bbeea00a61aba55b671b476b21f2bc0bbb625c23c4c591e805433aac0be3d`. Runtime-plan SHA-256: `8c2078606ccc2da2f1fe38f4c97731fe05a09a751735540555a7efd713b28b4e`.
These are different objects: the versioned proposal is a decision envelope, not a new provider
schema. Only its nested strict `hs-hosted-plan/1` enters the existing runtime contract.

The original provider `LIVE_PROPOSAL.json` and all 303 receipt entries are unchanged. The new
revision records its reason and the original hash. `DRAFT.initial.json` preserves the first local
preparation draft; final inspection added the rejected-envelope capture limitation. Neither is an
execution/approval receipt. The original draft hash was
`ab085df1fefa2047c89601a42fd42c4348c2975270add26f53774c67ffe6f867`.

Preparation remains local and uncommitted so the exact source HEAD and imported path stay bound
to the existing receipt dependency. No source file, provider semantics, B59 artifact, human-review
packet or existing project record was edited. A later HEAD or implementation change invalidates
this plan and needs a newly bound plan/decision. This bound does not implement a redesign.

## Checks actually performed

- Resolve clean dependency HEAD 9391dc41… and tested code 18c090a…; ancestry verified. Their
  diff contains only the provider receipt and appended DECISIONS facts, no implementation change.
- Verify **303 provider + 41 B57/B58 + 1,515 B59 inventory entries**. All match. Read B59's
  first-run report, discrepancy and report-only correction; original executions remain retained,
  and corrected presentation refers to those executions with no new execution/reevaluation.
- Import actual implementation from the assigned worktree; unchanged fingerprint
  `5aa4ddcb87924f38df1098fe0df511ee85d5cb48566129b786cc7454d9d8e0b2`.
- Use actual `hs hosted plan` interface, strict HostedPlan validation, reversible encode/decode,
  frozen task/subject/initial-observation/instruction hash checks and explicit evaluator compatibility.
  No evaluator invocation or fixture execution was needed or performed.
- Read public official model/settings/JSON/pricing documentation. Direct fetches failed; official
  indexed documentation and the JSON page were available. A public curl fetch returned a 302,
  not pricing. No authenticated request or account availability check was made.
- Offline preflight forbids socket connections, provider dispatch and credential reads. Check
  the final decision hash and rejection of a deliberately incorrect hash. Lint the new preflight.
- Existing full-suite/type/schema evidence is reused from the sealed offline receipt, not reported
  as freshly rerun. No source or grading path changed and no commissioning was repeated.

The read-only `.venv/bin/python -m humanity_succeed --help` probe failed because this package
has no `__main__`; the installed `.venv/bin/hs` entry point was then used successfully.
This was an interface probe, not a provider attempt. No credential was inspected.

## Subsequent boundary (not run here)

After a separate exact-hash decision and fresh authorization, run:

```sh
.venv/bin/python docs/receipts/deepseek-live-compatibility-preparation/PREFLIGHT.py \
  --decision-sha256 411bbeea00a61aba55b671b476b21f2bc0bbb625c23c4c591e805433aac0be3d \
  --authorization /Users/vaquez/.local/state/humanity-succeed/deepseek-first-compatibility-001.authorization.json
```

Inspect the explicit human decision and preflight result before accessing the credential.
Only then may the separately approved existing `hs hosted execute` command be constructed
with the exact paths in the plan. This preparation intentionally does not issue that command
or create an authorization. Run operator timing from credential access; disclose lack of an
end-to-end watchdog. Export/verify/replay are offline. Protocol-rejected response capture is
limited as disclosed on the card; missing response data is an evidence limitation, not success.

No real key access, authenticated metadata request, inference, training, human-rating import,
private holdback access, Stack write, push, merge or publication occurred. Future live results
remain unknown. Path confirmation alone did not grant cloud access.
