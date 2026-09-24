# Example fixture status

These three YAML files are invented AI-authored **commissioning-development** fixtures. They are schema examples, not human-reviewed corpus records, unexposed tests or completed model observations. Their `reviews` arrays are empty and their rights/approval status is pending. Neither a human review nor a distribution license is fabricated.

- `correction.yaml` contains a preferred action sequence and a counterexample that claims correction without effects. Both start from a fresh copy of the same world. Expected results refer to **mechanical predicates**. The full hybrid outcome remains pending until the required semantic notification review exists.
- `feature-preserve.yaml` and `feature-standardize.yaml` reverse an explicit user request. They share one root and must remain in one split. They test a structured-layout surrogate; they do not test image understanding or objective beauty.

The builder must replay each demonstrated action through the actual synthetic engine to derive tool observations. It must not hand-invent success receipts. A training compiler may use only approved preferred trajectories in the train/dev splits; these files are not training eligible as supplied.

The schema validation performed while packaging checks structure and reference consistency. It does not execute the proposed environment or prove the expected outcomes; the terminal agent must implement and test that vertical slice.
