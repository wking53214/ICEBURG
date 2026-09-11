# Scorecard

Module status as reconstructed. The original repository kept a file like this
and the archive records it drifting out of date — a stale citation to
`QueueStress.compute_queue_loads()` survived in it well after `PathCongestion`
had replaced that wiring. This version is generated against the shipped code
and verified by `Iceburg/Tests/test_lineage_guard.py`.

Last verified: 2026-09-11, 119 tests passing.

## Shipped and exercised

| Module | Provenance | Status |
|---|---|---|
| `Latent/LatentPayload.py` | recovered + `peak_frustration` | **Hardened.** The one genuinely battle-tested subsystem. 19 tests covering clamping, convex accrual, the relief cap, non-decaying memory and peak, hash separation, and trajectory determinism. |
| `Model/Build_Graph.py` | recovered v2 + 1 fix | **Proven.** Topology, journey map and integrity validation. 12 tests. Correction 1/2/3 asserted directly. |
| `Sim/Simulator.py` | recovered v1 + v2 merged | **Proven.** Journey-based traversal, divert, binary structural termination. 15 tests. |
| `Loop/IntegrationLoop.py` | recovered v1 + v2 merged | **Proven.** Four-phase tick, hangup precedence, marker exclusion, reproducibility. 12 tests. |
| `Aggregation/PathCongestion.py` | recovered | **Proven.** Order-independent, bounded, peak-weighted. 8 tests. |
| `Engines/rl_ppo.py` | recovered + 1 fix | **Proven as inference.** Deterministic, session-stable weights. 8 tests. Not trained — `lr`/`gamma`/`eps_clip` are stored config. |
| `SDK/Telemetry.py` | reconstructed | **Proven.** Append-only, deep-copied payloads, two distinct hashes. 10 tests. |
| `Domain/CallerState.py` | recovered | **Proven** via the traversal and ledger tests. |
| `Domain/IngestAdapter.py` | recovered | **Proven.** Seeded-deterministic synthetic logs, pure mechanical stimulus derivation. 12 tests. |
| `Sim/cluster_runner.py` | reconstructed | **Proven.** Terminations invariant to worker count. 7 tests. |
| `Engines/rl_marl.py` | reconstructed | **Runs, with a known modeling gap.** See below. |
| `Domain/Intent.py`, `Domain/Emotion.py` | reconstructed | **Proven** consistent with the topology. 6 tests. |
| `Training/Modules/calibrate_expected_wait.py` | recovered | **Runs standalone.** Calibration harness. Archive records observable methods capping around AUC ≈ 0.73. Never run against real logs. |

## Shipped, deliberately not working

| Module | Why |
|---|---|
| `Domain/TwilioSyntheticLogGenerator.py` | Recovered exactly as written: signatures, docstrings, `pass` bodies. It was the next step in the locked build order and was never implemented. Filling in a plausible body would manufacture the precise failure mode this project existed to eliminate. `test_lineage_guard.py` asserts it is still declared a stub. |
| `Aggregation/QueueStress.py` | Superseded by `PathCongestion` under Correction 1. Retained because the two files side by side are the clearest statement of what that correction changed and what it deliberately did not. Nothing imports it, and a test enforces that. |

## Absent — no recoverable source

Listed, not stubbed. The archive is explicit that empty scaffolding was one of
the original repository's real problems.

| Area | Files |
|---|---|
| Replay subsystem | `recorder.py`, `ledger.py`, `snapshot.py`, `verifier.py`, `replay_runner.py` |
| API | `server.py`, `schemas.py` |
| SDK | `client.py`, `models.py`, `replay.py` |
| Registry | `module_registry.py` |
| Telemetry aggregation | `aggregator.py` |
| Engines | `bayes_gpu.py` |
| CLI / Admin | `cli.py`, `dashboard.py` |
| Governance | `lever_registry_spec.md`, `target_manifest_spec.md` |
| Validation | `tier0_stress_test.py`, `tier0_1_stress_test.py`, tier report |
| Deploy | k8s manifests, ArgoCD application, docker-compose |
| Entry point | `main.py` |

## Deleted, and staying deleted

| Module | Reason |
|---|---|
| `Engines/staffing_rl.py` | Staffing math needs AHT, shrinkage and answered-vs-offered data. None of it exists before the ACD door. Not a scope preference — epistemically impossible from where this system sits. |
| `Simulator.update_queue` | Maintained "current occupants" of a place that cannot exist (Correction 1). |
| `Domain/QueueState.py` | The only recoverable version carried `staffed_agents`, `abandonment_rate` and `StaffingAdjustment` — the same post-ACD lineage. Shipping it would have reintroduced the deleted model. |

## Known open issues

Carried forward from the original, not closed here.

1. **`MARLEngine` agents are fully independent.** No coordination modeling, no
   joint policy, no communication between agents. "Multi-agent" describes the
   decomposition, not the learning. Flagged repeatedly in the original work
   and never resolved; closing it is a modeling decision that needs real data.
2. **Every tunable constant is uncalibrated.** Sane-looking, not validated.
   This is the single largest gap between this system and a usable one.
3. **The observe phase never happened.** Synthetic Twilio generator, real
   Twilio adapter, live calibration — the locked next build order, reached as
   far as a specification stub.
4. **The `ClusterRunner` contract fork** between the original test suite and
   the real class was never reconciled. This reconstruction satisfies both.
5. **The original 108-test suite is unrecoverable.** The 119 tests here are
   new, written against documented invariants. They do not claim to be the
   originals.

## Production readiness

**No.** The engine is coherent, deterministic and tested, and that is the
honest ceiling of this claim. There is no API, no persistence, no deployment
path, no real data behind any constant, and no integration with a live
telephony platform. What exists is a correct and well-reasoned simulation
kernel with an unusually clear account of its own boundaries.
