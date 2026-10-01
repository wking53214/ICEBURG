# Provenance

ICEBURG was never a GitHub repository. It lived on a Chromebook, reachable
only through the SSH alias `chromebook-iceberg`, and was later renamed and
continued in a separate private repository. No copy of the working
tree survives here. What survives is the conversation around it.

This repository was reconstructed on 2026-09-11 by mining five archives of
AI conversation history for every trace of the system:

| Archive | Files mentioning Iceberg/Iceburg | Occurrences |
|---|---:|---:|
| Archive A | 425 | 65,676 |
| Archive B | 82 | 5,260 |
| Archive C | 5 | 3,632 |
| Archive D | 39 | 881 |
| Archive E | 0 | 0 |
| **Total** | **551** | **75,449** |

The five archives are private repositories, labelled A to E in this document.

Active development runs 2026-06-23 to 2026-08-16.

## Why this state is "peak capacity"

There are two candidate peaks, and they are not the same repository.

**The structured build (early July 2026)** — 113 files under `full3`, a
parallel 43-file `flat3`, 108 tests passing and 1 skipped, organised into
`Domain/ Latent/ Model/ Aggregation/ Engines/ Sim/ Loop/ SDK/ Replay/
Registry/ Telemetry/ API/ CLI/ Admin/ Training/ Validation/ Governance/
Deploy/`. This is the architecture at its most complete.

**The renamed successor (August 2026)** - the same system renamed and pushed
toward production, in a separate private repository. But a cleanup commit
deleted around 30 files and seven directories on the way, including
`Admin/`, `API/`, `CLI/`, `SDK/`, `Replay/`, `Registry/` and `Main.py`. Test
count fell to 78/79. The archive's own audits of that repository are
unsparing: stale `structure.txt`, phantom references, a truncated test file,
~90 files flat at root, committed `__pycache__`.

This reconstruction targets the **first** peak — the structured architecture
immediately after the four locked domain corrections of 2026-07-02 were
applied. That is the system at maximum coherence rather than maximum
surface area, and it is the state the recovered source actually belongs to.

## Recovery method

1. Full-text sweep of all five archives for `iceburg|iceberg`.
2. Extraction of verbatim source from three formats found in the transcripts:
   file dumps delimited `----- Path/File.py -----` followed by `# Row Count: N`,
   fenced `python` design blocks, and inline attachment bodies.
3. Every extracted region parsed with `ast` before being accepted. Regions
   that would not parse were discarded rather than patched into looking right.
4. Where multiple versions of a file existed, the latest one consistent with
   the 2026-07-02 corrections was taken.
5. Modules with no recoverable source were rebuilt from their archived
   contracts, and are marked as such in the file header and below.

## Per-file provenance

`RECOVERED` — extracted verbatim from an archived transcript, unmodified
except where a specific fix is noted.
`RECONSTRUCTED` — no source survived; rebuilt from the archived contract.
`NEW` — written for this reconstruction; no original counterpart.

| File | Status | Source |
|---|---|---|
| `Latent/LatentPayload.py` | RECOVERED + 1 addition | Archive A `6ac96fa8` (2026-07-01) |
| `Domain/CallerState.py` | RECOVERED | Archive A `07c432bf` (2026-07-03) |
| `Domain/IngestAdapter.py` | RECOVERED | Archive A `f1a41769` (2026-07-03) |
| `Domain/TwilioSyntheticLogGenerator.py` | RECOVERED (stub, as written) | Archive A `f1a41769` |
| `Domain/Intent.py` | RECONSTRUCTED | member set from archive refs + `Build_Graph` |
| `Domain/Emotion.py` | RECONSTRUCTED | `CallerState.new()` default pins `NEUTRAL` |
| `Model/Build_Graph.py` | RECOVERED v2 + 1 fix | Archive A `07c432bf`, "Blue Design v1" |
| `Aggregation/PathCongestion.py` | RECOVERED | Archive A `07c432bf` |
| `Aggregation/QueueStress.py` | RECOVERED (superseded) | Archive A `3f1cb83f` |
| `Engines/rl_ppo.py` | RECOVERED + 1 fix | Archive A `a24f3eca` (2026-07-02) |
| `Engines/rl_marl.py` | RECONSTRUCTED | archived contract only |
| `Sim/Simulator.py` | RECOVERED v1 + v2 patches merged | Archive A `07c432bf` |
| `Sim/cluster_runner.py` | RECONSTRUCTED | archived contract only |
| `Loop/IntegrationLoop.py` | RECOVERED v1 + v2 patches merged | Archive A `6ac96fa8`, `07c432bf` |
| `SDK/Telemetry.py` | RECONSTRUCTED | archived contract (append-only, `{type, payload}`, two hashes, deep-copy) |
| `Training/Modules/calibrate_expected_wait.py` | RECOVERED | Archive A `f1a41769` |
| `Tests/*` | NEW | see below |
| `run_worked_example.py` | NEW | — |

