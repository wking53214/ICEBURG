# Architecture

Iceberg is a deterministic IVR simulation and governance platform. It models
what happens to a caller inside an interactive voice response system, finds
where that system generates friction, and recommends fixes — without ever
claiming to see anything it cannot actually observe.

Everything below follows from one boundary and four corrections.

## The boundary

Iceberg's world ends at the ACD door.

An IVR hands a caller off to an automatic call distributor, and from that
instant onward — real wait for an agent, average handle time, staffing,
shrinkage, whether the balance read back was correct, whether the transaction
posted — none of it is observable from where Iceberg sits. Not inconvenient
to obtain. Not out of scope by preference. Epistemically unavailable.

This boundary is why `StaffingRLEngine` was deleted rather than demoted, and
why `Simulator.record_termination` refuses to judge execution quality. A
system that reports on data it cannot see is worse than one that reports
less.

## The four corrections

Locked 2026-07-02. Not to be re-derived or re-litigated.

### Correction 1 — no queue nodes exist in the IVR

> "A queue doesn't exist in an IVR, only directionality."

An IVR has no hold music, no waiting state, no accumulation of callers at a
place. It does exactly one thing: given what a caller wants, determine a
direction and move them. There is no such thing as "3 people waiting in the
billing queue" inside an IVR.

The earlier graph had `{intent}_queue` nodes callers could dwell at across
ticks, and `QueueStress` aggregated their "current occupants". That modeling
was wrong, not imprecise — it invented a place that cannot exist.

*Consequences:* queue nodes deleted from the topology; `QueueStress`
superseded by `PathCongestion`, which measures **co-navigation** (an
instantaneous coincidence of moving callers at the same menu) rather than
occupancy; `Simulator.update_queue` deleted.

### Correction 2 — the IVR's job ends at handoff, not at agent connection

> "The end point is when the call leaves the IVR, when the door opens, not
> when it closes behind them."

Handoff is an instant, a transition — not a node anyone dwells at.

*Consequences:* handoff nodes are terminal markers; `Simulator.step` raises
if asked to step a caller standing on one; `IntegrationLoop` Phase B excludes
markers from aggregation entirely, because no data exists past the door.

### Correction 3 — self-service needs real depth, and is a first-class success path

> "If the IVR has the balance 5 menus deep, THAT is why Iceberg exists — put
> it at position 1 and you've optimized the IVR to full efficiency."

The earlier graph gave self-service intents a single pass-through node, so
there was no path where a caller got their answer and hung up satisfied
without needing a human — even though that is the IVR's original purpose.
Real self-service has real steps, and real friction can occur at every one.

*Consequences:* journeys are declared per intent as data, because **depth is
configuration, and depth is the lever Iceberg optimizes**. The default
topology deliberately buries `balance` five steps deep: that is the "before"
picture.

### Correction 4 — outcome classification is binary and structural

> "Anyone who hangs up before being given information is an abandon and
> received too much friction. It's intent, not execution."

Two outcomes, not three:

- **SUCCESS** — the call ended *after* reaching the point where the caller's
  declared intent would be addressed: either a self-service resolution or a
  handoff. Both are first-class.
- **ABANDONMENT** — the call ended *before* that point, anywhere in the
  journey.

"Intent, not execution" is load-bearing. Iceberg classifies whether the
caller *reached* the point where their intent would be addressed. It does not
verify whether the spoken-back balance was numerically correct — that is
post-IVR execution data, the same boundary as AHT.

*Consequences:* no threshold participates in classification. There is nothing
here for a client to declare. `peak_frustration` is demoted from abandonment
classifier to **severity signal** — how bad, never whether.

## Tiers

```
                    raw call logs
                          |
   Tier "on-ramp"   Domain/IngestAdapter.py
                    mechanical translation to friction stimuli
                    (no modeling judgment lives here)
                          |
   Tier 1           Latent/LatentPayload.py   <- the friction engine
                    Domain/CallerState.py         node-agnostic, deterministic
                          |
   Tier 2           Sim/Simulator.py          <- per-caller traversal
                    Model/Build_Graph.py          NO ML in this path
                          |
   Tier 3           Aggregation/PathCongestion.py <- co-navigation, per node
                          |
   Tier 3.5         Loop/IntegrationLoop.py   <- the only place tiers meet
                          |
   Tier 4           Engines/rl_ppo.py         <- triage signal only
                    Engines/rl_marl.py            never sees a caller
                          |
   throughout       SDK/Telemetry.py          <- append-only ledger
```

