# Publication and separate key-connectivity scope

Anthony explicitly requested: “first push the pre reg on git. then i would like you to test call
deepseek just to test the api key.” This authorizes publication and a narrowly scoped key check;
it does not authorize the pending multi-turn subject-model checkpoint.

The preparation packet is published byte-for-byte on branch
`provider/deepseek-first-compatibility-prereg`, including its original inventory. The registration
records prospective connectivity planning before authenticated access. It does not claim that
already-executed B59 work is being preregistered now, or establish a formal study registration.
B59, blank human review, original decisions and the six-condition local design remain unchanged.

Completed compatibility decision-plan hash:
`411bbeea00a61aba55b671b476b21f2bc0bbb625c23c4c591e805433aac0be3d`.
Its runtime source remains `9391dc41cbd71edcbde8d48841bad38ad4e4c0f2` at the original execution
worktree, with tested implementation `18c090a188b6904d6f50e4e0f0f0f2296554e867`.
The separate publication worktree adds documents, without moving that execution branch.
The preparation README's uncommitted state is a retained snapshot of its preparation date;
the separate publication commit now records those documents. It is not a new runtime identity.

## Key check (separate from inference)

[KEY_CHECK_PLAN.json](KEY_CHECK_PLAN.json) SHA-256:
`40d9e91f1ddcfe89c00da0a4ef3586e20596680a6e427d61e1dde0079a28ec89`.

One authenticated **GET https://api.deepseek.com/models**, at most 30 seconds, at most 65,536
response bytes; **zero inference requests**, no retries, redirects, proxy inheritance or model
substitution. This uses the [official metadata endpoint](https://api-docs.deepseek.com/api/list-models/).
No prompt or synthetic task leaves the machine. The designated file remains
`/Users/vaquez/.config/humanity-succeed/deepseek-compatibility.env`.
The probe reads it only after the successful push, using the existing strict explicit-file reader.
It never prints or retains the key, response body or remote exception text.

Result stays local at
`/Users/vaquez/.local/state/humanity-succeed/deepseek-key-check-001/result.json`.
This new scope changes the earlier preparation-only boundary only for this one metadata probe;
it does not fill the pending compatibility authorization, approve a model, or allow inference.
A missing/invalid credential is a local refusal with no request; a failure is retained and stopped.
No key check has happened at this pre-request publication commit. A Git commit records this
plan before the check, not a fabricated successful result or human hash approval for inference.

The code is a disposable metadata diagnostic, not an extension of the subject provider.
The existing engine/action transport/evaluation/replay interfaces are unchanged. Tests and results
in the inherited offline receipts remain their historical evidence, not freshly repeated runs.
