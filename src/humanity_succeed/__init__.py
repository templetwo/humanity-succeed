"""humanity-succeed: an offline research instrument.

Instrument under construction. No behavioral result about any model is established by this
repository's test suite.

Importing this package must not import MLX, load weights, or touch the network.
"""

__version__ = "0.1.0.dev0"
COMPILER_VERSION = "hs-compiler/0.1.0"
ENGINE_VERSION = "hs-engine/0.1.0"
EVALUATOR_VERSION = "hs-evaluator/0.2.0"
# 0.2.0 (WP2 repair R1, docs/DECISIONS.md B42) only adds the notification_after_state predicate;
# every 0.1.0 predicate is unchanged, so a 0.1.0 record replays faithfully under 0.1.0 rules.
SUPPORTED_EVALUATOR_VERSIONS = ("hs-evaluator/0.1.0", "hs-evaluator/0.2.0")