The split between Tier 2 and Tier 4 is the "transmission / differential"
separation. `Simulator` walks one caller and makes no policy inference.
`PPOEngine` and `MARLEngine` see only aggregate congestion and never an
individual caller. They are not injected into traversal; the loop calls them.

## The tick

`IntegrationLoop.run()` owns the tick. Four ordered phases:

- **A — advance.** Step, divert, or hang up every active caller. A hangup
  takes precedence over a diversion: the caller's act preempts the system's.
- **B — group.** Bucket survivors by their current node, **step-kind nodes
  only**. Callers at markers have crossed the boundary and never aggregate.
- **C — aggregate and triage.** `compute_path_congestion` rolls each bucket
  into `{load, peak, breadth, n}`; the engine turns that into a triage
  distribution.
- **D — sweep.** Every caller now standing on a terminal marker is
  terminated and classified.

Phase order is not arbitrary. Aggregating before the sweep is what makes
congestion a measure of callers who are *still navigating*.

## Determinism

Replay equivalence is the property everything else rests on: two runs over
identical inputs must produce byte-identical ledgers.

- No randomness in any engine path. The RL engines store `lr`, `gamma` and
  `eps_clip` as **config only** — this is deterministic inference over fixed
  seeded weights, not training.
- Nothing uses Python's built-in `hash()`, which is randomized per
  interpreter session and would silently break cross-session replay.
  `ClusterRunner.select_worker` rolls its own stable hash for the same reason.
- Every iteration over callers is `sorted()`.
- Telemetry payloads are deep-copied on record. `CallerState.snapshot()`
  returns `posterior` by reference, and storing it by reference would let a
  later in-place mutation retroactively alter an already-recorded entry — an
  append-only violation via aliasing, and a silent one.

Two hashes, deliberately kept distinct rather than collapsed into one
ambiguous `hash`:

| | covers | moves when |
|---|---|---|
| `structural_hash()` | all state, including `step_index` | every step, quiet or not — this is what replay equivalence needs |
| `content_hash()` | emotionally meaningful state only | something real actually changed |

## The friction engine

`LatentPayload` is the part of this system that was genuinely hardened —
tested, fuzzed, and repeatedly attacked. It is event-driven, not flat-drift:
quiet steps move nothing. The earlier flat-drift version pinned `memory_flag`
to 1.0 by step ~100 regardless of what happened.

Properties worth knowing:

- **Convex accrual past tolerance.** The first adverse event costs less than
  the fifth.
- **Friction and resolution are not mutually exclusive.** A caller can
  misroute and reach the right place in the same step. An earlier `elif`
  meant the friction branch always won and relief silently never fired.
- **Relief is capped on a friction step.** It may at most undo that step's
  trust damage. Without the cap, a misroute-then-resolve step netted *higher*
  trust than a step where nothing happened — rewarding a manufactured
  stumble over running clean.
- **Relief targets `trust_baseline` plus a bounded overshoot**, not 1.0. A
  well-handled failure can end above the pre-call baseline. That is intended.
- **`memory_flag` never decays.** It is the permanent record that friction
  occurred, independent of whether the call ultimately felt resolved.
- **`peak_frustration` never decays.** Relief pulls final frustration down, so
  a caller who spiked then got smoothed reads calm at call-end — exactly the
  caller an end-state check misses.

## Unvalidated constants

Every tunable in this system — `_TOLERANCE`, `_FRICTION_CAP`, `_DILATION_K`,
`_RELIEF_RATE`, `_TRUST_OVERSHOOT_CAP`, `_WAIT_NORMALIZATION_SECONDS`, the
`PathCongestion` weights, `DEFAULT_EXPECTED_DWELL_SECONDS` — is a placeholder
that produces sane-looking behavior. None is calibrated against real call
data, because no real call data ever reached this system.

They are marked as such in the source. Treat every one as "needs domain
expertise before this goes anywhere near production", not as settled.

## Known open issues, carried forward

These were open in the original system and are not closed here.

- **`MARLEngine` agents are fully independent.** No coordination modeling, no
  joint policy, no communication. "Multi-agent" describes the decomposition,
  not the learning. Flagged repeatedly in the original work, never resolved.
- **The `ClusterRunner` contract fork.** The test suite and the real class
  disagreed on the constructor. Never reconciled.
- **No real data.** The observe phase — synthetic Twilio-shaped generator,
  then a real Twilio adapter, then live calibration — was the locked next
  build order. It got as far as a specification stub.
- **Calibration ceiling.** `calibrate_expected_wait` found observable methods
  cap around AUC ≈ 0.73.
