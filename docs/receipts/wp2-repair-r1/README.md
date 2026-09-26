# Receipts: WP2 outside-review repair round R1

Base `b2e08b8` → `d0a4426` (reproducers and baseline) → `85e9429` (repairs and tests) → the receipts
commit that adds this file. Scripted instrument only: no model was called or trained. Nothing here
was pushed, tagged or released. WP3 is held.

| Folder | What it holds | Commit it measures |
|---|---|---|
| `baseline/` | `uv sync --locked`, Python identity, pytest (213 passed), ruff, schema check | `b2e08b8` source, run at `d0a4426` before any `src/` change |
| `before/` | First reproducer run: all six findings reproduce | `d0a4426` (src identical to `b2e08b8`) |
| `before-final/` | The final reproducer (three added cases) run against the frozen source in a temporary detached worktree | `d0a4426` source with the `85e9429` script |
| `after/` | The same commands on the candidate: 295 passed, ruff clean, schemas unchanged, reproducer, demo | `85e9429` (`after/HEAD`) |
| `compat/` | All 30 committed pre-repair bundles re-verified against their anchors and replayed under their recorded evaluator, then hashed again | `85e9429` |
| `demo/` | Fresh demonstration bundles, replays and `comparison.html`, with 13 assertions: 10 original, 3 in the amended-contract group | `85e9429` |
| `FINDINGS_REGISTER.md` | Attribution, original labels, execution and static standing, repair status, residual limits | — |

Each command has `.cmd`, `.stdout`, `.stderr` and `.exit` files, and skips and failures are kept
as they happened. There were none: no test skipped on this macOS APFS host.

Redaction: in `baseline/00_sync.stderr` and `after/00_sync.stderr`, the local workspace path in
uv's build lines is replaced with `file://<workspace>`. In `after/06_demo.cmd`, the scratch
state-root path is replaced with `<scratch>`. The unredacted `baseline/00_sync.stderr` still exists
in commit `d0a4426`, which is local only; decide before any push whether that commit is published
as it is.

Reproduce from a checkout of this branch:

```sh
uv sync --locked --group dev
uv run pytest
uv run ruff check src tests scripts
uv run python scripts/export_schemas.py --check
uv run python scripts/reproduce_kimi_wp2.py
uv run python docs/receipts/wp2-repair-r1/compat/reverify_committed_bundles.py
uv run hs demo --out /tmp/hs-demo --state-root /tmp/hs-state
```
