# Route training probes toward validation failures

The provisional repair could still miss an explicitly wrong rule when both training probes passed. This follow-up uses paid validation pass and fail outcomes to choose training probes with matching input features. The proposer receives the selected training observations. Full validation and independent qualification preserve the existing critical-case and family guards. [Previous benchmark](opening-provisional-repair.md) · [Runner](../benchmarks/opening_repair_probe_routing.py)

For each categorical input feature, the router compares how often it occurs in paid validation failures and passes. It prioritizes features that occur disproportionately in failures and retains the seeded training order on ties. Each round reserves enough budget for full validation of the repair, chooses at most two unused training rows, and runs the probes on the instruction alone. A failed probe can trigger a repair. A rejected first repair can supply provisional context only when it preserves the exact passing rows and matched-field counts. Only a strict improvement over the last accepted candidate can replace the final nominee.

The opt-in CPO API accepts a caller-provided input feature extractor. Its source and installed wheel replay the three cohort traces. [Routed repair API](routed-repair-cycle.md)

The search cap is 56 lookups per panel, with at most two later proposals. The comparison replays the two published cohorts and adds 30 panels under new seeds and disjoint inputs. Every cohort uses the same scripted rule generator and five opening conditions. The third cohort is primary.

## Results

| Method | Original panels passes / calls | Second cohort passes / calls | Probe transfer passes / calls |
| --- | ---: | ---: | ---: |
| Opening screen | 411 / 1,613 | 411 / 1,611 | 402 / 1,612 |
| One repair, instruction-only probes | 508 / 1,865 | 494 / 1,852 | 490 / 1,831 |
| Up to two repairs with provisional context | 540 / 1,940 | 524 / 1,921 | 506 / 1,877 |
| Routed training probes | 540 / 1,940 | 540 / 1,945 | 540 / 1,957 |
| Adaptive CPO | 529 / 1,929 | 520 / 1,987 | 522 / 2,023 |
| Sequential GEPA | 520 / 2,032 | 507 / 2,050 | 517 / 2,045 |
| Batched GEPA | 411 / 2,108 | 411 / 2,106 | 398 / 2,107 |

On the primary cohort, routing gained 34 passes over the provisional policy for 80 additional counted calls. It recovered 28 passes from wrong rules and six from two omissions. It beat sequential GEPA by 23 passes and used 88 fewer calls, beat batched GEPA by 142 passes and used 150 fewer calls, and beat adaptive CPO by 18 passes and used 66 fewer calls. Every matched critical pass was preserved. It cleared the gate against all three controls on the primary cohort.

The original cohort matched the prior provisional policy’s 540 passes and call count. The second cohort recovered the previously missed critical cases and also finished at 540 passes. These results establish a scripted comparison across the tested policy generator and its categorical input features. Live model performance and costs remain unmeasured. [Costs, profile gates, and trace hashes](opening-repair-probe-routing-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_probe_routing
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_probe_routing \
  --execute 0f7fb5223f8d5b79a614717356cb110fee8286206779e4f2988242e7094ff760 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each reproduced both published cohorts and exercised 90 typed panels and 180 GEPA paths. Twelve focused tests passed, including feature ranking, deterministic tie order, probe isolation, and single final qualification. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 4.6 GiB free. The 29.3 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_opening_repair_probe_routing.py) · [Verification receipt](opening-repair-probe-routing-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
