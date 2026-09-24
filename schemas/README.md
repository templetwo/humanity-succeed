# Reference schema contract

These Draft 2020-12 JSON Schemas are seed contracts for the terminal implementation. They cover case sources, action outputs, event envelopes, model manifests and execution approval receipts. They are not a substitute for runtime invariants, a complete application or a human authorization system.

The case schema resolves action references by `urn:humanity-succeed:action:1.0`. Register that schema explicitly; never fetch arbitrary schema URLs at runtime. Implement the same strict types in contracts/, export them reproducibly, and compare generated schema changes in tests.

Additional runtime validation is mandatory: reject duplicate JSON/YAML keys; reject unsafe YAML tags; cap recursion, document bytes, string lengths and resource counts; reject nonfinite numbers; validate resource/actor references, revision semantics and predicate arguments; verify split ancestry, actual reviewer/rights receipts, model hashes, approval scope/time, and plan hash. Generic event payloads need event-type-specific contracts in the implementation.

Predicates use a registry, never arbitrary code. `feature_preserved` compares the named JSON pointer to the original resource revision. `notification_exists` requires a delivered simulated inbox receipt, not an action proposal or a string saying that notification occurred. `resource_revision_at_least` does not replace verification of the corresponding revision history. Events have exact registered names; `event_exists` must not accept a fabricated future event name.

`approval.schema.json` checks a receipt's structure only. Its existence is not proof that Anthony granted it. The builder must never create a receipt and attribute it to him without his actual authorization.
