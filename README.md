# ICEBURG

A deterministic IVR simulation and governance platform, reconstructed from
archives.

Iceberg models what happens to a caller inside an interactive voice response
system — where they get stuck, how friction accumulates, whether they reach
what they called for — and it does so without claiming to see anything past
the point where the IVR hands off to a human.

```
$ python3 run_worked_example.py

graph: 20 nodes, 8 journeys, 9 markers, 0 queues (Correction 1)

caller  intent      outcome       via            hops   peak_frustration
------------------------------------------------------------------------
c005    complaint   success       handoff           3             0.0000
c001    billing     success       handoff           4             0.0000
c003    tech        success       handoff           4             0.0000
c004    balance     abandonment   -                 5             0.0000
c000    balance     success       self_service      7             0.0000
c002    balance     success       self_service      7             0.5000

ticks: 6   terminated: 6
ledger: 37 events
ledger structural_hash: 733a7aa54e8f6044f381dc734e133c1800bc67c8a74f31b3b8a82639bd365cb2
```

Read that table and you can see the whole design. `balance` takes seven hops
because the default topology deliberately buries it five menus deep — that is
the "before" picture, and menu depth is the lever Iceberg exists to move.
`c004` abandoned at hop five, having never reached the point where its intent
would be addressed. `c002` reached that point *and* carries a peak frustration
of 0.5: it succeeded, and it hurt. Both facts are recorded, and neither is
allowed to overwrite the other.

## What this repository is

ICEBURG never existed on GitHub. It lived on a Chromebook behind the SSH
alias `chromebook-iceberg`, was later renamed `sentinel_os`, and no working
tree survives. This repository was rebuilt on 2026-09-11 from 75,449
references across 551 files of AI conversation history spanning 2026-06-23 to
2026-08-16.

About 72% of the 2,031 lines of engine source is **verbatim recovered
code** — extracted from archived transcripts, parsed to verify it is real,
and left unmodified. The rest was rebuilt from archived contracts. Every file
says which it is in its own header, and [PROVENANCE.md](PROVENANCE.md) is the
complete ledger, including the four places where the recovered code did not
run as written and what was changed.

**This is a faithful reconstruction, not a running production system.** Large
parts of the original — the replay subsystem, the API and SDK, the CLI,
governance specs, deployment manifests — left no recoverable source and are
listed as absent rather than stubbed out.

## Quick start

```bash
pip install -r requirements.txt
python3 -m pytest Iceburg/Tests -q     # 119 passed
python3 run_worked_example.py
```

Requires Python 3.10+ and numpy.

## Layout

```
Iceburg/
  Latent/       LatentPayload.py            the friction engine
  Domain/       CallerState.py              caller + dynamic state
                Intent.py  Emotion.py       fixed vocabularies
                IngestAdapter.py            raw logs -> friction stimuli
                TwilioSyntheticLogGenerator.py   specification stub, as written
  Model/        Build_Graph.py              routing topology + journeys
  Aggregation/  PathCongestion.py           Tier 3 co-navigation aggregation
                QueueStress.py              superseded; kept for lineage
  Engines/      rl_ppo.py  rl_marl.py       triage signal, aggregate only
  Sim/          Simulator.py                per-caller traversal, no ML
                cluster_runner.py           deterministic sharding
  Loop/         IntegrationLoop.py          the tick; where the tiers meet
  SDK/          Telemetry.py                append-only deterministic ledger
  Training/     Modules/calibrate_expected_wait.py
  Tests/                                    119 tests
```

## The idea, in one paragraph

An IVR has no queues — only directionality. It never accumulates callers at a
place; it takes what someone wants and moves them. So Iceberg does not model
occupancy, it models *co-navigation*: how many callers are moving through the
same menu at the same instant, and how much distress they are each carrying.
The IVR's job ends the moment the door to a human opens, so everything past
that door — wait times, handle times, staffing — is not merely out of scope
but unobservable, and Iceberg refuses to report on it. A call either reached
the point where its caller's stated intent would be addressed, or it did not.
That is the whole classification: binary, structural, no threshold, nothing
for a client to tune. How badly the caller suffered on the way is recorded
separately, as severity, and is never allowed to decide the verdict.

The full reasoning, including the four locked corrections that produced this
design and the failure modes each one closed, is in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Status

| | |
|---|---|
| Tests | 119 passing |
| Determinism | verified — identical inputs produce identical ledger hashes |
| Real call data | none, ever. Every tunable constant is an uncalibrated placeholder |
| Production readiness | no. See [SCORECARD.md](SCORECARD.md) |

The original project's own discipline is worth preserving here: it spent most
of its life hunting down plausible-looking code that had never actually been
executed, and stale documentation that outlived the decision it described. In
that spirit, the reconstruction records that **the archived v2 design raised
an exception on its own default topology** — it had been written, reviewed and
adopted as a locked decision, and never run. See PROVENANCE.md.

## Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — the boundary, the four corrections, the tiers, the tick
- [PROVENANCE.md](PROVENANCE.md) — recovery method and per-file ledger
- [SCORECARD.md](SCORECARD.md) — module-by-module status and what is absent