## Changes made during reconstruction

Four. Each one is marked in the source with `RECONSTRUCTION FIX 2026-09-11`
and each exists because the recovered code did not run as written.

**1. `Build_Graph.validate()` — escape counting.**
The v2 design raised `Integrity Error: intent_menu has 2 handoff escapes` on
its own default topology. `complaint` and `general` are declared with no
steps, so their handoff markers are direct children of `intent_menu`, and the
max-one-escape rule counted them as diverts. The fix excludes handoffs that
are a declared journey successor from that node; the rule's stated purpose,
"max 1 for deterministic divert", is preserved exactly.

**2. `LatentPayload.peak_frustration` — added.**
`Simulator.record_termination` reads it and the recovered `LatentPayload`
did not define it: it was added to the class after the version that survives
in the archive. Rebuilt from its documented semantics — a never-decaying
high-water mark, reset at a call boundary, recorded at termination as
severity and never as the classifier.

**3. `PPOEngine.compute_action` — empty input.**
Raised `ValueError: zero-size array to reduction operation maximum` on the
final tick. Unreachable before Correction 1, because a queue-occupancy
aggregator always emitted one key per queue; node-kind filtering in
`IntegrationLoop` Phase B made "no step-kind node is occupied" a real state.
Empty in, empty out.

**4. `Domain/QueueState.py` — not shipped.**
The only recoverable version carried `staffed_agents`, `abandonment_rate` and
a `StaffingAdjustment` class. That is post-ACD data Iceberg cannot observe —
the exact lineage Correction 2 and the StaffingRLEngine deletion retired.
Shipping it would have reintroduced the deleted model. `Simulator.update_queue`,
its only consumer, is deleted for the same reason.

Findings 1 and 3 are worth stating plainly: **the v2 design, as archived, was
never executed.** It was written, reviewed, and adopted as a locked decision,
and it raises on its own default topology. That is precisely the failure mode
the transcripts themselves return to over and over — plausible-looking code
that was never run.

## Tests

The original suite (108 passed, 1 skipped) is **not recoverable**. Test
bodies never appear in the archives; only filenames and the contracts they
asserted. The 119 tests here are new, written against the invariants the
archive documents explicitly: the four corrections, replay equivalence,
determinism under sharding, the friction engine's anti-gaming properties, and
the append-only ledger.

They are not the original tests and do not claim to be. Where the archive
records a contract fork that was never resolved — `test_cluster_runner.py`
expected a no-arg `ClusterRunner()` with `.select_worker()` while the real
class required `(simulator, telemetry, workers)` — the reconstruction follows
the real class and provides `select_worker()` so both expectations hold.

## Not recovered

No source survives for: `Replay/` (recorder, ledger, snapshot, verifier,
replay_runner), `Registry/module_registry.py`, `API/` (server, schemas),
`SDK/` (client, models, replay), `CLI/cli.py`, `Admin/dashboard.py`,
`Telemetry/aggregator.py`, `Engines/bayes_gpu.py`, `Validation/`,
`Governance/` (lever and target manifest specs), `Deploy/`, `main.py`.

These are listed rather than stubbed. An empty module that looks like a
module is worse than an absent one, and the archive is explicit that empty
scaffolding — `Training/Modules/`, `Website/Assets/`, `Marketing/Assets/`,
`certification/` — was one of the original repo's real problems.
