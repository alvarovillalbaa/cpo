# Transfer posterior allocation to four-cycle prompt optimization

Posterior allocation saved validation lookups on the archived ARC-AGI pool and lost accuracy on AIME. This replay uses the fixed allocation rule on the 16-panel MMLU confirmation archive. Each panel uses the 32 original seeded episodes, 12 validation cases and eight independent qualification cases per cycle, and a disjoint final holdout. The two archived models are Llama 3 8B Instruct and Mistral 7B v0.1. [Math allocation result](recorded-score-allocation.md) · [MMLU snapshot and provenance](routed-start-model-confirmation.md)

## Protocol

- **Original route** widens after three incumbent misses and uses the existing two-case screen with a backup finalist.
- **Exact race when wide** keeps that trigger and the same six-candidate roster. It replaces the shared screen with strict exact CPO racing.
- **Posterior allocation when wide** replaces the same screen with the published score allocator. Its estimated probabilities determine the order of evaluations. Exact completed scores determine the nominee.
- **Posterior allocation on every fresh search** uses the allocator on all 12 offered challengers and removes the initial routing decision.

All CPO arms keep the original archive qualification, final reserve for the starting prompt, 52-lookup search ceiling, and independent qualification rule. They reserve logical search slots and charge only distinct underlying lookups. The two primary GEPA controls use official 0.1.4 at paid cap 52 and can reinvest cache savings. The comparison also includes the previously selected lower-cost batched GEPA point at cap 47 and retaining the start. The primary candidate is posterior allocation when wide. It needs at least 10% lookup savings against both cap-52 controls and a nonnegative lower endpoint for the joint paired range. The resampling keeps all trajectories and both models together within each of 421 held-out cases. [Benchmark runner](../benchmarks/routed_score_allocation.py)

## Results

| Method | Holdout passes / 26,944 | Paid lookups |
| --- | ---: | ---: |
| Retain start | 17,617 | 0 |
| Original route | 17,724 | 49,330 |
| Exact race when wide | 17,710 | 50,898 |
| Posterior allocation when wide | 17,727 | 51,141 |
| Posterior allocation on every fresh search | 17,769 | 93,671 |
| Batched GEPA, cap 47 | 17,687 | 45,679 |
| Batched GEPA, cap 52 | 17,694 | 57,271 |
| Sequential GEPA, cap 52 | 17,721 | 81,537 |

Using the posterior allocator only when the route widens gained three passes and used 1,811 more lookups than the original route. It changed the final prompt in 13 of 512 episodes. Its paired range against the original route was −10 to +16 passes. It gained 17 passes over exact racing at the same routing trigger, with a paired range of +2 to +32 and 243 additional lookups. Relative to the two cap-52 GEPA controls, it saved 10.7% against batched and 37.3% against sequential. Its joint range was −52 to +59, leaving the primary gate inconclusive. The cap-47 batched control used 5,462 fewer lookups and scored 40 fewer passes. [Results and paired ranges](routed-score-allocation-results-v1.json)

Applying posterior allocation to all fresh searches gained 45 passes over the original route and used 44,341 more lookups. It changed 150 of 512 final prompts. Its paired range against the original route was −13 to +100. It also used more lookups than both cap-52 GEPA controls and failed the savings gate. The original route remains the better-supported allocation for this cohort. These results use archived outcomes and fixed proposal rosters. Fresh-model performance remains unverified.

## Reproduce

Use GEPA 0.1.4 and the bundled archives.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_score_allocation
PYTHONHASHSEED=0 python -B -m benchmarks.routed_score_allocation \
  --execute 205570639ce89aa25997497620e94f4d428c6ca59103c1ece1e1ceadc1096481 \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced 64 published control traces. Nine focused tests passed, including budget admission, preserving critical passes, and shared lookup accounting. The CLI rejected a wrong seal and refused to overwrite an existing result. Storage Guard measured 21.0 GiB free. The 15.7 MB temporary overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_routed_score_allocation.py)
