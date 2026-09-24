# Receipts

| File | What it is |
|---|---|
| `SCOPE_RECEIPT.md` | Anthony's authorization (quoted), what was not done, Stack/compass checks, host facts |
| `PACKET_VERIFICATION.json` | ZIP hash; 24/24 manifest files verified at import commit `7121557`; originals compared |
| `wp2-tests.txt` | `pytest -rA` at commit `365090d`: 154 passed, exit 0 |
| `wp2-lint.txt` | `ruff check` and generated-schema freeze check at `365090d` |
| `wp2-demo/` | `hs demo` output at `365090d`: 15 scripted bundles, 15 replays, `comparison.html/json` |
| `wp2-anchors/` | `hs evidence anchor` for each demo bundle, made at the time of the run |

Every bundle is a `scripted_instrument` run. None is a model result.

An anchor committed to the same repository is only as independent as that repository's history.
Once pushed, the remote holds a third-party copy. That is still not a trusted timestamp.

Reproduce any single row:

```sh
uv run hs evidence verify docs/receipts/wp2-demo/bundles/t-correction-claim-warm \
  --anchor docs/receipts/wp2-anchors/t-correction-claim-warm.anchor.json
uv run hs evidence replay docs/receipts/wp2-demo/bundles/t-correction-claim-warm --out /tmp/replay
```
