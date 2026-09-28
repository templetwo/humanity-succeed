# Holdback custody: a guide for the human custodian

This is for the person who agrees to hold the 40-trajectory formal-commissioning suite -- not for
the builder, and not for whoever is running `hs` day to day. If that is you, read this whole page
before you write a single fixture.

## Why custody exists

BUILD_SPEC §5.2: held-back material must live "outside builder/trainer search paths under a named
custodian." §9: "The agent cannot author, inspect, and then call its own fixtures independently
held back." The builder wrote and tested 160 development trajectories, including 40 the partitioner
marks `holdback_designate` -- but those 40 are still builder-authored and builder-exposed. They can
demonstrate development behavior; they can never certify anything, because the same hands that
wrote them also get to grade them. Formal commissioning needs a second, independent 40: written by
someone who never saw the evaluator's internals, kept somewhere the builder cannot reach, and bound
to a hash before any run touches them.

**Honest limit:** this custody scheme verifies *bytes*, not *people*. A `CustodyRecord` is a claim
the custodian makes, attested by the record itself, never independently checked. Nothing here can
prove you are who you say you are, or that you never showed the builder your drafts before sealing
them. What it *can* prove is that the sealed bytes did not change between sealing and the formal
run, and that those bytes did not live somewhere the builder's own tools would have found them. That
is a real, useful guarantee. It is not certification, and no summary this tooling prints should be
read as one.

## Who may be custodian

Anyone except the builder. Not the seat, session, or person who wrote the commissioning suite,
`contract.py`, `execute.py`, the evaluator, or any of the class generators. In practice: a different
person, working on a machine the builder does not have access to.

## Exactly what to supply

Forty trajectories, in the exact §9 shapes, one holdback group per slot the contract already
reserves (`humanity_succeed.commissioning.contract.CLASSES`, `holdback_groups` field):

| Class | Shape | Holdback groups | Trajectories |
|---|---|---|---|
| C1 correction / claim | pair | 2 | 4 |
| C2 blocked / chosen | pair | 2 | 4 |
| C3 justified / unnecessary refusal | pair | 2 | 4 |
| C4 real error / false alarm | pair | 2 | 4 |
| C5 requested work / substitution | pair | 2 | 4 |
| C6 multiple acceptable paths | triplet | 4 | 12 |
| C7 reversed-goal feature preservation | pair | 4 | 8 |
| **Total** | | **18 groups** | **40** |

Each class's shape and pass/fail split is the same contract every development group follows --
read `docs/WP3_DESIGN.md`'s "Class contracts" section for what each member of a group must do
(C1's real-correction/claim-only pair, C3's justified/unnecessary-refusal twins, C6's
path-a/path-b/invalid triplet, and so on). Write your own scenarios to that contract: different
nouns, numbers, actor names, resource ids and wording than anything in the development suite. Write
each member's `Expectation` (`mechanical`, `conduct`, `contained`, `judgment_heavy`, `rationale`)
**before you run anything** -- that is what makes it a golden expectation and not a description of
what happened to occur.

On disk, lay it out exactly like a development suite:

```
your-holdback-root/
  SUITE.json          # a SuiteManifest: authorship "custodian_supplied", split "commissioning_holdback"
  cases/*.yaml
  trajectories/*.yaml
```

`SuiteManifest`, `Group`, `Member` and `Expectation` are defined in
`src/humanity_succeed/commissioning/contract.py`; case and trajectory files follow the same schema
every development fixture uses (`humanity_succeed.contracts.case`, `humanity_succeed.runner.scripted`).
Set `authorship: custodian_supplied` and `split: commissioning_holdback` on the manifest and on
every case inside it -- both are checked, and a mismatch blocks sealing.

## What NOT to do

- **Do not store the holdback inside this repository, or inside the `hs` state root
  (`~/.local/share/humanity-succeed` by default, or `$HS_STATE_ROOT`).** Both `seal_holdback.py`
  and `commissioning.custody.load_custody` refuse a holdback root that resolves inside either one,
  by ancestry -- a symlink, a differently-cased alias, or a directory nested three levels down all
  still count as "inside."
- **Do not copy or template your fixtures from `cases/commissioning_suite_v1/`.** Every fixture
  there is builder-authored and already exposed. The plan command's split audit
  (`humanity_succeed.corpus.splits.audit_splits`) walks derivation lineage and also flags
  cross-split near-duplicate text and world content; a holdback built by editing a development file
  shares lineage or trips the near-duplicate check, and formal commissioning is blocked on that
  suite. Write new scenarios from the class contract, not from the existing files.
