# Threat model and validity boundaries

## Protected assets

Private records and credentials; source/evaluator separation; unexposed test roots; frozen weights; correct trial counts; durable effect records; reviewer blinding; approved execution scope; legitimate human choices in the task; honest reporting of unknowns.

## In scope

Accidental answer-key exposure through serialization/logs/errors; model-generated tool injection; malformed or duplicate-key JSON; action arguments that resemble host paths; arbitrary predicate execution; silently changed model/template/quantization; training-label contamination; hidden context truncation; condition-aware scoring; phantom tool success; interrupted transactions; correlated observations counted as independent; inappropriate retries; misleading zero/no-effect labels; unreviewed or mislicensed training content; style-only victories; public upload by an over-enthusiastic builder.

## Controls

Typed allowlist views; process-separated local provider; resource handles and fixed tools; no raw host capability; safe YAML loader with duplicate-key rejection; bounded JSON parser; predicate registry; atomic SQLite event/effect transactions; manifest/artifact hashes and external-anchor distinction; split derivation registry; independent test custody; paired-condition manifest; explicit model files; network-free core and disabled training telemetry; truthful exit states; real human approvals and reviews; static no-network report exports.

No arbitrary Python, SQL, shell, HTTP, plugins or file paths may be evaluated from case sources or subject output. Treat natural language in every resource and simulated inbox as data, not instructions to the runner.

## Limits

This application is not an OS sandbox against a hostile local administrator, malicious Python dependency, malicious remote-code model loader, or a compromised operating system. An operator-readable file is not cryptographically secret from the operator. A hash does not prove a file was created before an event without a trustworthy timestamp/anchor. No protocol can infer universal moral agreement or experienced desire from the logged behaviors.

Absence of observed misconduct in these cases is not proof of absence elsewhere. Equivalence on a task panel is not deployment approval. A containment layer preventing an effect is not evidence that the model chose the right action.

## Required fail-closed cases

Unknown tools/fields; missing expected revision; corrupt manifest; absent approved rights for execution; absent/mismatched run approval; unqualified predicate; hidden-state leak; unavailable model/adapter/runtime; implicit fallback; context overflow; plan exceeding cap; missing required evidence. Preserve the record and name the limitation without fabricating a successful outcome.
