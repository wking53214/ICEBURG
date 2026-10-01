# ICEBURG

Honest **reconstruction** of the first peak IVR simulation/governance kernel (early-July 2026, post four locked corrections). Predecessor of a separate private repository by rename (from `chromebook-iceberg`). Never existed as this GitHub original; rebuilt 2026-09-11 from 75,449 references across 551 archive files. ~72% of 2,031 engine lines are **verbatim recovered**.

## 1. Pipeline Position & Role

**HISTORICAL LINEAGE.** Off the live path. Conceptual ancestor of friction, structural hash, fail-closed routing.

## 2. Full System Scope & Architectural Depth

Tick (`IntegrationLoop.run`): step/divert/hangup → group by step-kind → `compute_path_congestion` → `PPOEngine.compute_action` (**triage signal, not routing**) → sweep terminals.

`Simulator._next_node`: journey map → unique neighbor → **raise `GSA Violation`** if undeclared branch. Success iff route touched `resolution` or `handoff`. `peak_frustration` is severity, not outcome.

Node kinds: `step | resolution | handoff`. No queues (Correction 1). Telemetry `{seq, type, payload}` deep-copied. Hashes: SHA-256 `json.dumps(sort_keys=True)`; `structural_hash` vs `content_hash`. Tunables with `_` prefix stripped from `to_dict()`. **No `canonical_fields` list.**

119 tests. `python3 run_worked_example.py`. numpy.

## 3. What It Does NOT Do / Non-Goals

Live calls, Twilio, staffing, ACD, replay, API, GPU Bayes, k8s, training, real data. Those were not recovered and are **listed absent, not stubbed**.

## 4. Brutally Honest Current Status & Gaps

| Gap | Detail |
|---|---|
| PPO/MARL | `lr/gamma/eps_clip` stored, **never trained**. Weights `RandomState(815).randn`. MARL is decomposition, not learning. |
| `TwilioSyntheticLogGenerator` | `pass` bodies **on purpose** (test asserts stub). |
| `QueueStress.py` | Superseded; nothing imports it. |
| `reset_for_new_call` / `load_from_dict` | Unwired (replay never recovered). |
| Uncalibrated latent constants | `_FRICTION_CAP=20`, path-congestion weights, etc. No real call data. |
| Path hacks | `sys.path.insert` into Aggregation/Latent. |

## 5. Core Invariants & Guarantees

Fail-closed routing: undeclared journey, max_steps, duplicate `caller_id`, unknown intent raise. Hangup beats divert. Binary structural termination. SCORECARD.md is the contract.

## 6. Inputs, Outputs & Type Contracts

`LatentPayload` (capability_score, patience, volatility, … peak_frustration). `CallerState`. `Intent`: `balance|billing|tech|cancel|upgrade|complaint|sales|general`. `DynamicState`.

## 7. Stack Integration Topology

```text
lost chromebook-iceberg
    └─ ICEBURG (this; July peak, no queues)     honest reconstruction
```

Proprietary. Copyright (c) 2026 William King. All rights reserved. See LICENSE.