- **Do not show the builder your draft fixtures, run them past the builder for a sanity check, or
  ask the builder which predicates exist beyond what `docs/WP3_DESIGN.md` already documents.**
  Any of that reintroduces exactly the "author, inspect, and call your own fixtures" problem §9
  rules out. If you are unsure whether a scenario is expressible, that uncertainty is fine to leave
  in your own notes; it is not something to resolve by asking the builder to look at your file.

## How to seal it

Once your 40 trajectories and their `SUITE.json` are complete and sitting outside this repository:

```
uv run python scripts/seal_holdback.py \
  --holdback /path/outside/this/repo/your-holdback-root \
  --custodian "your name or role" \
  --statement "how you kept it out of the builder's reach" \
  --out /path/outside/this/repo/custody-record.json
```

This checks the manifest's shape (`authorship`, `split`, and every structural rule
`contract.suite_problems` enforces), refuses a holdback path inside the repository *or* inside the
`hs` state root (`--state-root`, else `$HS_STATE_ROOT`, else `~/.local/share/humanity-succeed` --
the same precedence `hs` itself uses; pass `--state-root` explicitly if you run `hs` with a
non-default one), computes a sha256 over every referenced file, and writes a `CustodyRecord` JSON
file to `--out`. It never prints or re-displays your fixture contents -- only validation messages,
counts, and the computed hash. It refuses to overwrite an existing `--out` file, so a re-seal after
any change to the holdback (even one byte) needs a new output path, and produces a new hash: the
record and the bytes it fixes travel together.

Exit codes: `0` sealed; `2` invalid input (a bad argument, an unreadable or unparsable manifest, or
`--out` already exists); `3` the holdback is not a valid, independent custody submission (inside
the repository or the state root, wrong `authorship`/`split`, or a structural problem
`suite_problems` reports).

Keep the `custody-record.json` file and the holdback root together, off the builder's machine. If
you want to make the commitment public before a formal run without revealing the fixtures
themselves, you can publish just the `holdback_suite_sha256` field from the record -- that commits
you to the exact bytes without exposing them.

## How to run formal commissioning

Once you are ready to hand the sealed holdback and its custody record to whoever runs `hs`:

```
hs commission plan \
  --suite cases/commissioning_suite_v1 \
  --holdback /path/outside/this/repo/your-holdback-root \
  --custody /path/outside/this/repo/custody-record.json \
  --out NEW_PLAN_DIR

hs commission run --plan NEW_PLAN_DIR --provider scripted --out NEW_BUNDLE_DIR
```

`plan` validates both suites, runs the split audit across them together, partitions the development
suite, and checks your custody record against the holdback bytes on disk. `run` re-hashes every
planned file, runs every fixture (development and holdback) through the scripted provider, and
reports which fixtures met their written expectations -- development and formal results are kept
and reported separately; a formal result never borrows credit from the development run alongside
it. Without a valid, independent custody record, formal commissioning reports
`blocked_no_independent_holdback` or `blocked_custody_invalid`; that is the correct, honest state
whenever no custodian exists yet, not a bug to work around.

## What exposure means

A formal commissioning run is the one place your holdback stops being held back. `commission run`
records the run in an append-only exposure ledger under the state root, keyed by
`holdback_suite_sha256`. Once that hash has an entry, reusing the same holdback for another formal
run is refused (BUILD_SPEC A20) -- rerunning it would no longer be testing the evaluator against
material it has never seen. This holds however the run went:

- **A miss stays in the record.** A fixture that misses its expectation is not quietly retried or
  removed from the count; the report keeps it, and the claim boundary stays honest about the
  denominator.
- **A fixed evaluator needs a fresh holdback.** If a miss leads to an evaluator change, the old
  holdback is exposed and cannot be reused to check the fix. That means a new custodian round (or
  the same custodian, writing genuinely new fixtures) with a fresh `CustodyRecord` -- not a second
  run against the same 40 trajectories.

Nothing in this process, this script, or its output certifies the evaluator, the instrument, or any
model. It reports exactly which fixtures met their written expectations, under the custody
guarantees described above, and no more (BUILD_SPEC §9; `contract.CLAIM_BOUNDARY`).
