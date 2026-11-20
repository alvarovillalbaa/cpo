# Find training failures when probe routing stalls

The [stall recovery comparison](opening-stall-recovery.md) lost matched critical cases when the router lacked one input feature. All seven losing panels reached an opening with validation misses but found no error in either training probe batch, so the optimizer made no repair proposal.

`run_routed_repair_cycle` now accepts `fallback_probe_limit`, which defaults to zero. When a passing probe batch would otherwise end search, the fallback samples unused training rows with the least exposure to already probed feature values. The seeded, family-balanced training order breaks ties. The fallback stops at the first observed error. It spends from the existing search cap after reserving a full validation panel, and its feedback comes only from training. The two-stage repair limit and separate qualification still apply. [API](../cpo/routed_repair_cycle.py)

The comparison enables `recover_stalls=True` for all routed arms and tests fallback caps of zero, four, and 12 under the same 56-lookup search ceiling. It reproduces the two earlier 60-panel cohorts and adds 60 disjoint scripted confirmation panels. A fourth mode supplies no categorical feature mappings to the router and keeps the original family labels available for scheduling. The evaluator and proposer see the same cases in all modes.

## Scripted confirmation

Each cell gives holdout passes out of 1,080 and total counted calls. Both GEPA controls use the same prompts, search cap, cases, and qualification schedule across feature modes.

| Method | Clean | Missing field | Redundant metadata | No router features |
| --- | ---: | ---: | ---: | ---: |
| Stall recovery | 1,080 / 3,932 | 1,056 / 3,929 | 1,080 / 3,932 | 1,054 / 3,874 |
| Up to four fallback probes | 1,080 / 3,932 | 1,073 / 3,963 | 1,080 / 3,932 | 1,072 / 3,922 |
| Up to 12 fallback probes | 1,080 / 3,932 | 1,080 / 3,977 | 1,080 / 3,932 | 1,080 / 3,935 |
| Sequential GEPA | 1,010 / 4,153 | 1,010 / 4,153 | 1,010 / 4,153 | 1,010 / 4,153 |
| Batched GEPA | 812 / 4,295 | 812 / 4,295 | 812 / 4,295 | 812 / 4,295 |

The 12-probe option passed both GEPA gates in every confirmation mode and preserved every matched critical pass. It used 10 extra training probes on three missing-field panels and 10 on four panels with no router features. Each of those seven panels produced an accepted repair. The intact and redundant-feature modes used zero fallback probes and exactly matched the routed arm. Across the two earlier cohorts it also recovered all 41 critical passes previously lost to sequential GEPA with a field hidden. The same scripted rule generator supplies all three cohorts. Live comparison remains pending. [Sealed results](opening-probe-fallback-results-v1.json)

A separate fixture exposed overlapping attribute pairs and limited each proposal to one witnessed edit. CPO's aggregate pass lead did not clear the critical-loss and cost gates across all profiles. [Interaction transfer](opening-interaction-transfer.md)

## Reproduce offline

Use GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_probe_fallback
PYTHONHASHSEED=0 python -B -m benchmarks.opening_probe_fallback \
  --execute d28b0eb31b07f4a12b9784644bb14286bd9080ce8386ad697323818c118e0d82 \
  --out NEW_REPORT.json
```

Two clean source replays and an installed-wheel replay blocked sockets and DNS and matched byte for byte. Each covered 180 scripted panels under four feature modes and 360 native GEPA paths. Sixteen focused tests passed in each environment. The installed wheel also reproduced the prior 90 default panel traces and the complete stall-recovery result with fallback disabled. The runner rejected an altered seal and preserved an existing report. Storage Guard measured 4.5 GiB free and the scratch exports were removed under the standing LAB exception. [Verification receipt](opening-probe-fallback-verification-v1.json)
